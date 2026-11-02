"""Flexible stock search: symbols, company names, old symbols, former names, common short forms and typos.

Index (refreshed weekly from NSE public files, cached on disk):
  * EQUITY_L.csv        — every NSE mainboard equity (symbol + company name)
  * SME_EQUITY_L.csv    — NSE Emerge (SME) equities
  * symbolchange.csv    — old symbol -> new symbol (e.g. BOROSIL -> BORORENEW)
  * namechange.csv      — former company names (e.g. Zomato Limited -> Eternal Limited)
  * a short list of everyday nicknames (SBI, HUL, L&T, RIL…)
"""
from __future__ import annotations

import difflib
import io
import re
from dataclasses import dataclass
from functools import lru_cache
from typing import Any

import pandas as pd
import requests

from .config import DATA_DIR, DEMO_MODE
from .data import _cached

NSE = "https://nsearchives.nseindia.com"
FILES = {
    "main": f"{NSE}/content/equities/EQUITY_L.csv",
    "sme": f"{NSE}/emerge/corporates/content/SME_EQUITY_L.csv",
    "symchange": f"{NSE}/content/equities/symbolchange.csv",
    "namechange": f"{NSE}/content/equities/namechange.csv",
}
_UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36",
       "Referer": "https://www.nseindia.com/"}

# Everyday names people type that neither the symbol nor the official name contains.
ALIASES = {
    "sbi": "SBIN", "state bank": "SBIN", "hul": "HINDUNILVR", "hindustan unilever": "HINDUNILVR", "ril": "RELIANCE",
    "l&t": "LT", "lnt": "LT", "l and t": "LT", "larsen": "LT", "m&m": "M&M", "mahindra": "M&M", "hdfc": "HDFCBANK",
    "icici": "ICICIBANK", "airtel": "BHARTIARTL", "zomato": "ETERNAL", "lic": "LICI", "bob": "BANKBARODA",
    "bank of baroda": "BANKBARODA", "policybazaar": "POLICYBZR", "policy bazaar": "POLICYBZR", "dmart": "DMART",
    "nykaa": "NYKAA", "paytm": "PAYTM", "hal": "HAL", "bel": "BEL", "maruti": "MARUTI", "kotak": "KOTAKBANK",
    "jio financial": "JIOFIN", "adani ports": "ADANIPORTS", "ultratech": "ULTRACEMCO", "bajaj finance": "BAJFINANCE",
    "bajaj finserv": "BAJAJFINSV", "dr reddy": "DRREDDY", "dr reddys": "DRREDDY", "sun pharma": "SUNPHARMA",
    "power grid": "POWERGRID", "coal india": "COALINDIA", "indigo": "INDIGO", "interglobe": "INDIGO", "tcs": "TCS",
}
STOP = {"limited", "ltd", "the", "co", "company", "corporation", "corp", "inc", "pvt", "private", "plc"}


def _norm(s: str) -> str:
    s = str(s).lower().replace("&", " and ")
    s = re.sub(r"[^a-z0-9 ]+", " ", s)
    return " ".join(w for w in s.split() if w not in STOP)


def _pretty(name: str) -> str:
    """NSE lists some names in capitals: 'BOROSIL RENEWABLES LIMITED' -> 'Borosil Renewables Limited'."""
    if not name.isupper():
        return name
    small = {"OF", "AND", "THE", "&", "FOR", "IN"}
    return " ".join(w.lower() if w in small else (w if len(w) <= 3 else w.capitalize()) for w in name.split())


def _sym(s: str) -> str:
    return re.sub(r"[^A-Z0-9]", "", str(s).upper())


@dataclass
class Match:
    symbol: str
    name: str
    board: str
    score: float
    reason: str

    @property
    def label(self) -> str:
        board = " · SME" if self.board == "SME" else ""
        hint = f" ({self.reason})" if self.reason.startswith(("old symbol", "formerly")) else ""
        return f"{self.symbol} — {self.name}{board}{hint}"


# --------------------------------------------------------------------------- index
def _download(url: str) -> pd.DataFrame:
    r = requests.get(url, headers=_UA, timeout=25)
    r.raise_for_status()
    df = pd.read_csv(io.StringIO(r.content.decode("latin-1")))
    df.columns = [c.strip().upper().replace("_", " ") for c in df.columns]
    return df


def _build() -> dict[str, Any]:
    rows: dict[str, dict[str, str]] = {}
    try:
        m = _download(FILES["main"])
        for _, r in m.iterrows():
            rows[str(r["SYMBOL"]).strip()] = {"name": str(r["NAME OF COMPANY"]).strip(), "board": "Mainboard"}
    except Exception:
        pass
    try:
        s = _download(FILES["sme"])
        for _, r in s.iterrows():
            rows.setdefault(str(r["SYMBOL"]).strip(), {"name": str(r["NAME OF COMPANY"]).strip(), "board": "SME"})
    except Exception:
        pass
    if not rows:  # offline: whatever we ship
        for f in ("classification.csv", "fallback_nifty50.csv"):
            p = DATA_DIR / f
            if p.exists():
                df = pd.read_csv(p)
                for _, r in df.iterrows():
                    rows.setdefault(str(r["Symbol"]), {"name": str(r.get("Company", r.get("Company Name", r["Symbol"]))), "board": "Mainboard"})
    old_syms: dict[str, str] = {}
    try:
        sc = _download(FILES["symchange"])
        sc["EFFECTIVE DATE"] = pd.to_datetime(sc["EFFECTIVE DATE"], errors="coerce", format="mixed")
        for _, r in sc.sort_values("EFFECTIVE DATE").iterrows():
            old, new = str(r["OLD SYMBOL"]).strip(), str(r["NEW SYMBOL"]).strip()
            old_syms[old] = new
        # follow chains (A -> B -> C) and keep only targets that still trade
        for old in list(old_syms):
            seen, cur = {old}, old_syms[old]
            while cur in old_syms and old_syms[cur] not in seen:
                seen.add(cur)
                cur = old_syms[cur]
            old_syms[old] = cur
        old_syms = {o: n for o, n in old_syms.items() if n in rows and o not in rows}
    except Exception:
        pass
    old_names: list[tuple[str, str]] = []
    try:
        nc = _download(FILES["namechange"])
        for _, r in nc.iterrows():
            sym = str(r["SYMBOL"]).strip()
            if sym in rows:
                old_names.append((str(r["OLD NAME OF THE COMPANY"]).strip(), sym))
    except Exception:
        pass
    return {"rows": rows, "old_syms": old_syms, "old_names": old_names}


@lru_cache(maxsize=1)
def _index() -> dict[str, Any]:
    if DEMO_MODE:
        df = pd.read_csv(DATA_DIR / "fallback_nifty50.csv")
        rows = {r["Symbol"]: {"name": r["Company Name"], "board": "Mainboard"} for _, r in df.iterrows()}
        data = {"rows": rows, "old_syms": {}, "old_names": []}
    else:
        data = _cached("search:index:v1", 7 * 24 * 3600, _build)
    rows = data["rows"]
    entries = [(sym, v["name"], v["board"], _sym(sym), _norm(v["name"])) for sym, v in rows.items()]
    old_names = [(_norm(n), sym, n) for n, sym in data["old_names"]]
    aliases = {k: v for k, v in ALIASES.items() if v in rows}
    popular: set[str] = set()
    try:  # Nifty Total Market members: used only to break ties in favour of the stock people usually mean
        popular = set(pd.read_csv(DATA_DIR / "classification.csv")["Symbol"].astype(str))
    except Exception:
        pass
    return {"rows": rows, "entries": entries, "old_syms": {_sym(k): v for k, v in data["old_syms"].items()},
            "old_names": old_names, "aliases": aliases, "popular": popular}


def refresh() -> None:
    from .data import _cache_forget

    _cache_forget("search:index:v1")
    _index.cache_clear()


# --------------------------------------------------------------------------- search
def search(query: str, limit: int = 8) -> list[Match]:
    q_raw = (query or "").strip()
    if not q_raw:
        return []
    idx = _index()
    rows = idx["rows"]
    qs, qn = _sym(q_raw), _norm(q_raw)
    qtok = qn.split()
    best: dict[str, Match] = {}

    def add(sym: str, score: float, reason: str) -> None:
        if sym not in rows:
            return
        if sym not in best or score > best[sym].score:
            best[sym] = Match(sym, _pretty(rows[sym]["name"]), rows[sym]["board"], round(score, 1), reason)

    # 1) exact symbol, nickname, old symbol
    for sym, name, board, s_norm, n_norm in idx["entries"]:
        if qs and s_norm == qs:
            add(sym, 100, "symbol")
    alias = idx["aliases"].get(q_raw.lower()) or idx["aliases"].get(qn)
    if alias:
        add(alias, 98, "common name")
    if qs in idx["old_syms"]:
        add(idx["old_syms"][qs], 97, f"old symbol {q_raw.upper()}")

    # 2) prefixes, words, substrings
    for sym, name, board, s_norm, n_norm in idx["entries"]:
        if not qs:
            continue
        if s_norm.startswith(qs) and len(qs) >= 2:
            add(sym, 90 - min(10, len(s_norm) - len(qs)), "symbol starts with")
        if qn and n_norm.startswith(qn):
            add(sym, 89 - min(8, (len(n_norm) - len(qn)) / 6), "name starts with")
        elif qtok and all(any(w.startswith(t) for w in n_norm.split()) for t in qtok):
            add(sym, 82 - min(8, (len(n_norm) - len(qn)) / 8), "name contains")
        elif len(qn) >= 3 and qn in n_norm:
            add(sym, 76, "name contains")
    for n_norm, sym, original in idx["old_names"]:
        if qn and (n_norm.startswith(qn) or (qtok and all(any(w.startswith(t) for w in n_norm.split()) for t in qtok))):
            add(sym, 80, f"formerly {original}")

    # 3) typo tolerance (only if nothing solid was found)
    if not best or max(m.score for m in best.values()) < 80:
        for sym, name, board, s_norm, n_norm in idx["entries"]:
            first = n_norm.split()[0] if n_norm else ""
            r_sym = difflib.SequenceMatcher(None, s_norm.lower(), qs.lower()).ratio() if qs else 0
            r_name = max((difflib.SequenceMatcher(None, a, b).ratio()
                          for a, b in [(n_norm[: len(qn) + 2], qn), (first, qtok[0] if len(qtok) == 1 else "")] if a and b),
                         default=0)
            r = max(r_sym + 0.02, r_name)  # a near-miss on the ticker itself is the stronger signal
            if r >= 0.78:
                add(sym, 50 + 25 * min(r, 1), "similar spelling")
    pop = idx["popular"]
    out = sorted(best.values(), key=lambda m: (-m.score, m.symbol not in pop, m.board != "Mainboard", len(m.symbol)))
    return out[:limit]


def resolve(query: str) -> Match | None:
    """Best match when it is unambiguous enough to act on directly (used by the CLI)."""
    res = search(query, limit=3)
    if not res:
        return None
    if res[0].score >= 98 or (len(res) == 1 and res[0].score >= 70) or (len(res) > 1 and res[0].score - res[1].score >= 12):
        return res[0]
    return None
