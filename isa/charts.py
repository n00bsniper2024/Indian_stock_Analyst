"""Plotly figures. Palette = validated dark-mode categorical slots; up/down use the fixed
status pair (green good / red critical) because that is the market convention, always
paired with labels or signs so colour never carries meaning alone. No dual-axis charts.
"""
from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from .technicals import add_indicators

SURFACE = "#1a1a19"
PANEL = "#222220"
GRID = "#33332f"
TEXT = "#f0efec"
MUTED = "#a3a29a"
S = ["#3987e5", "#d95926", "#199e70", "#c98500", "#d55181", "#008300", "#9085e9", "#e66767"]
UP, DOWN, NEUTRAL, WARN = "#0ca30c", "#d03b3b", "#383835", "#fab219"
FONT = "Inter, Segoe UI, system-ui, sans-serif"


def _layout(fig: go.Figure, title: str | None = None, height: int = 380, legend: bool = True) -> go.Figure:
    fig.update_layout(
        title=dict(text=title, font=dict(size=15, color=TEXT), x=0.01, xanchor="left") if title else None,
        paper_bgcolor=SURFACE, plot_bgcolor=SURFACE, font=dict(family=FONT, color=TEXT, size=12),
        height=height, margin=dict(l=10, r=10, t=48 if title else 16, b=10), showlegend=legend,
        legend=dict(orientation="h", yanchor="top", y=-0.12, xanchor="left", x=0, bgcolor="rgba(0,0,0,0)", font=dict(color=MUTED)),
        hoverlabel=dict(bgcolor=PANEL, font=dict(color=TEXT, family=FONT), bordercolor=GRID),
        bargap=0.25,
    )
    fig.update_xaxes(gridcolor=GRID, zerolinecolor=GRID, linecolor=GRID, tickfont=dict(color=MUTED))
    fig.update_yaxes(gridcolor=GRID, zerolinecolor=GRID, linecolor=GRID, tickfont=dict(color=MUTED))
    return fig


# =========================================================================== price chart
def price_chart(df: pd.DataFrame, title: str, intraday: bool = False, show: dict[str, bool] | None = None,
                levels: dict[str, Any] | None = None, bars: int = 300) -> go.Figure:
    show = show or {}
    x = add_indicators(df).iloc[-bars:]
    rows = ["price", "volume"] + [k for k in ("RSI", "MACD") if show.get(k, True)]
    heights = {"price": 0.55, "volume": 0.13, "RSI": 0.16, "MACD": 0.16}
    fig = make_subplots(rows=len(rows), cols=1, shared_xaxes=True, vertical_spacing=0.025,
                        row_heights=[heights[r] for r in rows])
    fig.add_trace(go.Candlestick(x=x.index, open=x["Open"], high=x["High"], low=x["Low"], close=x["Close"], name="Price",
                                 increasing=dict(line=dict(color=UP, width=1), fillcolor=UP),
                                 decreasing=dict(line=dict(color=DOWN, width=1), fillcolor=DOWN)), 1, 1)
    for i, n in enumerate((20, 50, 200)):
        if show.get(f"EMA{n}", True) and x[f"EMA{n}"].notna().any():
            fig.add_trace(go.Scatter(x=x.index, y=x[f"EMA{n}"], name=f"EMA {n}", line=dict(color=S[[0, 3, 6][i]], width=1.6)), 1, 1)
    if show.get("Bollinger", False):
        fig.add_trace(go.Scatter(x=x.index, y=x["BB_up"], name="Bollinger", line=dict(color=MUTED, width=1, dash="dot")), 1, 1)
        fig.add_trace(go.Scatter(x=x.index, y=x["BB_low"], name="Bollinger low", line=dict(color=MUTED, width=1, dash="dot"),
                                 fill="tonexty", fillcolor="rgba(163,162,154,0.06)", showlegend=False), 1, 1)
    if show.get("Supertrend", True):
        st_up = x["Supertrend"].where(x["ST_dir"] > 0)
        st_dn = x["Supertrend"].where(x["ST_dir"] < 0)
        fig.add_trace(go.Scatter(x=x.index, y=st_up, name="Supertrend ↑", line=dict(color=UP, width=1.2, dash="dash")), 1, 1)
        fig.add_trace(go.Scatter(x=x.index, y=st_dn, name="Supertrend ↓", line=dict(color=DOWN, width=1.2, dash="dash")), 1, 1)
    if levels and show.get("Levels", True):
        for lv in levels.get("supports", []):
            fig.add_hline(y=lv["level"], line=dict(color=UP, width=1, dash="dot"), row=1, col=1,
                          annotation_text=f"S ₹{lv['level']:,.0f} ({lv['touches']}×)", annotation_font=dict(color=MUTED, size=10),
                          annotation_position="bottom right")
        for lv in levels.get("resistances", []):
            fig.add_hline(y=lv["level"], line=dict(color=DOWN, width=1, dash="dot"), row=1, col=1,
                          annotation_text=f"R ₹{lv['level']:,.0f} ({lv['touches']}×)", annotation_font=dict(color=MUTED, size=10),
                          annotation_position="top right")
    vol_colors = np.where(x["Close"] >= x["Open"], UP, DOWN)
    fig.add_trace(go.Bar(x=x.index, y=x["Volume"], marker_color=vol_colors, opacity=0.55, name="Volume", showlegend=False), 2, 1)
    fig.add_trace(go.Scatter(x=x.index, y=x["VolSMA20"], line=dict(color=S[0], width=1.2), name="Vol 20 avg", showlegend=False), 2, 1)
    r = 3
    if "RSI" in rows:
        fig.add_trace(go.Scatter(x=x.index, y=x["RSI"], name="RSI 14", line=dict(color=S[6], width=1.6), showlegend=False), r, 1)
        for lvl in (70, 30):
            fig.add_hline(y=lvl, line=dict(color=GRID, width=1, dash="dash"), row=r, col=1)
        fig.update_yaxes(range=[0, 100], title_text="RSI", row=r, col=1)
        r += 1
    if "MACD" in rows:
        fig.add_trace(go.Bar(x=x.index, y=x["MACD_hist"], marker_color=np.where(x["MACD_hist"] >= 0, UP, DOWN), opacity=0.6, name="MACD hist", showlegend=False), r, 1)
        fig.add_trace(go.Scatter(x=x.index, y=x["MACD"], line=dict(color=S[0], width=1.4), name="MACD", showlegend=False), r, 1)
        fig.add_trace(go.Scatter(x=x.index, y=x["MACD_signal"], line=dict(color=S[1], width=1.4), name="Signal", showlegend=False), r, 1)
        fig.update_yaxes(title_text="MACD", row=r, col=1)
    fig.update_yaxes(title_text="Vol", row=2, col=1)
    breaks = [dict(bounds=["sat", "mon"])]
    if intraday:
        breaks.append(dict(bounds=[15.5, 9.25], pattern="hour"))
    fig.update_xaxes(rangebreaks=breaks, rangeslider_visible=False)
    _layout(fig, title, height=660 if len(rows) == 4 else 580)
    fig.update_layout(hovermode="x unified", legend=dict(yanchor="bottom", y=1.01, xanchor="right", x=1), margin=dict(t=70))
    return fig


def trend_matrix(timeframes: list[dict[str, Any]]) -> go.Figure:
    tfs = [t for t in timeframes if t.get("available")]
    comps = list(dict.fromkeys(k for t in tfs for k in t["components"]))
    cols = comps + ["Trend score"]
    z, text = [], []
    for t in tfs:
        zr, tr = [], []
        for c in comps:
            v = t["components"].get(c)
            zr.append(None if v is None else (1 if v > 0 else -1))
            tr.append("—" if v is None else ("✓ yes" if v > 0 else "✗ no"))
        zr.append(t["score"] / 100)
        tr.append(f"{t['score']:+d}<br>{t['trend']}")
        z.append(zr)
        text.append(tr)
    fig = go.Figure(go.Heatmap(z=z, x=cols, y=[t["timeframe"] for t in tfs], text=text, texttemplate="%{text}",
                               textfont=dict(size=11, color=TEXT), zmin=-1, zmax=1, xgap=2, ygap=2, showscale=False,
                               colorscale=[[0, DOWN], [0.5, NEUTRAL], [1, UP]], hovertemplate="%{y} · %{x}: %{text}<extra></extra>"))
    fig.update_yaxes(autorange="reversed")
    return _layout(fig, "Multi-timeframe trend matrix", height=90 + 52 * len(tfs), legend=False)


def gauge(value: float | None, title: str, lo: float = 0, hi: float = 100, suffix: str = "") -> go.Figure:
    v = 0 if value is None else value
    span = hi - lo
    steps = [dict(range=[lo, lo + span * 0.3], color="#3a2120"), dict(range=[lo + span * 0.3, lo + span * 0.6], color="#2c2c29"),
             dict(range=[lo + span * 0.6, hi], color="#1d3320")]
    bar = UP if (v - lo) / span >= 0.6 else DOWN if (v - lo) / span < 0.3 else WARN
    fig = go.Figure(go.Indicator(mode="gauge" if value is None else "gauge+number", value=v,
                                 number=dict(suffix=suffix, font=dict(size=34, color=TEXT)),
                                 title=dict(text=title, font=dict(size=13, color=MUTED)),
                                 gauge=dict(axis=dict(range=[lo, hi], tickcolor=MUTED, tickfont=dict(color=MUTED, size=10)),
                                            bar=dict(color=bar if value is not None else NEUTRAL, thickness=0.28), bgcolor=SURFACE, borderwidth=0, steps=steps)))
    if value is None:
        fig.add_annotation(text="n/a", x=0.5, y=0.2, showarrow=False, font=dict(size=24, color=MUTED))
    return _layout(fig, None, height=210, legend=False).update_layout(margin=dict(l=34, r=34, t=40, b=0))


def radar(components: dict[str, float | None], title: str = "Health profile") -> go.Figure:
    items = [(k, v) for k, v in components.items() if v is not None]
    if len(items) < 3:
        return _layout(go.Figure(), title + " (insufficient data)", height=360, legend=False)
    k, v = zip(*items)
    fig = go.Figure(go.Scatterpolar(r=list(v) + [v[0]], theta=list(k) + [k[0]], fill="toself", line=dict(color=S[0], width=2),
                                    fillcolor="rgba(57,135,229,0.25)", marker=dict(size=8), hovertemplate="%{theta}: %{r:.0f}/100<extra></extra>"))
    fig.update_layout(polar=dict(bgcolor=SURFACE, radialaxis=dict(range=[0, 100], gridcolor=GRID, tickfont=dict(color=MUTED, size=9)),
                                 angularaxis=dict(gridcolor=GRID, tickfont=dict(color=TEXT, size=11))))
    return _layout(fig, title, height=360, legend=False)


# =========================================================================== fundamentals
def bars(table: pd.DataFrame, cols: list[str], title: str, unit: str = "₹ cr") -> go.Figure:
    fig = go.Figure()
    for i, c in enumerate([c for c in cols if c in table]):
        y = table[c]
        fig.add_trace(go.Bar(x=table.index, y=y, name=c, marker=dict(color=S[i], cornerradius=4),
                             text=[f"{v:,.0f}" if pd.notna(v) else "" for v in y], textposition="outside", textfont=dict(color=MUTED, size=10),
                             hovertemplate=f"%{{x}} · {c}: %{{y:,.1f}} {unit}<extra></extra>"))
    fig.update_layout(barmode="group", bargroupgap=0.08)
    fig.update_yaxes(title_text=unit)
    return _layout(fig, title, height=340, legend=len(cols) > 1)


def lines(table: pd.DataFrame, cols: list[str], title: str, unit: str = "%") -> go.Figure:
    fig = go.Figure()
    for i, c in enumerate([c for c in cols if c in table]):
        fig.add_trace(go.Scatter(x=table.index, y=table[c], name=c, mode="lines+markers", line=dict(color=S[i], width=2),
                                 marker=dict(size=8, line=dict(color=SURFACE, width=2)),
                                 hovertemplate=f"%{{x}} · {c}: %{{y:.1f}}{unit}<extra></extra>"))
    fig.update_yaxes(title_text=unit, rangemode="tozero")
    return _layout(fig, title, height=340, legend=len(cols) > 1)


def signed_bars(series: pd.Series, title: str, unit: str = "%") -> go.Figure:
    s = series.dropna()
    fig = go.Figure(go.Bar(x=s.index.astype(str), y=s.values, marker=dict(color=np.where(s.values >= 0, UP, DOWN), cornerradius=4),
                           text=[f"{v:+.1f}{unit}" for v in s.values], textposition="outside", textfont=dict(color=MUTED, size=11),
                           hovertemplate="%{x}: %{y:+.2f}" + unit + "<extra></extra>"))
    fig.add_hline(y=0, line=dict(color=GRID, width=1))
    return _layout(fig, title, height=300, legend=False)


# =========================================================================== valuation
def dcf_heatmap(sens: dict[str, Any], price: float) -> go.Figure:
    vals = np.array(sens["values"], dtype=float)
    up = 100 * (vals / price - 1)
    text = [[f"₹{v:,.0f}<br>{u:+.0f}%" if np.isfinite(v) else "n/a" for v, u in zip(rv, ru)] for rv, ru in zip(vals, up)]
    lim = float(np.nanmax(np.abs(up))) if np.isfinite(up).any() else 50
    fig = go.Figure(go.Heatmap(z=up, x=[f"g {g}%" for g in sens["terminal_g_pct"]], y=[f"WACC {w}%" for w in sens["wacc_pct"]],
                               text=text, texttemplate="%{text}", textfont=dict(size=11, color=TEXT), zmid=0, zmin=-lim, zmax=lim,
                               colorscale=[[0, DOWN], [0.5, NEUTRAL], [1, UP]], xgap=2, ygap=2,
                               colorbar=dict(title=dict(text="vs price %", font=dict(color=MUTED)), tickfont=dict(color=MUTED)),
                               hovertemplate="%{y}, %{x}: %{text}<extra></extra>"))
    fig.update_yaxes(autorange="reversed")
    return _layout(fig, "DCF sensitivity — fair value per share (WACC × terminal growth)", height=360, legend=False)


def football_field(ff: list[dict[str, Any]], price: float) -> go.Figure:
    fig = go.Figure()
    for i, r in enumerate(ff):
        fig.add_trace(go.Bar(y=[r["method"]], x=[r["high"] - r["low"]], base=[r["low"]], orientation="h",
                             marker=dict(color=S[i % len(S)], cornerradius=4), showlegend=False,
                             text=f"₹{r['low']:,.0f} – ₹{r['high']:,.0f}", textposition="outside", cliponaxis=False,
                             textfont=dict(color=MUTED, size=11),
                             hovertemplate=f"{r['method']}: ₹{r['low']:,.0f} – ₹{r['high']:,.0f}<extra></extra>"))
    fig.add_vline(x=price, line=dict(color=TEXT, width=2, dash="dash"), annotation_text=f"Price ₹{price:,.0f}",
                  annotation_font=dict(color=TEXT), annotation_position="top")
    lo = min([r["low"] for r in ff] + [price])
    hi = max([r["high"] for r in ff] + [price])
    fig.update_yaxes(autorange="reversed")
    fig.update_xaxes(title_text="₹ per share", range=[max(0, lo - 0.05 * (hi - lo)), hi + 0.25 * (hi - lo)])
    return _layout(fig, "Valuation football field", height=110 + 52 * len(ff), legend=False)


def pe_band(band: pd.DataFrame, median: float, p25: float, p75: float) -> go.Figure:
    fig = go.Figure()
    fig.add_hrect(y0=p25, y1=p75, fillcolor="rgba(57,135,229,0.12)", line_width=0)
    fig.add_trace(go.Scatter(x=band.index, y=band["PE"], name="P/E", line=dict(color=S[0], width=2),
                             hovertemplate="%{x|%b %Y}: %{y:.1f}x<extra></extra>"))
    fig.add_hline(y=median, line=dict(color=S[1], width=1.5, dash="dash"), annotation_text=f"median {median:.1f}x",
                  annotation_font=dict(color=MUTED))
    fig.update_yaxes(title_text="P/E (x)")
    return _layout(fig, "Historical P/E band (shaded = 25th–75th percentile)", height=320, legend=False)


def peer_scatter(peers: pd.DataFrame, symbol: str) -> go.Figure:
    d = peers.dropna(subset=["P/E", "ROE %"]).copy()
    d = d[(d["P/E"] > 0) & (d["P/E"] < 200)]
    if d.empty:
        return _layout(go.Figure(), "Peer map (insufficient data)", height=360, legend=False)
    size = d["Mcap (₹ cr)"].fillna(d["Mcap (₹ cr)"].median() if d["Mcap (₹ cr)"].notna().any() else 1)
    size = 14 + 36 * np.sqrt(size / size.max())
    me = d["Symbol"] == symbol
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=d.loc[~me, "P/E"], y=d.loc[~me, "ROE %"], mode="markers+text", text=d.loc[~me, "Symbol"],
                             textposition="top center", textfont=dict(color=MUTED, size=10), name="Peers",
                             marker=dict(size=size[~me], color=S[0], opacity=0.75, line=dict(color=SURFACE, width=2)),
                             hovertemplate="%{text}: P/E %{x:.1f}x, ROE %{y:.1f}%<extra></extra>"))
    fig.add_trace(go.Scatter(x=d.loc[me, "P/E"], y=d.loc[me, "ROE %"], mode="markers+text", text=d.loc[me, "Symbol"],
                             textposition="top center", textfont=dict(color=TEXT, size=12), name=symbol,
                             marker=dict(size=size[me], color=S[1], line=dict(color=SURFACE, width=2)),
                             hovertemplate="%{text}: P/E %{x:.1f}x, ROE %{y:.1f}%<extra></extra>"))
    fig.update_xaxes(title_text="P/E (x) — cheaper ←")
    fig.update_yaxes(title_text="ROE % — better ↑")
    return _layout(fig, "Peer map: valuation vs quality (bubble = market cap)", height=400)


def relative_strength(close: pd.Series, bench: pd.Series | None, symbol: str, days: int = 252) -> go.Figure:
    c = close.iloc[-days:]
    fig = go.Figure(go.Scatter(x=c.index, y=100 * c / c.iloc[0], name=symbol, line=dict(color=S[0], width=2)))
    if bench is not None:
        b = bench.reindex(c.index).ffill().dropna()
        if len(b):
            fig.add_trace(go.Scatter(x=b.index, y=100 * b / b.iloc[0], name="Nifty 50", line=dict(color=S[1], width=2)))
    fig.add_hline(y=100, line=dict(color=GRID, width=1))
    fig.update_yaxes(title_text="Indexed (start = 100)")
    fig.update_layout(hovermode="x unified")
    return _layout(fig, "Relative performance vs Nifty 50 (1 year)", height=320)


# =========================================================================== category view
def category_treemap(snap: pd.DataFrame, ret_col: str = "1D %", group: str | None = None) -> go.Figure:
    d = snap.dropna(subset=[ret_col]).copy()
    if group is None:
        group = "Sector" if "Sector" in d and d["Sector"].nunique() > 1 else "Industry (detail)" if "Industry (detail)" in d else "Industry"
    d["Industry"] = d[group].fillna("Other").astype(str)
    d["size"] = d["Turnover ₹cr (20D avg)"].clip(lower=0.1)
    lim = max(float(d[ret_col].abs().quantile(0.95)), 0.5)
    d["label"] = d["Symbol"] + "<br>" + d[ret_col].map(lambda v: f"{v:+.1f}%")
    fig = go.Figure(go.Treemap(
        labels=d["label"].tolist() + sorted(d["Industry"].unique()),
        parents=d["Industry"].tolist() + [""] * d["Industry"].nunique(),
        values=d["size"].tolist() + [0] * d["Industry"].nunique(),
        marker=dict(colors=d[ret_col].tolist() + [0] * d["Industry"].nunique(), colorscale=[[0, DOWN], [0.5, NEUTRAL], [1, UP]],
                    cmid=0, cmin=-lim, cmax=lim, line=dict(color=SURFACE, width=2), showscale=False),
        textfont=dict(color=TEXT, family=FONT), hovertemplate="%{label}<extra></extra>", branchvalues="remainder"))
    return _layout(fig, f"Category heatmap — colour = {ret_col} return, size = traded value", height=520, legend=False).update_layout(margin=dict(l=4, r=4, t=48, b=4))


def returns_heatmap(snap: pd.DataFrame, top: int = 40) -> go.Figure:
    cols = ["1D %", "1W %", "1M %", "3M %", "1Y %"]
    d = snap.head(top)
    z = d[cols].to_numpy(dtype=float)
    lim = float(np.nanpercentile(np.abs(z), 95)) if np.isfinite(z).any() else 5
    fig = go.Figure(go.Heatmap(z=z, x=cols, y=d["Symbol"], text=[[f"{v:+.1f}" if np.isfinite(v) else "" for v in r] for r in z],
                               texttemplate="%{text}", textfont=dict(size=10, color=TEXT), zmid=0, zmin=-lim, zmax=lim,
                               colorscale=[[0, DOWN], [0.5, NEUTRAL], [1, UP]], xgap=2, ygap=2, showscale=False,
                               hovertemplate="%{y} %{x}: %{z:+.2f}%<extra></extra>"))
    fig.update_yaxes(autorange="reversed")
    return _layout(fig, f"Returns across periods (top {len(d)} by traded value)", height=120 + 22 * len(d), legend=False)


# =========================================================================== zones, breakouts, horizons
RATING_COLORS = {"Strong Buy": "#0ca30c", "Buy": "#6cc56c", "Neutral": "#8a8980", "Sell": "#ec835a", "Strong Sell": "#d03b3b"}


def zones_chart(df: pd.DataFrame, tf: dict[str, Any], title: str, intraday: bool, bars: int = 160) -> go.Figure:
    """Candles + volume with support/resistance ZONES shaded and pattern lines/triggers drawn."""
    d = df.iloc[-bars:].copy()
    x = [str(i)[:16] for i in d.index] if intraday else d.index
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.03, row_heights=[0.8, 0.2])
    fig.add_trace(go.Candlestick(x=x, open=d["Open"], high=d["High"], low=d["Low"], close=d["Close"], name="Price",
                                 increasing=dict(line=dict(color=UP, width=1), fillcolor=UP),
                                 decreasing=dict(line=dict(color=DOWN, width=1), fillcolor=DOWN), showlegend=False), 1, 1)
    fig.add_trace(go.Bar(x=x, y=d["Volume"], marker_color=np.where(d["Close"] >= d["Open"], UP, DOWN), opacity=0.5,
                         showlegend=False, name="Volume"), 2, 1)
    z = tf.get("zones", {})
    for i, s in enumerate(z.get("supports", [])):
        fig.add_hrect(y0=s["low"], y1=s["high"], fillcolor="rgba(12,163,12,0.16)", line_width=0, row=1, col=1,
                      annotation_text=f"S{i + 1} ₹{s['low']:,.0f}–{s['high']:,.0f} ({s['touches']}×)", annotation_position="bottom left",
                      annotation_font=dict(color=MUTED, size=10))
    for i, r in enumerate(z.get("resistances", [])):
        fig.add_hrect(y0=r["low"], y1=r["high"], fillcolor="rgba(208,59,59,0.16)", line_width=0, row=1, col=1,
                      annotation_text=f"R{i + 1} ₹{r['low']:,.0f}–{r['high']:,.0f} ({r['touches']}×)", annotation_position="top left",
                      annotation_font=dict(color=MUTED, size=10))
    first = str(d.index[0])[:16]
    for p in tf.get("patterns", []):
        col = UP if p["direction"] == "bullish" else DOWN if p["direction"] == "bearish" else WARN
        for ln in p.get("lines", []):
            if ln["x0"] < first:
                continue
            fig.add_shape(type="line", x0=ln["x0"], y0=ln["y0"], x1=ln["x1"], y1=ln["y1"], line=dict(color=col, width=2), row=1, col=1)
        if p.get("trigger") and p["status"] != "forming" or (p.get("trigger") and p["pattern"] in ("Consolidation range", "Double bottom", "Double top")):
            fig.add_hline(y=p["trigger"], line=dict(color=col, width=1.2, dash="dash"), row=1, col=1,
                          annotation_text=f"{p['pattern']} trigger ₹{p['trigger']:,.0f}", annotation_position="top right",
                          annotation_font=dict(color=col, size=10))
    if intraday:
        fig.update_xaxes(type="category", nticks=8)
    else:
        fig.update_xaxes(rangebreaks=[dict(bounds=["sat", "mon"])] if tf.get("timeframe") == "1 Day" else [])
    fig.update_xaxes(rangeslider_visible=False)
    _layout(fig, title, height=600, legend=False)
    fig.update_layout(hovermode="x unified")
    return fig


def horizon_bars(horizons: dict[str, Any]) -> go.Figure:
    names = [n for n, v in horizons.items() if v.get("score") is not None]
    vals = [horizons[n]["score"] for n in names]
    labels = [horizons[n]["rating"] for n in names]
    fig = go.Figure(go.Bar(x=names, y=vals, marker=dict(color=[RATING_COLORS.get(l, NEUTRAL) for l in labels], cornerradius=4),
                           text=[f"{l}<br>{v} · {horizons[n]['confidence']}" for n, l, v in zip(names, labels, vals)],
                           textposition="outside", textfont=dict(color=TEXT, size=11),
                           hovertemplate="%{x}: score %{y}<extra></extra>"))
    for y, t in ((70, "Strong Buy"), (58, "Buy"), (45, "Neutral / Sell")):
        fig.add_hline(y=y, line=dict(color=GRID, width=1, dash="dot"), annotation_text=t, annotation_font=dict(color=MUTED, size=10),
                      annotation_position="top right")
    fig.update_yaxes(range=[0, 112], title_text="Model score (0-100)")
    fig.update_xaxes(range=[-0.5, len(names) + 0.3], tickangle=0)  # room on the right for the threshold labels
    return _layout(fig, "Model rating by investment horizon", height=340, legend=False)


def history_compare(hist: dict[str, Any]) -> go.Figure:
    names = [n for n, v in hist.items() if isinstance(v, dict) and v.get("available")]
    fig = go.Figure()
    fig.add_trace(go.Bar(x=names, y=[hist[n]["pct_positive_similar"] for n in names], name="After similar setups",
                         marker=dict(color=S[0], cornerradius=4), text=[f"{hist[n]['pct_positive_similar']:.0f}%" for n in names],
                         textposition="outside", textfont=dict(color=MUTED, size=10)))
    fig.add_trace(go.Bar(x=names, y=[hist[n]["pct_positive_all_days"] for n in names], name="All days (baseline)",
                         marker=dict(color=S[1], cornerradius=4), text=[f"{hist[n]['pct_positive_all_days']:.0f}%" for n in names],
                         textposition="outside", textfont=dict(color=MUTED, size=10)))
    fig.update_layout(barmode="group", bargroupgap=0.08)
    fig.update_yaxes(range=[0, 105], title_text="% of times the stock was higher")
    return _layout(fig, "Did this technical setup help in the past? (this stock, ~10 years)", height=340)


# =========================================================================== IPO
def ipo_subscription(rows: list[dict[str, Any]]) -> go.Figure:
    keep = []
    for r in rows:
        c = (r.get("category") or "")
        t = r.get("times")
        if t is None or not r.get("offered"):
            continue
        cl = c.lower()
        short = ("QIB" if "qualified" in cl else "NII (₹2–10 lakh)" if "two lakh" in cl else "NII (> ₹10 lakh)" if "ten lakh" in cl
                 else "NII total" if c.strip() == "Non Institutional Investors" else "Retail" if "Retail" in c or c.startswith("Individual Investors")
                 else "Employees" if "mploy" in c else "Shareholders" if "hareholder" in c else "Total" if c.strip().lower() == "total" else None)
        if short:
            keep.append((short, float(t)))
    if not keep:
        return _layout(go.Figure(), "Subscription by category (not available yet)", height=260, legend=False)
    names, vals = zip(*keep)
    fig = go.Figure(go.Bar(y=list(names), x=list(vals), orientation="h",
                           marker=dict(color=[S[1] if n == "Total" else S[0] for n in names], cornerradius=4),
                           text=[f"{v:.2f}×" for v in vals], textposition="outside", textfont=dict(color=TEXT, size=12),
                           hovertemplate="%{y}: %{x:.2f}× subscribed<extra></extra>"))
    fig.add_vline(x=1, line=dict(color=MUTED, width=1, dash="dash"), annotation_text="1× = fully subscribed",
                  annotation_position="bottom right", annotation_font=dict(color=MUTED, size=10))
    fig.update_yaxes(autorange="reversed")
    fig.update_xaxes(title_text="times subscribed", range=[0, max(vals) * 1.25 + 0.5])
    return _layout(fig, "Subscription by investor category (NSE + BSE)", height=120 + 42 * len(keep), legend=False)


def ipo_listing_history(recent: pd.DataFrame) -> go.Figure:
    d = recent.sort_values("listing_date").tail(20)
    fig = go.Figure()
    fig.add_trace(go.Bar(x=d["symbol"], y=d["listing_gain_pct"], name="Listing-day gain (open vs issue)",
                         marker=dict(color=S[0], cornerradius=4)))
    fig.add_trace(go.Bar(x=d["symbol"], y=d["return_since_ipo_pct"], name="Return since IPO (today)",
                         marker=dict(color=S[1], cornerradius=4)))
    fig.add_hline(y=0, line=dict(color=GRID, width=1))
    fig.update_layout(barmode="group", bargroupgap=0.08)
    fig.update_yaxes(title_text="% vs issue price")
    return _layout(fig, "Recent mainboard IPOs: listing-day gain vs return since IPO", height=360)


def ipo_financials(table: list[dict[str, Any]]) -> go.Figure:
    d = pd.DataFrame(table)
    if d.empty:
        return _layout(go.Figure(), "Financials (not extracted)", height=260, legend=False)
    fig = go.Figure()
    for i, (c, lbl) in enumerate((("revenue_cr", "Revenue"), ("pat_cr", "Net profit"), ("net_worth_cr", "Net worth"), ("borrowings_cr", "Borrowings"))):
        if c in d and d[c].notna().any():
            fig.add_trace(go.Bar(x=d["period"], y=d[c], name=lbl, marker=dict(color=S[i], cornerradius=4),
                                 text=[f"{v:,.0f}" if pd.notna(v) else "" for v in d[c]], textposition="outside",
                                 textfont=dict(color=MUTED, size=10)))
    fig.update_layout(barmode="group", bargroupgap=0.08)
    fig.update_yaxes(title_text="₹ crore")
    return _layout(fig, "Restated financials from the prospectus (₹ crore; stub periods are not annualised)", height=360)
