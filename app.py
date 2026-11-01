"""Indian Stock Analyst — Streamlit dashboard.

Run:  streamlit run app.py
"""
from __future__ import annotations

import hmac
import json
import os
import re
import time
from dataclasses import replace

import pandas as pd
import streamlit as st

from isa import charts
from isa.ai import generate_report, qa_messages
from isa.analysis import build_fact_pack, fact_pack_json, find_peers
from isa.config import DEMO_MODE, ValuationDefaults
from isa.data import get_batch_prices, get_peer_info, get_stock, resample_ohlcv
from isa.fundamentals import annual_table, quarterly_table
from isa.llm import PROVIDERS, LLMError, default_key, list_models, stream_chat
from isa.overview import breadth, category_snapshot
from isa.report import DISCLAIMER, to_html, to_markdown
from isa.classify import load_classification
from isa.horizons import FACTOR_LABELS
from isa.news import news_bundle
from isa.patterns import frames as tf_frames
from isa.universe import CATEGORIES, flat_categories, industries_from_nifty500, load_all_equities, load_index
from isa.valuation import pe_band, peer_table, valuation_summary

st.set_page_config(page_title="Indian Stock Analyst", page_icon="📈", layout="wide", initial_sidebar_state="expanded")


def _require_password() -> None:
    """If ISA_PASSWORD is set (e.g. when the service is reachable from other devices), ask for it once per session."""
    expected = os.getenv("ISA_PASSWORD", "")
    if not expected or st.session_state.get("_auth_ok"):
        return
    st.markdown("## 📈 Indian Stock Analyst")
    with st.form("login"):
        entered = st.text_input("Password", type="password")
        ok = st.form_submit_button("Open dashboard")
    if ok:
        if hmac.compare_digest(entered.encode(), expected.encode()):
            st.session_state["_auth_ok"] = True
            st.rerun()
        time.sleep(1)  # slow down guessing
        st.error("Wrong password.")
    st.stop()


_require_password()

st.markdown(
    """<style>
    .block-container{padding-top:1.4rem;padding-bottom:2rem}
    div[data-testid="stMetric"]{background:#1f1f1d;border:1px solid #2c2c29;border-radius:10px;padding:10px 14px}
    div[data-testid="stMetricLabel"] p{color:#a3a29a}
    div[data-testid="stMetricValue"]{font-size:1.45rem}
    .card{background:#1f1f1d;border:1px solid #2c2c29;border-radius:12px;padding:14px 18px;margin-bottom:12px}
    .verdict{font-size:1.05rem;border-left:4px solid #3987e5}
    .flag{color:#f2a0a0} .ok{color:#7fd67f}

    /* ---- tabs as buttons: wrap onto a second row instead of scrolling sideways ---- */
    [role="tablist"]{flex-wrap:wrap;gap:8px;overflow:visible !important;padding:4px 0 10px 0;border-bottom:1px solid #2c2c29}
    [data-testid="stTab"]{background:#1f1f1d;border:1px solid #3a3a36;border-radius:10px;padding:9px 16px !important;
        margin:0 !important;height:auto;min-height:40px;cursor:pointer;transition:background .15s,border-color .15s}
    [data-testid="stTab"] p{font-size:0.98rem !important;font-weight:600;color:#e4e3de;margin:0}
    [data-testid="stTab"]:hover{border-color:#3987e5;background:#1f2a3a}
    [data-testid="stTab"][aria-selected="true"]{background:#3987e5;border-color:#3987e5;box-shadow:0 2px 10px rgba(57,135,229,.35)}
    [data-testid="stTab"][aria-selected="true"] p{color:#ffffff}
    [data-testid="stTab"]:focus-visible{outline:2px solid #9ec5f4;outline-offset:2px}
    .react-aria-SelectionIndicator{display:none !important}

    /* ---- radio groups (sidebar views, timeframe pickers) as full-width buttons ---- */
    [data-testid="stElementContainer"]:has(> [data-testid="stRadio"]), [data-testid="stRadio"]{width:100% !important}
    [data-testid="stRadioGroup"]{gap:8px;width:100% !important}
    [data-testid="stRadioGroup"][aria-orientation="vertical"]{display:flex;flex-direction:column}
    [data-testid="stRadioGroup"] > div{width:100%}

    /* ---- horizon rating cards: responsive grid that wraps instead of squashing text ---- */
    .hz-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:10px;margin-bottom:10px}
    .hz-card{background:#1f1f1d;border:1px solid #2c2c29;border-radius:12px;padding:12px 10px;text-align:center}
    .hz-card .h{color:#a3a29a;font-size:.85rem} .hz-card .r{font-size:1.15rem;font-weight:700;white-space:nowrap}
    .hz-card .s{color:#a3a29a;font-size:.8rem}
    [data-testid="stRadioOption"]{width:100%;background:#1f1f1d;border:1px solid #3a3a36;border-radius:10px;
        padding:10px 14px;cursor:pointer;transition:background .15s,border-color .15s}
    [data-testid="stRadioOption"] > div > div:first-child{display:none}   /* hide the radio dot */
    [data-testid="stRadioOption"] p{font-size:1rem !important;font-weight:600;color:#e4e3de;margin:0}
    [data-testid="stRadioOption"]:hover{border-color:#3987e5;background:#1f2a3a}
    [data-testid="stRadioOption"][data-selected="true"]{background:#3987e5;border-color:#3987e5;box-shadow:0 2px 10px rgba(57,135,229,.35)}
    [data-testid="stRadioOption"][data-selected="true"] p{color:#ffffff}
    [data-testid="stRadioOption"]:has(input:focus-visible){outline:2px solid #9ec5f4;outline-offset:2px}
    </style>""",
    unsafe_allow_html=True,
)

# --------------------------------------------------------------------------- cached loaders
@st.cache_data(ttl=7 * 24 * 3600, show_spinner=False)
def cached_index(slug: str):
    return load_index(slug)


@st.cache_data(ttl=7 * 24 * 3600, show_spinner=False)
def cached_all_equities():
    return load_all_equities()


@st.cache_data(ttl=7 * 24 * 3600, show_spinner=False)
def cached_industries():
    return industries_from_nifty500()


@st.cache_data(ttl=1800, show_spinner=False)
def cached_stock(symbol: str):
    return get_stock(symbol)


@st.cache_data(ttl=1800, show_spinner=False)
def cached_batch(symbols: tuple[str, ...]):
    return get_batch_prices(list(symbols), period="1y")


@st.cache_data(ttl=12 * 3600, show_spinner=False)
def cached_peers(symbol: str):
    syms = find_peers(symbol)
    return peer_table(get_peer_info(syms + [symbol])) if syms else pd.DataFrame()


@st.cache_data(ttl=1800, show_spinner=False)
def cached_pack(symbol: str, rf: float, erp: float, tg: float, with_peers: bool, g_override: float | None):
    sd = cached_stock(symbol)
    settings = replace(ValuationDefaults(), risk_free=rf, equity_risk_premium=erp, terminal_growth=tg)
    return build_fact_pack(symbol, settings, with_peers=with_peers, sd=sd, growth_override=g_override)


def tag_badges(text: str) -> str:
    text = str(text)
    text = text.replace("[DATA]", ":green-badge[DATA]").replace("[INFERENCE]", ":blue-badge[INFERENCE]")
    return text.replace("[ASSUMPTION]", ":orange-badge[ASSUMPTION]")


def bullets(items, empty: str = "—") -> None:
    if not items:
        st.caption(empty)
        return
    if isinstance(items, str):
        st.markdown(tag_badges(items))
        return
    st.markdown("\n".join(f"- {tag_badges(i)}" for i in items))


def fmt(v, suffix: str = "", nd: int = 1, prefix: str = "") -> str:
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return "—"
    return f"{prefix}{v:,.{nd}f}{suffix}"


# --------------------------------------------------------------------------- sidebar
VIEWS = ["🔎 Stock analysis", "🗺️ Market overview", "📚 Stock universe"]
with st.sidebar:
    st.markdown("## 📈 Indian Stock Analyst")
    if DEMO_MODE:
        st.warning("DEMO MODE — synthetic data. Unset ISA_DEMO to use live market data.")
    view = st.radio("View", VIEWS, label_visibility="collapsed", key="view")

    st.markdown("### 🤖 AI engine")
    provider = st.selectbox("Provider", list(PROVIDERS), index=0, help="DeepSeek is cheapest; Gemini has a free tier; Claude is strongest at careful financial reasoning; Ollama runs locally for free.")
    p = PROVIDERS[provider]
    if p.note:
        st.caption(p.note)
    base_url = None
    if provider == "Custom (OpenAI-compatible)":
        base_url = st.text_input("Base URL", placeholder="https://your-endpoint/v1")
    elif provider.startswith("Ollama"):
        base_url = st.text_input("Ollama URL", value=p.base_url or "")
    api_key = ""
    if p.env_key:
        api_key = st.text_input(f"API key ({p.env_key})", value=default_key(provider), type="password",
                                help="Kept only in this browser session. Put it in .env to avoid re-typing.")
        if p.key_url:
            st.caption(f"[Get a {provider} key]({p.key_url})")
    mk = f"models::{provider}"
    if st.button("Load models", width="stretch", disabled=bool(p.env_key) and not api_key):
        try:
            st.session_state[mk] = list_models(provider, api_key, base_url)
            st.success(f"{len(st.session_state[mk])} models found")
        except LLMError as e:
            st.error(str(e))
    models = st.session_state.get(mk) or list(p.preferred[:1])
    model = st.selectbox("Model", models, index=0, accept_new_options=True,
                         help="Click 'Load models' to fetch the live list, or type a model id.")

    st.markdown("### ⚙️ Valuation assumptions")
    d = ValuationDefaults()
    rf = st.slider("Risk-free (10Y G-Sec) %", 5.0, 9.0, round(100 * d.risk_free, 2), 0.05) / 100
    erp = st.slider("Equity risk premium %", 4.0, 10.0, round(100 * d.equity_risk_premium, 2), 0.25) / 100
    tg = st.slider("Terminal growth %", 3.0, 8.0, round(100 * d.terminal_growth, 2), 0.25) / 100
    with_peers = st.toggle("Fetch peer comparison", value=True, help="Pulls ~8 same-industry peers from Yahoo (slower first time).")
    if st.button("♻️ Refresh market data", width="stretch"):
        st.cache_data.clear()
        st.rerun()
    st.caption(DISCLAIMER)


# --------------------------------------------------------------------------- category picker
@st.cache_data(ttl=24 * 3600, show_spinner=False)
def cached_classification() -> pd.DataFrame:
    return load_classification().copy()


CLASS_GROUPS = {"Sector (NSE)": "Sector", "Industry": "Industry", "Market-cap bucket": "Cap bucket"}


def category_picker(key: str) -> tuple[str, pd.DataFrame, str]:
    """Browse by index (market cap, sector indices, themes) or by classification (sector, industry, cap bucket)."""
    groups = list(CATEGORIES) + list(CLASS_GROUPS)
    c1, c2, c3 = st.columns([1, 2, 1])
    group = c1.selectbox("Browse by", groups, key=f"{key}_grp")
    if group in CLASS_GROUPS:
        cls = cached_classification()
        col = CLASS_GROUPS[group]
        if group == "Industry":
            sector = c3.selectbox("Within sector", ["All sectors"] + sorted(cls["Sector"].dropna().unique()), key=f"{key}_sec")
            if sector != "All sectors":
                cls = cls[cls["Sector"] == sector]
        counts = cls[col].value_counts()
        order = ["Large cap", "Mid cap", "Small cap", "Micro cap", "Unclassified"] if col == "Cap bucket" else sorted(counts.index)
        opts = [o for o in order if o in counts.index]
        name = c2.selectbox(group, opts, format_func=lambda o: f"{o} ({counts[o]})", key=f"{key}_{col}")
        sub = cls[cls[col] == name]
        grouping = "Industry" if col == "Sector" else "Sector"
        meta = pd.DataFrame({"Symbol": sub["Symbol"], "Company Name": sub["Company"], "Industry": sub[grouping]}).reset_index(drop=True)
        return name, meta, "classification"
    name = c2.selectbox("Category", list(CATEGORIES[group]), key=f"{key}_cat")
    df, src = cached_index(flat_categories()[name])
    return name, df, src


def with_classification(snap: pd.DataFrame) -> pd.DataFrame:
    cls = cached_classification()[["Symbol", "Sector", "Industry", "Cap bucket"]].rename(columns={"Industry": "Industry (detail)"})
    out = snap.merge(cls, on="Symbol", how="left")
    front = ["Symbol", "Company", "Sector", "Industry (detail)", "Cap bucket"]
    return out[[c for c in front if c in out] + [c for c in out.columns if c not in front and c != "Industry"]]


# =========================================================================== UNIVERSE
def universe_view() -> None:
    st.title("📚 Stock universe")
    st.caption("Every stock in the Nifty Total Market (~750: large, mid, small and micro caps) with NSE sector, finer industry, "
               "market-cap bucket and index memberships. Filter, then select a row to analyse it.")
    cls = cached_classification()
    c1, c2, c3, c4 = st.columns(4)
    sectors = c1.multiselect("Sector", sorted(cls["Sector"].dropna().unique()))
    pool = cls[cls["Sector"].isin(sectors)] if sectors else cls
    inds = c2.multiselect("Industry", sorted(pool["Industry"].dropna().unique()))
    caps = c3.multiselect("Market cap", ["Large cap", "Mid cap", "Small cap", "Micro cap"])
    idx_q = c4.text_input("Index contains", placeholder="e.g. Nifty IT, Defence")
    f = pool
    if inds:
        f = f[f["Industry"].isin(inds)]
    if caps:
        f = f[f["Cap bucket"].isin(caps)]
    if idx_q:
        f = f[f["Indices"].str.contains(idx_q, case=False, na=False)]
    m = st.columns(5)
    m[0].metric("Stocks", len(f))
    for i, cap in enumerate(["Large cap", "Mid cap", "Small cap", "Micro cap"]):
        m[i + 1].metric(cap, int((f["Cap bucket"] == cap).sum()))
    if len(f):
        tm = f.copy()
        tm["size"] = pd.to_numeric(tm["Market cap (₹ cr)"], errors="coerce").fillna(1000).clip(lower=100)
        import plotly.express as px

        fig = px.treemap(tm, path=[px.Constant("All"), "Sector", "Industry", "Symbol"], values="size", color="Cap bucket",
                         color_discrete_map={"Large cap": charts.S[0], "Mid cap": charts.S[2], "Small cap": charts.S[3],
                                             "Micro cap": charts.S[4], "Unclassified": charts.NEUTRAL, "(?)": charts.PANEL})
        fig.update_traces(marker=dict(line=dict(color=charts.SURFACE, width=1)), hovertemplate="%{label}<br>₹%{value:,.0f} cr<extra></extra>")
        charts._layout(fig, "Sector → industry → stock (size = market cap, colour = cap bucket)", height=560)
        fig.update_layout(margin=dict(l=4, r=4, t=48, b=4))
        st.plotly_chart(fig, width="stretch")
    ev = st.dataframe(f, hide_index=True, width="stretch", height=480, on_select="rerun", selection_mode="single-row",
                      column_config={"Market cap (₹ cr)": st.column_config.NumberColumn(format="%,.0f")})
    rows = ev.selection.rows if ev and hasattr(ev, "selection") else []
    if rows:
        sym = f.iloc[rows[0]]["Symbol"]
        st.button(f"🔎 Analyse {sym}", type="primary", on_click=lambda s=sym: st.session_state.update(symbol=s, view=VIEWS[0]))
    st.caption("Cap buckets follow index membership (Nifty 100 / Midcap 150 / Smallcap 250 / Microcap 250), which mirrors "
               "SEBI-AMFI market-cap ranks. Industry detail is from Yahoo; refresh with `python -m isa.cli refresh-classification`.")


# =========================================================================== MARKET OVERVIEW
def market_overview() -> None:
    st.title("🗺️ Market overview")
    name, meta, src = category_picker("ov")
    if src == "fallback" and not DEMO_MODE:
        st.warning("Could not reach NSE for the constituent list — showing the bundled Nifty 50 snapshot instead.")
    with st.spinner(f"Downloading 1-year prices for {len(meta)} stocks (one batched request)…"):
        try:
            prices = cached_batch(tuple(meta["Symbol"].tolist()))
        except Exception as e:
            st.error(f"Price download failed: {e}")
            return
    snap = category_snapshot(prices, meta)
    if not snap.empty:
        snap = with_classification(snap)
    if snap.empty:
        st.error("No price data returned. Yahoo may be rate-limiting — wait a minute and press Refresh.")
        return
    b = breadth(snap)
    m = st.columns(6)
    m[0].metric("Stocks", b["stocks"])
    m[1].metric("Advancers / decliners (1D)", f"{b['advancers_1d']} / {b['decliners_1d']}")
    m[2].metric("Above 200-DMA", f"{b['pct_above_200dma']:.0f}%")
    m[3].metric("In uptrend (daily)", f"{b['uptrend_share']:.0f}%")
    m[4].metric("Median 1M return", f"{b['median_1m']:+.1f}%")
    m[5].metric("Median 1Y return", f"{b['median_1y']:+.1f}%")
    period = st.segmented_control("Heatmap period", ["1D %", "1W %", "1M %", "3M %", "1Y %"], default="1D %")
    st.plotly_chart(charts.category_treemap(snap, period or "1D %"), width="stretch")
    c1, c2 = st.columns([3, 2])
    with c1:
        st.subheader(f"{name} — screener")
        st.caption("Select a row, then open the full analysis.")
        ev = st.dataframe(
            snap, hide_index=True, width="stretch", height=520, on_select="rerun", selection_mode="single-row",
            column_config={
                "1D %": st.column_config.NumberColumn(format="%+.2f"), "1W %": st.column_config.NumberColumn(format="%+.2f"),
                "1M %": st.column_config.NumberColumn(format="%+.2f"), "3M %": st.column_config.NumberColumn(format="%+.2f"),
                "1Y %": st.column_config.NumberColumn(format="%+.2f"),
                "RSI": st.column_config.ProgressColumn(min_value=0, max_value=100, format="%.0f"),
                "Trend score": st.column_config.ProgressColumn(min_value=-100, max_value=100, format="%+d"),
                "Price": st.column_config.NumberColumn(format="₹%.2f"),
            },
        )
        rows = ev.selection.rows if ev and hasattr(ev, "selection") else []
        if rows:
            sym = snap.iloc[rows[0]]["Symbol"]
            def _jump(s: str = sym) -> None:
                st.session_state["symbol"] = s
                st.session_state["view"] = VIEWS[0]

            st.button(f"🔎 Analyse {sym}", type="primary", on_click=_jump)
    with c2:
        st.plotly_chart(charts.returns_heatmap(snap, top=25), width="stretch")


# =========================================================================== STOCK ANALYSIS
def stock_picker() -> str | None:
    name, meta, _ = category_picker("st")
    syms = meta["Symbol"].tolist()
    names = meta["Company Name"].tolist() if "Company Name" in meta else syms
    labels = [f"{s} — {n}" for s, n in zip(syms, names)]
    c1, c2 = st.columns([2, 1])
    default = st.session_state.get("symbol")
    idx = syms.index(default) if default in syms else 0
    choice = c1.selectbox("Stock", range(len(syms)), index=idx, format_func=lambda i: labels[i], key=f"st_pick_{name}")
    typed = c2.text_input("…or any NSE symbol", value="" if default in syms else (default or ""), placeholder="e.g. IRCTC",
                          help="Overrides the list while filled. Clear it to go back to the list.").strip().upper()
    return typed or syms[choice]


def render_verdict(report: dict) -> None:
    v = report.get("verdict", {})
    stance = v.get("stance", "—")
    icon = {"Bullish": "🟢", "Bearish": "🔴"}.get(stance.split()[0] if stance else "", "🟡")
    st.markdown(f"<div class='card verdict'><b>{icon} {stance}</b> · conviction <b>{v.get('conviction', '—')}</b> · "
                f"{v.get('time_horizon', '')}<br>{v.get('one_liner', '')}</div>", unsafe_allow_html=True)


def render_report(report: dict, pack: dict, figs: list) -> None:
    if report.get("_parse_error"):
        st.warning("The model did not return valid JSON — showing raw output.")
        st.markdown(report.get("_raw", ""))
        return
    render_verdict(report)
    a = report.get("_audit", {})
    if a.get("figures_checked"):
        msg = f"Number audit: **{a['traced_pct']}%** of {a['figures_checked']} figures in the note trace back to the computed data."
        if a["unverified"]:
            st.warning(msg + " Not found in data (treat with suspicion): " + ", ".join(a["unverified"][:12]))
        else:
            st.success(msg)
    sug = report.get("investment_suggestion") or {}
    if sug:
        st.subheader(f"💡 Suggestion — best horizon: {sug.get('best_horizon', '—')}")
        st.markdown(tag_badges(sug.get("summary", "")))
        if sug.get("avoid_if"):
            st.markdown(f"**Doesn't apply if:** {tag_badges(sug['avoid_if'])}")
    hr = report.get("horizon_ratings") or []
    if hr:
        st.subheader("🎯 Ratings by horizon (model vs AI)")
        st.dataframe(pd.DataFrame([{"Horizon": h.get("horizon"), "Model": h.get("model_rating"), "AI": h.get("ai_rating"),
                                    "Conviction": h.get("conviction"), "Why": h.get("rationale"), "Plan": h.get("plan")} for h in hr]),
                     hide_index=True, width="stretch")
        changed = [h for h in hr if h.get("model_rating") and h.get("ai_rating") and h["model_rating"] != h["ai_rating"]]
        if changed:
            st.caption("The AI changed the model rating for: " + ", ".join(h["horizon"] for h in changed) + " — see 'Why'.")
    st.subheader("Executive summary")
    bullets(report.get("executive_summary"))
    st.markdown(f"**Business:** {report.get('business_overview', '—')}")
    c1, c2 = st.columns(2)
    h = report.get("company_health", {})
    with c1:
        st.subheader(f"Company health — {h.get('assessment', '—')}")
        st.markdown(tag_badges(h.get("summary", "")))
        st.markdown("**Strengths**")
        bullets(h.get("strengths"))
        st.markdown("**Red flags**")
        bullets(h.get("red_flags"), "None flagged")
    with c2:
        f = report.get("fundamentals", {})
        st.subheader("Fundamentals")
        for k in ("growth", "profitability", "balance_sheet", "cash_flow_and_earnings_quality", "recent_quarters"):
            if f.get(k):
                st.markdown(f"**{k.replace('_', ' ').capitalize()}** — {tag_badges(f[k])}")
    v = report.get("valuation", {})
    st.subheader(f"Valuation — {v.get('assessment', '—')}")
    st.markdown(tag_badges(v.get("summary", "")))
    st.markdown(f"**Market-implied expectations:** {tag_badges(v.get('market_implied_expectations', '—'))}")
    st.markdown(f"**Model fair-value range:** {v.get('model_fair_value_range', '—')}")
    bullets(v.get("key_assumptions"))
    t = report.get("technical", {})
    st.subheader("Technical view")
    st.markdown(tag_badges(t.get("summary", "")))
    tc = st.columns(3)
    for col, (k, lbl) in zip(tc, [("short_term", "Short term"), ("medium_term", "Medium term"), ("long_term", "Long term")]):
        col.markdown(f"<div class='card'><b>{lbl}</b><br>{t.get(k, '—')}</div>", unsafe_allow_html=True)
    kl = t.get("key_levels", {})
    st.markdown(f"**Support:** {' · '.join(kl.get('support', [])) or '—'}  \n**Resistance:** {' · '.join(kl.get('resistance', [])) or '—'}  \n**Invalidation:** {t.get('invalidation', '—')}")
    bullets(t.get("chart_observations"))
    lb = report.get("levels_and_breakouts") or []
    if lb:
        st.subheader("🧱 Levels & breakouts (AI read)")
        for t in lb:
            st.markdown(f"**{t.get('timeframe')}** — support {' · '.join(t.get('support_zones', [])) or '—'} | resistance "
                        f"{' · '.join(t.get('resistance_zones', [])) or '—'}  \n" + (f"Patterns: {'; '.join(t.get('patterns', []))}  \n" if t.get("patterns") else "")
                        + tag_badges(t.get("read", "")))
    nr = report.get("news_and_results") or {}
    if nr:
        st.subheader(f"📰 News & results — sentiment: {nr.get('news_sentiment', '—')}")
        st.markdown(f"**Latest results:** {tag_badges(nr.get('latest_results', '—'))}")
        bullets(nr.get("key_announcements"), "No material announcements")
        if nr.get("upcoming_events"):
            st.markdown("**Upcoming:** " + "; ".join(nr["upcoming_events"]))
    c1, c2 = st.columns(2)
    with c1:
        st.subheader("🐂 Bull case")
        bullets(report.get("bull_case"))
        st.subheader("⚡ Catalysts")
        bullets(report.get("catalysts"))
        st.subheader("🔄 What would change the view")
        bullets(report.get("what_would_change_my_mind"))
    with c2:
        st.subheader("🐻 Bear case")
        bullets(report.get("bear_case"))
        st.subheader("⚠️ Risks")
        bullets(report.get("risks"))
        st.subheader("📋 Quarterly monitoring checklist")
        bullets(report.get("monitoring_checklist"))
    with st.expander("Data gaps the AI flagged"):
        bullets(report.get("data_gaps"))
    m = pack["meta"]
    d1, d2 = st.columns(2)
    d1.download_button("⬇️ Download report (HTML with charts)", to_html(report, pack, figs), file_name=f"{m['symbol']}_research_note.html", mime="text/html", width="stretch")
    d2.download_button("⬇️ Download report (Markdown)", to_markdown(report, pack), file_name=f"{m['symbol']}_research_note.md", mime="text/markdown", width="stretch")


def stock_analysis() -> None:
    symbol = stock_picker()
    if not symbol:
        return
    symbol = re.sub(r"[^A-Z0-9&\-]", "", symbol)
    try:
        with st.spinner(f"Fetching {symbol} and computing analysis…"):
            sd = cached_stock(symbol)
            g_override = st.session_state.get(f"g_{symbol}")
            pack = cached_pack(symbol, rf, erp, tg, with_peers, g_override)
    except Exception as e:
        st.error(f"Could not analyse {symbol}: {e}")
        return
    st.session_state["symbol"] = symbol
    meta, sc, tech, fund, val = pack["meta"], pack["scores"], pack["technical"], pack["fundamentals"], pack["valuation"]
    perf = tech["performance"]

    st.markdown(f"## {meta['company']}  ·  `{meta['exchange_symbol']}`")
    cl = pack.get("classification") or {}
    chips = [f":blue-badge[{cl['Sector']}]" if cl.get("Sector") else "",
             f":violet-badge[{cl.get('Industry')}]" if cl.get("Industry") and cl.get("Industry") != cl.get("Sector") else "",
             f":gray-badge[NSE: {cl['NSE industry']}]" if cl.get("NSE industry") else "",
             f":orange-badge[{cl['Cap bucket']}]" if cl.get("Cap bucket") and cl.get("Cap bucket") != "Unclassified" else ""]
    st.markdown(" ".join(c for c in chips if c) or f"{meta.get('sector') or '—'} › {meta.get('industry') or '—'}")
    st.caption((f"Indices: {cl['Indices']} · " if cl.get("Indices") else "") + f"prices as of {meta['price_as_of']} · {meta['data_source']}")
    for w in meta.get("warnings", []):
        st.warning(w)
    m = st.columns(6)
    m[0].metric("Price", fmt(perf["last_close"], nd=2, prefix="₹"), fmt(perf["returns_pct"]["1D"], "%", 2))
    m[1].metric("Market cap", fmt(val["multiples"].get("market_cap_cr"), " cr", 0, "₹"))
    m[2].metric("P/E", fmt(val["multiples"].get("pe_ttm_or_latest_fy"), "x"))
    m[3].metric("P/B", fmt(val["multiples"].get("pb"), "x", 2))
    m[4].metric("52W range", f"{perf['low_52w']:,.0f} – {perf['high_52w']:,.0f}", f"{perf['pct_from_52w_high']:+.1f}% from high", delta_color="off")
    m[5].metric("1Y return", fmt(perf["returns_pct"]["1Y"], "%"), f"vs Nifty {perf.get('relative_strength_vs_nifty_pct', {}).get('1Y', 0):+.1f}pp" if perf.get("relative_strength_vs_nifty_pct") else None)

    g = st.columns(4)
    ov = sc["overall_signal"]
    g[0].plotly_chart(charts.gauge(ov.get("score"), f"Overall model signal · {ov.get('label')}"), width="stretch")
    g[1].plotly_chart(charts.gauge(sc["fundamental_health_0_100"], "Fundamental health"), width="stretch")
    g[2].plotly_chart(charts.gauge(sc["valuation_0_100_higher_is_cheaper"], "Valuation (higher = cheaper)"), width="stretch")
    g[3].plotly_chart(charts.gauge(sc["technical_trend_minus100_100"], "Technical trend", -100, 100), width="stretch")

    hv = pack.get("horizon_view") or {}
    hz = hv.get("horizons", {})
    if hz:
        st.markdown("### 🎯 Rating by investment horizon")
        icon = {"Strong Buy": "🟢", "Buy": "🟢", "Neutral": "⚪", "Sell": "🟠", "Strong Sell": "🔴"}
        cards = "".join(
            f"<div class='hz-card'><div class='h'>{hname}</div><div class='r'>{icon.get(h['rating'], '⚪')} {h['rating']}</div>"
            f"<div class='s'>score {h.get('score', '—')} · {h.get('confidence', '—')} confidence</div></div>"
            for hname, h in hz.items())
        st.markdown(f"<div class='hz-grid'>{cards}</div>", unsafe_allow_html=True)
        st.info(f"**{hv.get('suggestion', '')}** {hv.get('disclaimer', '')}")

    names = ["📊 Summary", "🎯 Horizons & plan", "🧱 Levels & breakouts", "📈 Technical", "🏦 Fundamentals", "💰 Valuation",
             "📰 News & results", "👥 Peers", "🤖 AI report", "💬 Ask AI", "🧾 Data"]
    T = dict(zip(names, st.tabs(names)))
    t_annual = annual_table(sd)
    figs_for_report: list = []

    # ---------------- summary
    with T["📊 Summary"]:
        c1, c2 = st.columns(2)
        comps = {k: v["score"] for k, v in fund["health"]["components"].items()}
        rfig = charts.radar(comps, "Fundamental health profile")
        c1.plotly_chart(rfig, width="stretch")
        rs = charts.relative_strength(sd.daily["Close"], sd.benchmark, symbol)
        c2.plotly_chart(rs, width="stretch")
        figs_for_report += [rfig, rs]
        c1, c2 = st.columns(2)
        rets = pd.Series({**perf["returns_pct"], **{f"{k} CAGR": v for k, v in perf["cagr_pct"].items()}})
        c1.plotly_chart(charts.signed_bars(rets, "Returns by period"), width="stretch")
        with c2:
            st.markdown("#### 🚩 Red flags (rule-based)")
            if fund["red_flags"]:
                for f_ in fund["red_flags"]:
                    st.markdown(f"<span class='flag'>⚠ {f_}</span>", unsafe_allow_html=True)
            else:
                st.markdown("<span class='ok'>✓ No rule-based red flags triggered</span>", unsafe_allow_html=True)
            st.markdown("#### 📌 Recent technical events")
            for e in tech["recent_events"][:6]:
                st.markdown(f"- `{e['date']}` {e['event']}")
            st.markdown("#### Risk")
            st.markdown(f"Volatility {perf['volatility_annual_pct']}% p.a. · beta vs Nifty {perf.get('beta_vs_nifty_2y', '—')} · "
                        f"max drawdown (5Y) {perf['max_drawdown_5y_pct']}% · avg traded value ₹{perf['avg_traded_value_20d_cr']} cr/day")
        if meta.get("business_summary"):
            with st.expander("Business description (Yahoo)"):
                st.write(meta["business_summary"])

    # ---------------- technical
    with T["📈 Technical"]:
        tf_opts = ["Daily", "Weekly", "Monthly"] + (["1 Hour", "4 Hour"] if sd.intraday is not None and len(sd.intraday) > 30 else [])
        c1, c2 = st.columns([1, 3])
        tf = c1.radio("Timeframe", tf_opts, horizontal=False)
        show = {k: True for k in c2.pills("Overlays", ["EMA20", "EMA50", "EMA200", "Supertrend", "Bollinger", "Levels", "RSI", "MACD"],
                                          default=["EMA20", "EMA50", "EMA200", "Supertrend", "Levels", "RSI", "MACD"], selection_mode="multi")}
        bars_n = c2.slider("Bars shown", 60, 1000, 250, 10)
        df_tf = {"Daily": sd.daily, "Weekly": resample_ohlcv(sd.daily, "W-FRI"), "Monthly": resample_ohlcv(sd.daily, "ME"),
                 "1 Hour": sd.intraday, "4 Hour": resample_ohlcv(sd.intraday, "4h") if sd.intraday is not None else None}[tf]
        from isa.technicals import support_resistance
        lv = tech["support_resistance"] if tf == "Daily" else support_resistance(df_tf, lookback=min(len(df_tf), 250), window=3 if tf != "Daily" else 5)
        pfig = charts.price_chart(df_tf, f"{symbol} · {tf}", intraday=tf in ("1 Hour", "4 Hour"), show=show, levels=lv, bars=bars_n)
        st.plotly_chart(pfig, width="stretch")
        if tf == "Daily":
            figs_for_report.insert(0, pfig)
        tm = charts.trend_matrix(tech["timeframes"])
        st.plotly_chart(tm, width="stretch")
        figs_for_report.append(tm)
        c1, c2, c3 = st.columns(3)
        with c1:
            st.markdown("#### Support / resistance (daily)")
            sr = pd.DataFrame([{"Type": "Resistance", **r} for r in tech["support_resistance"]["resistances"][::-1]] +
                              [{"Type": "Support", **s} for s in tech["support_resistance"]["supports"]])
            st.dataframe(sr, hide_index=True, width="stretch")
            st.caption(f"ATR(14) ₹{tech['atr14']} ({tech['atr_pct']}% of price) — a common stop distance is 1.5–2× ATR.")
        with c2:
            fib = tech["fibonacci_1y"]
            st.markdown(f"#### Fibonacci (1Y {fib['direction']})")
            st.dataframe(pd.DataFrame({"Level": list(fib["levels"]), "₹": list(fib["levels"].values())}), hide_index=True, width="stretch")
            st.caption(f"Swing high ₹{fib['swing_high']:,} · swing low ₹{fib['swing_low']:,}")
        with c3:
            ch = tech["regression_channel_6m"]
            st.markdown("#### 6-month regression channel")
            st.markdown(f"Slope **{ch['annualised_slope_pct']:+.1f}%/yr** (R² {ch['r_squared']})  \nPosition: **{ch['position_in_channel_sd']:+.2f} σ** from mid  \n"
                        f"Channel ₹{ch['lower']:,} – ₹{ch['mid']:,} – ₹{ch['upper']:,}")
            st.markdown("#### Last candle")
            st.markdown(", ".join(tech["candlestick_last_bar"]) or "No notable single-bar pattern")

    # ---------------- fundamentals
    with T["🏦 Fundamentals"]:
        if t_annual.empty:
            st.info("No annual statements available from Yahoo for this stock.")
        else:
            cr = t_annual.copy()
            for c in ("Revenue", "EBITDA", "Net profit", "CFO", "FCF", "Capex", "Debt", "Cash"):
                if c in cr:
                    cr[c] = cr[c] / 1e7
            c1, c2 = st.columns(2)
            f1 = charts.bars(cr, ["Revenue", "EBITDA", "Net profit"], "Revenue & profit (₹ crore)")
            c1.plotly_chart(f1, width="stretch")
            f2 = charts.lines(cr, ["OPM %", "EBITDA margin %", "NPM %"], "Margins")
            c2.plotly_chart(f2, width="stretch")
            c1, c2 = st.columns(2)
            f3 = charts.lines(cr, ["ROE %", "ROCE %", "ROA %"], "Return ratios")
            c1.plotly_chart(f3, width="stretch")
            f4 = charts.bars(cr, ["Net profit", "CFO", "FCF"], "Profit vs cash flow (₹ crore) — cash should track profit")
            c2.plotly_chart(f4, width="stretch")
            figs_for_report += [f1, f2, f3, f4]
            c1, c2 = st.columns(2)
            if "Debt/Equity" in cr:
                c1.plotly_chart(charts.lines(cr, ["Debt/Equity"], "Debt / equity", unit="x"), width="stretch")
            if "Receivable days" in cr:
                c2.plotly_chart(charts.lines(cr, ["Receivable days", "Inventory days"], "Working-capital days", unit=" days"), width="stretch")
        qt = quarterly_table(sd)
        if not qt.empty:
            st.markdown("### Quarterly trend")
            q = qt.copy()
            for c in ("Revenue", "Operating profit", "Net profit"):
                if c in q:
                    q[c] = q[c] / 1e7
            c1, c2 = st.columns(2)
            c1.plotly_chart(charts.bars(q, ["Revenue", "Net profit"], "Quarterly revenue & profit (₹ crore)"), width="stretch")
            if "Profit YoY %" in q and q["Profit YoY %"].notna().any():
                c2.plotly_chart(charts.signed_bars(q["Profit YoY %"], "Quarterly net profit YoY %"), width="stretch")
            elif "Profit QoQ %" in q:
                c2.plotly_chart(charts.signed_bars(q["Profit QoQ %"], "Quarterly net profit QoQ %"), width="stretch")
        st.markdown("### Quality scores")
        pio = fund["piotroski"]
        st.markdown(f"**Piotroski F-score: {pio.get('score', '—')} / {pio.get('evaluated', 9)} evaluated**  ·  "
                    f"Altman Z''-EM: **{fund['altman_z_em'].get('score', '—')}** ({fund['altman_z_em'].get('zone')})")
        cols = st.columns(3)
        for i, chk in enumerate(pio.get("checks", [])):
            icon = "✅" if chk["pass"] else "❌" if chk["pass"] is False else "➖"
            cols[i % 3].markdown(f"<div class='card'>{icon} {chk['test']}</div>", unsafe_allow_html=True)
        st.markdown("### Health score breakdown")
        st.dataframe(pd.DataFrame([{"Component": k, "Score (0-100)": v["score"], "Basis": v["basis"]} for k, v in fund["health"]["components"].items()]),
                     hide_index=True, width="stretch")
        with st.expander("Full annual table"):
            st.dataframe(t_annual.T.style.format(lambda v: f"{v:,.2f}" if isinstance(v, (int, float)) and abs(v) < 1e6 else (f"{v / 1e7:,.0f} cr" if isinstance(v, (int, float)) and pd.notna(v) else "—")), width="stretch")
        st.caption("Data gaps: " + " ".join(fund["data_gaps"]))

    # ---------------- valuation
    with T["💰 Valuation"]:
        mu = val["multiples"]
        m = st.columns(6)
        m[0].metric("P/E", fmt(mu.get("pe_ttm_or_latest_fy"), "x"))
        m[1].metric("EV/EBITDA", fmt(mu.get("ev_ebitda"), "x"))
        m[2].metric("P/B", fmt(mu.get("pb"), "x", 2))
        m[3].metric("PEG", fmt(mu.get("peg"), "", 2))
        m[4].metric("Earnings yield", fmt(mu.get("earnings_yield_pct"), "%", 2))
        m[5].metric("Dividend yield", fmt(mu.get("dividend_yield_pct"), "%", 2))
        if val.get("football_field"):
            ff = charts.football_field(val["football_field"], perf["last_close"])
            st.plotly_chart(ff, width="stretch")
            figs_for_report.append(ff)
        dcf = val.get("dcf", {})
        c1, c2 = st.columns([3, 2])
        with c1:
            if dcf.get("applicable"):
                st.plotly_chart(charts.dcf_heatmap(dcf["sensitivity"], perf["last_close"]), width="stretch")
            elif val.get("justified_pb", {}).get("applicable"):
                jp = val["justified_pb"]
                st.markdown(f"#### Justified P/B (lender)\nAvg ROE {jp['avg_roe_3y_pct']}% · Ke {jp['cost_of_equity_pct']}% · g {jp['sustainable_growth_pct']}% → "
                            f"justified P/B **{jp['justified_pb']}x** × BVPS ₹{jp['bvps']} = **₹{jp['fair_value_per_share']:,}** ({jp['upside_pct']:+.1f}% vs price)")
            else:
                st.info(f"DCF not shown: {dcf.get('reason')}")
        with c2:
            if dcf.get("applicable"):
                st.markdown("#### DCF (FCFF, 2-stage)")
                st.markdown(f"Base FCF ₹{dcf['base_fcf_cr']:,} cr · stage-1 growth {dcf['stage1_growth_pct']}% (hist. revenue CAGR {dcf['historical_revenue_cagr_pct']}%) · terminal g {dcf['terminal_growth_pct']}%")
                st.metric("Model fair value", fmt(dcf.get("fair_value_per_share"), nd=0, prefix="₹"), fmt(dcf.get("upside_pct"), "% vs price"))
                st.markdown(f"**Reverse DCF:** the current price implies **{dcf.get('implied_stage1_growth_pct', '—')}%** FCF growth for 5 years, "
                            f"then fading to {dcf['terminal_growth_pct']}%. Ask yourself if that is achievable.")
                new_g = st.slider("Try your own stage-1 growth %", 0.0, 40.0, float(dcf["stage1_growth_pct"]), 0.5, key=f"gs_{symbol}")
                if abs(new_g - dcf["stage1_growth_pct"]) > 0.01 and st.button("Recalculate DCF"):
                    st.session_state[f"g_{symbol}"] = new_g / 100
                    st.rerun()
            st.markdown("#### WACC build-up")
            st.dataframe(pd.DataFrame([(k.replace("_pct", " %").replace("_", " ").capitalize(), v) for k, v in val["wacc"].items()],
                                      columns=["Input", "Value"]), hide_index=True, width="stretch")
        band = pe_band(sd, t_annual)
        ph = val.get("pe_history")
        if ph and len(band):
            st.plotly_chart(charts.pe_band(band, ph["median"], ph["p25"], ph["p75"]), width="stretch")
            st.caption(f"Current P/E is {ph['current_vs_median_pct']:+.1f}% vs its {ph['months']}-month median. P/E uses the latest *reported* annual EPS, so it lags.")
        if val.get("street_targets_yahoo"):
            s = val["street_targets_yahoo"]
            st.caption(f"Street targets (Yahoo, {s.get('analysts')} analysts): low ₹{s['targetLowPrice']:,.0f} · mean ₹{s['targetMeanPrice']:,.0f} · high ₹{s['targetHighPrice']:,.0f}")

    # ---------------- horizons & plan
    with T["🎯 Horizons & plan"]:
        if not hz:
            st.info("Horizon ratings unavailable.")
        else:
            c1, c2 = st.columns(2)
            hb = charts.horizon_bars(hz)
            c1.plotly_chart(hb, width="stretch")
            hist = {n: h.get("historical", {}) for n, h in hz.items()}
            if any(isinstance(v, dict) and v.get("available") for v in hist.values()):
                c2.plotly_chart(charts.history_compare(hist), width="stretch")
                c2.caption(hv.get("historical_check", {}).get("method", ""))
            figs_for_report.append(hb)
            for hname, h in hz.items():
                if h.get("score") is None:
                    continue
                with st.expander(f"{hname} — {h['rating']} (score {h['score']}, {h['confidence']} confidence)", expanded=hname == hv.get("best_horizon")):
                    for n_ in h.get("notes", []):
                        st.warning(n_)
                    a, b = st.columns([3, 2])
                    a.markdown("**What drives this rating**")
                    a.dataframe(pd.DataFrame(h["drivers"]).rename(columns=str.capitalize), hide_index=True, width="stretch",
                                column_config={"Score": st.column_config.ProgressColumn(min_value=0, max_value=100, format="%d"),
                                               "Weight": st.column_config.NumberColumn(format="%.2f")})
                    hh = h.get("historical", {})
                    if hh.get("available"):
                        b.markdown("**Past behaviour after similar setups**")
                        b.markdown(f"Up **{hh['pct_positive_similar']}%** of the time (vs {hh['pct_positive_all_days']}% on all days) · "
                                   f"median {hh['median_return_similar_pct']:+.1f}% · worst-10% {hh['worst_10pct_similar_pct']:+.1f}% · "
                                   f"{hh['samples']} samples")
                        edge = hh["edge_pp"]
                        b.caption("✅ setup has had an edge" if edge >= 5 else "⚠️ setup has been a worse-than-average signal" if edge <= -5
                                  else "➖ no meaningful edge — treat the technical part of this rating with caution")
                    pl = h.get("plan")
                    if pl:
                        b.markdown(f"**Trade plan ({pl['timeframe_used']} levels)**  \n"
                                   f"Entry ₹{pl['entry_zone'][0]:,.0f}–{pl['entry_zone'][1]:,.0f} ({pl['entry_basis']})  \n"
                                   f"Stop ₹{pl['stop_loss']:,.0f} ({pl['stop_pct']:+.1f}%) · Targets " + " / ".join(f"₹{t:,.0f}" for t in pl["targets"])
                                   + (f"  \nReward/risk to T1: **{pl['reward_risk_t1']}×**" if pl.get("reward_risk_t1") else ""))
                        (b.success if pl.get("attractive") else b.warning)(pl["note"])

    # ---------------- levels & breakouts
    with T["🧱 Levels & breakouts"]:
        brk = pack.get("breakouts", {})
        fr = tf_frames(sd)
        avail = [k for k in ("1H", "4H", "1D", "1W") if brk.get(k, {}).get("available")]
        if not avail:
            st.info("Not enough price history for zone analysis.")
        else:
            st.caption("Zones are price bands built from repeated swing highs/lows (thicker = more touches, recent = stronger). "
                       "Patterns show status, trigger, measured-move target and the level that invalidates them.")
            summ = [{"Timeframe": brk[k]["timeframe"], "Bias": brk[k]["breakout_bias"],
                     "Nearest support": (f"₹{brk[k]['zones']['supports'][0]['low']:,.0f}–{brk[k]['zones']['supports'][0]['high']:,.0f}" if brk[k]["zones"].get("supports") else "—"),
                     "Nearest resistance": (f"₹{brk[k]['zones']['resistances'][0]['low']:,.0f}–{brk[k]['zones']['resistances'][0]['high']:,.0f}" if brk[k]["zones"].get("resistances") else "—"),
                     "Patterns": "; ".join(f"{p['pattern']} ({p['status']})" for p in brk[k]["patterns"]) or "none"} for k in avail]
            st.dataframe(pd.DataFrame(summ), hide_index=True, width="stretch")
            ktf = st.segmented_control("Timeframe", avail, default="1D" if "1D" in avail else avail[0], key=f"brk_tf_{symbol}") or avail[0]
            t_ = brk[ktf]
            nbars = st.slider("Bars shown", 60, 400, {"1H": 160, "4H": 140, "1D": 180, "1W": 156}[ktf], 10, key=f"brk_bars_{symbol}_{ktf}")
            zf = charts.zones_chart(fr[ktf], t_, f"{symbol} · {t_['timeframe']} — zones & patterns", intraday=ktf in ("1H", "4H"), bars=nbars)
            st.plotly_chart(zf, width="stretch")
            if ktf == "1D":
                figs_for_report.append(zf)
            c1, c2 = st.columns(2)
            zrows = [{"Type": "Resistance", "Zone ₹": f"{z['low']:,.2f} – {z['high']:,.2f}", "Touches": z["touches"], "Distance %": z["distance_pct"], "Last touch": z["last_touch"]}
                     for z in t_["zones"].get("resistances", [])[::-1]]
            if t_["zones"].get("inside"):
                zi = t_["zones"]["inside"]
                zrows.append({"Type": "Price inside", "Zone ₹": f"{zi['low']:,.2f} – {zi['high']:,.2f}", "Touches": zi["touches"], "Distance %": 0.0, "Last touch": zi["last_touch"]})
            zrows += [{"Type": "Support", "Zone ₹": f"{z['low']:,.2f} – {z['high']:,.2f}", "Touches": z["touches"], "Distance %": z["distance_pct"], "Last touch": z["last_touch"]}
                      for z in t_["zones"].get("supports", [])]
            c1.markdown("**Zones**")
            c1.dataframe(pd.DataFrame(zrows), hide_index=True, width="stretch")
            c2.markdown("**Patterns**")
            if t_["patterns"]:
                prow = [{"Pattern": p["pattern"], "Direction": p["direction"], "Status": p["status"], "Trigger ₹": p["trigger"],
                         "Target ₹": p["target"], "Invalidation ₹": p["invalidation"], "Note": p["note"]} for p in t_["patterns"]]
                c2.dataframe(pd.DataFrame(prow), hide_index=True, width="stretch")
            else:
                c2.caption("No pattern detected on this timeframe right now.")

    # ---------------- news & results
    with T["📰 News & results"]:
        try:
            nb = news_bundle(symbol, meta["company"])
        except Exception as e:
            nb = None
            st.error(f"News unavailable: {e}")
        if nb:
            for e_ in nb.get("errors", []):
                st.caption(f"⚠️ Could not fetch: {e_} (NSE sometimes blocks cloud servers; it usually works from a home/office connection)")
            m = st.columns(4)
            m[0].metric("Next results", nb.get("next_results_date") or "not announced",
                        f"in {nb['days_to_results']} days" if nb.get("days_to_results") is not None else None, delta_color="off")
            ht = nb.get("headline_tone", {})
            m[1].metric("Headlines (30 days)", len(nb.get("news", [])), f"{ht.get('positive', 0)} + / {ht.get('negative', 0)} −", delta_color="off")
            m[2].metric("Exchange filings (120 days)", len(nb.get("announcements", [])))
            uca = nb.get("upcoming_corporate_actions", [])
            m[3].metric("Upcoming corporate action", uca[0]["action"][:28] if uca else "none", uca[0]["ex_date"] if uca else None, delta_color="off")
            if nb.get("attention_items"):
                st.markdown("#### ⚠️ Filings that deserve attention")
                for a in nb["attention_items"]:
                    st.markdown(f"- `{a['date'][:10]}` **{', '.join(a['tags'])}** — {a['text'][:220]}" + (f" [PDF]({a['link']})" if a.get("link") else ""))
            c1, c2 = st.columns(2)
            with c1:
                st.markdown("#### 🏛️ Exchange announcements (NSE)")
                tags_all = sorted({t for a in nb.get("announcements", []) for t in a["tags"]})
                pick = st.multiselect("Filter by type", tags_all, default=[t for t in tags_all if t not in ("Other", "Routine compliance")], key=f"ann_{symbol}")
                for a in [a for a in nb.get("announcements", []) if set(a["tags"]) & set(pick)][:25]:
                    st.markdown(f"- `{a['date'][:10]}` *{', '.join(a['tags'])}* — {a['text'][:200]}" + (f" [PDF]({a['link']})" if a.get("link") else ""))
            with c2:
                st.markdown("#### 📰 Press headlines (Google News, India)")
                for n in nb.get("news", [])[:20]:
                    t_icon = "🟢" if n["tone"] > 0 else "🔴" if n["tone"] < 0 else "⚪"
                    st.markdown(f"- {t_icon} `{n['date']}` [{n['title']}]({n['link']}) — *{n['source']}*")
                st.caption("Tone dots are a rough keyword count. Headlines from aggregators often disagree on numbers — trust exchange filings first.")
            c1, c2 = st.columns(2)
            with c1:
                st.markdown("#### 📅 Board meetings")
                st.dataframe(pd.DataFrame(nb.get("board_meetings", [])[:8]), hide_index=True, width="stretch")
            with c2:
                st.markdown("#### 💸 Corporate actions")
                st.dataframe(pd.DataFrame(nb.get("corporate_actions", [])[:8]), hide_index=True, width="stretch")
            qt2 = quarterly_table(sd)
            if not qt2.empty:
                st.markdown("#### 📊 Latest quarterly results (₹ crore)")
                q2 = qt2.copy()
                for c in ("Revenue", "Operating profit", "Net profit"):
                    if c in q2:
                        q2[c] = q2[c] / 1e7
                st.dataframe(q2.T.style.format(lambda v: "—" if pd.isna(v) else f"{v:,.1f}"), width="stretch")
                st.caption("Quarterly numbers from Yahoo (it sometimes skips a quarter); growth is compared with the same quarter a year earlier by date.")

    # ---------------- peers
    with T["👥 Peers"]:
        peers = pd.DataFrame(pack.get("peers") or [])
        if peers.empty:
            st.info("No peers loaded. Enable 'Fetch peer comparison' in the sidebar (uses NSE's industry classification from the Nifty 500).")
        else:
            psc = charts.peer_scatter(peers, symbol)
            st.plotly_chart(psc, width="stretch")
            figs_for_report.append(psc)
            st.dataframe(peers, hide_index=True, width="stretch")
            pr = val.get("peers", {})
            if pr.get("peer_median"):
                st.caption("Peer medians: " + ", ".join(f"{k} {v}" for k, v in pr["peer_median"].items()))

    # ---------------- AI report
    rkey = f"report::{symbol}::{provider}::{model}"
    with T["🤖 AI report"]:
        st.caption("The AI receives only the computed fact pack (see the Data tab) and must tag every claim as "
                   "[DATA], [INFERENCE] or [ASSUMPTION]. A number audit then checks its figures against the data.")
        c1, c2 = st.columns([1, 3])
        go_ = c1.button("🤖 Generate AI analysis", type="primary", width="stretch")
        c2.markdown(f"Engine: **{provider}** · model **{model or '—'}**")
        if go_:
            if not model:
                st.error("Choose a model in the sidebar first.")
            else:
                with st.spinner(f"{provider} is writing the research note (usually 20–90 s)…"):
                    try:
                        st.session_state[rkey] = generate_report(pack, provider, api_key, model, base_url)
                    except LLMError as e:
                        st.error(str(e))
        if rkey in st.session_state:
            render_report(st.session_state[rkey], pack, figs_for_report)

    # ---------------- Ask AI
    with T["💬 Ask AI"]:
        hkey = f"chat::{symbol}"
        hist = st.session_state.setdefault(hkey, [])
        for msg in hist:
            st.chat_message(msg["role"]).markdown(tag_badges(msg["content"]))
        q = st.chat_input(f"Ask about {symbol} — e.g. 'Is the margin trend sustainable?'")
        if q:
            hist.append({"role": "user", "content": q})
            st.chat_message("user").markdown(q)
            with st.chat_message("assistant"):
                try:
                    ans = st.write_stream(stream_chat(provider, api_key, model, qa_messages(pack, hist, st.session_state.get(rkey)), base_url=base_url))
                    hist.append({"role": "assistant", "content": ans if isinstance(ans, str) else "".join(ans)})
                except LLMError as e:
                    st.error(str(e))

    # ---------------- raw data
    with T["🧾 Data"]:
        st.caption("This is exactly what the AI sees. Every chart and score is computed from it in Python.")
        st.download_button("⬇️ Fact pack (JSON)", fact_pack_json(pack, compact=False), file_name=f"{symbol}_fact_pack.json", mime="application/json")
        st.json(pack, expanded=False)
        if sd.news:
            st.markdown("#### Recent headlines (Yahoo)")
            for n in sd.news[:8]:
                st.markdown(f"- [{n['title']}]({n['url']}) — {n['publisher']} {n['date']}" if n.get("url") else f"- {n['title']}")


if view == VIEWS[0]:
    stock_analysis()
elif view == VIEWS[1]:
    market_overview()
else:
    universe_view()
