"""News, results and exchange announcements.

Sources (all free, no key):
  * NSE corporate announcements  — every filing (results, orders, acquisitions, SAST/pledge, insider trades…)
  * NSE board meetings           — upcoming results dates (event risk for short-term trades)
  * NSE corporate actions        — dividends, bonus, splits, buybacks with ex-dates
  * Google News RSS (India)      — press coverage headlines
NSE blocks some cloud/datacenter IPs; the app then shows what it could fetch and says what failed.
"""
from __future__ import annotations

import re
import time
import xml.etree.ElementTree as ET
from datetime import date, datetime, timedelta
from email.utils import parsedate_to_datetime
from typing import Any
from urllib.parse import quote_plus

import requests

from .config import DEMO_MODE
from .data import _cached

_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
       "Chrome/130.0 Safari/537.36")
_session: requests.Session | None = None
_session_at = 0.0


def _nse() -> requests.Session:
    global _session, _session_at
    if _session is None or time.time() - _session_at > 600:
        s = requests.Session()
        s.headers.update({"User-Agent": _UA, "Accept": "application/json,text/plain,*/*",
                          "Accept-Language": "en-US,en;q=0.9", "Referer": "https://www.nseindia.com/"})
        try:
            s.get("https://www.nseindia.com", timeout=10)
        except requests.RequestException:
            pass
        _session, _session_at = s, time.time()
    return _session


def _nse_json(path: str) -> Any:
    r = _nse().get(f"https://www.nseindia.com/api/{path}", timeout=15)
    r.raise_for_status()
    return r.json()


# --------------------------------------------------------------------------- tagging
ROUTINE = (r"trading window|closure of trading|newspaper publication|loss of share certificate|duplicate share|"
           r"certificate under regulation 74|depositories and participants|compliance certificate|"
           r"investor complaints|statement of deviation|reconciliation of share capital")
TAGS: list[tuple[str, str]] = [
    ("Results", r"financial result|outcome of board meeting|quarterly result|audited|unaudited"),
    ("Board meeting", r"board meeting"),
    ("Dividend/bonus/split", r"dividend|bonus|split|sub-division|record date|buyback|buy back"),
    ("Order/contract", r"\border (worth|valued|value|from|received|for supply|of rs|of ₹|aggregating)|\borders? worth|bagged|bags an? order|contract|award(ed)?\b|letter of (intent|award)|\bloi\b|secured an? (order|contract)"),
    ("M&A / investment", r"acqui|merger|amalgamation|stake|joint venture|investment in|subsidiar|demerger|scheme of arrangement"),
    ("Fund raising", r"\bqip\b|preferential|rights issue|ncd|debenture|fund rais|allotment"),
    ("Promoter / pledge / SAST", r"pledge|encumbrance|takeover|sast|regulation 29|regulation 31|promoter"),
    ("Insider trading", r"insider trading|regulation 7\(|pit\b|reg\. 7"),
    ("Rating", r"credit rating|\bcrisil\b|\bicra\b|\bcare ratings\b|\bindia ratings\b"),
    ("Management change", r"resign|appointment|cessation|ceo|cfo|managing director|key managerial"),
    ("Regulatory / legal", r"\bsebi\b|penalty|show cause|litigation|court|tribunal|nclt|search|investigation|gst demand|tax demand|order passed"),
    ("Analyst/investor meet", r"analyst|investor meet|conference call|earnings call|transcript|presentation"),
]
POS = r"\b(beat|beats|surge|surges|soar|jumps?|record|wins?|bag|bags|secures?|upgrade[sd]?|raises? guidance|order win|strong|rall(y|ies)|gains?|outperform|approval|expands?)\b"
NEG = r"\b(miss(es)?|falls?|plunge[sd]?|slump|down ?grade[sd]?|probe|penalty|fraud|default|resigns?|cuts? guidance|weak|loss|losses|declines?|drops?|raid|ban|pledge[sd]?|lawsuit|recall)\b"


def tag(text: str) -> list[str]:
    t = text.lower()
    if re.search(ROUTINE, t):  # routine filings get one tag only, so they never raise alerts
        return ["Routine compliance"]
    return [name for name, rx in TAGS if re.search(rx, t)] or ["Other"]


def tone(text: str) -> int:
    t = text.lower()
    return (1 if re.search(POS, t) else 0) - (1 if re.search(NEG, t) else 0)


# --------------------------------------------------------------------------- NSE feeds
def _parse_date(s: str, fmt: str) -> date | None:
    try:
        return datetime.strptime(s.strip(), fmt).date()
    except (ValueError, AttributeError):
        return None


def announcements(symbol: str, days: int = 120) -> list[dict[str, Any]]:
    to, fr = date.today(), date.today() - timedelta(days=days)
    path = (f"corporate-announcements?index=equities&symbol={quote_plus(symbol)}"
            f"&from_date={fr:%d-%m-%Y}&to_date={to:%d-%m-%Y}")
    raw = _nse_json(path) or []
    out = []
    for a in raw:
        text = (a.get("attchmntText") or a.get("desc") or "").strip()
        out.append({
            "date": (a.get("sort_date") or a.get("an_dt") or "")[:16],
            "subject": a.get("desc") or "",
            "text": re.sub(r"\s+", " ", text)[:400],
            "tags": tag(f"{a.get('desc', '')} {text}"),
            "link": a.get("attchmntFile") or "",
            "nse_industry": a.get("smIndustry") or "",
        })
    return sorted(out, key=lambda x: x["date"], reverse=True)


def board_meetings(symbol: str) -> list[dict[str, Any]]:
    raw = _nse_json(f"corporate-board-meetings?index=equities&symbol={quote_plus(symbol)}") or []
    out = []
    for b in raw:
        d = _parse_date(b.get("bm_date", ""), "%d-%b-%Y")
        out.append({"date": str(d) if d else b.get("bm_date"), "purpose": b.get("bm_purpose", ""),
                    "details": re.sub(r"\s+", " ", b.get("bm_desc", ""))[:300],
                    "is_results": bool(re.search(r"result", b.get("bm_desc", "") + b.get("bm_purpose", ""), re.I))})
    return sorted(out, key=lambda x: str(x["date"]), reverse=True)


def corporate_actions(symbol: str) -> list[dict[str, Any]]:
    raw = _nse_json(f"corporates-corporateActions?index=equities&symbol={quote_plus(symbol)}") or []
    out = []
    for c in raw:
        d = _parse_date(c.get("exDate", ""), "%d-%b-%Y")
        out.append({"ex_date": str(d) if d else c.get("exDate"), "action": c.get("subject", ""),
                    "record_date": c.get("recDate", "")})
    return sorted(out, key=lambda x: str(x["ex_date"]), reverse=True)


# --------------------------------------------------------------------------- Google News
def _query_name(company: str, symbol: str) -> str:
    name = re.sub(r"\b(limited|ltd\.?|ltd|inc\.?|corporation|co\.)\b", "", company, flags=re.I)
    name = re.sub(r"\(DEMO\)|[.,]", "", name).strip()
    return name or symbol


def google_news(company: str, symbol: str, days: int = 30, limit: int = 25) -> list[dict[str, Any]]:
    q = f'"{_query_name(company, symbol)}" (share OR stock OR results OR NSE) when:{days}d'
    url = f"https://news.google.com/rss/search?q={quote_plus(q)}&hl=en-IN&gl=IN&ceid=IN:en"
    r = requests.get(url, headers={"User-Agent": _UA}, timeout=15)
    r.raise_for_status()
    root = ET.fromstring(r.content)
    out = []
    for it in root.iter("item"):
        title = (it.findtext("title") or "").strip()
        src = it.find("source")
        source = src.text if src is not None and src.text else ""
        if source and title.endswith(f" - {source}"):
            title = title[: -len(source) - 3]
        try:
            dt = parsedate_to_datetime(it.findtext("pubDate") or "").date().isoformat()
        except (TypeError, ValueError):
            dt = ""
        out.append({"date": dt, "title": title, "source": source, "link": it.findtext("link") or "",
                    "tags": tag(title), "tone": tone(title)})
    out.sort(key=lambda x: x["date"], reverse=True)
    return out[:limit]


# --------------------------------------------------------------------------- bundle
def _safe(fn, *args, **kw) -> tuple[Any, str | None]:
    try:
        return fn(*args, **kw), None
    except Exception as exc:  # network, 403, JSON
        return [], f"{fn.__name__}: {str(exc)[:120]}"


def news_bundle(symbol: str, company: str) -> dict[str, Any]:
    if DEMO_MODE:
        return _demo_bundle(symbol)

    def fetch() -> dict[str, Any]:
        ann, e1 = _safe(announcements, symbol)
        bm, e2 = _safe(board_meetings, symbol)
        ca, e3 = _safe(corporate_actions, symbol)
        gn, e4 = _safe(google_news, company, symbol)
        return {"announcements": ann, "board_meetings": bm, "corporate_actions": ca, "news": gn,
                "errors": [e for e in (e1, e2, e3, e4) if e], "fetched": datetime.now().isoformat(timespec="minutes")}

    b = _cached(f"news:{symbol}", 2 * 3600, fetch)
    return summarise(b)


def summarise(b: dict[str, Any]) -> dict[str, Any]:
    today = date.today().isoformat()
    upcoming = [m for m in b["board_meetings"] if str(m["date"]) >= today]
    next_results = min((m["date"] for m in upcoming if m["is_results"]), default=None)
    days_to_results = (date.fromisoformat(next_results) - date.today()).days if next_results else None
    upcoming_ca = [c for c in b["corporate_actions"] if str(c["ex_date"]) >= today]
    tag_counts: dict[str, int] = {}
    for a in b["announcements"][:60]:
        for t in a["tags"]:
            tag_counts[t] = tag_counts.get(t, 0) + 1
    tones = [n["tone"] for n in b["news"]]
    alerts = [a for a in b["announcements"][:60] if any(t in a["tags"] for t in ("Promoter / pledge / SAST", "Regulatory / legal", "Rating", "Management change"))]
    nse_industry = next((a["nse_industry"] for a in b["announcements"] if a.get("nse_industry")), "")
    return {
        **b,
        "next_results_date": next_results,
        "days_to_results": days_to_results,
        "upcoming_corporate_actions": upcoming_ca[:5],
        "announcement_tag_counts": tag_counts,
        "recent_results_filings": [a for a in b["announcements"] if "Results" in a["tags"]][:4],
        "attention_items": alerts[:8],
        "headline_tone": {"positive": sum(1 for t in tones if t > 0), "negative": sum(1 for t in tones if t < 0),
                          "neutral": sum(1 for t in tones if t == 0),
                          "note": "rough keyword count on headlines only — the AI reads the actual headlines"},
        "nse_industry": nse_industry,
    }


def for_fact_pack(nb: dict[str, Any]) -> dict[str, Any]:
    """Compact version for the AI (keeps token use small)."""
    return {
        "next_results_date": nb.get("next_results_date"), "days_to_results": nb.get("days_to_results"),
        "upcoming_corporate_actions": nb.get("upcoming_corporate_actions"),
        "recent_announcements": [{"date": a["date"][:10], "tags": a["tags"], "text": a["text"][:220]} for a in nb.get("announcements", [])[:15]],
        "attention_items": [{"date": a["date"][:10], "tags": a["tags"], "text": a["text"][:220]} for a in nb.get("attention_items", [])],
        "recent_corporate_actions": nb.get("corporate_actions", [])[:5],
        "news_headlines": [{"date": n["date"], "title": n["title"], "source": n["source"]} for n in nb.get("news", [])[:15]],
        "headline_tone_rough": nb.get("headline_tone"),
        "fetch_errors": nb.get("errors"),
    }


def _demo_bundle(symbol: str) -> dict[str, Any]:
    d = date.today()
    b = {
        "announcements": [
            {"date": f"{d - timedelta(days=12)} 18:30", "subject": "Financial Results", "text": "DEMO: Company has informed the Exchange about audited financial results for the quarter ended September.", "tags": ["Results"], "link": "", "nse_industry": "Demo Industry"},
            {"date": f"{d - timedelta(days=30)} 10:00", "subject": "Updates", "text": "DEMO: Company has bagged an order worth ₹500 crore.", "tags": ["Order/contract"], "link": "", "nse_industry": "Demo Industry"},
        ],
        "board_meetings": [{"date": str(d + timedelta(days=9)), "purpose": "Board Meeting Intimation", "details": "DEMO: to consider quarterly results", "is_results": True}],
        "corporate_actions": [{"ex_date": str(d - timedelta(days=40)), "action": "DEMO: Interim Dividend - Rs 5 Per Share", "record_date": ""}],
        "news": [{"date": str(d - timedelta(days=2)), "title": f"DEMO: {symbol} shares rise after order win", "source": "Demo", "link": "", "tags": ["Order/contract"], "tone": 1}],
        "errors": [], "fetched": datetime.now().isoformat(timespec="minutes"),
    }
    return summarise(b)
