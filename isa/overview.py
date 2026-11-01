"""Category snapshot: one row per stock, computed from a single batched price download."""
from __future__ import annotations

import numpy as np
import pandas as pd

from .technicals import rsi, trend_assessment


def category_snapshot(prices: dict[str, pd.DataFrame], meta: pd.DataFrame) -> pd.DataFrame:
    names = dict(zip(meta["Symbol"], meta.get("Company Name", meta["Symbol"])))
    inds = dict(zip(meta["Symbol"], meta.get("Industry", pd.Series(["—"] * len(meta)))))
    rows = []
    for sym, df in prices.items():
        c = df["Close"].dropna()
        if len(c) < 30:
            continue

        def ret(n: int) -> float:
            return float(100 * (c.iloc[-1] / c.iloc[-n - 1] - 1)) if len(c) > n else np.nan

        tr = trend_assessment(df.iloc[-260:], "Daily")
        hi52 = float(df["High"].iloc[-252:].max())
        rows.append({
            "Symbol": sym,
            "Company": names.get(sym, sym),
            "Industry": inds.get(sym, "—"),
            "Price": round(float(c.iloc[-1]), 2),
            "1D %": ret(1), "1W %": ret(5), "1M %": ret(21), "3M %": ret(63),
            "1Y %": ret(min(252, len(c) - 1)),
            "RSI": float(rsi(c).iloc[-1]),
            "From 52W high %": 100 * (float(c.iloc[-1]) / hi52 - 1),
            "Above 200DMA": bool(c.iloc[-1] > c.rolling(200).mean().iloc[-1]) if len(c) >= 200 else None,
            "Trend score": tr.get("score"),
            "Trend": tr.get("trend"),
            "Turnover ₹cr (20D avg)": float((df["Close"] * df["Volume"]).iloc[-20:].mean() / 1e7),
        })
    out = pd.DataFrame(rows)
    if out.empty:
        return out
    num = out.select_dtypes("number").columns
    out[num] = out[num].round(2)
    return out.sort_values("Turnover ₹cr (20D avg)", ascending=False).reset_index(drop=True)


def breadth(snap: pd.DataFrame) -> dict[str, float]:
    if snap.empty:
        return {}
    return {
        "stocks": int(len(snap)),
        "advancers_1d": int((snap["1D %"] > 0).sum()),
        "decliners_1d": int((snap["1D %"] < 0).sum()),
        "pct_above_200dma": round(100 * snap["Above 200DMA"].dropna().mean(), 1) if snap["Above 200DMA"].notna().any() else float("nan"),
        "median_1m": round(float(snap["1M %"].median()), 2),
        "median_1y": round(float(snap["1Y %"].median()), 2),
        "uptrend_share": round(100 * (snap["Trend score"] >= 25).mean(), 1),
    }
