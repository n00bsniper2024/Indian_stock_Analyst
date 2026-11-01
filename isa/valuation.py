"""Valuation: multiples, historical P/E band, 2-stage FCFF DCF with sensitivity,
reverse DCF (what growth the price implies), justified P/B for lenders, peer-relative
values, and a football-field summary. All per-share values in ₹.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd

from .config import ValuationDefaults
from .data import StockData, to_float
from .fundamentals import annual_table, col, is_financial


@dataclass
class DCFInputs:
    base_fcf: float
    growth_1: float  # years 1-5
    terminal_g: float
    wacc: float
    years: int
    net_debt: float
    shares: float


def dcf_value(p: DCFInputs) -> float:
    """Two-stage FCFF DCF: growth_1 for 5 years, linear fade to terminal_g by `years`."""
    if p.wacc <= p.terminal_g + 0.005 or p.shares <= 0:
        return float("nan")
    fcf, pv = p.base_fcf, 0.0
    for yr in range(1, p.years + 1):
        g = p.growth_1 if yr <= 5 else p.growth_1 + (p.terminal_g - p.growth_1) * (yr - 5) / (p.years - 5)
        fcf *= 1 + g
        pv += fcf / (1 + p.wacc) ** yr
    tv = fcf * (1 + p.terminal_g) / (p.wacc - p.terminal_g)
    pv += tv / (1 + p.wacc) ** p.years
    return (pv - p.net_debt) / p.shares


def reverse_dcf(p: DCFInputs, price: float) -> float | None:
    """Stage-1 growth that justifies the current price (bisection)."""
    lo, hi = -0.3, 0.8

    def f(g: float) -> float:
        return dcf_value(DCFInputs(p.base_fcf, g, p.terminal_g, p.wacc, p.years, p.net_debt, p.shares)) - price

    if not (np.isfinite(f(lo)) and np.isfinite(f(hi))) or f(lo) * f(hi) > 0:
        return None
    for _ in range(80):
        mid = (lo + hi) / 2
        if f(lo) * f(mid) <= 0:
            hi = mid
        else:
            lo = mid
    return round(100 * (lo + hi) / 2, 1)


def _shares(sd: StockData) -> float:
    s = to_float(sd.info.get("sharesOutstanding"))
    if not np.isfinite(s) or s <= 0:
        sh = col(sd.balance_a, "shares").dropna()
        s = float(sh.iloc[-1]) if len(sh) else float("nan")
    return s


def multiples(sd: StockData, t: pd.DataFrame) -> dict[str, Any]:
    price, info = sd.last_price, sd.info
    shares = _shares(sd)
    mcap = price * shares if np.isfinite(shares) else to_float(info.get("marketCap"))
    last = t.iloc[-1] if not t.empty else pd.Series(dtype=float)
    eps = to_float(last.get("EPS"))
    if not np.isfinite(eps) or eps == 0:
        eps = to_float(info.get("trailingEps"))
    debt, cash = to_float(last.get("Debt")), to_float(last.get("Cash"))
    ev = mcap + (debt if np.isfinite(debt) else 0) - (cash if np.isfinite(cash) else 0)
    ebitda, rev, eq = to_float(last.get("EBITDA")), to_float(last.get("Revenue")), to_float(last.get("Equity"))
    eps_s = t["EPS"].dropna() if "EPS" in t else pd.Series(dtype=float)
    eps_cagr = None
    if len(eps_s) >= 3 and eps_s.iloc[0] > 0 and eps_s.iloc[-1] > 0:
        eps_cagr = (eps_s.iloc[-1] / eps_s.iloc[0]) ** (1 / (len(eps_s) - 1)) - 1
    pe = price / eps if np.isfinite(eps) and eps > 0 else None
    dy = to_float(info.get("dividendYield"))
    if np.isfinite(dy) and dy < 0.2:  # some yfinance versions return a fraction, newer ones a percent
        dy *= 100

    def r(x: Any, n: int = 2) -> Any:
        return round(float(x), n) if x is not None and np.isfinite(x) else None

    return {
        "price": r(price),
        "market_cap_cr": r(mcap / 1e7, 0),
        "enterprise_value_cr": r(ev / 1e7, 0),
        "pe_ttm_or_latest_fy": r(pe, 1),
        "forward_pe_yahoo": r(to_float(info.get("forwardPE")), 1),
        "pb": r(mcap / eq, 2) if np.isfinite(eq) and eq > 0 else r(to_float(info.get("priceToBook"))),
        "ev_ebitda": r(ev / ebitda, 1) if np.isfinite(ebitda) and ebitda > 0 else None,
        "ev_sales": r(ev / rev, 2) if np.isfinite(rev) and rev > 0 else None,
        "earnings_yield_pct": r(100 / pe, 2) if pe else None,
        "dividend_yield_pct": r(dy, 2),
        "peg": r(pe / (100 * eps_cagr), 2) if pe and eps_cagr and eps_cagr > 0 else None,
        "eps_cagr_pct": r(100 * eps_cagr, 1) if eps_cagr is not None else None,
        "eps_latest": r(eps, 2),
        "book_value_per_share": r(eq / shares, 2) if np.isfinite(eq) and np.isfinite(shares) and shares > 0 else None,
    }


def pe_band(sd: StockData, t: pd.DataFrame) -> pd.DataFrame:
    """Monthly P/E using the latest *reported* annual EPS (60-day reporting lag)."""
    ni = col(sd.income_a, "net_income")
    sh = col(sd.balance_a, "shares").reindex(ni.index)
    eps = (ni / sh.where(sh > 0)).where(sh.notna(), col(sd.income_a, "eps")).dropna()  # bonus/split-consistent
    if len(eps) < 2:
        return pd.DataFrame()
    px = sd.daily["Close"].resample("ME").last()
    avail = pd.Series(eps.values, index=eps.index + pd.Timedelta(days=60))
    eps_m = avail.reindex(px.index.union(avail.index)).sort_index().ffill().reindex(px.index)
    pe = (px / eps_m).where(eps_m > 0).dropna()
    return pd.DataFrame({"PE": pe, "Price": px.reindex(pe.index)})


def wacc_breakdown(sd: StockData, t: pd.DataFrame, beta: float | None, d: ValuationDefaults) -> dict[str, Any]:
    b = beta if beta is not None and np.isfinite(beta) else to_float(sd.info.get("beta"))
    b = float(np.clip(b if np.isfinite(b) else 1.0, 0.6, 2.0))
    ke = d.risk_free + b * d.equity_risk_premium
    last = t.iloc[-1] if not t.empty else pd.Series(dtype=float)
    debt, interest = to_float(last.get("Debt")), to_float(last.get("Interest"))
    kd = interest / debt if np.isfinite(debt) and debt > 0 and np.isfinite(interest) else d.risk_free + 0.02
    kd = float(np.clip(kd, d.risk_free, d.risk_free + 0.07))
    mcap = sd.last_price * _shares(sd)
    debt = debt if np.isfinite(debt) else 0.0
    we = mcap / (mcap + debt) if mcap + debt > 0 else 1.0
    wacc = we * ke + (1 - we) * kd * (1 - d.tax_rate)
    return {"beta_used": round(b, 2), "cost_of_equity_pct": round(100 * ke, 2), "pre_tax_cost_of_debt_pct": round(100 * kd, 2),
            "equity_weight_pct": round(100 * we, 1), "wacc_pct": round(100 * wacc, 2), "risk_free_pct": round(100 * d.risk_free, 2),
            "erp_pct": round(100 * d.equity_risk_premium, 2), "tax_rate_pct": round(100 * d.tax_rate, 2), "_wacc": wacc, "_ke": ke}


def dcf_block(sd: StockData, t: pd.DataFrame, w: dict[str, Any], d: ValuationDefaults, growth_override: float | None = None) -> dict[str, Any]:
    if t.empty or "FCF" not in t:
        return {"applicable": False, "reason": "no cash-flow statements"}
    fcf = t["FCF"].dropna().iloc[-3:]
    if len(fcf) == 0 or fcf.median() <= 0:
        return {"applicable": False, "reason": "free cash flow is negative/erratic — DCF not meaningful; use multiples"}
    base = float(fcf.median())
    rev = t["Revenue"].dropna()
    hist_g = (rev.iloc[-1] / rev.iloc[0]) ** (1 / max(len(rev) - 1, 1)) - 1 if len(rev) >= 2 and rev.iloc[0] > 0 else 0.10
    g1 = growth_override if growth_override is not None else float(np.clip(hist_g, 0.0, 0.20))
    last = t.iloc[-1]
    net_debt = (to_float(last.get("Debt")) if np.isfinite(to_float(last.get("Debt"))) else 0) - (to_float(last.get("Cash")) if np.isfinite(to_float(last.get("Cash"))) else 0)
    shares = _shares(sd)
    p = DCFInputs(base, g1, d.terminal_growth, w["_wacc"], d.forecast_years, net_debt, shares)
    fair = dcf_value(p)
    waccs = [w["_wacc"] + x for x in (-0.02, -0.01, 0.0, 0.01, 0.02)]
    gs = [d.terminal_growth + x for x in (-0.01, -0.005, 0.0, 0.005, 0.01)]
    grid = [[round(dcf_value(DCFInputs(base, g1, g, wc, d.forecast_years, net_debt, shares)), 0) for g in gs] for wc in waccs]
    vals = [v for row in grid for v in row if np.isfinite(v)]
    price = sd.last_price
    return {
        "applicable": True,
        "base_fcf_cr": round(base / 1e7, 1),
        "stage1_growth_pct": round(100 * g1, 1),
        "historical_revenue_cagr_pct": round(100 * hist_g, 1),
        "terminal_growth_pct": round(100 * d.terminal_growth, 2),
        "fair_value_per_share": round(fair, 1) if np.isfinite(fair) else None,
        "upside_pct": round(100 * (fair / price - 1), 1) if np.isfinite(fair) else None,
        "implied_stage1_growth_pct": reverse_dcf(p, price),
        "sensitivity": {"wacc_pct": [round(100 * x, 1) for x in waccs], "terminal_g_pct": [round(100 * x, 1) for x in gs], "values": grid},
        "range": [round(min(vals), 0), round(max(vals), 0)] if vals else None,
    }


def justified_pb(sd: StockData, t: pd.DataFrame, w: dict[str, Any], d: ValuationDefaults) -> dict[str, Any]:
    """Gordon-growth justified P/B for lenders: P/B = (ROE - g) / (Ke - g)."""
    roe = t["ROE %"].dropna().iloc[-3:].mean() / 100 if "ROE %" in t and t["ROE %"].notna().any() else float("nan")
    eq = to_float(t.iloc[-1].get("Equity")) if not t.empty else float("nan")
    shares = _shares(sd)
    ke, g = w["_ke"], min(d.terminal_growth + 0.02, w["_ke"] - 0.01)
    if not np.isfinite(roe) or not np.isfinite(eq) or shares <= 0:
        return {"applicable": False, "reason": "missing ROE/book value"}
    pb = (roe - g) / (ke - g)
    bvps = eq / shares
    fair = pb * bvps
    return {"applicable": True, "avg_roe_3y_pct": round(100 * roe, 1), "cost_of_equity_pct": round(100 * ke, 2),
            "sustainable_growth_pct": round(100 * g, 1), "justified_pb": round(pb, 2), "bvps": round(bvps, 1),
            "fair_value_per_share": round(fair, 1), "upside_pct": round(100 * (fair / sd.last_price - 1), 1)}


PEER_FIELDS = {
    "trailingPE": "P/E", "priceToBook": "P/B", "enterpriseToEbitda": "EV/EBITDA", "returnOnEquity": "ROE %",
    "operatingMargins": "Op margin %", "revenueGrowth": "Revenue growth %", "debtToEquity": "Debt/Equity", "marketCap": "Mcap (₹ cr)",
}


def peer_table(infos: dict[str, dict[str, Any]]) -> pd.DataFrame:
    rows = []
    for sym, i in infos.items():
        row = {"Symbol": sym, "Name": (i.get("shortName") or i.get("longName") or sym)[:30]}
        for k, lbl in PEER_FIELDS.items():
            v = to_float(i.get(k))
            if k in ("returnOnEquity", "operatingMargins", "revenueGrowth") and np.isfinite(v):
                v *= 100
            if k == "marketCap" and np.isfinite(v):
                v /= 1e7
            if k == "debtToEquity" and np.isfinite(v):
                v /= 100  # Yahoo reports D/E in percent
            # Yahoo occasionally returns nonsense multiples (e.g. EV/EBITDA > 1000x); drop implausible values
            if k in ("trailingPE", "enterpriseToEbitda") and np.isfinite(v) and not (0 < v < 300):
                v = float("nan")
            if k == "priceToBook" and np.isfinite(v) and not (0 < v < 100):
                v = float("nan")
            row[lbl] = round(v, 2) if np.isfinite(v) else None
        rows.append(row)
    return pd.DataFrame(rows)


def peer_relative(sd: StockData, mult: dict[str, Any], peers: pd.DataFrame) -> dict[str, Any]:
    if peers is None or peers.empty:
        return {"available": False}
    others = peers[peers["Symbol"] != sd.symbol]
    med = {c: float(others[c].dropna().median()) for c in ("P/E", "P/B", "EV/EBITDA", "ROE %") if c in others and others[c].notna().sum() >= 2}
    out: dict[str, Any] = {"available": True, "peer_count": int(len(others)), "peer_median": {k: round(v, 2) for k, v in med.items()}}
    eps, bvps = mult.get("eps_latest"), mult.get("book_value_per_share")
    if "P/E" in med and eps and eps > 0:
        q = others["P/E"].dropna()
        q = q[(q > 0) & (q < 300)]
        if len(q) >= 2:
            out["pe_implied_range"] = [round(eps * q.quantile(0.25), 0), round(eps * q.quantile(0.75), 0)]
            out["pe_implied_median"] = round(eps * med["P/E"], 0)
    if "P/B" in med and bvps:
        q = others["P/B"].dropna()
        if len(q) >= 2:
            out["pb_implied_range"] = [round(bvps * q.quantile(0.25), 0), round(bvps * q.quantile(0.75), 0)]
    return out


def valuation_summary(sd: StockData, beta: float | None, settings: ValuationDefaults | None = None,
                      peers: pd.DataFrame | None = None, growth_override: float | None = None) -> dict[str, Any]:
    d = settings or ValuationDefaults()
    t = annual_table(sd)
    fin = is_financial(sd)
    mult = multiples(sd, t)
    w = wacc_breakdown(sd, t, beta, d)
    out: dict[str, Any] = {"multiples": mult, "wacc": {k: v for k, v in w.items() if not k.startswith("_")}}
    band = pe_band(sd, t)
    if len(band) >= 12:
        pe_now = mult.get("pe_ttm_or_latest_fy")
        out["pe_history"] = {
            "median": round(float(band["PE"].median()), 1),
            "p25": round(float(band["PE"].quantile(0.25)), 1),
            "p75": round(float(band["PE"].quantile(0.75)), 1),
            "months": int(len(band)),
            "current_vs_median_pct": round(100 * (pe_now / band["PE"].median() - 1), 1) if pe_now else None,
        }
    out["dcf"] = {"applicable": False, "reason": "DCF on free cash flow is not meaningful for lenders/insurers"} if fin else dcf_block(sd, t, w, d, growth_override)
    if fin:
        out["justified_pb"] = justified_pb(sd, t, w, d)
    out["peers"] = peer_relative(sd, mult, peers) if peers is not None else {"available": False}
    i = sd.info
    tgt = {k: to_float(i.get(k)) for k in ("targetLowPrice", "targetMeanPrice", "targetHighPrice")}
    if all(np.isfinite(v) for v in tgt.values()):
        out["street_targets_yahoo"] = {k: round(v, 0) for k, v in tgt.items()} | {"analysts": i.get("numberOfAnalystOpinions")}

    # football field ------------------------------------------------------------
    ff: list[dict[str, Any]] = []
    perf_hi = float(sd.daily["High"].iloc[-252:].max())
    perf_lo = float(sd.daily["Low"].iloc[-252:].min())
    ff.append({"method": "52-week range", "low": round(perf_lo, 0), "high": round(perf_hi, 0)})
    dcf = out["dcf"]
    if dcf.get("applicable") and dcf.get("range"):
        ff.append({"method": "DCF (WACC ±2%, g ±1%)", "low": dcf["range"][0], "high": dcf["range"][1]})
    if "pe_history" in out and mult.get("eps_latest") and mult["eps_latest"] > 0:
        e = mult["eps_latest"]
        ff.append({"method": "Own P/E band (25th-75th pct)", "low": round(e * out["pe_history"]["p25"], 0), "high": round(e * out["pe_history"]["p75"], 0)})
    pr = out["peers"]
    if pr.get("pe_implied_range"):
        ff.append({"method": "Peer P/E (25th-75th pct)", "low": pr["pe_implied_range"][0], "high": pr["pe_implied_range"][1]})
    if pr.get("pb_implied_range") and fin:
        ff.append({"method": "Peer P/B (25th-75th pct)", "low": pr["pb_implied_range"][0], "high": pr["pb_implied_range"][1]})
    jp = out.get("justified_pb", {})
    if jp.get("applicable"):
        ff.append({"method": "Justified P/B (ROE-based)", "low": round(jp["fair_value_per_share"] * 0.85, 0), "high": round(jp["fair_value_per_share"] * 1.15, 0)})
    if "street_targets_yahoo" in out:
        s = out["street_targets_yahoo"]
        ff.append({"method": "Street targets (Yahoo)", "low": s["targetLowPrice"], "high": s["targetHighPrice"]})
    out["football_field"] = ff

    # valuation score: 100 = looks cheap on every lens available, 0 = expensive ----------
    signals: list[float] = []
    if dcf.get("upside_pct") is not None:
        signals.append(float(np.clip(50 + dcf["upside_pct"], 0, 100)))
    if jp.get("upside_pct") is not None:
        signals.append(float(np.clip(50 + jp["upside_pct"], 0, 100)))
    ph = out.get("pe_history", {})
    if ph.get("current_vs_median_pct") is not None:
        signals.append(float(np.clip(50 - ph["current_vs_median_pct"], 0, 100)))
    if pr.get("pe_implied_median") and mult.get("price"):
        signals.append(float(np.clip(50 + 100 * (pr["pe_implied_median"] / mult["price"] - 1), 0, 100)))
    if mult.get("peg"):
        signals.append(float(np.clip(100 - 40 * mult["peg"], 0, 100)))
    out["valuation_score"] = round(float(np.mean(signals))) if signals else None
    out["valuation_score_basis"] = f"{len(signals)} lenses (DCF/justified P/B upside, own P/E history, peer P/E, PEG); 50 = fairly valued"
    return out


def safe_round(x: Any, n: int = 2) -> Any:
    try:
        v = float(x)
        return round(v, n) if math.isfinite(v) else None
    except (TypeError, ValueError):
        return None
