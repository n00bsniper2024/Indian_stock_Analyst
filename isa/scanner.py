"""Breakout scanner: stocks pressing against their 20-day high, plus an honest test of how often that led to a breakout.

Default rules come from a study on ~700 NSE stocks (2019-2026): rules were chosen on 2019-2023 and checked on
2024-2026. On the unseen years, the default rules broke out within 10 days ~70% of the time (vs ~42% for any liquid
stock near its high) and gave a clean breakout ~33% of the time (vs ~17%). Two out of three picks still fail or
stall. The backtest here lets anyone re-check those numbers on fresh data instead of trusting them.

Definitions (used everywhere in this module):
  pivot            highest high of the last 20 sessions, including today
  breakout         a daily close above the pivot within the next 10 sessions
  clean breakout   after that close, price trades 10% above the pivot within 30 sessions before any close 3% below it
"""
from __future__ import annotations

import hashlib
from dataclasses import asdict, dataclass, replace
from typing import Any, Callable

import numpy as np
import pandas as pd

from .config import DATA_DIR, DEMO_MODE
from .data import _cached, _yf_batch_prices

BREAKOUT_WINDOW = 10
CLEAN_WINDOW = 30
CLEAN_UP = 0.10
CLEAN_FAIL = 0.03


@dataclass(frozen=True)
class Rules:
    near_pivot_pct: float = 2.0      # close within this % below the 20-day high
    not_broken_yet: bool = True      # close has not already gone above yesterday's 20-day high
    trend_template: bool = True      # close > 50 SMA > 150 SMA > 200 SMA, 200 SMA rising over 20 sessions
    near_52w_pct: float = 10.0       # close within this % of the 52-week high (0 = off)
    min_6m_return_pct: float = 40.0  # close vs 126 sessions ago (None/0 = off)
    min_10d_swing_pct: float = 12.0  # (10-day high - 10-day low) / close; active stocks break out more often
    max_10d_swing_pct: float = 0.0   # 0 = off. Set e.g. 6 for the textbook "tight base"
    volume_drying_up: bool = False   # 10-day avg volume < 50-day avg volume (textbook; tested as a negative)
    min_price: float = 100.0
    min_traded_cr: float = 5.0       # 20-day average daily traded value, ₹ crore


PRESETS: dict[str, Rules] = {
    "Tested default (strong stock pressing on its high)": Rules(),
    "Looser: more stocks, lower hit rate": Rules(near_pivot_pct=4, near_52w_pct=15, min_6m_return_pct=20, min_10d_swing_pct=8),
    "Textbook tight base / VCP (for comparison)": Rules(near_pivot_pct=5, near_52w_pct=25, min_6m_return_pct=0,
                                                        min_10d_swing_pct=0, max_10d_swing_pct=6, volume_drying_up=True),
}


# --------------------------------------------------------------------------- data
def universe() -> pd.DataFrame:
    """Nifty Total Market stocks with sector / industry / cap bucket (bundled, ~750)."""
    return pd.read_csv(DATA_DIR / "classification.csv")


def load_history(symbols: list[str], years: int = 3, progress: Callable[[float, str], None] | None = None) -> dict[str, pd.DataFrame]:
    """Daily OHLCV for many stocks. Long history is cached for a day; the last 5 sessions are refreshed every 15 min
    so the scan sees today's candle."""
    syms = tuple(sorted(set(symbols)))
    if DEMO_MODE:
        from .demo import demo_prices

        return {s: demo_prices(s, days=252 * years + 60) for s in syms}

    def _long() -> dict[str, pd.DataFrame]:
        out: dict[str, pd.DataFrame] = {}
        for i in range(0, len(syms), 100):
            if progress:
                progress(i / len(syms), f"Downloading {years} years of prices… {i}/{len(syms)} stocks")
            out.update(_yf_batch_prices(syms[i : i + 100], period=f"{years}y"))
        return out

    tag = hashlib.sha1(",".join(syms).encode()).hexdigest()[:12]
    hist = _cached(f"scan:long:{years}y:{tag}", 20 * 3600, _long)
    if progress:
        progress(0.95, "Refreshing the latest sessions…")
    recent = _cached(f"scan:recent:{tag}", 15 * 60, lambda: _yf_batch_prices(syms, period="5d"))
    merged = {}
    for s, df in hist.items():
        r = recent.get(s)
        if r is not None and len(r):
            df = pd.concat([df[df.index < r.index[0]], r])
        merged[s] = df
    return merged


def to_wide(hist: dict[str, pd.DataFrame]) -> dict[str, pd.DataFrame]:
    """dict of per-stock frames -> one frame per field (dates x symbols)."""
    hist = {s: d for s, d in hist.items() if len(d) > 60}
    out = {}
    for col in ("Open", "High", "Low", "Close", "Volume"):
        out[col] = pd.DataFrame({s: d[col] for s, d in hist.items()}).sort_index()
    return out


# --------------------------------------------------------------------------- features & rules
def features(w: dict[str, pd.DataFrame]) -> dict[str, pd.DataFrame]:
    o, h, l, c, v = (w[k] for k in ("Open", "High", "Low", "Close", "Volume"))
    f: dict[str, pd.DataFrame] = {"o": o, "h": h, "l": l, "c": c, "v": v}
    f["pivot"] = h.rolling(20, min_periods=20).max()
    f["pivot_prev"] = f["pivot"].shift(1)
    s50, s150, s200 = (c.rolling(n, min_periods=n).mean() for n in (50, 150, 200))
    f["s50"], f["s150"], f["s200"] = s50, s150, s200
    f["trend"] = (c > s50) & (s50 > s150) & (s150 > s200) & (s200 > s200.shift(20))
    f["hi252"] = h.rolling(252, min_periods=200).max()
    f["r126"] = c / c.shift(126) - 1
    f["swing10"] = (h.rolling(10).max() - l.rolling(10).min()) / c
    f["vol_ratio"] = v.rolling(10).mean() / v.rolling(50).mean()
    f["traded_cr"] = (c * v).rolling(20).mean() / 1e7
    f["gap"] = 1 - c / f["pivot"]
    return f


def signals(f: dict[str, pd.DataFrame], r: Rules) -> pd.DataFrame:
    c = f["c"]
    m = (f["gap"] <= r.near_pivot_pct / 100) & (c >= r.min_price) & (f["traded_cr"] >= r.min_traded_cr)
    if r.not_broken_yet:
        m &= c <= f["pivot_prev"]
    if r.trend_template:
        m &= f["trend"]
    if r.near_52w_pct:
        m &= c >= (1 - r.near_52w_pct / 100) * f["hi252"]
    if r.min_6m_return_pct:
        m &= f["r126"] >= r.min_6m_return_pct / 100
    if r.min_10d_swing_pct:
        m &= f["swing10"] >= r.min_10d_swing_pct / 100
    if r.max_10d_swing_pct:
        m &= f["swing10"] <= r.max_10d_swing_pct / 100
    if r.volume_drying_up:
        m &= f["vol_ratio"] < 1
    return m.fillna(False)


def baseline(f: dict[str, pd.DataFrame], r: Rules) -> pd.DataFrame:
    """What a signal is compared with: any liquid stock within 8% of its 20-day high."""
    return ((f["gap"] <= 0.08) & (f["c"] >= r.min_price) & (f["traded_cr"] >= r.min_traded_cr)).fillna(False)


def scan_today(f: dict[str, pd.DataFrame], r: Rules, meta: pd.DataFrame | None = None) -> pd.DataFrame:
    sig = signals(f, r)
    if sig.empty:
        return pd.DataFrame()
    last = sig.index[-1]
    hits = [s for s in sig.columns if bool(sig.at[last, s])]
    rows = []
    for s in hits:
        g = lambda k: f[k].at[last, s]  # noqa: E731
        rows.append({
            "Symbol": s, "Close": g("c"), "Pivot (20-day high)": g("pivot"), "Gap to pivot %": 100 * g("gap"),
            "6-month return %": 100 * g("r126"), "10-day swing %": 100 * g("swing10"),
            "Below 52-week high %": 100 * (1 - g("c") / g("hi252")) if g("hi252") else np.nan,
            "Volume vs 50-day avg": g("v") / f["v"][s].rolling(50).mean().iat[-1],
            "Traded ₹ cr/day": g("traded_cr"),
        })
    out = pd.DataFrame(rows)
    if out.empty:
        return out
    if meta is not None and len(meta):
        out = out.merge(meta[["Symbol", "Company", "Sector", "Industry", "Cap bucket"]], on="Symbol", how="left")
    return out.sort_values("Gap to pivot %").reset_index(drop=True)


# --------------------------------------------------------------------------- outcomes & backtest
def outcomes(f: dict[str, pd.DataFrame]) -> tuple[pd.DataFrame, pd.DataFrame]:
    """For every stock-day: did it break out within 10 sessions (1/0, NaN if too recent), and was it clean?
    Vectorised over all stocks at once."""
    c, h, piv = f["c"].values, f["h"].values, f["pivot"].values
    n = c.shape[0]
    first = np.zeros(c.shape, dtype=int)  # sessions until breakout close, 0 = none
    for j in range(BREAKOUT_WINDOW, 0, -1):
        fut = np.full(c.shape, np.nan)
        fut[:-j] = c[j:]
        first = np.where(fut > piv, j, first)
    state = np.zeros(c.shape)  # 0 undecided, 1 clean, -1 failed
    for m in range(1, BREAKOUT_WINDOW + CLEAN_WINDOW):
        cm, hm = np.full(c.shape, np.nan), np.full(c.shape, np.nan)
        cm[:-m], hm[:-m] = c[m:], h[m:]
        active = (first > 0) & (m >= first) & (m < first + CLEAN_WINDOW) & (state == 0)
        fail = active & (cm < piv * (1 - CLEAN_FAIL))
        state[fail] = -1
        state[active & ~fail & (hm >= piv * (1 + CLEAN_UP))] = 1
    brk = (first > 0).astype(float)
    clean = (state == 1).astype(float)
    brk[n - BREAKOUT_WINDOW:] = np.nan
    clean[n - BREAKOUT_WINDOW - CLEAN_WINDOW:] = np.nan
    brk[np.isnan(piv)] = np.nan
    clean[np.isnan(piv)] = np.nan
    idx, cols = f["c"].index, f["c"].columns
    return pd.DataFrame(brk, idx, cols), pd.DataFrame(clean, idx, cols)


def _stack(mask: pd.DataFrame, brk: pd.DataFrame, clean: pd.DataFrame) -> pd.DataFrame:
    m = mask.stack()
    m = m[m]
    df = pd.DataFrame({"breakout": brk.stack().reindex(m.index), "clean": clean.stack().reindex(m.index)})
    df.index.names = ["date", "symbol"]
    return df.reset_index()


def backtest(f: dict[str, pd.DataFrame], r: Rules, warmup: int = 260) -> dict[str, Any]:
    brk, clean = outcomes(f)
    sig, base = signals(f, r), baseline(f, r)
    sig.iloc[:warmup] = False
    base.iloc[:warmup] = False
    s, b = _stack(sig, brk, clean), _stack(base, brk, clean)
    done_s, done_b = s.dropna(subset=["breakout"]), b.dropna(subset=["breakout"])
    cl_s, cl_b = s.dropna(subset=["clean"]), b.dropna(subset=["clean"])

    def pct(x: pd.Series) -> float | None:
        return round(100 * float(x.mean()), 1) if len(x) else None

    def by_year(df: pd.DataFrame, col: str) -> pd.Series:
        d = df.dropna(subset=[col])
        return (100 * d.groupby(d["date"].dt.year)[col].mean()).round(1)

    years = pd.DataFrame({
        "Rules: breakout %": by_year(s, "breakout"), "All near-high stocks: breakout %": by_year(b, "breakout"),
        "Rules: clean %": by_year(s, "clean"), "All near-high stocks: clean %": by_year(b, "clean"),
        "Signals": s.groupby(s["date"].dt.year).size(),
    })
    recent = s.sort_values("date", ascending=False).head(400).copy()
    recent["Outcome"] = np.select(
        [recent["breakout"].isna(), recent["breakout"] == 0, recent["clean"] == 1, recent["clean"].isna()],
        ["Too recent to judge", "No breakout in 10 sessions", "Clean breakout (+10%)", "Broke out; still running"],
        default="Broke out, then failed / stalled",
    )
    start = sig.index[warmup] if len(sig.index) > warmup else sig.index[0]
    return {
        "rules": asdict(r), "from": str(pd.Timestamp(start).date()), "to": str(pd.Timestamp(sig.index[-1]).date()),
        "stocks": int(sig.shape[1]), "signals": int(len(s)), "distinct_stocks": int(s["symbol"].nunique()) if len(s) else 0,
        "per_day": round(len(s) / max(1, (sig.index >= start).sum()), 1),
        "breakout_pct": pct(done_s["breakout"]), "clean_pct": pct(cl_s["clean"]),
        "base_breakout_pct": pct(done_b["breakout"]), "base_clean_pct": pct(cl_b["clean"]),
        "years": years, "recent": recent[["date", "symbol", "Outcome"]].rename(columns={"date": "Signal date", "symbol": "Symbol"}),
    }


# --------------------------------------------------------------------------- Chartink export
def chartink(r: Rules) -> str:
    """The same rules in Chartink scan-clause syntax (paste into Chartink's scan editor)."""
    lines = [f"latest close >= {1 - r.near_pivot_pct / 100:.2f} * latest max( 20 , latest high )"]
    if r.not_broken_yet:
        lines.append("latest close <= 1 day ago max( 20 , latest high )")
    if r.trend_template:
        lines += ["latest close > latest sma( close,50 )", "latest sma( close,50 ) > latest sma( close,150 )",
                  "latest sma( close,150 ) > latest sma( close,200 )", "latest sma( close,200 ) > 20 days ago sma( close,200 )"]
    if r.near_52w_pct:
        lines.append(f"latest close >= {1 - r.near_52w_pct / 100:.2f} * latest max( 252 , latest high )")
    if r.min_6m_return_pct:
        lines.append(f"latest close >= {1 + r.min_6m_return_pct / 100:.2f} * 126 days ago close")
    if r.min_10d_swing_pct:
        lines.append(f"latest max( 10 , latest high ) - latest min( 10 , latest low ) >= {r.min_10d_swing_pct / 100:.2f} * latest close")
    if r.max_10d_swing_pct:
        lines.append(f"latest max( 10 , latest high ) - latest min( 10 , latest low ) <= {r.max_10d_swing_pct / 100:.2f} * latest close")
    if r.volume_drying_up:
        lines.append("latest sma( volume,10 ) < latest sma( volume,50 )")
    lines.append(f"latest close > {r.min_price:g}")
    lines.append(f"latest sma( volume,20 ) * latest close > {int(r.min_traded_cr * 1e7)}")
    return "( {cash} (\n  " + " and\n  ".join(lines) + "\n) )"


def with_changes(r: Rules, **kw: Any) -> Rules:
    return replace(r, **kw)
