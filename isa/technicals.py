"""Technical analysis computed in plain pandas/numpy (no TA-Lib needed).

Everything here is deterministic; the AI layer receives these numbers and explains them.
"""
from __future__ import annotations

import math
from typing import Any

import numpy as np
import pandas as pd

from .data import StockData, resample_ohlcv


# =========================================================================== indicators
def ema(s: pd.Series, n: int) -> pd.Series:
    return s.ewm(span=n, adjust=False, min_periods=n).mean()


def sma(s: pd.Series, n: int) -> pd.Series:
    return s.rolling(n, min_periods=n).mean()


def rsi(close: pd.Series, n: int = 14) -> pd.Series:
    d = close.diff()
    up = d.clip(lower=0).ewm(alpha=1 / n, adjust=False, min_periods=n).mean()
    dn = (-d.clip(upper=0)).ewm(alpha=1 / n, adjust=False, min_periods=n).mean()
    rs = up / dn.replace(0, np.nan)
    out = 100 - 100 / (1 + rs)
    return out.where(dn != 0, 100.0)


def macd(close: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9) -> pd.DataFrame:
    line = ema(close, fast) - ema(close, slow)
    sig = line.ewm(span=signal, adjust=False, min_periods=signal).mean()
    return pd.DataFrame({"MACD": line, "MACD_signal": sig, "MACD_hist": line - sig})


def true_range(df: pd.DataFrame) -> pd.Series:
    pc = df["Close"].shift()
    return pd.concat([df["High"] - df["Low"], (df["High"] - pc).abs(), (df["Low"] - pc).abs()], axis=1).max(axis=1)


def atr(df: pd.DataFrame, n: int = 14) -> pd.Series:
    return true_range(df).ewm(alpha=1 / n, adjust=False, min_periods=n).mean()


def adx(df: pd.DataFrame, n: int = 14) -> pd.DataFrame:
    up = df["High"].diff()
    dn = -df["Low"].diff()
    plus_dm = np.where((up > dn) & (up > 0), up, 0.0)
    minus_dm = np.where((dn > up) & (dn > 0), dn, 0.0)
    tr = true_range(df).ewm(alpha=1 / n, adjust=False, min_periods=n).mean()
    pdi = 100 * pd.Series(plus_dm, index=df.index).ewm(alpha=1 / n, adjust=False, min_periods=n).mean() / tr
    mdi = 100 * pd.Series(minus_dm, index=df.index).ewm(alpha=1 / n, adjust=False, min_periods=n).mean() / tr
    dx = 100 * (pdi - mdi).abs() / (pdi + mdi).replace(0, np.nan)
    return pd.DataFrame({"ADX": dx.ewm(alpha=1 / n, adjust=False, min_periods=n).mean(), "+DI": pdi, "-DI": mdi})


def bollinger(close: pd.Series, n: int = 20, k: float = 2.0) -> pd.DataFrame:
    mid = sma(close, n)
    sd = close.rolling(n, min_periods=n).std()
    return pd.DataFrame({"BB_mid": mid, "BB_up": mid + k * sd, "BB_low": mid - k * sd})


def supertrend(df: pd.DataFrame, n: int = 10, mult: float = 3.0) -> pd.DataFrame:
    a = atr(df, n)
    hl2 = (df["High"] + df["Low"]) / 2
    upper, lower = (hl2 + mult * a).to_numpy(), (hl2 - mult * a).to_numpy()
    close = df["Close"].to_numpy()
    st = np.full(len(df), np.nan)
    direction = np.zeros(len(df))
    fu, fl = upper.copy(), lower.copy()
    for i in range(1, len(df)):
        if np.isnan(upper[i]) or np.isnan(fu[i - 1]):
            continue
        fu[i] = upper[i] if (upper[i] < fu[i - 1] or close[i - 1] > fu[i - 1]) else fu[i - 1]
        fl[i] = lower[i] if (lower[i] > fl[i - 1] or close[i - 1] < fl[i - 1]) else fl[i - 1]
        if direction[i - 1] == 0:
            direction[i] = 1 if close[i] >= fl[i] else -1
        elif direction[i - 1] == 1:
            direction[i] = -1 if close[i] < fl[i] else 1
        else:
            direction[i] = 1 if close[i] > fu[i] else -1
        st[i] = fl[i] if direction[i] == 1 else fu[i]
    return pd.DataFrame({"Supertrend": st, "ST_dir": direction}, index=df.index)


def stochastic(df: pd.DataFrame, n: int = 14, d: int = 3) -> pd.DataFrame:
    ll, hh = df["Low"].rolling(n).min(), df["High"].rolling(n).max()
    k = 100 * (df["Close"] - ll) / (hh - ll).replace(0, np.nan)
    return pd.DataFrame({"%K": k, "%D": k.rolling(d).mean()})


def obv(df: pd.DataFrame) -> pd.Series:
    return (np.sign(df["Close"].diff()).fillna(0) * df["Volume"]).cumsum()


def add_indicators(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    c = out["Close"]
    for n in (20, 50, 100, 200):
        out[f"EMA{n}"] = ema(c, n)
    out["SMA50"], out["SMA200"] = sma(c, 50), sma(c, 200)
    out["RSI"] = rsi(c)
    out = out.join(macd(c)).join(bollinger(c)).join(adx(out)).join(supertrend(out)).join(stochastic(out))
    out["ATR"] = atr(out)
    out["OBV"] = obv(out)
    out["VolSMA20"] = sma(out["Volume"], 20)
    return out


# =========================================================================== trend scoring
def _last(s: pd.Series) -> float:
    s = s.dropna()
    return float(s.iloc[-1]) if len(s) else float("nan")


def trend_assessment(df: pd.DataFrame, label: str) -> dict[str, Any]:
    """Score trend from -100 (strong down) to +100 (strong up) with transparent components."""
    if df is None or len(df) < 30:
        return {"timeframe": label, "available": False, "reason": "not enough bars"}
    x = add_indicators(df)
    close = float(x["Close"].iloc[-1])
    comp: dict[str, int] = {}

    def vote(name: str, cond: bool | None, w: int) -> None:
        if cond is None:
            return
        comp[name] = w if cond else -w

    e20, e50, e200 = _last(x["EMA20"]), _last(x["EMA50"]), _last(x["EMA200"])
    vote("Price > EMA20", close > e20 if not math.isnan(e20) else None, 10)
    vote("Price > EMA50", close > e50 if not math.isnan(e50) else None, 15)
    vote("Price > EMA200", close > e200 if not math.isnan(e200) else None, 20)
    vote("EMA20 > EMA50", e20 > e50 if not (math.isnan(e20) or math.isnan(e50)) else None, 10)
    vote("EMA50 > EMA200", e50 > e200 if not (math.isnan(e50) or math.isnan(e200)) else None, 10)
    e50s = x["EMA50"].dropna()
    vote("EMA50 rising", bool(e50s.iloc[-1] > e50s.iloc[-11]) if len(e50s) > 11 else None, 10)
    vote("MACD histogram > 0", _last(x["MACD_hist"]) > 0 if not math.isnan(_last(x["MACD_hist"])) else None, 10)
    st_dir = _last(x["ST_dir"])
    vote("Supertrend bullish", st_dir > 0 if st_dir != 0 and not math.isnan(st_dir) else None, 15)

    max_pts = sum(abs(v) for v in comp.values()) or 1
    score = round(100 * sum(comp.values()) / max_pts)
    adx_v, rsi_v = _last(x["ADX"]), _last(x["RSI"])
    if score >= 60:
        trend = "Strong uptrend"
    elif score >= 25:
        trend = "Uptrend"
    elif score > -25:
        trend = "Sideways"
    elif score > -60:
        trend = "Downtrend"
    else:
        trend = "Strong downtrend"
    strength = "strong" if adx_v >= 25 else "weak / range-bound" if adx_v < 20 else "developing"
    rsi_zone = "overbought" if rsi_v >= 70 else "oversold" if rsi_v <= 30 else "bullish zone" if rsi_v >= 55 else "bearish zone" if rsi_v <= 45 else "neutral"
    return {
        "timeframe": label,
        "available": True,
        "bars": int(len(df)),
        "last_bar": str(df.index[-1].date()) if hasattr(df.index[-1], "date") else str(df.index[-1]),
        "close": round(close, 2),
        "score": score,
        "trend": trend,
        "adx": round(adx_v, 1),
        "trend_strength": strength,
        "rsi": round(rsi_v, 1),
        "rsi_zone": rsi_zone,
        "macd_hist": round(_last(x["MACD_hist"]), 3),
        "ema20": round(e20, 2), "ema50": round(e50, 2), "ema200": None if math.isnan(e200) else round(e200, 2),
        "supertrend": round(_last(x["Supertrend"]), 2),
        "components": comp,
    }


def multi_timeframe(sd: StockData) -> list[dict[str, Any]]:
    d = sd.daily
    frames: list[tuple[str, pd.DataFrame | None]] = []
    if sd.intraday is not None and len(sd.intraday) > 30:
        frames += [("1 Hour", sd.intraday), ("4 Hour", resample_ohlcv(sd.intraday, "4h"))]
    frames += [
        ("Daily", d.iloc[-750:]),
        ("Weekly", resample_ohlcv(d, "W-FRI").iloc[-520:]),
        ("Monthly", resample_ohlcv(d, "ME").iloc[-240:]),
    ]
    return [trend_assessment(f, lbl) for lbl, f in frames]


# =========================================================================== levels
def support_resistance(df: pd.DataFrame, lookback: int = 250, window: int = 5, max_levels: int = 3) -> dict[str, Any]:
    d = df.iloc[-lookback:]
    if len(d) < 2 * window + 5:
        return {"supports": [], "resistances": []}
    hi, lo = d["High"].to_numpy(), d["Low"].to_numpy()
    pivots: list[tuple[float, int]] = []
    for i in range(window, len(d) - window):
        if hi[i] == hi[i - window : i + window + 1].max():
            pivots.append((hi[i], i))
        if lo[i] == lo[i - window : i + window + 1].min():
            pivots.append((lo[i], i))
    a = _last(atr(d)) or float(d["Close"].iloc[-1]) * 0.02
    tol = max(0.6 * a, float(d["Close"].iloc[-1]) * 0.006)
    clusters: list[dict[str, Any]] = []
    for price, idx in sorted(pivots):
        if clusters and abs(price - clusters[-1]["level"]) <= tol:
            c = clusters[-1]
            c["prices"].append(price)
            c["idx"].append(idx)
            c["level"] = float(np.mean(c["prices"]))
        else:
            clusters.append({"level": price, "prices": [price], "idx": [idx]})
    close = float(d["Close"].iloc[-1])
    n = len(d)
    levels = [
        {
            "level": round(c["level"], 2),
            "touches": len(c["prices"]),
            "last_touch_bars_ago": int(n - 1 - max(c["idx"])),
            "distance_pct": round(100 * (c["level"] / close - 1), 2),
            "strength": len(c["prices"]) + 2 * (1 - (n - 1 - max(c["idx"])) / n),
        }
        for c in clusters
    ]
    sup = sorted([l for l in levels if l["level"] < close], key=lambda l: (-l["strength"], -l["level"]))[:max_levels]
    res = sorted([l for l in levels if l["level"] > close], key=lambda l: (-l["strength"], l["level"]))[:max_levels]
    for l in sup + res:
        l.pop("strength", None)
    return {"supports": sorted(sup, key=lambda l: -l["level"]), "resistances": sorted(res, key=lambda l: l["level"])}


def fibonacci(df: pd.DataFrame, lookback: int = 250) -> dict[str, Any]:
    d = df.iloc[-lookback:]
    hi_i, lo_i = d["High"].idxmax(), d["Low"].idxmin()
    hi, lo = float(d["High"].max()), float(d["Low"].min())
    up_move = lo_i < hi_i  # swing low came first -> retracements measured down from high
    rng = hi - lo
    ratios = [0.236, 0.382, 0.5, 0.618, 0.786]
    levels = {f"{r:.1%}": round(hi - r * rng if up_move else lo + r * rng, 2) for r in ratios}
    return {"swing_high": round(hi, 2), "swing_low": round(lo, 2), "direction": "up-swing" if up_move else "down-swing", "levels": levels}


# =========================================================================== events & patterns
def candlestick_patterns(df: pd.DataFrame) -> list[str]:
    if len(df) < 3:
        return []
    o, h, l, c = (df[k].to_numpy()[-3:] for k in ("Open", "High", "Low", "Close"))
    out: list[str] = []
    body = abs(c[-1] - o[-1])
    rng = h[-1] - l[-1] or 1e-9
    upper, lower = h[-1] - max(c[-1], o[-1]), min(c[-1], o[-1]) - l[-1]
    if body / rng < 0.1:
        out.append("Doji (indecision)")
    if lower > 2 * body and upper < body and body / rng > 0.1:
        out.append("Hammer / hanging-man shape (long lower wick)")
    if upper > 2 * body and lower < body and body / rng > 0.1:
        out.append("Shooting-star / inverted-hammer shape (long upper wick)")
    if c[-2] < o[-2] and c[-1] > o[-1] and c[-1] >= o[-2] and o[-1] <= c[-2]:
        out.append("Bullish engulfing")
    if c[-2] > o[-2] and c[-1] < o[-1] and c[-1] <= o[-2] and o[-1] >= c[-2]:
        out.append("Bearish engulfing")
    return out


def recent_events(df: pd.DataFrame, lookback: int = 120) -> list[dict[str, str]]:
    x = add_indicators(df)
    ev: list[dict[str, str]] = []
    tail = x.iloc[-lookback:]
    cross = np.sign(tail["SMA50"] - tail["SMA200"]).diff()
    for dt, v in cross[cross != 0].dropna().items():
        ev.append({"date": str(dt.date()), "event": "Golden cross (50DMA > 200DMA)" if v > 0 else "Death cross (50DMA < 200DMA)"})
    hh = x["High"].rolling(252, min_periods=200).max().shift()
    ll = x["Low"].rolling(252, min_periods=200).min().shift()
    ups = tail.index[(tail["Close"] > hh.loc[tail.index])]
    downs = tail.index[(tail["Close"] < ll.loc[tail.index])]
    if len(ups):
        ev.append({"date": str(ups[-1].date()), "event": f"Close above prior 52-week high (breakout; {len(ups)} such closes in last {lookback} bars)"})
    if len(downs):
        ev.append({"date": str(downs[-1].date()), "event": f"Close below prior 52-week low (breakdown; {len(downs)} such closes in last {lookback} bars)"})
    spikes = tail[(tail["Volume"] > 2.5 * tail["VolSMA20"])]
    for dt, row in spikes.iloc[-3:].iterrows():
        chg = row["Close"] / x["Close"].shift().loc[dt] - 1
        ev.append({"date": str(dt.date()), "event": f"Volume spike {row['Volume'] / row['VolSMA20']:.1f}x avg, price {chg:+.1%}"})
    # simple RSI divergence over the last ~60 bars
    w = x.iloc[-60:]
    if len(w) == 60:
        a, b = w.iloc[:30], w.iloc[30:]
        if b["Close"].max() > a["Close"].max() and b["RSI"].max() < a["RSI"].max() - 3:
            ev.append({"date": str(w.index[-1].date()), "event": "Bearish RSI divergence (higher price high, lower RSI high)"})
        if b["Close"].min() < a["Close"].min() and b["RSI"].min() > a["RSI"].min() + 3:
            ev.append({"date": str(w.index[-1].date()), "event": "Bullish RSI divergence (lower price low, higher RSI low)"})
    return sorted(ev, key=lambda e: e["date"], reverse=True)[:12]


def regression_channel(df: pd.DataFrame, lookback: int = 120) -> dict[str, Any]:
    y = np.log(df["Close"].iloc[-lookback:].to_numpy())
    t = np.arange(len(y))
    slope, intercept = np.polyfit(t, y, 1)
    resid = y - (slope * t + intercept)
    sd = resid.std()
    return {
        "lookback_bars": lookback,
        "annualised_slope_pct": round((math.exp(slope * 252) - 1) * 100, 1),
        "r_squared": round(1 - resid.var() / y.var(), 2) if y.var() > 0 else 0.0,
        "position_in_channel_sd": round(resid[-1] / sd, 2) if sd > 0 else 0.0,
        "upper": round(float(np.exp(slope * t[-1] + intercept + 2 * sd)), 2),
        "mid": round(float(np.exp(slope * t[-1] + intercept)), 2),
        "lower": round(float(np.exp(slope * t[-1] + intercept - 2 * sd)), 2),
    }


# =========================================================================== performance & risk
def performance(sd: StockData) -> dict[str, Any]:
    c = sd.daily["Close"]
    last = float(c.iloc[-1])

    def ret(days: int) -> float | None:
        if len(c) <= days:
            return None
        return round(100 * (last / float(c.iloc[-days - 1]) - 1), 2)

    def cagr(years: int) -> float | None:
        days = 252 * years
        if len(c) <= days:
            return None
        return round(100 * ((last / float(c.iloc[-days - 1])) ** (1 / years) - 1), 2)

    r = c.pct_change().dropna()
    peak = c.cummax()
    dd = c / peak - 1
    year = c.iloc[-252:]
    out: dict[str, Any] = {
        "last_close": round(last, 2),
        "as_of": str(c.index[-1].date()),
        "returns_pct": {"1D": ret(1), "1W": ret(5), "1M": ret(21), "3M": ret(63), "6M": ret(126), "1Y": ret(252)},
        "cagr_pct": {"3Y": cagr(3), "5Y": cagr(5), "10Y": cagr(10)},
        "volatility_annual_pct": round(float(r.iloc[-252:].std() * math.sqrt(252) * 100), 1),
        "max_drawdown_5y_pct": round(float(dd.iloc[-1260:].min() * 100), 1),
        "drawdown_from_ath_pct": round(float(dd.iloc[-1] * 100), 1),
        "high_52w": round(float(sd.daily["High"].iloc[-252:].max()), 2),
        "low_52w": round(float(sd.daily["Low"].iloc[-252:].min()), 2),
        "pct_from_52w_high": round(100 * (last / float(sd.daily["High"].iloc[-252:].max()) - 1), 1),
        "avg_traded_value_20d_cr": round(float((sd.daily["Close"] * sd.daily["Volume"]).iloc[-20:].mean() / 1e7), 2),
        "positive_days_1y_pct": round(float((year.pct_change() > 0).mean() * 100), 1),
    }
    if sd.benchmark is not None and len(sd.benchmark) > 260:
        b = sd.benchmark.reindex(c.index).ffill()
        rb = b.pct_change()
        joined = pd.concat([r, rb], axis=1, join="inner").dropna().iloc[-504:]
        if len(joined) > 100:
            cov = np.cov(joined.iloc[:, 0], joined.iloc[:, 1])
            out["beta_vs_nifty_2y"] = round(float(cov[0, 1] / cov[1, 1]), 2)
            out["correlation_vs_nifty_2y"] = round(float(joined.corr().iloc[0, 1]), 2)
        for lbl, days in (("3M", 63), ("6M", 126), ("1Y", 252)):
            if len(b.dropna()) > days:
                bret = float(b.iloc[-1] / b.iloc[-days - 1] - 1) * 100
                sret = out["returns_pct"].get(lbl)
                if sret is not None:
                    out.setdefault("relative_strength_vs_nifty_pct", {})[lbl] = round(sret - bret, 2)
    return out


# =========================================================================== bundle
def technical_summary(sd: StockData) -> dict[str, Any]:
    d = sd.daily
    tfs = multi_timeframe(sd)
    weights = {"1 Hour": 0.5, "4 Hour": 0.75, "Daily": 1.5, "Weekly": 1.5, "Monthly": 1.0}
    avail = [t for t in tfs if t.get("available")]
    wsum = sum(weights[t["timeframe"]] for t in avail) or 1
    composite = sum(t["score"] * weights[t["timeframe"]] for t in avail) / wsum
    daily = next((t for t in tfs if t["timeframe"] == "Daily"), {})
    atr_v = _last(atr(d))
    return {
        "composite_trend_score": round(composite),
        "timeframes": tfs,
        "support_resistance": support_resistance(d),
        "fibonacci_1y": fibonacci(d),
        "regression_channel_6m": regression_channel(d, 120),
        "candlestick_last_bar": candlestick_patterns(d),
        "recent_events": recent_events(d),
        "atr14": round(atr_v, 2),
        "atr_pct": round(100 * atr_v / float(d["Close"].iloc[-1]), 2),
        "daily_rsi": daily.get("rsi"),
        "performance": performance(sd),
    }
