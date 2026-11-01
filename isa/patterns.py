"""Support/resistance ZONES and breakout-pattern detection on 1H, 4H, 1D and 1W bars.

Everything is rule-based and reproducible; each pattern carries a status, a trigger level,
a measured-move target and an invalidation level so the reader (and the AI) can check it.

Patterns: zone breakout/breakdown (with volume confirmation, retest, failure), consolidation
range breakout, ascending/descending/symmetrical triangles, rising/falling wedges, double
top/bottom, trendline breaks, 52-week/all-time-high breakouts, Bollinger squeeze, NR7/inside bar.
"""
from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from .data import StockData, resample_ohlcv
from .technicals import atr, bollinger, sma

TF_CONFIG = {
    "1H": {"lookback": 350, "w": 3, "recent": 3, "label": "1 Hour"},
    "4H": {"lookback": 250, "w": 3, "recent": 2, "label": "4 Hour"},
    "1D": {"lookback": 260, "w": 5, "recent": 3, "label": "1 Day"},
    "1W": {"lookback": 156, "w": 3, "recent": 2, "label": "1 Week"},
}


# --------------------------------------------------------------------------- swings
def swings(df: pd.DataFrame, w: int) -> tuple[list[int], list[int]]:
    hi, lo = df["High"].to_numpy(), df["Low"].to_numpy()
    highs = [i for i in range(w, len(df) - w) if hi[i] == hi[i - w: i + w + 1].max()]
    lows = [i for i in range(w, len(df) - w) if lo[i] == lo[i - w: i + w + 1].min()]
    return highs, lows


def _atr_last(df: pd.DataFrame) -> float:
    a = atr(df).dropna()
    return float(a.iloc[-1]) if len(a) else float(df["Close"].iloc[-1]) * 0.02


def _ts(df: pd.DataFrame, i: int) -> str:
    return str(df.index[i])[:16]


# --------------------------------------------------------------------------- zones
def zones(df: pd.DataFrame, w: int, max_each: int = 3) -> dict[str, Any]:
    """Cluster swing highs/lows into price ZONES (bands, not lines) and rank by touches, recency and volume."""
    if len(df) < 2 * w + 10:
        return {"supports": [], "resistances": [], "inside": None}
    highs, lows = swings(df, w)
    a = _atr_last(df)
    px = float(df["Close"].iloc[-1])
    vol = df["Volume"].to_numpy()
    vavg = float(np.nanmean(vol)) or 1.0
    pts = sorted([(float(df["High"].iloc[i]), i) for i in highs] + [(float(df["Low"].iloc[i]), i) for i in lows])
    tol = max(0.5 * a, px * 0.004)
    clusters: list[list[tuple[float, int]]] = []
    for p, i in pts:
        if clusters and p - np.mean([q for q, _ in clusters[-1]]) <= tol:
            clusters[-1].append((p, i))
        else:
            clusters.append([(p, i)])
    n = len(df)
    out = []
    for c in clusters:
        prices = [p for p, _ in c]
        idx = [i for _, i in c]
        lo_, hi_ = min(prices) - 0.15 * a, max(prices) + 0.15 * a
        if hi_ - lo_ < 0.3 * a:
            mid = (hi_ + lo_) / 2
            lo_, hi_ = mid - 0.15 * a, mid + 0.15 * a
        recency = 1 - (n - 1 - max(idx)) / n
        vfac = float(np.mean([vol[i] for i in idx]) / vavg) if vavg else 1.0
        strength = len(c) + 2 * recency + 0.5 * min(vfac, 3)
        out.append({
            "low": round(lo_, 2), "high": round(hi_, 2), "mid": round((lo_ + hi_) / 2, 2), "touches": len(c),
            "last_touch": _ts(df, max(idx)), "bars_since_touch": int(n - 1 - max(idx)),
            "distance_pct": round(100 * ((lo_ + hi_) / 2 / px - 1), 2),
            "strength": round(strength, 2),
        })
    inside = next((z for z in out if z["low"] <= px <= z["high"]), None)
    sup = sorted([z for z in out if z["high"] < px], key=lambda z: -z["strength"])[:max_each]
    res = sorted([z for z in out if z["low"] > px], key=lambda z: -z["strength"])[:max_each]
    return {"supports": sorted(sup, key=lambda z: -z["high"]), "resistances": sorted(res, key=lambda z: z["low"]),
            "inside": inside, "atr": round(a, 2)}


# --------------------------------------------------------------------------- pattern helpers
def _vol_ok(df: pd.DataFrame, i: int, mult: float = 1.5) -> bool:
    v = df["Volume"]
    avg = sma(v, 20).iloc[i]
    return bool(pd.notna(avg) and avg > 0 and v.iloc[i] >= mult * avg)


def _fit(idx: list[int], prices: list[float]) -> tuple[float, float]:
    slope, intercept = np.polyfit(idx, prices, 1)
    return float(slope), float(intercept)


def _pattern(name: str, direction: str, status: str, trigger: float | None, target: float | None,
             invalidation: float | None, note: str, **extra: Any) -> dict[str, Any]:
    r = lambda x: None if x is None or not np.isfinite(x) else round(float(x), 2)  # noqa: E731
    return {"pattern": name, "direction": direction, "status": status, "trigger": r(trigger), "target": r(target),
            "invalidation": r(invalidation), "note": note, **extra}


def zone_breaks(df: pd.DataFrame, w: int, recent: int) -> list[dict[str, Any]]:
    """Breakout above a resistance zone / breakdown below a support zone in the last `recent` bars."""
    if len(df) < 60:
        return []
    base = df.iloc[:-recent]
    z = zones(base, w, max_each=4)
    a = _atr_last(df)
    closes = df["Close"].iloc[-recent:]
    last = float(df["Close"].iloc[-1])
    pats = []
    for zr in z["resistances"]:
        crossed = [k for k in range(len(closes)) if closes.iloc[k] > zr["high"]]
        if crossed:
            i = len(df) - recent + crossed[0]
            vol = _vol_ok(df, i)
            failed = last < zr["low"]
            nxt = next((x for x in z["resistances"] if x["low"] > zr["high"]), None)
            target = nxt["low"] if nxt else zr["high"] + 3 * a
            status = "failed breakout (back below zone)" if failed else "breakout confirmed" if vol else "breakout (unconfirmed: weak volume)"
            pats.append(_pattern("Resistance-zone breakout", "bullish", status, zr["high"], target, zr["low"],
                                 f"Closed above ₹{zr['low']:,}–{zr['high']:,} ({zr['touches']} touches)", volume_confirmed=vol,
                                 bar=_ts(df, i)))
            break
    for zs in z["supports"]:
        crossed = [k for k in range(len(closes)) if closes.iloc[k] < zs["low"]]
        if crossed:
            i = len(df) - recent + crossed[0]
            vol = _vol_ok(df, i)
            failed = last > zs["high"]
            nxt = next((x for x in z["supports"] if x["high"] < zs["low"]), None)
            target = nxt["high"] if nxt else zs["low"] - 3 * a
            status = "failed breakdown (back above zone)" if failed else "breakdown confirmed" if vol else "breakdown (unconfirmed: weak volume)"
            pats.append(_pattern("Support-zone breakdown", "bearish", status, zs["low"], target, zs["high"],
                                 f"Closed below ₹{zs['low']:,}–{zs['high']:,} ({zs['touches']} touches)", volume_confirmed=vol,
                                 bar=_ts(df, i)))
            break
    if not pats:  # approaching tests are useful too
        full = zones(df, w, max_each=1)
        if full["resistances"] and (full["resistances"][0]["low"] - last) <= a:
            zr = full["resistances"][0]
            pats.append(_pattern("Testing resistance zone", "neutral", "forming", zr["high"], None, zr["low"] - a,
                                 f"Within 1 ATR of resistance ₹{zr['low']:,}–{zr['high']:,}; a close above ₹{zr['high']:,} with volume would be a breakout"))
        if full["supports"] and (last - full["supports"][0]["high"]) <= a:
            zs = full["supports"][0]
            pats.append(_pattern("Testing support zone", "neutral", "forming", zs["low"], None, zs["high"] + a,
                                 f"Within 1 ATR of support ₹{zs['low']:,}–{zs['high']:,}; a close below ₹{zs['low']:,} would be a breakdown"))
    return pats


def consolidation(df: pd.DataFrame, recent: int, n: int = 20) -> list[dict[str, Any]]:
    if len(df) < n + recent + 20:
        return []
    box = df.iloc[-(n + recent):-recent]
    a = _atr_last(box)
    hi, lo = float(box["High"].max()), float(box["Low"].min())
    width = hi - lo
    if width > 4.5 * a or width / lo > 0.12:
        return []
    last = float(df["Close"].iloc[-1])
    rec = df["Close"].iloc[-recent:]
    if (rec > hi).any():
        i = len(df) - recent + int(np.argmax((rec > hi).to_numpy()))
        return [_pattern("Range breakout", "bullish", "breakout confirmed" if _vol_ok(df, i) else "breakout (unconfirmed: weak volume)",
                         hi, hi + width, lo, f"Broke out of a {n}-bar range ₹{lo:,.0f}–₹{hi:,.0f}", bar=_ts(df, i))]
    if (rec < lo).any():
        i = len(df) - recent + int(np.argmax((rec < lo).to_numpy()))
        return [_pattern("Range breakdown", "bearish", "breakdown confirmed" if _vol_ok(df, i) else "breakdown (unconfirmed: weak volume)",
                         lo, lo - width, hi, f"Broke down from a {n}-bar range ₹{lo:,.0f}–₹{hi:,.0f}", bar=_ts(df, i))]
    if lo <= last <= hi:
        return [_pattern("Consolidation range", "neutral", "forming", hi, hi + width, lo,
                         f"Tight {n}-bar range ₹{lo:,.0f}–₹{hi:,.0f} ({width / a:.1f} ATR wide); watch for a close outside it",
                         range_low=round(lo, 2), range_high=round(hi, 2))]
    return []


def triangles(df: pd.DataFrame, w: int, window: int = 80) -> list[dict[str, Any]]:
    d = df.iloc[-window:]
    if len(d) < 40:
        return []
    highs, lows = swings(d, w)
    highs, lows = highs[-3:], lows[-3:]
    if len(highs) < 2 or len(lows) < 2:
        return []
    a = _atr_last(d)
    sh, ih = _fit(highs, [float(d["High"].iloc[i]) for i in highs])
    sl, il = _fit(lows, [float(d["Low"].iloc[i]) for i in lows])
    n = len(d) - 1
    start = min(highs[0], lows[0])
    flat = 0.6 * a / 20  # less than ~0.6 ATR drift over 20 bars counts as flat
    up_h, dn_h, flat_h = sh > flat, sh < -flat, abs(sh) <= flat
    up_l, dn_l, flat_l = sl > flat, sl < -flat, abs(sl) <= flat
    upper_now, lower_now = sh * n + ih, sl * n + il
    upper_start, lower_start = sh * start + ih, sl * start + il
    height = upper_start - lower_start
    converging = (upper_now - lower_now) < 0.75 * height
    if height <= 0 or upper_now <= lower_now:
        return []
    name, bias = None, "neutral"
    if flat_h and up_l:
        name, bias = "Ascending triangle", "bullish"
    elif dn_h and flat_l:
        name, bias = "Descending triangle", "bearish"
    elif dn_h and up_l:
        name, bias = "Symmetrical triangle", "neutral"
    elif up_h and up_l and converging:
        name, bias = "Rising wedge", "bearish"
    elif dn_h and dn_l and converging:
        name, bias = "Falling wedge", "bullish"
    elif up_h and up_l:
        name, bias = "Rising channel", "bullish"
    elif dn_h and dn_l:
        name, bias = "Falling channel", "bearish"
    if not name:
        return []
    last = float(d["Close"].iloc[-1])
    lines = [{"x0": _ts(d, start), "y0": round(upper_start, 2), "x1": _ts(d, n), "y1": round(upper_now, 2), "label": "upper"},
             {"x0": _ts(d, start), "y0": round(lower_start, 2), "x1": _ts(d, n), "y1": round(lower_now, 2), "label": "lower"}]
    if last > upper_now + 0.2 * a:
        status, direction, trig, tgt, inv = "breakout confirmed" if _vol_ok(d, n) else "breakout (unconfirmed: weak volume)", "bullish", upper_now, upper_now + height, lower_now
    elif last < lower_now - 0.2 * a:
        status, direction, trig, tgt, inv = "breakdown confirmed" if _vol_ok(d, n) else "breakdown (unconfirmed: weak volume)", "bearish", lower_now, lower_now - height, upper_now
    else:
        status, direction = "forming", bias
        trig, tgt, inv = (upper_now, upper_now + height, lower_now) if bias != "bearish" else (lower_now, lower_now - height, upper_now)
    return [_pattern(name, direction, status, trig, tgt, inv,
                     f"Upper line ₹{upper_now:,.0f}, lower line ₹{lower_now:,.0f} now; pattern height ₹{height:,.0f}", lines=lines)]


def double_top_bottom(df: pd.DataFrame, w: int, window: int = 120) -> list[dict[str, Any]]:
    d = df.iloc[-window:]
    if len(d) < 40:
        return []
    highs, lows = swings(d, w)
    a = _atr_last(d)
    last = float(d["Close"].iloc[-1])
    out = []
    if len(lows) >= 2:
        i1, i2 = lows[-2], lows[-1]
        l1, l2 = float(d["Low"].iloc[i1]), float(d["Low"].iloc[i2])
        mids = [h for h in highs if i1 < h < i2]
        if mids and i2 - i1 >= 8 and abs(l1 - l2) <= max(1.0 * a, 0.02 * l1) and len(d) - 1 - i2 <= 40:
            neck = float(max(d["High"].iloc[h] for h in mids))
            if neck - max(l1, l2) >= 2 * a:
                status = "breakout confirmed" if last > neck else "forming (needs close above neckline)"
                out.append(_pattern("Double bottom", "bullish", status, neck, neck + (neck - min(l1, l2)), min(l1, l2) - 0.2 * a,
                                    f"Lows ₹{l1:,.0f} and ₹{l2:,.0f}, neckline ₹{neck:,.0f}"))
    if len(highs) >= 2:
        i1, i2 = highs[-2], highs[-1]
        h1, h2 = float(d["High"].iloc[i1]), float(d["High"].iloc[i2])
        mids = [lo for lo in lows if i1 < lo < i2]
        if mids and i2 - i1 >= 8 and abs(h1 - h2) <= max(1.0 * a, 0.02 * h1) and len(d) - 1 - i2 <= 40:
            neck = float(min(d["Low"].iloc[lo] for lo in mids))
            if min(h1, h2) - neck >= 2 * a:
                status = "breakdown confirmed" if last < neck else "forming (needs close below neckline)"
                out.append(_pattern("Double top", "bearish", status, neck, neck - (max(h1, h2) - neck), max(h1, h2) + 0.2 * a,
                                    f"Highs ₹{h1:,.0f} and ₹{h2:,.0f}, neckline ₹{neck:,.0f}"))
    return out


def trendline_break(df: pd.DataFrame, w: int, window: int = 120) -> list[dict[str, Any]]:
    d = df.iloc[-window:]
    if len(d) < 40:
        return []
    highs, lows = swings(d, w)
    a = _atr_last(d)
    n = len(d) - 1
    last = float(d["Close"].iloc[-1])
    out = []
    if len(highs) >= 2:
        i1, i2 = highs[-2], highs[-1]
        h1, h2 = float(d["High"].iloc[i1]), float(d["High"].iloc[i2])
        if h2 < h1 - 0.5 * a:  # lower highs -> falling resistance line
            slope = (h2 - h1) / (i2 - i1)
            line_now = h2 + slope * (n - i2)
            if last > line_now + 0.2 * a:
                out.append(_pattern("Falling trendline breakout", "bullish", "breakout confirmed" if _vol_ok(d, n) else "breakout (unconfirmed: weak volume)",
                                    line_now, h1, min(float(d["Low"].iloc[-5:].min()), line_now - 0.3 * a), f"Closed above the line joining lower highs ₹{h1:,.0f} → ₹{h2:,.0f}",
                                    lines=[{"x0": _ts(d, i1), "y0": round(h1, 2), "x1": _ts(d, n), "y1": round(line_now, 2), "label": "trendline"}]))
    if len(lows) >= 2:
        i1, i2 = lows[-2], lows[-1]
        l1, l2 = float(d["Low"].iloc[i1]), float(d["Low"].iloc[i2])
        if l2 > l1 + 0.5 * a:  # higher lows -> rising support line
            slope = (l2 - l1) / (i2 - i1)
            line_now = l2 + slope * (n - i2)
            if last < line_now - 0.2 * a:
                out.append(_pattern("Rising trendline breakdown", "bearish", "breakdown confirmed" if _vol_ok(d, n) else "breakdown (unconfirmed: weak volume)",
                                    line_now, l1, max(float(d["High"].iloc[-5:].max()), line_now + 0.3 * a), f"Closed below the line joining higher lows ₹{l1:,.0f} → ₹{l2:,.0f}",
                                    lines=[{"x0": _ts(d, i1), "y0": round(l1, 2), "x1": _ts(d, n), "y1": round(line_now, 2), "label": "trendline"}]))
    return out


def high_low_breakouts(df: pd.DataFrame, tf: str, recent: int) -> list[dict[str, Any]]:
    bars = {"1D": 252, "1W": 52}.get(tf)
    if not bars or len(df) < bars + recent:
        return []
    prior = df.iloc[:-recent]
    hi52, lo52 = float(prior["High"].iloc[-bars:].max()), float(prior["Low"].iloc[-bars:].min())
    ath = float(prior["High"].max())
    last = float(df["Close"].iloc[-1])
    a = _atr_last(df)
    out = []
    if last > ath:
        out.append(_pattern("All-time-high breakout", "bullish", "breakout confirmed" if _vol_ok(df, len(df) - 1, 1.2) else "breakout (unconfirmed: weak volume)",
                            ath, None, ath - a, f"Closed above the prior all-time high ₹{ath:,.0f} — no overhead supply"))
    elif last > hi52:
        out.append(_pattern("52-week-high breakout", "bullish", "breakout confirmed" if _vol_ok(df, len(df) - 1, 1.2) else "breakout (unconfirmed: weak volume)",
                            hi52, None, hi52 - a, f"Closed above the prior 52-week high ₹{hi52:,.0f}"))
    elif last < lo52:
        out.append(_pattern("52-week-low breakdown", "bearish", "breakdown confirmed", lo52, None, lo52 + a,
                            f"Closed below the prior 52-week low ₹{lo52:,.0f}"))
    return out


def squeeze(df: pd.DataFrame) -> list[dict[str, Any]]:
    if len(df) < 140:
        return []
    bb = bollinger(df["Close"])
    bw = ((bb["BB_up"] - bb["BB_low"]) / bb["BB_mid"]).dropna()
    if len(bw) < 120:
        return []
    pct = float((bw.iloc[-120:] < bw.iloc[-1]).mean())
    last = float(df["Close"].iloc[-1])
    if pct <= 0.10:
        return [_pattern("Volatility squeeze", "neutral", "forming", float(bb["BB_up"].iloc[-1]), None, float(bb["BB_low"].iloc[-1]),
                         "Bollinger bandwidth near its 120-bar low — a sharp move is likely; direction is unknown until price closes outside a band")]
    was_tight = (bw.iloc[-6:-1] <= bw.iloc[-120:].quantile(0.15)).any()
    if was_tight and last > bb["BB_up"].iloc[-1]:
        return [_pattern("Squeeze breakout", "bullish", "breakout confirmed" if _vol_ok(df, len(df) - 1) else "breakout (unconfirmed: weak volume)",
                         float(bb["BB_up"].iloc[-1]), None, float(bb["BB_mid"].iloc[-1]), "Price closed above the upper band right after a squeeze")]
    if was_tight and last < bb["BB_low"].iloc[-1]:
        return [_pattern("Squeeze breakdown", "bearish", "breakdown confirmed", float(bb["BB_low"].iloc[-1]), None, float(bb["BB_mid"].iloc[-1]),
                         "Price closed below the lower band right after a squeeze")]
    return []


def small_bars(df: pd.DataFrame) -> list[dict[str, Any]]:
    if len(df) < 8:
        return []
    rng = (df["High"] - df["Low"]).iloc[-7:]
    out = []
    h, l = df["High"].to_numpy(), df["Low"].to_numpy()
    if rng.iloc[-1] == rng.min():
        out.append(_pattern("NR7 (narrowest range of 7 bars)", "neutral", "forming", float(h[-1]), None, float(l[-1]),
                            "Compression bar — a move beyond its high/low often starts a short swing"))
    elif h[-1] < h[-2] and l[-1] > l[-2]:
        out.append(_pattern("Inside bar", "neutral", "forming", float(h[-2]), None, float(l[-2]),
                            "Bar inside the previous bar's range — break of the mother bar's high/low sets direction"))
    return out


# --------------------------------------------------------------------------- per-timeframe bundle
def merge_closing_stub(df: pd.DataFrame) -> pd.DataFrame:
    """Yahoo's last NSE hourly bar (15:15-15:30) covers only 15 minutes; fold it into the 14:15 bar
    so it doesn't masquerade as a 'narrow range' bar or distort ATR."""
    if df is None or df.empty:
        return df
    key = df.index.where(~((df.index.hour == 15) & (df.index.minute >= 15)), df.index - pd.Timedelta(hours=1))
    agg = {"Open": "first", "High": "max", "Low": "min", "Close": "last", "Volume": "sum"}
    return df.groupby(key).agg(agg)


def frames(sd: StockData) -> dict[str, pd.DataFrame]:
    out: dict[str, pd.DataFrame] = {}
    if sd.intraday is not None and len(sd.intraday) > 60:
        hourly = merge_closing_stub(sd.intraday)
        out["1H"] = hourly
        out["4H"] = resample_ohlcv(hourly, "4h")
    out["1D"] = sd.daily
    out["1W"] = resample_ohlcv(sd.daily, "W-FRI")
    return out


def analyse_timeframe(df: pd.DataFrame, tf: str) -> dict[str, Any]:
    cfg = TF_CONFIG[tf]
    d = df.iloc[-cfg["lookback"]:]
    if len(d) < 40:
        return {"timeframe": cfg["label"], "available": False, "reason": f"only {len(d)} bars"}
    w, rec = cfg["w"], cfg["recent"]
    pats = (zone_breaks(d, w, rec) + consolidation(d, rec) + triangles(d, w) + double_top_bottom(d, w)
            + trendline_break(d, w) + high_low_breakouts(df, tf, rec) + squeeze(d) + small_bars(d))
    names = {p["pattern"]: p for p in pats}
    if "Double bottom" in names and "Double top" in names:
        bottom_ok = names["Double bottom"]["status"].startswith("breakout")
        top_ok = names["Double top"]["status"].startswith("breakdown")
        drop = "Double top" if bottom_ok and not top_ok else "Double bottom" if top_ok and not bottom_ok else None
        pats = [p for p in pats if p["pattern"] != drop]
    # de-duplicate: keep the first of each pattern name
    seen, uniq = set(), []
    for p in pats:
        if p["pattern"] not in seen:
            uniq.append(p)
            seen.add(p["pattern"])
    confirmed = [p for p in uniq if "confirmed" in p["status"]]
    bull = sum(1 for p in confirmed if p["direction"] == "bullish") + 0.5 * sum(1 for p in uniq if p["direction"] == "bullish" and p not in confirmed)
    bear = sum(1 for p in confirmed if p["direction"] == "bearish") + 0.5 * sum(1 for p in uniq if p["direction"] == "bearish" and p not in confirmed)
    bias = "bullish" if bull > bear else "bearish" if bear > bull else "neutral"
    z = zones(d, w)
    return {
        "timeframe": cfg["label"], "available": True, "bars": int(len(d)), "last_bar": _ts(d, len(d) - 1),
        "close": round(float(d["Close"].iloc[-1]), 2), "atr": z.get("atr"),
        "zones": z, "patterns": uniq, "breakout_bias": bias,
    }


def breakout_scan(sd: StockData) -> dict[str, Any]:
    fr = frames(sd)
    out = {tf: analyse_timeframe(fr[tf], tf) for tf in ("1H", "4H", "1D", "1W") if tf in fr}
    for tf in ("1H", "4H"):
        out.setdefault(tf, {"timeframe": TF_CONFIG[tf]["label"], "available": False, "reason": "no intraday data"})
    return out
