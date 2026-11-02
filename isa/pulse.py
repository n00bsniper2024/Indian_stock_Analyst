"""Market pulse: headline Indian indices for the scrolling ticker (cached a few minutes)."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

import pandas as pd

from .config import DEMO_MODE
from .data import _cached, _retry

IST = timezone(timedelta(hours=5, minutes=30))
INDICES = [
    ("Nifty 50", "^NSEI"), ("Sensex", "^BSESN"), ("Bank Nifty", "^NSEBANK"), ("Nifty 500", "^CRSLDX"),
    ("Midcap 50", "^NSEMDCP50"), ("Smallcap 100", "^CNXSC"), ("India VIX", "^INDIAVIX"), ("Nifty IT", "^CNXIT"),
    ("Nifty Auto", "^CNXAUTO"), ("Nifty Pharma", "^CNXPHARMA"), ("Nifty FMCG", "^CNXFMCG"), ("Nifty Metal", "^CNXMETAL"),
    ("Nifty Energy", "^CNXENERGY"), ("PSU Bank", "^CNXPSUBANK"), ("Nifty Realty", "^CNXREALTY"), ("USD/INR", "INR=X"),
]


def _fetch() -> dict[str, Any]:
    import yfinance as yf

    tickers = [t for _, t in INDICES]
    intra = _retry(lambda: yf.download(tickers, period="5d", interval="15m", group_by="ticker", progress=False, auto_adjust=False, threads=True))
    daily = _retry(lambda: yf.download(tickers, period="10d", interval="1d", group_by="ticker", progress=False, auto_adjust=False, threads=True))
    items, last_ts = [], None
    for name, t in INDICES:
        try:
            x = intra[t]["Close"].dropna()
            d = daily[t]["Close"].dropna()
        except (KeyError, TypeError):
            continue
        if x.empty or len(d) < 2:
            continue
        ts = x.index[-1]
        today = ts.tz_convert(IST).date() if ts.tzinfo else ts.date()
        d_dates = [i.date() for i in d.index]
        prev = float(d.iloc[-2]) if d_dates[-1] == today else float(d.iloc[-1])  # previous session's official close
        last = float(x.iloc[-1])
        sess = x[[(i.tz_convert(IST).date() if i.tzinfo else i.date()) == today for i in x.index]]
        items.append({"name": name, "symbol": t, "value": last, "chg": 100 * (last / prev - 1) if prev else None, "invert": t == "^INDIAVIX",
                      "spark": [float(v) for v in (sess if len(sess) > 3 else x.iloc[-26:]).tolist()]})
        if t == "^NSEI":
            last_ts = ts
    return {"items": items, "last_ts": last_ts}


def _demo() -> dict[str, Any]:
    from .demo import demo_prices

    items = []
    for name, t in INDICES:
        c = demo_prices(t, days=30)["Close"]
        items.append({"name": name, "symbol": t, "value": float(c.iloc[-1]), "chg": float(100 * (c.iloc[-1] / c.iloc[-2] - 1)),
                      "spark": c.iloc[-20:].tolist()})
    return {"items": items, "last_ts": None}


def market_pulse() -> dict[str, Any]:
    """{items: [{name, value, chg %, spark}], live: bool, as_of: str}. Never raises; empty items on failure."""
    try:
        data = _demo() if DEMO_MODE else _cached("pulse:v1", 5 * 60, _fetch)
    except Exception:
        return {"items": [], "live": False, "as_of": ""}
    ts = data.get("last_ts")
    now = datetime.now(IST)
    live, as_of = False, "demo data" if DEMO_MODE else ""
    if ts is not None:
        t_ist = ts.tz_convert(IST) if ts.tzinfo else pd.Timestamp(ts).tz_localize(IST)
        # Yahoo bars are delayed; "live" = the latest Nifty bar is from the last 40 minutes on a weekday session
        live = now.weekday() < 5 and (now - t_ist.to_pydatetime()) < timedelta(minutes=40) and (9, 15) <= (now.hour, now.minute) <= (15, 45)
        as_of = (t_ist + timedelta(minutes=15)).strftime("%d %b, %H:%M IST")  # bar start + bar length
    return {"items": data["items"], "live": live, "as_of": as_of}
