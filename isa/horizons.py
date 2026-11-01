"""Horizon-wise model ratings (1 week → long term), a trade plan, and a historical check.

Each horizon blends different evidence, because what moves a stock over a week (trend, breakouts,
where price sits between zones) is not what moves it over five years (business quality, valuation).
Weights are explicit below; missing inputs are skipped and the remaining weights re-normalised.

The ratings are a transparent MODEL SIGNAL for research — not personalised investment advice.
"""
from __future__ import annotations

import math
from typing import Any

import numpy as np
import pandas as pd

from .technicals import add_indicators

HORIZONS = {
    "1 Week": {"days": 5, "weights": {"trend_short": .30, "breakout_short": .25, "location": .15, "momentum_rsi": .15, "news": .05, "trend_medium": .10}},
    "4 Weeks": {"days": 21, "weights": {"trend_medium": .30, "breakout_medium": .20, "rel_strength_3m": .15, "trend_short": .10, "location": .10, "earnings_momentum": .10, "news": .05}},
    "3 Months": {"days": 63, "weights": {"trend_medium": .25, "trend_long": .10, "rel_strength_3m": .15, "earnings_momentum": .20, "fundamentals": .15, "valuation": .10, "news": .05}},
    "6 Months": {"days": 126, "weights": {"trend_long": .20, "trend_medium": .10, "rel_strength_1y": .10, "earnings_momentum": .20, "fundamentals": .25, "valuation": .15}},
    "1 Year": {"days": 252, "weights": {"trend_long": .15, "rel_strength_1y": .10, "earnings_momentum": .15, "fundamentals": .35, "valuation": .25}},
    "Long term (3Y+)": {"days": 756, "weights": {"fundamentals": .50, "valuation": .30, "trend_long": .10, "earnings_momentum": .10}},
}

FACTOR_LABELS = {
    "trend_short": "Short-term trend (1H/4H/1D)", "trend_medium": "Medium-term trend (1D/1W)", "trend_long": "Long-term trend (1W/1M)",
    "breakout_short": "Breakouts 1H/4H/1D", "breakout_medium": "Breakouts 1D/1W", "location": "Room to resistance vs risk to support",
    "momentum_rsi": "RSI momentum", "rel_strength_3m": "Relative strength vs Nifty (3M)", "rel_strength_1y": "Relative strength vs Nifty (1Y)",
    "earnings_momentum": "Earnings momentum (recent quarters YoY)", "fundamentals": "Fundamental health", "valuation": "Valuation",
    "news": "News & announcements tone",
}


def label_for(score: float) -> str:
    return ("Strong Buy" if score >= 70 else "Buy" if score >= 58 else "Neutral" if score >= 45
            else "Sell" if score >= 33 else "Strong Sell")


def _clip(x: float) -> float:
    return float(np.clip(x, 0, 100))


# --------------------------------------------------------------------------- factor scores (0-100, 50 = neutral)
def factors(pack: dict[str, Any]) -> dict[str, dict[str, Any]]:
    tech, fund, val = pack["technical"], pack["fundamentals"], pack["valuation"]
    tf = {t["timeframe"]: t["score"] for t in tech["timeframes"] if t.get("available")}
    perf = tech["performance"]
    br = pack.get("breakouts", {})
    news = pack.get("news", {})
    out: dict[str, dict[str, Any]] = {}

    def add(key: str, score: float | None, basis: str) -> None:
        if score is not None and math.isfinite(score):
            out[key] = {"score": round(_clip(score)), "basis": basis, "label": FACTOR_LABELS[key]}

    def avg_tf(names: list[str], w: list[float]) -> tuple[float | None, str]:
        pairs = [(tf[n], wi) for n, wi in zip(names, w) if n in tf]
        if not pairs:
            return None, "n/a"
        s = sum(v * wi for v, wi in pairs) / sum(wi for _, wi in pairs)
        return (s + 100) / 2, ", ".join(f"{n} {tf[n]:+d}" for n in names if n in tf)

    s, b = avg_tf(["1 Hour", "4 Hour", "Daily"], [0.25, 0.35, 0.4])
    add("trend_short", s, f"trend scores {b}")
    s, b = avg_tf(["Daily", "Weekly"], [0.5, 0.5])
    add("trend_medium", s, f"trend scores {b}")
    s, b = avg_tf(["Weekly", "Monthly"], [0.5, 0.5])
    add("trend_long", s, f"trend scores {b}")

    def br_score(names: list[str]) -> tuple[float | None, str]:
        vals, notes = [], []
        for n in names:
            t = br.get(n, {})
            if not t.get("available"):
                continue
            sc = 50.0
            for p in t.get("patterns", []):
                conf = "confirmed" in p["status"] and "unconfirmed" not in p["status"]
                weak = "unconfirmed" in p["status"]
                fail = "failed" in p["status"]
                d = {"bullish": 1, "bearish": -1}.get(p["direction"], 0)
                if fail:
                    d = -d
                sc += d * (25 if conf else 14 if weak else 8)
            vals.append(_clip(sc))
            notes.append(f"{n}: {t.get('breakout_bias')}")
        return (float(np.mean(vals)), "; ".join(notes)) if vals else (None, "")

    s, b = br_score(["1H", "4H", "1D"])
    add("breakout_short", s, b)
    s, b = br_score(["1D", "1W"])
    add("breakout_medium", s, b)

    z = br.get("1D", {}).get("zones", {})
    px = perf["last_close"]
    if z.get("resistances") and z.get("supports"):
        up = z["resistances"][0]["low"] - px
        down = px - z["supports"][0]["high"]
        if up > 0 and down > 0:
            rr = up / down
            add("location", 50 + 15 * math.log2(rr), f"next resistance {up / px:+.1%} away vs support {-down / px:.1%} (reward/risk {rr:.1f}×)")
    elif z.get("supports") and not z.get("resistances"):
        add("location", 70, "no overhead resistance zone in the last year (price at highs)")

    rsi = tech.get("daily_rsi")
    if rsi is not None:
        sc = 50 + (rsi - 50) * 1.6 if rsi <= 70 else 82 - (rsi - 70) * 3  # momentum good, overbought fades
        add("momentum_rsi", sc, f"daily RSI {rsi}")

    rs = perf.get("relative_strength_vs_nifty_pct", {})
    if rs.get("3M") is not None:
        add("rel_strength_3m", 50 + 2.5 * rs["3M"], f"{rs['3M']:+.1f} pp vs Nifty over 3M")
    if rs.get("1Y") is not None:
        add("rel_strength_1y", 50 + 1.2 * rs["1Y"], f"{rs['1Y']:+.1f} pp vs Nifty over 1Y")

    q = fund.get("quarterly", {})
    yoy = [v.get("Profit YoY %") for v in list(q.values())[-2:] if v.get("Profit YoY %") is not None]
    ryoy = [v.get("Revenue YoY %") for v in list(q.values())[-2:] if v.get("Revenue YoY %") is not None]
    if yoy or ryoy:
        p_ = float(np.clip(np.mean(yoy), -60, 80)) if yoy else None
        r_ = float(np.clip(np.mean(ryoy), -40, 60)) if ryoy else None
        sc = np.mean([x for x in (50 + 1.0 * p_ if p_ is not None else None, 50 + 1.6 * r_ if r_ is not None else None) if x is not None])
        add("earnings_momentum", sc, f"recent quarters profit YoY {p_:+.0f}%" if p_ is not None else f"revenue YoY {r_:+.0f}%")
    else:
        g = fund.get("growth_cagr_pct", {})
        if g.get("net_profit") is not None:
            add("earnings_momentum", 50 + 1.5 * (g["net_profit"] - 8), f"no matched quarters; using annual PAT CAGR {g['net_profit']}%")

    h = fund.get("health", {}).get("overall")
    if h is not None:
        penalty = 5 * min(3, len(fund.get("red_flags", [])))
        add("fundamentals", h - penalty, f"health {h}/100" + (f", −{penalty} for {len(fund['red_flags'])} red flag(s)" if penalty else ""))
    v = val.get("valuation_score")
    if v is not None:
        add("valuation", v, f"valuation score {v}/100 (higher = cheaper)")

    tone = news.get("headline_tone_rough") or {}
    tot = sum(tone.get(k, 0) for k in ("positive", "negative", "neutral"))
    if tot >= 3:
        sc = 50 + 30 * (tone["positive"] - tone["negative"]) / tot
        n_alert = len(news.get("attention_items") or [])
        add("news", sc - 4 * min(n_alert, 3), f"{tone['positive']} positive / {tone['negative']} negative headlines" + (f", {n_alert} alert filing(s)" if n_alert else ""))
    return out


# --------------------------------------------------------------------------- historical check
def daily_score_series(df: pd.DataFrame) -> pd.Series:
    """Vectorised version of technicals.trend_assessment on daily bars (same rules, every day)."""
    x = add_indicators(df)
    c = x["Close"]
    parts = [
        (c > x["EMA20"], x["EMA20"], 10), (c > x["EMA50"], x["EMA50"], 15), (c > x["EMA200"], x["EMA200"], 20),
        (x["EMA20"] > x["EMA50"], x["EMA50"], 10), (x["EMA50"] > x["EMA200"], x["EMA200"], 10),
        (x["EMA50"] > x["EMA50"].shift(10), x["EMA50"].shift(10), 10), (x["MACD_hist"] > 0, x["MACD_hist"], 10),
        (x["ST_dir"] > 0, x["ST_dir"].where(x["ST_dir"] != 0), 15),
    ]
    num = pd.Series(0.0, index=x.index)
    den = pd.Series(0.0, index=x.index)
    for cond, avail, w in parts:
        ok = avail.notna()
        num += np.where(ok, np.where(cond, w, -w), 0)
        den += np.where(ok, w, 0)
    return (100 * num / den.replace(0, np.nan)).round()


def historical_check(daily: pd.DataFrame, years: int = 10) -> dict[str, Any]:
    d = daily.iloc[-(252 * years + 260):]
    if len(d) < 400:
        return {"available": False}
    score = daily_score_series(d)
    now = float(score.iloc[-1])
    close = d["Close"]
    out: dict[str, Any] = {"available": True, "current_daily_score": int(now), "method":
                           "Days in the last ~10 years whose daily trend score was within ±20 of today's; forward returns measured from those days. "
                           "Overlapping windows and changing regimes make this indicative, not a forecast."}
    for name, cfg in HORIZONS.items():
        h = cfg["days"]
        fwd = close.shift(-h) / close - 1
        valid = fwd.notna() & score.notna()
        base = fwd[valid]
        sim = fwd[valid & ((score - now).abs() <= 20)]
        if len(base) < 100 or len(sim) < 30:
            out[name] = {"available": False, "samples": int(len(sim))}
            continue
        out[name] = {
            "available": True, "samples": int(len(sim)),
            "pct_positive_similar": round(100 * float((sim > 0).mean()), 1),
            "median_return_similar_pct": round(100 * float(sim.median()), 2),
            "pct_positive_all_days": round(100 * float((base > 0).mean()), 1),
            "median_return_all_days_pct": round(100 * float(base.median()), 2),
            "worst_10pct_similar_pct": round(100 * float(sim.quantile(0.1)), 2),
            "edge_pp": round(100 * float((sim > 0).mean() - (base > 0).mean()), 1),
        }
    return out


# --------------------------------------------------------------------------- trade plan
def trade_plan(pack: dict[str, Any], horizon: str) -> dict[str, Any] | None:
    tfmap = {"1 Week": "1D", "4 Weeks": "1D", "3 Months": "1W", "6 Months": "1W", "1 Year": "1W", "Long term (3Y+)": "1W"}
    br = pack.get("breakouts", {}).get(tfmap[horizon], {})
    if not br.get("available"):
        return None
    z, a = br["zones"], br.get("atr") or 0
    px = pack["technical"]["performance"]["last_close"]
    sup, res = z.get("supports", []), z.get("resistances", [])
    confirmed_up = next((p for p in br.get("patterns", []) if p["direction"] == "bullish" and p["status"].startswith("breakout confirmed")), None)
    if confirmed_up and confirmed_up.get("trigger"):
        entry_lo, entry_hi = confirmed_up["trigger"], confirmed_up["trigger"] + 0.5 * a
        basis = f"retest of the {confirmed_up['pattern'].lower()} level"
    elif sup:
        entry_lo, entry_hi = sup[0]["low"], sup[0]["high"]
        basis = "nearest support zone (buy-on-dip area)"
    else:
        entry_lo, entry_hi = px - 0.5 * a, px
        basis = "current price (no support zone below)"
    stop = (sup[1]["low"] if len(sup) > 1 and sup[0]["low"] - sup[1]["low"] < 3 * a else entry_lo) - 0.5 * a if sup else entry_lo - 2 * a
    targets = [r["low"] for r in res[:2]]
    pt = next((p["target"] for p in br.get("patterns", []) if p["direction"] == "bullish" and p.get("target")), None)
    if pt and (not targets or pt > targets[-1]):
        targets.append(pt)
    if not targets:
        targets = [round(px + 2 * a, 2), round(px + 4 * a, 2)]
    mid = (entry_lo + entry_hi) / 2
    risk = mid - stop
    rr = round((targets[0] - mid) / risk, 2) if risk > 0 and targets[0] > mid else None
    return {
        "timeframe_used": br["timeframe"], "entry_zone": [round(entry_lo, 2), round(entry_hi, 2)], "entry_basis": basis,
        "stop_loss": round(stop, 2), "stop_pct": round(100 * (stop / mid - 1), 1),
        "targets": [round(t, 2) for t in targets[:3]], "reward_risk_t1": rr,
        "attractive": bool(rr is not None and rr >= 1.5),
        "note": ("Reward/risk to the first target is below 1.5× — unattractive at these levels; better entries are lower or after a breakout."
                 if rr is None or rr < 1.5 else "Levels come from support/resistance zones and ATR.")
                + " Size positions so a stop-out is a loss you can accept.",
    }


# --------------------------------------------------------------------------- bundle
def horizon_ratings(pack: dict[str, Any], daily: pd.DataFrame | None = None) -> dict[str, Any]:
    f = factors(pack)
    hist = historical_check(daily) if daily is not None else {"available": False}
    days_to_results = (pack.get("news") or {}).get("days_to_results")
    out: dict[str, Any] = {}
    for name, cfg in HORIZONS.items():
        used = {k: w for k, w in cfg["weights"].items() if k in f}
        coverage = sum(used.values()) / sum(cfg["weights"].values())
        if coverage < 0.5:
            out[name] = {"rating": "Insufficient data", "score": None, "coverage_pct": round(100 * coverage)}
            continue
        wsum = sum(used.values())
        score = sum(f[k]["score"] * w for k, w in used.items()) / wsum
        spread = float(np.std([f[k]["score"] for k in used]))
        conf_pts = (1 if coverage >= 0.85 else 0) + (1 if spread < 15 else 0)
        h = hist.get(name, {})
        notes: list[str] = []
        if h.get("available") and abs(score - 50) >= 5:
            if abs(h.get("edge_pp", 0)) >= 5 and np.sign(h["edge_pp"]) == np.sign(score - 50):
                conf_pts += 1  # history agrees with the call
            elif h.get("edge_pp", 0) * (score - 50) < 0 and abs(h.get("edge_pp", 0)) >= 3:
                conf_pts -= 1  # history points the other way
                notes.append(f"History disagrees: after similar setups this stock rose {h['pct_positive_similar']}% of the time vs "
                             f"{h['pct_positive_all_days']}% on all days.")
        if days_to_results is not None and 0 <= days_to_results <= cfg["days"] * 1.45:
            notes.append(f"Quarterly results due in {days_to_results} days — a binary event inside this horizon.")
            if cfg["days"] <= 21:
                conf_pts -= 1
        if name == "1 Week":
            conf_pts -= 1  # weekly moves are dominated by noise; never 'High' confidence
        out[name] = {
            "rating": label_for(score), "score": round(score), "confidence": ["Low", "Low", "Medium", "High"][int(np.clip(conf_pts, 0, 3))],
            "coverage_pct": round(100 * coverage),
            "drivers": sorted(({"factor": f[k]["label"], "score": f[k]["score"], "weight": round(w / wsum, 2), "basis": f[k]["basis"]}
                               for k, w in used.items()), key=lambda d: -d["weight"]),
            "historical": h, "notes": notes, "plan": trade_plan(pack, name),
        }
    rated = [(n, v) for n, v in out.items() if v.get("score") is not None]
    buys = [(n, v) for n, v in rated if v["score"] >= 58]
    if buys:
        best = max(buys, key=lambda nv: (nv[1]["score"] + {"High": 6, "Medium": 3, "Low": 0}[nv[1]["confidence"]]))
        suggestion = (f"Best-fit horizon: {best[0]} — {best[1]['rating']} (score {best[1]['score']}, {best[1]['confidence'].lower()} confidence).")
    elif rated:
        worst = min(rated, key=lambda nv: nv[1]["score"])
        suggestion = ("No horizon scores a Buy right now — the model's view is to wait for a better setup."
                      + (f" Weakest: {worst[0]} ({worst[1]['rating']})." if worst[1]["score"] < 45 else ""))
    else:
        best, suggestion = None, "Not enough data to rate this stock."
    return {"horizons": out, "factors": f, "suggestion": suggestion,
            "best_horizon": best[0] if buys else None, "historical_check": {"available": hist.get("available"), "method": hist.get("method")},
            "disclaimer": "Model signal from fundamentals, technicals and news — not personalised investment advice."}
