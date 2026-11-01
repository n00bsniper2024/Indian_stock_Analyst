"""Market-data layer.

Primary source: Yahoo Finance via `yfinance` (free, NSE symbols use the `.NS` suffix, BSE `.BO`).
Known limits (surfaced to the user as data gaps, never hidden):
  * only ~4-5 years of annual and ~5 quarters of statements, no point-in-time stamps
  * no promoter pledge / full shareholding pattern (Yahoo "insiders" is only a proxy for promoters)
  * Yahoo throttles bursts of requests -> we cache on disk and back off on rate-limit errors

Set ISA_DEMO=1 to use a deterministic synthetic provider (offline demos, tests, screenshots).
"""
from __future__ import annotations

import hashlib
import pickle
import time
from dataclasses import dataclass, field
from typing import Any, Callable

import numpy as np
import pandas as pd

from .config import BENCHMARK, CACHE_DIR, DEMO_MODE


# --------------------------------------------------------------------------- containers
@dataclass
class StockData:
    symbol: str
    yf_symbol: str
    info: dict[str, Any]
    daily: pd.DataFrame  # OHLCV, DatetimeIndex ascending
    intraday: pd.DataFrame | None
    income_a: pd.DataFrame  # rows = period end (ascending), columns = line items
    income_q: pd.DataFrame
    balance_a: pd.DataFrame
    cashflow_a: pd.DataFrame
    benchmark: pd.Series | None  # Nifty 50 close
    news: list[dict[str, str]] = field(default_factory=list)
    source: str = "yahoo"
    fetched_at: float = field(default_factory=time.time)
    warnings: list[str] = field(default_factory=list)

    @property
    def name(self) -> str:
        return self.info.get("longName") or self.info.get("shortName") or self.symbol

    @property
    def last_price(self) -> float:
        return float(self.daily["Close"].iloc[-1]) if len(self.daily) else float("nan")


# --------------------------------------------------------------------------- disk cache
def _cached(key: str, ttl: int, fn: Callable[[], Any]) -> Any:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    path = CACHE_DIR / f"{hashlib.sha1(key.encode()).hexdigest()}.pkl"
    if path.exists() and time.time() - path.stat().st_mtime < ttl:
        try:
            with path.open("rb") as fh:
                return pickle.load(fh)
        except Exception:
            path.unlink(missing_ok=True)
    value = fn()
    try:
        with path.open("wb") as fh:
            pickle.dump(value, fh)
    except Exception:
        pass
    return value


def _cache_forget(key: str) -> None:
    (CACHE_DIR / f"{hashlib.sha1(key.encode()).hexdigest()}.pkl").unlink(missing_ok=True)


def _retry(fn: Callable[[], Any], attempts: int = 3, base_delay: float = 4.0) -> Any:
    last: Exception | None = None
    for i in range(attempts):
        try:
            return fn()
        except Exception as exc:  # yfinance raises YFRateLimitError / generic errors
            last = exc
            msg = str(exc).lower()
            if "rate" in msg or "too many" in msg or "429" in msg:
                time.sleep(base_delay * (2**i))
                continue
            raise
    raise RuntimeError(
        "Yahoo Finance is rate-limiting this network. Wait a few minutes and retry "
        f"(cached data is reused automatically). Last error: {last}"
    )


def _tidy_statement(df: pd.DataFrame | None) -> pd.DataFrame:
    """yfinance gives line items as rows and dates as columns (newest first). Flip it."""
    if df is None or not isinstance(df, pd.DataFrame) or df.empty:
        return pd.DataFrame()
    out = df.T.copy()
    out.index = pd.to_datetime(out.index, errors="coerce")
    out = out[~out.index.isna()].sort_index()
    out = out.apply(pd.to_numeric, errors="coerce")
    # drop periods that are completely empty (Yahoo sometimes returns a trailing all-NaN year)
    return out.dropna(how="all")


def _strip_tz(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        return df
    df = df.copy()
    if getattr(df.index, "tz", None) is not None:
        df.index = df.index.tz_convert("Asia/Kolkata").tz_localize(None)
    return df


def _parse_news(raw: Any) -> list[dict[str, str]]:
    items: list[dict[str, str]] = []
    for n in raw or []:
        c = n.get("content", n) if isinstance(n, dict) else {}
        title = c.get("title")
        if not title:
            continue
        provider = c.get("provider", {})
        url = c.get("canonicalUrl", {})
        items.append(
            {
                "title": title,
                "publisher": provider.get("displayName", "") if isinstance(provider, dict) else str(provider or c.get("publisher", "")),
                "date": str(c.get("pubDate") or c.get("providerPublishTime") or "")[:10],
                "url": url.get("url", "") if isinstance(url, dict) else str(c.get("link", "")),
            }
        )
    return items[:10]


# --------------------------------------------------------------------------- yahoo provider
def _yf_fetch(symbol: str, intraday: bool = True) -> StockData:
    import yfinance as yf

    warnings: list[str] = []
    ysym = f"{symbol}.NS"
    t = yf.Ticker(ysym)
    daily = _retry(lambda: t.history(period="max", interval="1d", auto_adjust=True))
    if daily is None or daily.empty:
        ysym = f"{symbol}.BO"
        t = yf.Ticker(ysym)
        daily = _retry(lambda: t.history(period="max", interval="1d", auto_adjust=True))
        if daily is None or daily.empty:
            raise ValueError(f"No price data on Yahoo for {symbol} (.NS or .BO). Check the symbol.")
        warnings.append("NSE data unavailable on Yahoo; using BSE (.BO) listing.")
    daily = _strip_tz(daily[["Open", "High", "Low", "Close", "Volume"]].dropna(subset=["Close"]))

    intra = None
    if intraday:
        try:
            intra = _strip_tz(_retry(lambda: t.history(period="720d", interval="60m", auto_adjust=True)))
            intra = intra[["Open", "High", "Low", "Close", "Volume"]].dropna(subset=["Close"])
        except Exception:
            warnings.append("Hourly data unavailable; intraday timeframe skipped.")

    try:
        info = _retry(lambda: t.get_info()) or {}
    except Exception:
        info = {}
        warnings.append("Company profile (info) unavailable from Yahoo.")

    def safe(attr: str) -> pd.DataFrame:
        try:
            return _tidy_statement(getattr(t, attr))
        except Exception:
            return pd.DataFrame()

    income_a, income_q = safe("income_stmt"), safe("quarterly_income_stmt")
    balance_a, cashflow_a = safe("balance_sheet"), safe("cashflow")
    if income_a.empty:
        warnings.append("Annual financial statements unavailable from Yahoo for this stock.")

    try:
        news = _parse_news(t.news)
    except Exception:
        news = []

    return StockData(
        symbol=symbol,
        yf_symbol=ysym,
        info=info,
        daily=daily,
        intraday=intra,
        income_a=income_a,
        income_q=income_q,
        balance_a=balance_a,
        cashflow_a=cashflow_a,
        benchmark=None,
        news=news,
        source="yahoo",
        warnings=warnings,
    )


def _yf_benchmark() -> pd.Series:
    import yfinance as yf

    h = _retry(lambda: yf.Ticker(BENCHMARK).history(period="max", interval="1d", auto_adjust=True))
    return _strip_tz(h)["Close"].rename("NIFTY50")


def _yf_batch_prices(symbols: tuple[str, ...], period: str = "1y") -> dict[str, pd.DataFrame]:
    import yfinance as yf

    tickers = [f"{s}.NS" for s in symbols]
    out: dict[str, pd.DataFrame] = {}
    for i in range(0, len(tickers), 100):  # chunk to stay polite with Yahoo
        chunk = tickers[i : i + 100]
        raw = _retry(
            lambda: yf.download(
                chunk, period=period, interval="1d", group_by="ticker",
                auto_adjust=True, threads=True, progress=False,
            )
        )
        if raw is None or raw.empty:
            continue
        for tk in chunk:
            try:
                df = raw[tk] if isinstance(raw.columns, pd.MultiIndex) else raw
                df = _strip_tz(df[["Open", "High", "Low", "Close", "Volume"]].dropna(subset=["Close"]))
                if len(df):
                    out[tk[:-3]] = df
            except (KeyError, TypeError):
                continue
    return out


def _yf_peer_info(symbols: tuple[str, ...]) -> dict[str, dict[str, Any]]:
    import yfinance as yf

    out: dict[str, dict[str, Any]] = {}
    for s in symbols:
        try:
            out[s] = _retry(lambda: yf.Ticker(f"{s}.NS").get_info()) or {}
        except Exception:
            out[s] = {}
        time.sleep(0.4)  # be gentle — peers are fetched one by one
    return out


# --------------------------------------------------------------------------- public API
def get_stock(symbol: str, intraday: bool = True) -> StockData:
    symbol = symbol.strip().upper().removesuffix(".NS").removesuffix(".BO")
    if DEMO_MODE:
        from .demo import demo_stock

        return demo_stock(symbol)
    sd: StockData = _cached(f"stock:{symbol}:{intraday}", 30 * 60, lambda: _yf_fetch(symbol, intraday))
    try:
        sd.benchmark = _cached("bench", 6 * 3600, _yf_benchmark)
    except Exception:
        sd.warnings.append("Nifty 50 benchmark unavailable; relative strength and beta skipped.")
    return sd


def get_batch_prices(symbols: list[str], period: str = "1y") -> dict[str, pd.DataFrame]:
    syms = tuple(sorted(set(symbols)))
    if DEMO_MODE:
        from .demo import demo_prices

        return {s: demo_prices(s, days=260) for s in syms}
    return _cached(f"batch:{period}:{','.join(syms)}", 30 * 60, lambda: _yf_batch_prices(syms, period))


def get_peer_info(symbols: list[str]) -> dict[str, dict[str, Any]]:
    syms = tuple(sorted(set(symbols)))
    if DEMO_MODE:
        from .demo import demo_info

        return {s: demo_info(s) for s in syms}
    return _cached(f"peers:{','.join(syms)}", 12 * 3600, lambda: _yf_peer_info(syms))


def resample_ohlcv(df: pd.DataFrame, rule: str) -> pd.DataFrame:
    """Resample OHLCV to weekly ('W-FRI'), monthly ('ME') or 4-hour ('4h') bars."""
    agg = {"Open": "first", "High": "max", "Low": "min", "Close": "last", "Volume": "sum"}
    return df.resample(rule).agg(agg).dropna(subset=["Close"])


def to_float(x: Any) -> float:
    try:
        v = float(x)
        return v if np.isfinite(v) else float("nan")
    except (TypeError, ValueError):
        return float("nan")
