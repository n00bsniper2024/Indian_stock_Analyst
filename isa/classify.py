"""Stock classification: NSE sector + finer industry + market-cap bucket + index memberships.

* Sector      — NSE's official sector (the "Industry" column of NSE index files, ~22 values)
* Industry    — finer industry from Yahoo (e.g. "Information Technology Services", "Banks - Regional")
* Cap bucket  — SEBI/AMFI-style by index membership: Nifty 100 = Large, Midcap 150 = Mid,
                Smallcap 250 = Small, Microcap 250 = Micro (these indices are built on the same
                full-market-cap ranks AMFI uses: 1-100, 101-250, 251-500, 501-750)
* Indices     — every tracked NSE index the stock belongs to

A snapshot ships in data/classification.csv so the app works instantly; refresh it with
`python -m isa.cli refresh-classification` (takes several minutes — one Yahoo request per stock).
"""
from __future__ import annotations

import time
from functools import lru_cache
from typing import Callable

import pandas as pd

from .config import DATA_DIR
from .universe import CATEGORIES, flat_categories, load_index

CLASSIFICATION_FILE = DATA_DIR / "classification.csv"
UNIVERSE_SLUG = "ind_niftytotalmarket_list"  # ~750 stocks: Nifty 500 + Microcap 250
CAP_ORDER = [("Large cap", "ind_nifty100list"), ("Mid cap", "ind_niftymidcap150list"),
             ("Small cap", "ind_niftysmallcap250list"), ("Micro cap", "ind_niftymicrocap250_list")]


def index_memberships() -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    for name, slug in flat_categories().items():
        if slug == "ind_nifty500list":
            continue
        try:
            df, src = load_index(slug)
        except Exception:
            continue
        if src == "fallback" and slug != "ind_nifty50list":
            continue
        for s in df["Symbol"]:
            out.setdefault(s, []).append(name.split(" (")[0])
    return out


def cap_buckets() -> dict[str, str]:
    out: dict[str, str] = {}
    for label, slug in CAP_ORDER:
        try:
            df, src = load_index(slug)
        except Exception:
            continue
        if src == "fallback":
            continue
        for s in df["Symbol"]:
            out.setdefault(s, label)
    return out


def build_classification(progress: Callable[[int, int, str], None] | None = None, pause: float = 0.35) -> pd.DataFrame:
    import yfinance as yf

    from .data import _retry

    uni, _ = load_index(UNIVERSE_SLUG)
    caps = cap_buckets()
    rows = []
    for i, r in uni.iterrows():
        sym = r["Symbol"]
        info: dict = {}
        try:
            info = _retry(lambda: yf.Ticker(f"{sym}.NS").get_info()) or {}
        except Exception:
            pass
        mcap = info.get("marketCap")
        rows.append({
            "Symbol": sym,
            "Company": r.get("Company Name", sym),
            "Sector": r.get("Industry", "Unclassified"),
            "Industry": info.get("industry") or r.get("Industry", "Unclassified"),
            "Market cap (₹ cr)": round(mcap / 1e7) if isinstance(mcap, (int, float)) and mcap else None,
            "Cap bucket": caps.get(sym, "Unclassified"),
        })
        if progress:
            progress(i + 1, len(uni), sym)
        time.sleep(pause)
    df = pd.DataFrame(rows)
    df.to_csv(CLASSIFICATION_FILE, index=False)
    return df


@lru_cache(maxsize=1)
def load_classification() -> pd.DataFrame:
    """Snapshot file + live index memberships. Missing columns are filled so the app never breaks."""
    if CLASSIFICATION_FILE.exists():
        df = pd.read_csv(CLASSIFICATION_FILE)
    else:
        uni, _ = load_index(UNIVERSE_SLUG)
        df = uni.rename(columns={"Company Name": "Company", "Industry": "Sector"})
        df["Industry"] = df["Sector"]
        df["Market cap (₹ cr)"] = None
        df["Cap bucket"] = df["Symbol"].map(cap_buckets()).fillna("Unclassified")
    mem = index_memberships()
    df["Indices"] = df["Symbol"].map(lambda s: ", ".join(mem.get(s, [])))
    return df


def classification_for(symbol: str, df: pd.DataFrame | None = None) -> dict[str, str]:
    df = load_classification() if df is None else df
    row = df[df["Symbol"] == symbol]
    if row.empty:
        return {}
    return {k: ("" if pd.isna(v) else v) for k, v in row.iloc[0].to_dict().items()}


def groups() -> list[str]:
    return list(CATEGORIES) + ["Sector (NSE)", "Industry", "Market-cap bucket"]
