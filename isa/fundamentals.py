"""Fundamental analysis from Yahoo statements: ratios, growth, Piotroski F-score,
Altman Z''-EM (emerging-market variant), deterministic red flags and a 0-100 health score.

All money values are reported in ₹ crore (1 crore = 10 million).
"""
from __future__ import annotations

import math
from typing import Any

import numpy as np
import pandas as pd

from .config import CRORE
from .data import StockData, to_float

ALIASES: dict[str, list[str]] = {
    "revenue": ["Total Revenue", "Operating Revenue", "Revenue"],
    "gross_profit": ["Gross Profit"],
    "ebitda": ["EBITDA", "Normalized EBITDA"],
    "ebit": ["EBIT", "Operating Income"],
    "op_income": ["Operating Income", "EBIT"],
    "interest": ["Interest Expense", "Interest Expense Non Operating"],
    "pbt": ["Pretax Income"],
    "tax": ["Tax Provision"],
    "net_income": ["Net Income", "Net Income Common Stockholders", "Net Income From Continuing Operation Net Minority Interest"],
    "eps": ["Diluted EPS", "Basic EPS"],
    "da": ["Reconciled Depreciation", "Depreciation And Amortization", "Depreciation Amortization Depletion"],
    "total_assets": ["Total Assets"],
    "equity": ["Stockholders Equity", "Common Stock Equity", "Total Equity Gross Minority Interest"],
    "total_debt": ["Total Debt"],
    "lt_debt": ["Long Term Debt", "Long Term Debt And Capital Lease Obligation"],
    "cash": ["Cash And Cash Equivalents", "Cash Cash Equivalents And Short Term Investments"],
    "current_assets": ["Current Assets"],
    "current_liabilities": ["Current Liabilities"],
    "retained_earnings": ["Retained Earnings"],
    "total_liabilities": ["Total Liabilities Net Minority Interest", "Total Liabilities"],
    "shares": ["Ordinary Shares Number", "Share Issued"],
    "receivables": ["Accounts Receivable", "Receivables"],
    "inventory": ["Inventory"],
    "cfo": ["Operating Cash Flow", "Cash Flow From Continuing Operating Activities"],
    "capex": ["Capital Expenditure"],
    "fcf": ["Free Cash Flow"],
    "dividends": ["Cash Dividends Paid", "Common Stock Dividend Paid"],
}


def col(df: pd.DataFrame, key: str) -> pd.Series:
    for name in ALIASES.get(key, [key]):
        if name in df.columns and df[name].notna().any():
            return df[name].astype(float)
    return pd.Series(np.nan, index=df.index, dtype=float)


def is_financial(sd: StockData) -> bool:
    sector = (sd.info.get("sector") or "").lower()
    industry = (sd.info.get("industry") or "").lower()
    return "financial" in sector or any(k in industry for k in ("bank", "insurance", "credit", "capital markets", "asset management"))


def _cagr(s: pd.Series) -> float | None:
    s = s.dropna()
    if len(s) < 2 or s.iloc[0] <= 0 or s.iloc[-1] <= 0:
        return None
    if isinstance(s.index, pd.DatetimeIndex):
        yrs = (s.index[-1] - s.index[0]).days / 365.25
    else:  # FY labels: one period per year
        yrs = float(len(s) - 1)
    if yrs < 0.9:
        return None
    return round(100 * ((s.iloc[-1] / s.iloc[0]) ** (1 / yrs) - 1), 1)


def _pct(a: float, b: float) -> float | None:
    if b is None or a is None or not np.isfinite(a) or not np.isfinite(b) or b == 0:
        return None
    return round(100 * a / b, 1)


def _cr(x: float) -> float | None:
    return None if x is None or not np.isfinite(x) else round(x / CRORE, 1)


def _clean(v: Any) -> Any:
    if isinstance(v, float) and not math.isfinite(v):
        return None
    return v


def annual_table(sd: StockData) -> pd.DataFrame:
    """Year-by-year metrics (index = fiscal year label like FY26)."""
    inc, bal, cf = sd.income_a, sd.balance_a, sd.cashflow_a
    idx = inc.index.union(bal.index).union(cf.index)
    if len(idx) == 0:
        return pd.DataFrame()
    inc, bal, cf = inc.reindex(idx), bal.reindex(idx), cf.reindex(idx)
    t = pd.DataFrame(index=idx)
    t["Revenue"] = col(inc, "revenue")
    t["EBITDA"] = col(inc, "ebitda")
    t["EBIT"] = col(inc, "ebit")
    t["Interest"] = col(inc, "interest").abs()
    t["Net profit"] = col(inc, "net_income")
    t["Reported EPS"] = col(inc, "eps")
    t["Gross profit"] = col(inc, "gross_profit")
    t["Total assets"] = col(bal, "total_assets")
    t["Equity"] = col(bal, "equity")
    t["Debt"] = col(bal, "total_debt")
    t["Cash"] = col(bal, "cash")
    t["Current assets"] = col(bal, "current_assets")
    t["Current liabilities"] = col(bal, "current_liabilities")
    t["Receivables"] = col(bal, "receivables")
    t["Inventory"] = col(bal, "inventory")
    t["Shares"] = col(bal, "shares")
    t["CFO"] = col(cf, "cfo")
    t["Capex"] = col(cf, "capex").abs()
    fcf = col(cf, "fcf")
    t["FCF"] = fcf.where(fcf.notna(), t["CFO"] - t["Capex"])
    t["Dividends"] = col(cf, "dividends").abs()
    # Yahoo restates share counts for bonuses/splits but not always the reported EPS (e.g. HDFC Bank's
    # 2025 1:1 bonus). Net profit / adjusted share count gives an EPS series consistent with adjusted prices.
    eps_adj = t["Net profit"] / t["Shares"].where(t["Shares"] > 0)
    t["EPS"] = eps_adj.where(eps_adj.notna(), t["Reported EPS"])

    avg_eq = t["Equity"].rolling(2, min_periods=1).mean()
    cap_emp = (t["Total assets"] - t["Current liabilities"]).rolling(2, min_periods=1).mean()
    t["OPM %"] = 100 * t["EBIT"] / t["Revenue"]
    t["EBITDA margin %"] = 100 * t["EBITDA"] / t["Revenue"]
    t["NPM %"] = 100 * t["Net profit"] / t["Revenue"]
    t["Gross margin %"] = 100 * t["Gross profit"] / t["Revenue"]
    t["ROE %"] = 100 * t["Net profit"] / avg_eq
    t["ROCE %"] = 100 * t["EBIT"] / cap_emp
    t["ROA %"] = 100 * t["Net profit"] / t["Total assets"]
    t["Debt/Equity"] = t["Debt"] / t["Equity"]
    t["Interest cover (x)"] = t["EBIT"] / t["Interest"].replace(0, np.nan)
    t["Current ratio"] = t["Current assets"] / t["Current liabilities"]
    t["CFO/PAT"] = t["CFO"] / t["Net profit"].where(t["Net profit"] > 0)
    t["Asset turnover"] = t["Revenue"] / t["Total assets"]
    t["Receivable days"] = 365 * t["Receivables"] / t["Revenue"]
    t["Inventory days"] = 365 * t["Inventory"] / t["Revenue"]
    t["Payout %"] = 100 * t["Dividends"] / t["Net profit"].where(t["Net profit"] > 0)
    t.index = [f"FY{str(d.year + (1 if d.month > 3 else 0))[-2:]}" for d in idx]
    # Yahoo sometimes has an extra balance-sheet year with no income statement: drop such empty years
    t = t[t["Revenue"].notna() | t["Net profit"].notna()]
    return t.loc[:, t.notna().any()]


def quarterly_table(sd: StockData) -> pd.DataFrame:
    q = sd.income_q
    if q.empty:
        return pd.DataFrame()
    t = pd.DataFrame(index=q.index)
    t["Revenue"] = col(q, "revenue")
    t["Operating profit"] = col(q, "op_income")
    t["Net profit"] = col(q, "net_income")
    t["EPS"] = col(q, "eps")
    t["OPM %"] = 100 * t["Operating profit"] / t["Revenue"]
    # Yahoo sometimes skips quarters, so compare by calendar date, never by row position.
    for label, days, (lo, hi) in (("QoQ", 91, (75, 105)), ("YoY", 365, (350, 380))):
        for colname, src in (("Revenue", "Revenue"), ("Profit", "Net profit")):
            vals = []
            for d in t.index:
                prior = t.index[(t.index <= d - pd.Timedelta(days=lo)) & (t.index >= d - pd.Timedelta(days=hi))]
                if len(prior) and pd.notna(t.at[prior[-1], src]) and t.at[prior[-1], src] not in (0,) and t.at[prior[-1], src] > 0:
                    vals.append(100 * (t.at[d, src] / t.at[prior[-1], src] - 1))
                else:
                    vals.append(np.nan)
            t[f"{colname} {label} %"] = vals
    t.index = [d.strftime("%b-%y") for d in q.index]
    return t.loc[:, t.notna().any()]


# --------------------------------------------------------------------------- quality scores
def piotroski(t: pd.DataFrame) -> dict[str, Any]:
    if len(t) < 2:
        return {"score": None, "max": 9, "checks": [], "note": "needs two fiscal years"}
    c, p = t.iloc[-1], t.iloc[-2]

    def g(row: pd.Series, k: str) -> float:
        return to_float(row.get(k))

    roa_c = g(c, "Net profit") / g(c, "Total assets")
    roa_p = g(p, "Net profit") / g(p, "Total assets")
    lev_c = g(c, "Debt") / g(c, "Total assets")
    lev_p = g(p, "Debt") / g(p, "Total assets")
    checks = [
        ("Positive net profit (ROA > 0)", roa_c > 0 if np.isfinite(roa_c) else None),
        ("Positive operating cash flow", g(c, "CFO") > 0 if np.isfinite(g(c, "CFO")) else None),
        ("ROA improved YoY", roa_c > roa_p if np.isfinite(roa_c) and np.isfinite(roa_p) else None),
        ("Cash flow > profit (low accruals)", g(c, "CFO") > g(c, "Net profit") if np.isfinite(g(c, "CFO")) else None),
        ("Leverage fell (Debt/Assets)", lev_c <= lev_p if np.isfinite(lev_c) and np.isfinite(lev_p) else None),
        ("Current ratio improved", g(c, "Current ratio") > g(p, "Current ratio") if np.isfinite(g(c, "Current ratio")) and np.isfinite(g(p, "Current ratio")) else None),
        ("No share dilution", g(c, "Shares") <= g(p, "Shares") * 1.005 if np.isfinite(g(c, "Shares")) and np.isfinite(g(p, "Shares")) else None),
        ("Gross/operating margin improved", (g(c, "Gross margin %") if np.isfinite(g(c, "Gross margin %")) else g(c, "OPM %")) > (g(p, "Gross margin %") if np.isfinite(g(p, "Gross margin %")) else g(p, "OPM %")) if np.isfinite(g(c, "OPM %")) and np.isfinite(g(p, "OPM %")) else None),
        ("Asset turnover improved", g(c, "Asset turnover") > g(p, "Asset turnover") if np.isfinite(g(c, "Asset turnover")) and np.isfinite(g(p, "Asset turnover")) else None),
    ]
    known = [v for _, v in checks if v is not None]
    return {
        "score": int(sum(known)) if known else None,
        "evaluated": len(known),
        "max": 9,
        "checks": [{"test": n, "pass": v} for n, v in checks],
        "interpretation": "8-9 strong, 5-7 average, 0-4 weak (scaled to tests evaluated)",
    }


def altman_z_em(t: pd.DataFrame, financial: bool) -> dict[str, Any]:
    """Altman Z''-score for emerging-market non-financial firms (constant 3.25)."""
    if financial or t.empty:
        return {"score": None, "zone": "not applicable to lenders/insurers" if financial else "no data"}
    c = t.iloc[-1]
    ta, tl = to_float(c.get("Total assets")), to_float(c.get("Total assets")) - to_float(c.get("Equity"))
    if not np.isfinite(ta) or ta <= 0 or not np.isfinite(tl) or tl <= 0:
        return {"score": None, "zone": "insufficient balance-sheet data"}
    wc = to_float(c.get("Current assets")) - to_float(c.get("Current liabilities"))
    re_ = to_float(c.get("Equity"))  # retained earnings rarely populated for Indian cos -> conservative proxy noted
    x1, x2, x3, x4 = wc / ta, re_ / ta, to_float(c.get("EBIT")) / ta, to_float(c.get("Equity")) / tl
    if not all(np.isfinite(v) for v in (x1, x2, x3, x4)):
        return {"score": None, "zone": "insufficient data"}
    z = 3.25 + 6.56 * x1 + 3.26 * x2 + 6.72 * x3 + 1.05 * x4
    zone = "safe" if z > 5.85 else "grey" if z >= 4.35 else "distress"
    return {"score": round(z, 2), "zone": zone, "note": "Z''-EM; book equity used as retained-earnings proxy (Yahoo rarely reports reserves separately)"}


def red_flags(t: pd.DataFrame, financial: bool, info: dict[str, Any]) -> list[str]:
    flags: list[str] = []
    if t.empty:
        return ["No financial statements available — fundamentals cannot be verified."]
    last = t.iloc[-1]
    if np.isfinite(to_float(last.get("Net profit"))) and to_float(last.get("Net profit")) < 0:
        flags.append("Loss-making in the latest fiscal year.")
    if not financial:
        cfo_pat = t.get("CFO/PAT", pd.Series(dtype=float)).dropna()
        if len(cfo_pat) >= 3 and cfo_pat.iloc[-3:].mean() < 0.7:
            flags.append(f"Weak cash conversion: 3-yr avg CFO/PAT {cfo_pat.iloc[-3:].mean():.2f} (<0.7) — profits not turning into cash.")
        de = to_float(last.get("Debt/Equity"))
        if np.isfinite(de) and de > 1.5:
            flags.append(f"High leverage: Debt/Equity {de:.2f}.")
        ic = to_float(last.get("Interest cover (x)"))
        if np.isfinite(ic) and ic < 2.5:
            flags.append(f"Thin interest cover {ic:.1f}x (EBIT/interest).")
        rd = t.get("Receivable days", pd.Series(dtype=float)).dropna()
        if len(rd) >= 3 and rd.iloc[-1] > 1.3 * rd.iloc[-3] and rd.iloc[-1] > 60:
            flags.append(f"Receivable days rising: {rd.iloc[-3]:.0f} → {rd.iloc[-1]:.0f} (possible aggressive revenue recognition or stressed customers).")
        fcf = t.get("FCF", pd.Series(dtype=float)).dropna()
        if len(fcf) >= 3 and (fcf.iloc[-3:] < 0).sum() >= 2:
            flags.append("Negative free cash flow in 2 of the last 3 years.")
    opm = t.get("OPM %", pd.Series(dtype=float)).dropna()
    if len(opm) >= 3 and opm.iloc[-1] < opm.iloc[-3] - 3:
        flags.append(f"Operating margin compression: {opm.iloc[-3]:.1f}% → {opm.iloc[-1]:.1f}%.")
    sh = t.get("Shares", pd.Series(dtype=float)).dropna()
    if len(sh) >= 2 and sh.iloc[-1] > sh.iloc[0] * 1.08:
        flags.append(f"Share count up {100 * (sh.iloc[-1] / sh.iloc[0] - 1):.1f}% over the period (equity dilution, merger or QIP — check which).")
    rev = t.get("Revenue", pd.Series(dtype=float)).dropna()
    if len(rev) >= 2 and rev.iloc[-1] < rev.iloc[-2] * 0.95:
        flags.append("Revenue declined more than 5% in the latest year.")
    promoter = to_float(info.get("heldPercentInsiders"))
    if np.isfinite(promoter) and 0.02 <= promoter < 0.25:
        flags.append(f"Low insider/promoter holding per Yahoo ({promoter:.0%}) — verify with NSE shareholding pattern.")
    return flags


def _scale(v: float | None, lo: float, hi: float) -> float | None:
    if v is None or not np.isfinite(v):
        return None
    return float(np.clip((v - lo) / (hi - lo) * 100, 0, 100))


def health_score(t: pd.DataFrame, financial: bool, pio: dict[str, Any]) -> dict[str, Any]:
    if t.empty:
        return {"overall": None, "components": {}}
    last = t.iloc[-1]
    rev_cagr = _cagr(t["Revenue"]) if "Revenue" in t else None
    pat_cagr = _cagr(t["Net profit"]) if "Net profit" in t else None
    comps: dict[str, dict[str, Any]] = {}

    if financial:
        prof = np.nanmean([s for s in (_scale(to_float(last.get("ROE %")), 5, 20), _scale(to_float(last.get("ROA %")), 0.3, 2.0)) if s is not None] or [np.nan])
        comps["Profitability"] = {"score": prof, "basis": f"ROE {to_float(last.get('ROE %')):.1f}%, ROA {to_float(last.get('ROA %')):.2f}%"}
    else:
        prof = np.nanmean([s for s in (_scale(to_float(last.get("ROCE %")), 5, 25), _scale(to_float(last.get("ROE %")), 5, 22), _scale(to_float(last.get("OPM %")), 3, 25)) if s is not None] or [np.nan])
        comps["Profitability"] = {"score": prof, "basis": f"ROCE {to_float(last.get('ROCE %')):.1f}%, ROE {to_float(last.get('ROE %')):.1f}%, OPM {to_float(last.get('OPM %')):.1f}%"}

    growth = np.nanmean([s for s in (_scale(rev_cagr, -2, 20), _scale(pat_cagr, -2, 25)) if s is not None] or [np.nan])
    comps["Growth"] = {"score": growth, "basis": f"Revenue CAGR {rev_cagr}%, PAT CAGR {pat_cagr}%"}

    if not financial:
        de, ic, cr = to_float(last.get("Debt/Equity")), to_float(last.get("Interest cover (x)")), to_float(last.get("Current ratio"))
        bs = np.nanmean([s for s in (100 - (_scale(de, 0, 1.5) or 0) if np.isfinite(de) else None, _scale(ic, 1.5, 10), _scale(cr, 0.8, 2.0)) if s is not None] or [np.nan])
        comps["Balance sheet"] = {"score": bs, "basis": f"D/E {de:.2f}, interest cover {ic:.1f}x, current ratio {cr:.2f}"}
        cfo_pat = t["CFO/PAT"].dropna().iloc[-3:].mean() if "CFO/PAT" in t else float("nan")
        fcf_pos = (t["FCF"].dropna() > 0).mean() if "FCF" in t else float("nan")
        cf = np.nanmean([s for s in (_scale(cfo_pat, 0.4, 1.1), fcf_pos * 100 if np.isfinite(fcf_pos) else None) if s is not None] or [np.nan])
        comps["Cash flow quality"] = {"score": cf, "basis": f"3y avg CFO/PAT {cfo_pat:.2f}, FCF positive in {fcf_pos:.0%} of years"}

    if pio.get("score") is not None and pio.get("evaluated"):
        comps["Improvement (Piotroski)"] = {"score": 100 * pio["score"] / pio["evaluated"], "basis": f"F-score {pio['score']}/{pio['evaluated']} tests passed"}

    for v in comps.values():
        v["score"] = None if v["score"] is None or not np.isfinite(v["score"]) else round(float(v["score"]))
    vals = [v["score"] for v in comps.values() if v["score"] is not None]
    return {"overall": round(float(np.mean(vals))) if vals else None, "components": comps}


def data_quality_checks(sd: StockData, t: pd.DataFrame) -> list[str]:
    """Cross-check statement-derived numbers against Yahoo's own quoted fields; disagreement = treat with care."""
    notes: list[str] = []
    if t.empty:
        return notes
    i, last = sd.info, t.iloc[-1]
    shares = to_float(i.get("sharesOutstanding"))
    eq = to_float(last.get("Equity"))
    bv_quote = to_float(i.get("bookValue"))
    if np.isfinite(shares) and shares > 0 and np.isfinite(eq) and np.isfinite(bv_quote) and bv_quote > 0:
        bv_stmt = eq / shares
        if abs(bv_stmt / bv_quote - 1) > 0.25:
            notes.append(f"Book value per share from statements (₹{bv_stmt:,.0f}) differs from Yahoo's quoted book value "
                         f"(₹{bv_quote:,.0f}) by {100 * (bv_stmt / bv_quote - 1):+.0f}% — consolidated vs standalone or a data error; "
                         "P/B, ROE and justified P/B may be off. Verify with the annual report.")
    eps_t, eps_q = to_float(last.get("EPS")), to_float(i.get("trailingEps"))
    if np.isfinite(eps_t) and np.isfinite(eps_q) and eps_q > 0 and abs(eps_t / eps_q - 1) > 0.35:
        notes.append(f"Latest fiscal-year EPS (₹{eps_t:,.2f}) and Yahoo trailing EPS (₹{eps_q:,.2f}) differ by "
                     f"{100 * (eps_t / eps_q - 1):+.0f}% — check for bonus/split adjustments or a sharp earnings change.")
    rep, adj = t.get("Reported EPS", pd.Series(dtype=float)).dropna(), t.get("EPS", pd.Series(dtype=float)).dropna()
    if len(rep) >= 2 and len(adj) >= 2:
        jump = (rep / adj).dropna()
        if len(jump) and (jump.max() / jump.min()) > 1.6:
            notes.append("Reported EPS history is not consistently adjusted for bonus issues/splits; EPS here is recomputed "
                         "as net profit ÷ Yahoo's adjusted share count.")
    sh = t.get("Shares", pd.Series(dtype=float)).dropna()
    if len(sh) >= 2 and sh.iloc[-1] > 1.25 * sh.iloc[0]:
        notes.append(f"Share count rose {100 * (sh.iloc[-1] / sh.iloc[0] - 1):.0f}% over the period — could be a merger, QIP, "
                     "rights issue or ESOPs; growth in revenue/profit may be partly acquired, not organic.")
    return notes


def fundamental_summary(sd: StockData) -> dict[str, Any]:
    fin = is_financial(sd)
    t = annual_table(sd)
    q = quarterly_table(sd)
    pio = piotroski(t) if not t.empty else {"score": None, "checks": []}
    out: dict[str, Any] = {
        "is_financial_company": fin,
        "currency_unit": "₹ crore",
        "fiscal_years": list(t.index),
        "growth_cagr_pct": {
            "revenue": _cagr(t["Revenue"]) if "Revenue" in t else None,
            "net_profit": _cagr(t["Net profit"]) if "Net profit" in t else None,
            "eps": _cagr(t["EPS"]) if "EPS" in t else None,
        },
        "piotroski": pio,
        "altman_z_em": altman_z_em(t, fin),
        "red_flags": red_flags(t, fin, sd.info),
        "health": health_score(t, fin, pio),
        "data_gaps": [
            "Promoter pledge %, full shareholding pattern (promoter/FII/DII/public trend) — not in Yahoo data; check NSE/BSE shareholding filings.",
            "Segment revenue, order book, management guidance and concall commentary — not available.",
            f"Only {len(t)} fiscal years of statements available from Yahoo; long-term history is limited.",
            "Peers come from NSE's broad industry classification sized by traded value; they may include dissimilar businesses.",
            "Consolidated cash flow of groups with lending arms (e.g. auto makers with finance subsidiaries) looks weak because loan growth is an operating outflow.",
        ],
    }
    out["data_quality"] = data_quality_checks(sd, t)
    promoter = to_float(sd.info.get("heldPercentInsiders"))
    if np.isfinite(promoter) and promoter < 0.02:
        out["data_gaps"].append("Yahoo shows ~0% insider/promoter holding: either the company has no promoter group "
                                "(e.g. HDFC Bank, ICICI Bank, ITC, L&T) or the data is missing — check the NSE shareholding pattern.")
    if fin:
        out["data_gaps"].append("Bank/NBFC metrics (NIM, GNPA/NNPA, CASA, capital adequacy, credit cost) are not available — health score uses ROE/ROA/growth only.")
    if not t.empty:
        keep = ["Revenue", "EBITDA", "Net profit", "EPS", "OPM %", "NPM %", "ROE %", "ROCE %", "Debt/Equity",
                "Interest cover (x)", "CFO", "FCF", "CFO/PAT", "Receivable days", "Payout %"]
        tbl = t[[c for c in keep if c in t.columns]].copy()
        for c in ("Revenue", "EBITDA", "Net profit", "CFO", "FCF"):
            if c in tbl:
                tbl[c] = tbl[c] / CRORE
        out["annual"] = {fy: {k: _clean(round(float(v), 2)) if pd.notna(v) else None for k, v in row.items()} for fy, row in tbl.iterrows()}
    if not q.empty:
        qt = q.copy()
        for c in ("Revenue", "Operating profit", "Net profit"):
            if c in qt:
                qt[c] = qt[c] / CRORE
        out["quarterly"] = {p: {k: _clean(round(float(v), 2)) if pd.notna(v) else None for k, v in row.items()} for p, row in qt.iterrows()}
    i = sd.info
    out["ownership_proxy"] = {
        "insiders_promoters_pct": _clean(round(100 * to_float(i.get("heldPercentInsiders")), 1)),
        "institutions_pct": _clean(round(100 * to_float(i.get("heldPercentInstitutions")), 1)),
        "note": "Yahoo 'insiders' approximates promoter holding; verify against the latest NSE shareholding pattern.",
    }
    return out
