"""Deterministic synthetic data for offline demos and tests (ISA_DEMO=1).

Numbers are FAKE. The UI labels every page as demo data when this provider is active.
"""
from __future__ import annotations

import zlib

import numpy as np
import pandas as pd

from .data import StockData


def _rng(symbol: str, salt: str = "") -> np.random.Generator:
    return np.random.default_rng(zlib.crc32(f"{symbol}{salt}".encode()))


def demo_prices(symbol: str, days: int = 2500, end: str | None = None) -> pd.DataFrame:
    rng = _rng(symbol, "px")
    idx = pd.bdate_range(end=end or pd.Timestamp.today().normalize(), periods=days)
    drift = rng.uniform(-0.0002, 0.0009)
    vol = rng.uniform(0.012, 0.024)
    # regime switches make trends visible on charts
    regimes = np.repeat(rng.normal(drift, 0.0008, size=days // 120 + 1), 120)[:days]
    rets = rng.normal(regimes, vol)
    close = rng.uniform(150, 3500) * np.exp(np.cumsum(rets))
    open_ = close * (1 + rng.normal(0, vol / 3, days))
    high = np.maximum(open_, close) * (1 + np.abs(rng.normal(0, vol / 2, days)))
    low = np.minimum(open_, close) * (1 - np.abs(rng.normal(0, vol / 2, days)))
    volume = rng.lognormal(13.5, 0.5, days) * (1 + 3 * (np.abs(rets) > 2 * vol))
    return pd.DataFrame({"Open": open_, "High": high, "Low": low, "Close": close, "Volume": volume.round()}, index=idx)


def demo_info(symbol: str) -> dict:
    rng = _rng(symbol, "info")
    px = float(demo_prices(symbol)["Close"].iloc[-1])
    shares = rng.uniform(2e8, 6e9)
    eps = px / rng.uniform(12, 55)
    sector = ["Technology", "Consumer Defensive", "Industrials", "Healthcare", "Financial Services"][zlib.crc32(symbol.encode()) % 5]
    return {
        "longName": f"{symbol.title()} Industries Ltd (DEMO)",
        "sector": sector,
        "industry": sector + " - Demo",
        "longBusinessSummary": "Synthetic demo company used to preview the dashboard offline. All figures are randomly generated.",
        "marketCap": px * shares,
        "sharesOutstanding": shares,
        "trailingPE": px / eps,
        "forwardPE": px / (eps * 1.15),
        "priceToBook": rng.uniform(1.5, 12),
        "trailingEps": eps,
        "dividendYield": rng.uniform(0, 2.5),
        "beta": rng.uniform(0.6, 1.4),
        "heldPercentInsiders": rng.uniform(0.3, 0.72),
        "heldPercentInstitutions": rng.uniform(0.1, 0.4),
        "fiftyTwoWeekHigh": px * 1.2,
        "fiftyTwoWeekLow": px * 0.75,
        "returnOnEquity": rng.uniform(0.08, 0.3),
        "enterpriseToEbitda": rng.uniform(8, 30),
        "currency": "INR",
        "financialCurrency": "INR",
    }


def _statements(symbol: str, info: dict) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    rng = _rng(symbol, "fin")
    years = pd.to_datetime([f"{y}-03-31" for y in range(2022, 2027)])
    g = rng.uniform(0.04, 0.22)
    rev = info["marketCap"] / rng.uniform(2, 8) * np.cumprod(np.r_[1, np.full(4, 1 + g)]) / (1 + g) ** 4
    rev = rev * (1 + rng.normal(0, 0.03, 5))
    opm = np.clip(rng.uniform(0.1, 0.28) + np.cumsum(rng.normal(0, 0.01, 5)), 0.03, 0.45)
    ebit = rev * opm
    da = rev * rng.uniform(0.02, 0.05)
    interest = ebit * rng.uniform(0.02, 0.15)
    pbt = ebit - interest
    tax = pbt * 0.2517
    ni = pbt - tax
    shares = info["sharesOutstanding"]
    income = pd.DataFrame(
        {
            "Total Revenue": rev, "Gross Profit": rev * rng.uniform(0.35, 0.6), "Operating Income": ebit,
            "EBIT": ebit, "EBITDA": ebit + da, "Interest Expense": interest, "Pretax Income": pbt,
            "Tax Provision": tax, "Net Income": ni, "Diluted EPS": ni / shares, "Basic EPS": ni / shares,
            "Reconciled Depreciation": da,
        },
        index=years,
    )
    assets = rev * rng.uniform(0.9, 1.6)
    equity = assets * rng.uniform(0.45, 0.7)
    debt = assets * rng.uniform(0.02, 0.25)
    cur_assets = assets * 0.4
    cur_liab = assets * rng.uniform(0.15, 0.3)
    balance = pd.DataFrame(
        {
            "Total Assets": assets, "Stockholders Equity": equity, "Total Debt": debt,
            "Current Assets": cur_assets, "Current Liabilities": cur_liab,
            "Cash And Cash Equivalents": assets * 0.08, "Retained Earnings": equity * 0.7,
            "Working Capital": cur_assets - cur_liab, "Ordinary Shares Number": np.full(5, shares),
            "Inventory": rev * 0.1, "Accounts Receivable": rev * 0.12,
            "Total Liabilities Net Minority Interest": assets - equity,
        },
        index=years,
    )
    cfo = ni * rng.uniform(0.8, 1.3, 5) + da
    capex = -rev * rng.uniform(0.03, 0.08, 5)
    cash = pd.DataFrame(
        {"Operating Cash Flow": cfo, "Capital Expenditure": capex, "Free Cash Flow": cfo + capex,
         "Cash Dividends Paid": -ni * 0.3},
        index=years,
    )
    q_idx = pd.to_datetime(["2025-09-30", "2025-12-31", "2026-03-31", "2026-06-30", "2026-09-30"])
    qrev = rev[-1] / 4 * np.cumprod(1 + rng.normal(g / 4, 0.03, 5))
    qni = qrev * (ni[-1] / rev[-1]) * (1 + rng.normal(0, 0.08, 5))
    income_q = pd.DataFrame({"Total Revenue": qrev, "Net Income": qni, "Operating Income": qrev * opm[-1],
                             "Diluted EPS": qni / shares}, index=q_idx)
    return income, income_q, balance, cash


def demo_stock(symbol: str) -> StockData:
    info = demo_info(symbol)
    daily = demo_prices(symbol)
    rng = _rng(symbol, "intra")
    last = daily["Close"].iloc[-1]
    idx = pd.date_range(end=daily.index[-1] + pd.Timedelta(hours=15), periods=24 * 60, freq="h")
    idx = idx[(idx.hour >= 9) & (idx.hour <= 15)]
    c = last * np.exp(np.cumsum(rng.normal(0, 0.004, len(idx))))
    intra = pd.DataFrame({"Open": c * 0.999, "High": c * 1.003, "Low": c * 0.997, "Close": c,
                          "Volume": rng.lognormal(11, 0.4, len(idx))}, index=idx)
    inc, inc_q, bal, cf = _statements(symbol, info)
    bench = demo_prices("NIFTY50")["Close"].rename("NIFTY50")
    return StockData(
        symbol=symbol, yf_symbol=f"{symbol}.NS", info=info, daily=daily, intraday=intra,
        income_a=inc, income_q=inc_q, balance_a=bal, cashflow_a=cf, benchmark=bench,
        news=[{"title": "Demo mode: no real news", "publisher": "ISA", "date": "", "url": ""}],
        source="demo", warnings=["DEMO MODE — all numbers are synthetic."],
    )
