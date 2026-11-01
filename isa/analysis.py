"""Builds the 'fact pack' — the single JSON document the AI layer is allowed to reason over."""
from __future__ import annotations

import json
import math
from datetime import datetime
from typing import Any

import numpy as np
import pandas as pd

from .config import ValuationDefaults
from .data import StockData, get_batch_prices, get_peer_info, get_stock
from .classify import classification_for
from .fundamentals import fundamental_summary
from .horizons import horizon_ratings
from .news import for_fact_pack, news_bundle
from .patterns import breakout_scan
from .technicals import technical_summary
from .universe import industries_from_nifty500, load_index
from .valuation import peer_table, valuation_summary


def _json_safe(o: Any) -> Any:
    if isinstance(o, dict):
        return {str(k): _json_safe(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [_json_safe(v) for v in o]
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, (np.floating, float)):
        f = float(o)
        return round(f, 4) if math.isfinite(f) else None
    if isinstance(o, (np.bool_,)):
        return bool(o)
    if isinstance(o, (pd.Timestamp, datetime)):
        return o.isoformat()[:10]
    return o


def find_peers(symbol: str, limit: int = 8) -> list[str]:
    """Same-industry companies (NSE Nifty 500 classification), closest in size to the stock.

    Size proxy = 20-day average traded value from one batched price request, so a large cap is
    compared with large caps and a small cap with small caps (not with whoever is first alphabetically).
    """
    try:
        group = next((df for _, df in industries_from_nifty500().items() if symbol in set(df["Symbol"])), None)
    except Exception:
        group = None
    if group is None:
        return []
    cands = group["Symbol"].tolist()
    # "Financial Services" mixes banks, NBFCs, insurers, exchanges and fintech: compare banks with banks.
    try:
        banks = set(load_index("ind_niftybanklist")[0]["Symbol"]) | set(load_index("ind_niftypsubanklist")[0]["Symbol"])
        if symbol in banks:
            cands = sorted(banks)
    except Exception:
        pass
    if len(cands) <= limit + 1:
        return [s for s in cands if s != symbol]
    try:
        prices = get_batch_prices(cands, period="1mo")
        tv = {s: float((d["Close"] * d["Volume"]).tail(20).mean()) for s, d in prices.items() if len(d)}
    except Exception:
        tv = {}
    if symbol not in tv or tv[symbol] <= 0:
        ranked = sorted((s for s in cands if s != symbol), key=lambda s: -tv.get(s, 0))
    else:
        me = math.log(tv[symbol])
        ranked = sorted((s for s in tv if s != symbol and tv[s] > 0), key=lambda s: abs(math.log(tv[s]) - me))
    return ranked[:limit]


def overall_signal(health: int | None, tech: int | None, val: int | None) -> dict[str, Any]:
    """Transparent blend. tech is -100..100 and is rescaled to 0..100."""
    parts = {}
    if health is not None:
        parts["fundamental_health"] = (health, 0.4)
    if val is not None:
        parts["valuation"] = (val, 0.3)
    if tech is not None:
        parts["technical_trend"] = ((tech + 100) / 2, 0.3)
    if not parts:
        return {"score": None, "label": "Insufficient data"}
    wsum = sum(w for _, w in parts.values())
    score = round(sum(v * w for v, w in parts.values()) / wsum)
    label = ("Strong positive" if score >= 70 else "Positive" if score >= 58 else "Neutral" if score >= 42
             else "Negative" if score >= 30 else "Strong negative")
    return {"score": score, "label": label, "weights": {k: w for k, (_, w) in parts.items()},
            "note": "Model signal for research only — not a buy/sell recommendation."}


def build_fact_pack(symbol: str, settings: ValuationDefaults | None = None, with_peers: bool = True,
                    sd: StockData | None = None, growth_override: float | None = None, with_news: bool = True) -> dict[str, Any]:
    sd = sd or get_stock(symbol)
    tech = technical_summary(sd)
    fund = fundamental_summary(sd)
    peers_df = None
    peer_syms: list[str] = []
    if with_peers:
        peer_syms = find_peers(sd.symbol)
        if peer_syms:
            infos = get_peer_info(peer_syms + [sd.symbol])
            peers_df = peer_table(infos)
    val = valuation_summary(sd, tech["performance"].get("beta_vs_nifty_2y"), settings, peers_df, growth_override)
    i = sd.info
    pack = {
        "meta": {
            "symbol": sd.symbol,
            "exchange_symbol": sd.yf_symbol,
            "company": sd.name,
            "sector": i.get("sector"),
            "industry": i.get("industry"),
            "website": i.get("website"),
            "employees": i.get("fullTimeEmployees"),
            "business_summary": (i.get("longBusinessSummary") or "")[:1500],
            "data_source": "DEMO (synthetic)" if sd.source == "demo" else "Yahoo Finance via yfinance + NSE index lists",
            "generated_at": datetime.now().isoformat(timespec="minutes"),
            "price_as_of": tech["performance"]["as_of"],
            "warnings": sd.warnings + fund.get("data_quality", []),
        },
        "scores": {
            "fundamental_health_0_100": fund["health"]["overall"],
            "valuation_0_100_higher_is_cheaper": val.get("valuation_score"),
            "technical_trend_minus100_100": tech["composite_trend_score"],
        },
        "technical": tech,
        "fundamentals": fund,
        "valuation": val,
        "peers": peers_df.to_dict(orient="records") if peers_df is not None else [],
        "recent_news_headlines": sd.news[:8],
    }
    pack["scores"]["overall_signal"] = overall_signal(fund["health"]["overall"], tech["composite_trend_score"], val.get("valuation_score"))

    # classification (sector / industry / cap bucket / indices)
    try:
        cls = classification_for(sd.symbol)
    except Exception:
        cls = {}
    pack["classification"] = cls

    # support/resistance zones + breakout patterns on 1H, 4H, 1D, 1W
    pack["breakouts"] = breakout_scan(sd)

    # exchange announcements, results calendar, corporate actions, press headlines
    if with_news:
        try:
            nb = news_bundle(sd.symbol, sd.name)
            pack["news"] = for_fact_pack(nb)
            if nb.get("nse_industry"):
                pack["classification"]["NSE industry"] = nb["nse_industry"]
        except Exception as exc:
            pack["news"] = {"fetch_errors": [str(exc)[:150]]}
    else:
        pack["news"] = {}

    # horizon-wise ratings (needs everything above)
    pack = _json_safe(pack)
    pack["horizon_view"] = _json_safe(horizon_ratings(pack, sd.daily))
    return pack


def fact_pack_json(pack: dict[str, Any], compact: bool = True) -> str:
    return json.dumps(pack, ensure_ascii=False, separators=(",", ":") if compact else None, indent=None if compact else 2)
