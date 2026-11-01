"""IPO centre: open/upcoming IPOs, issue details, live subscription, prospectus (RHP) sections,
financials extracted from the RHP, a rule-based listing-gain scorecard, and recent listing outcomes.

Sources: NSE public IPO APIs + NSE archives (RHP zips) + Yahoo prices for already-listed IPOs.
Arithmetic stays in code; the AI only extracts raw figures from the RHP (each one is then checked
against the RHP text) and writes the qualitative analysis.
"""
from __future__ import annotations

import io
import math
import re
import zipfile
from datetime import date, datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import requests

from .config import CACHE_DIR, DEMO_MODE
from .data import _cache_forget, _cached
from .news import _UA, _nse_json

NSE_ARCHIVE = "https://nsearchives.nseindia.com/content/ipo/{name}.zip"


# --------------------------------------------------------------------------- helpers
def _num(x: Any) -> float | None:
    if x is None:
        return None
    s = str(x).replace(",", "").strip()
    try:
        v = float(s)
        return v if math.isfinite(v) else None
    except ValueError:
        m = re.search(r"-?\d+(\.\d+)?", s)
        return float(m.group()) if m else None


def _date(s: str) -> date | None:
    for fmt in ("%d-%b-%Y", "%d-%B-%Y", "%d-%m-%Y"):
        try:
            return datetime.strptime(str(s).strip().title(), fmt).date()
        except ValueError:
            continue
    return None


def price_band(text: str) -> tuple[float | None, float | None]:
    nums = [float(n) for n in re.findall(r"\d+(?:\.\d+)?", str(text).replace(",", ""))]
    if not nums:
        return None, None
    return min(nums), max(nums)


def _money_to_cr(value: float, unit: str) -> float:
    u = unit.lower()
    if "billion" in u:
        return value * 100
    if "million" in u or u == "mn":
        return value / 10
    if "lakh" in u or "lac" in u:
        return value / 100
    return value  # crore


def parse_issue_amounts(text: str) -> dict[str, float]:
    """Pull ₹ amounts for fresh issue / offer for sale / total out of NSE's 'Issue Size' sentence."""
    out: dict[str, float] = {}
    t = str(text).replace(",", "")
    for key, rx in (("fresh_issue_cr", r"fresh issue[^.;]*?(?:rs\.?|₹|inr)\s*([\d.]+)\s*(crore|cr|million|mn|lakh|lakhs|billion)"),
                    ("ofs_cr", r"offer for sale[^.;]*?(?:rs\.?|₹|inr)\s*([\d.]+)\s*(crore|cr|million|mn|lakh|lakhs|billion)"),
                    ("total_cr", r"aggregating (?:up ?to )?(?:rs\.?|₹|inr)\s*([\d.]+)\s*(crore|cr|million|mn|lakh|lakhs|billion)")):
        m = re.search(rx, t, re.I)
        if m:
            out[key] = round(_money_to_cr(float(m.group(1)), m.group(2)), 2)
    if "fresh" in t.lower() and "offer for sale" not in t.lower():
        out["structure"] = "Fresh issue only (all money goes to the company)"
    elif "offer for sale" in t.lower() and "fresh" not in t.lower():
        out["structure"] = "Offer for sale only (existing shareholders selling; company gets nothing)"
    elif "offer for sale" in t.lower():
        out["structure"] = "Fresh issue + offer for sale"
    return out


# --------------------------------------------------------------------------- lists
def list_ipos() -> list[dict[str, Any]]:
    """Open + announced-upcoming IPOs on NSE (mainboard and SME)."""
    if DEMO_MODE:
        return _demo_list()

    def fetch() -> list[dict[str, Any]]:
        rows: dict[str, dict[str, Any]] = {}
        for path in ("ipo-current-issue", "all-upcoming-issues?category=ipo"):
            try:
                data = _nse_json(path) or []
            except Exception:
                data = []
            for r in data if isinstance(data, list) else data.get("data", []):
                sym = r.get("symbol")
                if not sym:
                    continue
                rows.setdefault(sym, {}).update({k: v for k, v in r.items() if v not in (None, "")})
        out = []
        today = date.today()
        for sym, r in rows.items():
            lo, hi = price_band(r.get("issuePrice", ""))
            start, end = _date(r.get("issueStartDate", "")), _date(r.get("issueEndDate", ""))
            status = ("Open" if start and end and start <= today <= end else "Upcoming" if start and start > today
                      else "Closed" if end and end < today else r.get("status", ""))
            out.append({
                "symbol": sym, "company": r.get("companyName", sym), "series": r.get("series", "EQ"),
                "board": "SME" if r.get("series") == "SME" else "Mainboard",
                "open": str(start) if start else r.get("issueStartDate"), "close": str(end) if end else r.get("issueEndDate"),
                "price_band": r.get("issuePrice"), "price_low": lo, "price_high": hi,
                "shares_offered": _num(r.get("issueSize") or r.get("noOfSharesOffered")),
                "subscription_x": _num(r.get("noOfTime")), "status": status,
            })
        for r in out:  # enrich from the issue page: price band (often missing for SME) and NSE+BSE subscription
            try:
                det = ipo_detail(r["symbol"], r["series"])
            except Exception:
                continue
            if r["price_high"] is None:
                pr = det["info"].get("Price Range") or det["info"].get("Issue Price") or ""
                r["price_band"] = pr or None
                r["price_low"], r["price_high"] = price_band(pr)
            tot = subscription_summary(det["subscription"]).get("total")
            if tot is not None:
                r["subscription_x"] = tot
            r["lot_size"] = _num(det["info"].get("Bid Lot") or det["info"].get("Lot Size") or det["info"].get("Minimum Order Quantity"))
        order = {"Open": 0, "Upcoming": 1, "Closed": 2}
        return sorted(out, key=lambda r: (order.get(r["status"], 3), str(r["close"])))

    return _cached("ipo:list", 15 * 60, fetch)


def ipo_detail(symbol: str, series: str = "EQ") -> dict[str, Any]:
    if DEMO_MODE:
        return _demo_detail(symbol)

    def fetch() -> dict[str, Any]:
        j = _nse_json(f"ipo-detail?symbol={symbol}&series={series}") or {}
        info: dict[str, str] = {}
        for d in (j.get("issueInfo") or {}).get("dataList", []):
            t, v = d.get("title"), d.get("value")
            if t and v:
                info[str(t).strip()] = re.sub(r"<[^>]+>", "", str(v)).strip().strip('"')
        links = {k: re.search(r"https?://\S+?\.(zip|pdf)", v).group(0) for k, v in
                 ((k, (d.get("value") or "")) for k, d in ((d.get("title"), d) for d in (j.get("issueInfo") or {}).get("dataList", [])) if k)
                 if re.search(r"https?://\S+?\.(zip|pdf)", v)}
        cat = (j.get("activeCat") or {}).get("dataList") or []
        rows = []
        for r in cat:
            if r.get("srNo") == "Sr.No.":
                continue
            off, bid, times = _num(r.get("noOfShareOffered")), _num(r.get("noOfSharesBid")), _num(r.get("noOfTotalMeant"))
            if not off:  # NSE sometimes publishes 0 shares offered (seen on SME issues): the multiple is meaningless
                times = None
            rows.append({"sr": r.get("srNo"), "category": r.get("category"), "offered": off, "bid": bid, "times": times})
        if not rows:  # fall back to NSE-only bid details
            for r in j.get("bidDetails") or []:
                rows.append({"sr": r.get("srNo"), "category": r.get("category"), "offered": _num(r.get("noOfSharesOffered")),
                             "bid": _num(r.get("noOfsharesBid")), "times": _num(r.get("noOfTime"))})
        demand = (j.get("demandGraphALL") or j.get("demandGraph") or {}).get("plotData") or {}
        return {"info": info, "links": links, "subscription": rows,
                "demand_by_price": {k: _num(v) for k, v in demand.items()},
                "fetched": datetime.now().isoformat(timespec="minutes")}

    return _cached(f"ipo:detail:{symbol}:{series}", 15 * 60, fetch)


def subscription_summary(rows: list[dict[str, Any]]) -> dict[str, float | None]:
    def find(pattern: str, sr: str | None = None) -> float | None:
        for r in rows:
            if (sr and r.get("sr") == sr) or (not sr and re.search(pattern, r.get("category") or "", re.I)):
                return r.get("times")
        return None

    out = {
        "total": find(r"^total$"),
        "qib": find(r"qualified institutional"),
        "nii": find(r"^non institutional investors$") or find("", "2"),
        "bnii": find(r"more than ten lakh"),
        "snii": find(r"two lakh rupees upto ten lakh"),
        "retail": find(r"retail individual") or find(r"^individual investors"),
        "employee": find(r"employee"),
    }
    if out["total"] is None:
        tot = next((r for r in rows if (r.get("category") or "").lower() == "total"), None)
        out["total"] = tot.get("times") if tot else None
    return out


def recent_listings(n: int = 30) -> pd.DataFrame:
    """Last n mainboard listings: issue price, listing-day open/close and today's price."""
    if DEMO_MODE:
        return _demo_recent()

    def fetch() -> pd.DataFrame:
        past = _nse_json("public-past-issues") or []
        rows = []
        for p in past:
            if p.get("securityType") != "EQ":
                continue
            ld, ip = _date(p.get("listingDate", "")), _num(p.get("issuePrice"))
            if not ld or not ip:
                continue
            rows.append({"symbol": p["symbol"], "company": p.get("company", ""), "listing_date": ld, "issue_price": ip})
        rows = sorted(rows, key=lambda r: r["listing_date"], reverse=True)[:n]
        if not rows:
            return pd.DataFrame()
        import yfinance as yf

        tick = [f"{r['symbol']}.NS" for r in rows]
        start = min(r["listing_date"] for r in rows)
        px = yf.download(tick, start=str(start), interval="1d", group_by="ticker", auto_adjust=False, progress=False, threads=True)
        out = []
        for r in rows:
            try:
                d = px[f"{r['symbol']}.NS"] if isinstance(px.columns, pd.MultiIndex) else px
                d = d.dropna(subset=["Close"])
                d = d[d.index.date >= r["listing_date"]]
                if d.empty:
                    continue
                first, last = d.iloc[0], d.iloc[-1]
                out.append({**r, "listing_open": round(float(first["Open"]), 2), "listing_close": round(float(first["Close"]), 2),
                            "listing_gain_pct": round(100 * (float(first["Open"]) / r["issue_price"] - 1), 1),
                            "listing_day_close_pct": round(100 * (float(first["Close"]) / r["issue_price"] - 1), 1),
                            "current_price": round(float(last["Close"]), 2),
                            "return_since_ipo_pct": round(100 * (float(last["Close"]) / r["issue_price"] - 1), 1)})
            except (KeyError, IndexError, TypeError):
                continue
        return pd.DataFrame(out)

    return _cached(f"ipo:recent:{n}", 6 * 3600, fetch)


def market_mood(recent: pd.DataFrame) -> dict[str, Any]:
    if recent is None or recent.empty:
        return {"available": False}
    last10 = recent.head(10)
    return {
        "available": True, "listings_considered": int(len(recent)),
        "median_listing_gain_pct_last10": round(float(last10["listing_gain_pct"].median()), 1),
        "pct_listed_above_issue_last10": round(100 * float((last10["listing_gain_pct"] > 0).mean()), 0),
        "median_return_since_ipo_pct": round(float(recent["return_since_ipo_pct"].median()), 1),
        "pct_trading_above_issue_now": round(100 * float((recent["return_since_ipo_pct"] > 0).mean()), 0),
    }


# --------------------------------------------------------------------------- RHP
SECTIONS = {
    # key: (heading regex, pages to take, max chars)
    "business": (r"(OUR BUSINESS|BUSINESS OVERVIEW)", 4, 14000),
    "industry": (r"\bINDUSTRY OVERVIEW\b", 2, 6000),
    "financial_summary": (r"SUMMARY OF (THE )?(RESTATED )?FINANCIAL (INFORMATION|STATEMENTS)", 5, 16000),
    "objects": (r"OBJECTS? OF THE (OFFER|ISSUE)", 3, 9000),
    "basis_price": (r"BASIS (FOR|OF) (THE )?(OFFER|ISSUE) PRICE", 7, 20000),
    "capital_structure": (r"\bCAPITAL STRUCTURE\b", 3, 8000),
    "risk_factors": (r"\bRISK FACTORS\b", 4, 14000),
    "mdna": (r"MANAGEMENT(.?S)? DISCUSSION AND ANALYSIS( OF FINANCIAL (CONDITION|POSITION) AND RESULTS? OF OPERATIONS?)?", 4, 14000),
    "litigation": (r"OUTSTANDING LITIGATIONS?( AND (OTHER )?MATERIAL DEVELOPMENTS)?", 2, 6000),
    "summary_doc": (r"SUMMARY OF (THE )?(OFFER|ISSUE) DOCUMENT|OFFER DOCUMENT SUMMARY", 6, 16000),
}


def _download_rhp(symbol: str, url: str | None = None) -> Path | None:
    folder = CACHE_DIR / "rhp"
    folder.mkdir(parents=True, exist_ok=True)
    pdf_path = folder / f"{symbol}.pdf"
    if pdf_path.exists() and pdf_path.stat().st_size > 10000:
        return pdf_path
    r = requests.get(url or NSE_ARCHIVE.format(name=f"RHP_{symbol}"), headers={"User-Agent": _UA, "Referer": "https://www.nseindia.com/"}, timeout=180)
    if r.status_code != 200:
        return None
    if r.content[:4] == b"%PDF":
        pdf_path.write_bytes(r.content)
        return pdf_path
    try:
        z = zipfile.ZipFile(io.BytesIO(r.content))
    except zipfile.BadZipFile:
        return None
    pdfs = [i for i in z.infolist() if i.filename.lower().endswith(".pdf")]
    if not pdfs:
        return None
    pref = [i for i in pdfs if re.search(r"rhp|red herring|prospectus", i.filename, re.I)] or pdfs
    best = max(pref, key=lambda i: i.file_size)
    pdf_path.write_bytes(z.read(best))
    return pdf_path


def _is_heading(page_text: str, rx: str) -> bool:
    """True if one of the first lines of the page IS the section heading (not a sentence that mentions it)."""
    pat = re.compile(rf"^(SECTION\s+[IVXL]+\s*[-–—:]\s*)?({rx})(\s+OF\s+[A-Z ,]+)?\s*$", re.I)
    for line in page_text.strip().splitlines()[:8]:
        ln = line.strip()
        if ln and "...." not in ln and pat.match(ln) and ln.upper() == ln:  # headings are upper case
            return True
    return False


def _heading_page(texts: dict[int, str], rx: str, start: int) -> int | None:
    for i in sorted(texts):
        if i >= start and _is_heading(texts[i], rx):
            return i
    return None


def rhp_sections(symbol: str, series: str = "EQ") -> dict[str, Any]:
    """Extract the decision-relevant sections of the RHP as text (with PDF page numbers)."""
    if DEMO_MODE:
        return {"available": False, "reason": "demo mode"}

    def build() -> dict[str, Any]:
        try:
            import pypdf
        except ImportError:
            return {"available": False, "reason": "The 'pypdf' package is missing — run: bash scripts/update.sh"}

        try:
            links = ipo_detail(symbol, series).get("links", {})
        except Exception:
            links = {}
        url = next((v for k, v in links.items() if re.search(r"red herring|prospectus", k, re.I)), None)
        path = _download_rhp(symbol, url)
        if not path:
            return {"available": False, "reason": "No prospectus (RHP) published on NSE for this issue yet — common for SME issues listed mainly on BSE"}
        reader = pypdf.PdfReader(str(path))
        n = len(reader.pages)
        cache: dict[int, str] = {}

        def page(i: int) -> str:
            if i not in cache:
                try:
                    cache[i] = reader.pages[i].extract_text() or ""
                except Exception:
                    cache[i] = ""
            return cache[i]

        # 1) table of contents -> printed page numbers
        toc_text = "\n".join(page(i) for i in range(min(12, n)))
        toc: dict[str, int] = {}
        for key, (rx, _, _) in SECTIONS.items():
            m = re.search(rf"({rx})[^\n]*?[.…]{{3,}}[^\n\d]*?(\d{{1,4}})\s*$", toc_text, re.I | re.M)
            if m:
                toc[key] = int(m.group(m.lastindex))
        # 2) find the page offset between printed numbers and PDF indices using the first located heading
        offset = None
        for key in sorted(toc, key=lambda k: toc[k]):
            guess = toc[key]
            for i in range(max(0, guess - 2), min(n, guess + 40)):
                if _is_heading(page(i), SECTIONS[key][0]):
                    offset = i - guess
                    break
            if offset is not None:
                break
        out: dict[str, Any] = {"available": True, "pages": n, "sections": {}, "file": path.name}
        for key, (rx, take, max_chars) in SECTIONS.items():
            start = None
            if key in toc and offset is not None:
                g = toc[key] + offset
                for i in range(max(0, g - 2), min(n, g + 4)):
                    if _is_heading(page(i), rx):
                        start = i
                        break
                start = start if start is not None else g
            if start is None:  # no TOC entry: scan the first 300 pages for a heading
                scan = {i: page(i) for i in range(8, min(n, 450))}
                start = _heading_page(scan, rx, 8)
            if start is None or start >= n:
                continue
            text = "\n".join(page(i) for i in range(start, min(n, start + take)))
            text = re.sub(r"[ \t]+", " ", text)
            out["sections"][key] = {"pdf_pages": f"{start + 1}-{min(n, start + take)}", "text": text[:max_chars]}
        return out

    key = f"ipo:rhp:{symbol}"
    out = _cached(key, 7 * 24 * 3600, build)
    if not out.get("available"):
        _cache_forget(key)  # never remember failures: the RHP or the PDF library may be available next time
    return out


# --------------------------------------------------------------------------- financials from RHP
def verify_numbers(extracted: dict[str, Any], source: str) -> dict[str, Any]:
    """Every number the AI extracted must literally appear in the RHP text (in Indian or western grouping)."""
    flat = re.sub(r"\s+", " ", source)
    digits = set(re.findall(r"\d[\d,]*\.?\d*", flat))
    norm = {d.replace(",", "").rstrip(".") for d in digits}
    checked, missing = 0, []

    def walk(o: Any, path: str) -> None:
        nonlocal checked
        if isinstance(o, dict):
            for k, v in o.items():
                walk(v, f"{path}.{k}" if path else k)
        elif isinstance(o, list):
            for i, v in enumerate(o):
                walk(v, f"{path}[{i}]")
        elif isinstance(o, (int, float)) and not isinstance(o, bool) and path and not path.endswith(("year", "is_full_year")):
            checked += 1
            v = float(o)
            cands = {f"{v:.2f}", f"{v:.1f}", f"{v:.0f}", str(v).rstrip("0").rstrip("."), f"{abs(v):.2f}", f"{abs(v):.0f}"}
            if not any(c.lstrip("-") in norm for c in cands):
                missing.append(f"{path}={o}")

    walk(extracted, "")
    return {"checked": checked, "not_found_in_rhp": missing[:30], "found_pct": round(100 * (1 - len(missing) / checked), 1) if checked else None}


def compute_financials(ex: dict[str, Any], price_high: float | None, fresh_issue_cr: float | None = None) -> dict[str, Any]:
    """Turn AI-extracted raw figures into ₹ crore metrics (all arithmetic here, not in the model)."""
    unit = (ex.get("unit") or "crore").lower()
    periods = [p for p in ex.get("periods", []) if isinstance(p, dict)]

    def cr(v: Any) -> float | None:
        x = _num(v)
        return None if x is None else round(_money_to_cr(x, unit), 2)

    def borrowings(p: dict[str, Any]) -> float | None:
        parts = [cr(p.get(k)) for k in ("non_current_borrowings", "current_borrowings")]
        if all(x is None for x in parts):
            return cr(p.get("total_borrowings"))
        return round(sum(x for x in parts if x is not None), 2)

    rows = []
    for p in periods:
        rows.append({"period": p.get("period"), "full_year": bool(p.get("is_full_year", True)),
                     "revenue_cr": cr(p.get("revenue_from_operations")), "ebitda_cr": cr(p.get("ebitda")),
                     "pat_cr": cr(p.get("profit_after_tax")), "net_worth_cr": cr(p.get("net_worth")),
                     "borrowings_cr": borrowings(p), "total_assets_cr": cr(p.get("total_assets")),
                     "eps": _num(p.get("basic_eps")), "cfo_cr": cr(p.get("cash_from_operations"))})
    df = pd.DataFrame(rows).astype(object).where(lambda d: pd.notna(d), None) if rows else pd.DataFrame()
    out: dict[str, Any] = {"table": rows, "unit_in_rhp": unit}
    full = df[df["full_year"] == True] if not df.empty else df  # noqa: E712
    if len(full) >= 1:
        last = full.iloc[-1]
        last = {k: (None if v is None or (isinstance(v, float) and math.isnan(v)) else v) for k, v in last.to_dict().items()}
        if last.get("revenue_cr") and last.get("pat_cr") is not None:
            out["pat_margin_pct"] = round(100 * last["pat_cr"] / last["revenue_cr"], 1)
        if last.get("ebitda_cr") and last.get("revenue_cr"):
            out["ebitda_margin_pct"] = round(100 * last["ebitda_cr"] / last["revenue_cr"], 1)
        if last.get("net_worth_cr") and last.get("pat_cr") is not None and last["net_worth_cr"] > 0:
            out["roe_pct"] = round(100 * last["pat_cr"] / last["net_worth_cr"], 1)
        if last.get("net_worth_cr") and last.get("borrowings_cr") is not None and last["net_worth_cr"] > 0:
            out["debt_to_equity"] = round(last["borrowings_cr"] / last["net_worth_cr"], 2)
        if last.get("cfo_cr") is not None and last.get("pat_cr") and last["pat_cr"] > 0:
            out["cfo_to_pat"] = round(last["cfo_cr"] / last["pat_cr"], 2)
        out["latest_full_year"] = last["period"]
        out["latest_pat_cr"] = last.get("pat_cr")
    if len(full) >= 2:
        f, l_ = full.iloc[0], full.iloc[-1]
        yrs = len(full) - 1
        for k, lbl in (("revenue_cr", "revenue_cagr_pct"), ("pat_cr", "pat_cagr_pct")):
            a, b = f.get(k), l_.get(k)
            if a and b and a > 0 and b > 0:
                out[lbl] = round(100 * ((b / a) ** (1 / yrs) - 1), 1)
    post = _num(ex.get("post_issue_shares"))
    basis = "as stated in RHP"
    if not post:
        pre = _num(ex.get("pre_issue_shares"))
        if not pre:
            cap, fv = _num(ex.get("equity_share_capital_latest")), _num(ex.get("face_value_per_share"))
            if cap and fv:
                pre = _money_to_cr(cap, unit) * 1e7 / fv
        fresh = _num(ex.get("fresh_issue_shares"))
        if not fresh and fresh_issue_cr and price_high:
            fresh = fresh_issue_cr * 1e7 / price_high
        if pre:
            post = pre + (fresh or 0)
            basis = "derived: pre-issue shares (share capital ÷ face value) + fresh issue ₹ ÷ upper band"
    if post:
        out["post_issue_shares"] = round(post)
        out["post_issue_shares_basis"] = basis
    if post and price_high:
        mcap = post * price_high / 1e7
        out["post_issue_mcap_cr_at_upper_band"] = round(mcap, 1)
        if out.get("latest_pat_cr") and out["latest_pat_cr"] > 0:
            out["pe_at_upper_band"] = round(mcap / out["latest_pat_cr"], 1)
        lf = full.iloc[-1].to_dict() if len(full) else {}
        if lf.get("revenue_cr"):
            out["mcap_to_sales"] = round(mcap / lf["revenue_cr"], 2)
        if lf.get("net_worth_cr"):
            out["pb_pre_issue_networth"] = round(mcap / lf["net_worth_cr"], 2)
    peers = [p for p in ex.get("peers", []) if isinstance(p, dict) and _num(p.get("pe"))]
    if peers:
        pes = [_num(p["pe"]) for p in peers if 0 < _num(p["pe"]) < 300]
        if pes:
            out["peer_median_pe"] = round(float(np.median(pes)), 1)
            if out.get("pe_at_upper_band"):
                out["pe_premium_to_peers_pct"] = round(100 * (out["pe_at_upper_band"] / out["peer_median_pe"] - 1), 1)
    return out


# --------------------------------------------------------------------------- listing-gain scorecard (rules, not a forecast)
def listing_scorecard(card: dict[str, Any], sub: dict[str, Any], fin: dict[str, Any], mood: dict[str, Any], amounts: dict[str, Any]) -> dict[str, Any]:
    pts: list[dict[str, Any]] = []

    def add(name: str, score: float, basis: str) -> None:
        pts.append({"factor": name, "score": int(round(float(np.clip(score, 0, 100)))), "basis": basis})

    tot, qib, nii, ret = sub.get("total"), sub.get("qib"), sub.get("nii"), sub.get("retail")
    if tot is not None:
        add("Overall subscription", 20 + 22 * math.log10(1 + tot) * 2, f"{tot:.2f}× subscribed")
    if qib is not None and card.get("board") == "Mainboard":
        add("QIB demand (institutions)", 15 + 25 * math.log10(1 + qib) * 2, f"QIB {qib:.2f}×")
    if nii is not None:
        add("NII / HNI demand", 20 + 20 * math.log10(1 + nii) * 2, f"NII {nii:.2f}×")
    if ret is not None:
        add("Retail demand", 25 + 15 * math.log10(1 + ret) * 2, f"Retail {ret:.2f}×")
    if fin.get("pe_premium_to_peers_pct") is not None:
        prem = fin["pe_premium_to_peers_pct"]
        add("Pricing vs listed peers", 60 - 0.6 * prem, f"IPO P/E {fin.get('pe_at_upper_band')}× vs peer median {fin.get('peer_median_pe')}× ({prem:+.0f}%)")
    if "Offer for sale only" in (amounts.get("structure") or ""):
        add("Issue structure", 35, amounts["structure"])
    elif "Fresh issue only" in (amounts.get("structure") or ""):
        add("Issue structure", 60, amounts["structure"])
    if mood.get("available"):
        add("Recent IPO market mood", 50 + 1.2 * mood["median_listing_gain_pct_last10"],
            f"median listing gain of last 10 mainboard IPOs {mood['median_listing_gain_pct_last10']:+.1f}%")
    if not pts:
        return {"score": None, "label": "Not enough data yet", "factors": []}
    weights = {"QIB demand (institutions)": 2.0, "Overall subscription": 1.5, "NII / HNI demand": 1.2, "Retail demand": 0.8,
               "Pricing vs listed peers": 1.0, "Issue structure": 0.5, "Recent IPO market mood": 1.0}
    w = sum(weights[p["factor"]] for p in pts)
    score = round(sum(p["score"] * weights[p["factor"]] for p in pts) / w)
    label = ("Strong listing-gain signals" if score >= 70 else "Positive signals" if score >= 57 else "Mixed signals" if score >= 43
             else "Weak signals")
    caveats = []
    if card.get("status") in ("Open", "Upcoming"):
        caveats.append("Subscription is still building — most demand (especially QIB/NII) arrives on the last day; recheck at close.")
    if card.get("board") == "SME":
        caveats.append("SME IPO: small, illiquid, large minimum ticket; listing outcomes are far more volatile than mainboard.")
    return {"score": score, "label": label, "factors": pts, "caveats": caveats,
            "note": "Rule-based summary of public demand and pricing signals — not a prediction of the listing price."}


# --------------------------------------------------------------------------- bundle
def ipo_fact_pack(card: dict[str, Any], extracted: dict[str, Any] | None = None) -> dict[str, Any]:
    det = ipo_detail(card["symbol"], card["series"])
    info = det["info"]
    sub = subscription_summary(det["subscription"])
    if sub.get("total") is None and card.get("subscription_x") is not None:
        sub["total"] = card["subscription_x"]  # overall figure from NSE's IPO list
    amounts = parse_issue_amounts(info.get("Issue Size", ""))
    lot = _num(info.get("Bid Lot") or info.get("Lot Size") or info.get("Minimum Order Quantity"))
    hi = card.get("price_high")
    if not amounts.get("total_cr") and card.get("shares_offered") and hi:
        amounts["approx_size_cr_excl_anchor"] = round(card["shares_offered"] * hi / 1e7, 1)
    try:
        recent = recent_listings()
    except Exception:
        recent = pd.DataFrame()
    mood = market_mood(recent)
    fin = compute_financials(extracted, hi, amounts.get("fresh_issue_cr")) if extracted and not extracted.get("_parse_error") else {}
    pack = {
        "ipo": {**card, "lot_size": lot, "min_investment_rs": round(lot * hi) if lot and hi else None,
                "face_value": info.get("Face Value"), "issue_type": info.get("Issue Type"),
                "issue_size_text": info.get("Issue Size"), "lead_managers": info.get("Book Running Lead Managers"),
                "registrar": info.get("Name of the Registrar"), "max_retail": info.get("Maximum Subscription Amount for Retail Investor"),
                "discount": info.get("Discount"), **amounts},
        "subscription_x": sub,
        "subscription_by_category": [r for r in det["subscription"] if r.get("times") is not None],
        "market_mood": mood,
        "financials_computed": fin,
        "rhp_extract": extracted or {},
        "documents": det["links"],
        "as_of": det["fetched"],
    }
    pack["listing_scorecard"] = listing_scorecard(card, sub, fin, mood, amounts)
    return pack


# --------------------------------------------------------------------------- demo data
def _demo_list() -> list[dict[str, Any]]:
    t = date.today()
    return [
        {"symbol": "DEMOIPO", "company": "Demo Precision Ltd (DEMO)", "series": "EQ", "board": "Mainboard", "open": str(t),
         "close": str(t), "price_band": "Rs.95 to Rs.100", "price_low": 95.0, "price_high": 100.0, "shares_offered": 2.0e7,
         "subscription_x": 3.4, "status": "Open"},
        {"symbol": "DEMOSME", "company": "Demo Fabrics Ltd (DEMO)", "series": "SME", "board": "SME", "open": str(t), "close": str(t),
         "price_band": "Rs.48 to Rs.50", "price_low": 48.0, "price_high": 50.0, "shares_offered": 3.0e6, "subscription_x": 12.1, "status": "Open"},
    ]


def _demo_detail(symbol: str) -> dict[str, Any]:
    rows = [{"sr": "1", "category": "Qualified Institutional Buyers(QIBs)", "offered": 4e6, "bid": 2.2e7, "times": 5.5},
            {"sr": "2", "category": "Non Institutional Investors", "offered": 3e6, "bid": 1.2e7, "times": 4.0},
            {"sr": "3", "category": "Retail Individual Investors(RIIs)", "offered": 7e6, "bid": 1.5e7, "times": 2.1},
            {"sr": None, "category": "Total", "offered": 1.4e7, "bid": 4.9e7, "times": 3.4}]
    return {"info": {"Issue Size": "Fresh Issue aggregating upto Rs. 200 crore (DEMO)", "Issue Type": "Book Building",
                     "Bid Lot": "150 Equity Shares", "Face Value": "Rs. 10", "Book Running Lead Managers": "Demo Capital",
                     "Name of the Registrar": "Demo Registrar"},
            "links": {}, "subscription": rows, "demand_by_price": {"95": 4.0e7, "100": 4.9e7}, "fetched": datetime.now().isoformat(timespec="minutes")}


def _demo_recent() -> pd.DataFrame:
    rng = np.random.default_rng(7)
    rows = []
    for i in range(12):
        ip = float(rng.uniform(100, 900))
        lg = float(rng.normal(12, 18))
        rows.append({"symbol": f"DEMO{i}", "company": f"Demo Listing {i}", "listing_date": date.today(), "issue_price": round(ip, 2),
                     "listing_open": round(ip * (1 + lg / 100), 2), "listing_close": round(ip * (1 + lg / 100), 2),
                     "listing_gain_pct": round(lg, 1), "listing_day_close_pct": round(lg, 1),
                     "current_price": round(ip * (1 + rng.normal(8, 25) / 100), 2), "return_since_ipo_pct": round(float(rng.normal(8, 25)), 1)})
    return pd.DataFrame(rows)
