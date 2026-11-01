"""Stock universe: NSE index constituents grouped into categories.

Lists are downloaded live from NSE's public archive (same CSVs niftyindices.com publishes),
cached on disk for 7 days, and fall back to a bundled Nifty 50 snapshot if NSE is unreachable.
"""
from __future__ import annotations

import io
import time
from pathlib import Path

import pandas as pd
import requests

from .config import CACHE_DIR, DATA_DIR

NSE_INDEX_URL = "https://nsearchives.nseindia.com/content/indices/{slug}.csv"
NSE_EQUITY_LIST_URL = "https://nsearchives.nseindia.com/content/equities/EQUITY_L.csv"
CACHE_TTL_SECONDS = 7 * 24 * 3600

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/130.0 Safari/537.36"
    ),
    "Accept": "text/csv,text/plain,*/*",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://www.nseindia.com/",
}

# Category label -> NSE CSV slug.  Grouped for the UI.
CATEGORIES: dict[str, dict[str, str]] = {
    "Market cap": {
        "Nifty 50 (Large cap)": "ind_nifty50list",
        "Nifty Next 50 (Large cap)": "ind_niftynext50list",
        "Nifty Midcap 150 (Mid cap)": "ind_niftymidcap150list",
        "Nifty Smallcap 250 (Small cap)": "ind_niftysmallcap250list",
        "Nifty Microcap 250 (Micro cap)": "ind_niftymicrocap250_list",
        "Nifty 500 (Broad market)": "ind_nifty500list",
        "Nifty Total Market (750 stocks)": "ind_niftytotalmarket_list",
    },
    "Sector indices": {
        "Nifty Bank": "ind_niftybanklist",
        "Nifty Financial Services": "ind_niftyfinancelist",
        "Nifty PSU Bank": "ind_niftypsubanklist",
        "Nifty IT": "ind_niftyitlist",
        "Nifty Pharma": "ind_niftypharmalist",
        "Nifty Healthcare": "ind_niftyhealthcarelist",
        "Nifty FMCG": "ind_niftyfmcglist",
        "Nifty Auto": "ind_niftyautolist",
        "Nifty Metal": "ind_niftymetallist",
        "Nifty Energy": "ind_niftyenergylist",
        "Nifty Oil & Gas": "ind_niftyoilgaslist",
        "Nifty Realty": "ind_niftyrealtylist",
        "Nifty Media": "ind_niftymedialist",
        "Nifty Consumer Durables": "ind_niftyconsumerdurableslist",
    },
    "Themes": {
        "Nifty India Defence": "ind_niftyindiadefence_list",
        "Nifty CPSE": "ind_niftycpselist",
        "Nifty PSE": "ind_niftypselist",
        "Nifty India Consumption": "ind_niftyconsumptionlist",
        "Nifty Infrastructure": "ind_niftyinfralist",
        "Nifty MNC": "ind_niftymnclist",
    },
}


def _cache_path(slug: str) -> Path:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    return CACHE_DIR / f"universe_{slug}.csv"


def _download_csv(url: str, timeout: int = 15) -> pd.DataFrame:
    s = requests.Session()
    s.headers.update(_HEADERS)
    try:  # warm-up request sets cookies; harmless if it fails
        s.get("https://www.nseindia.com", timeout=timeout)
    except requests.RequestException:
        pass
    r = s.get(url, timeout=timeout)
    r.raise_for_status()
    df = pd.read_csv(io.StringIO(r.text))
    df.columns = [c.strip() for c in df.columns]
    return df


def _normalise(df: pd.DataFrame) -> pd.DataFrame:
    rename = {"SYMBOL": "Symbol", "NAME OF COMPANY": "Company Name"}
    df = df.rename(columns=rename)
    keep = [c for c in ["Symbol", "Company Name", "Industry"] if c in df.columns]
    df = df[keep].copy()
    if "Industry" not in df.columns:
        df["Industry"] = "Unclassified"
    df["Symbol"] = df["Symbol"].astype(str).str.strip()
    df = df[~df["Symbol"].str.upper().str.startswith("DUMMY")]  # NSE placeholders for pending index changes
    return df.drop_duplicates("Symbol").reset_index(drop=True)


def load_index(slug: str, force: bool = False) -> tuple[pd.DataFrame, str]:
    """Return (constituents, source) where source is 'live', 'cache', 'stale-cache' or 'fallback'."""
    from .config import DEMO_MODE

    if DEMO_MODE:  # offline: never touch the network
        return _normalise(pd.read_csv(DATA_DIR / "fallback_nifty50.csv")), "fallback"
    path = _cache_path(slug)
    if not force and path.exists() and time.time() - path.stat().st_mtime < CACHE_TTL_SECONDS:
        return pd.read_csv(path), "cache"
    try:
        df = _normalise(_download_csv(NSE_INDEX_URL.format(slug=slug)))
        if len(df):
            df.to_csv(path, index=False)
            return df, "live"
    except Exception:
        pass
    if path.exists():
        return pd.read_csv(path), "stale-cache"
    fb = _normalise(pd.read_csv(DATA_DIR / "fallback_nifty50.csv"))
    return fb, "fallback"


def load_all_equities(force: bool = False) -> pd.DataFrame:
    """Every NSE-listed equity (for the search box). Falls back to Nifty 500 / Nifty 50."""
    path = _cache_path("EQUITY_L")
    if not force and path.exists() and time.time() - path.stat().st_mtime < CACHE_TTL_SECONDS:
        return pd.read_csv(path)
    try:
        df = _download_csv(NSE_EQUITY_LIST_URL)
        if " SERIES" in df.columns or "SERIES" in df.columns:
            col = "SERIES" if "SERIES" in df.columns else " SERIES"
            df = df[df[col].astype(str).str.strip().isin(["EQ", "BE", "BZ", "SM", "ST"])]
        df = _normalise(df)
        df.to_csv(path, index=False)
        return df
    except Exception:
        if path.exists():
            return pd.read_csv(path)
    df, _ = load_index("ind_nifty500list")
    return df


def industries_from_nifty500() -> dict[str, pd.DataFrame]:
    """Industry buckets derived from the Nifty 500 'Industry' column (NSE's own classification)."""
    df, _ = load_index("ind_nifty500list")
    return {ind: g.reset_index(drop=True) for ind, g in df.groupby("Industry")}


def flat_categories() -> dict[str, str]:
    out: dict[str, str] = {}
    for group in CATEGORIES.values():
        out.update(group)
    return out
