"""Visual design system for the dashboard (dark fintech, vibrant accents).

Direction from the ui-ux-pro-max skill (`--design-system "fintech stock market analytics dashboard dark vibrant"`):
Dark Mode (OLED) + Data-Dense Dashboard style, Fira Sans / Fira Code type pairing, green-up / red-down semantics,
accessible contrast (body text >= 4.5:1), visible focus, 150-300 ms transitions, prefers-reduced-motion respected,
no emoji as icons (Material Symbols instead), never colour alone to carry meaning (arrows and signs too).

Everything here returns HTML/CSS strings; app.py renders them with st.markdown(..., unsafe_allow_html=True).
"""
from __future__ import annotations

import hashlib
import html
import math
from typing import Any, Iterable

# --------------------------------------------------------------------------- tokens
T = {
    "bg": "#050816",
    "surface": "#0b1124",
    "card": "#0f172a",
    "card2": "#131c33",
    "border": "rgba(148,163,184,.16)",
    "border_strong": "rgba(148,163,184,.30)",
    "text": "#e2e8f0",
    "strong": "#f8fafc",
    "muted": "#94a3b8",
    "indigo": "#6366f1",
    "indigo_d": "#4f46e5",
    "violet": "#8b5cf6",
    "violet_d": "#7c3aed",
    "cyan": "#22d3ee",
    "gold": "#f59e0b",
    "pink": "#ec4899",
    "up": "#22c55e",
    "down": "#ef4444",
    "warn": "#f59e0b",
    "neutral": "#64748b",
}
TONE = {"up": T["up"], "down": T["down"], "warn": T["warn"], "neutral": T["neutral"], "info": T["cyan"], "brand": T["indigo"]}
CHART_COLORS = ["#6366f1", "#22d3ee", "#f59e0b", "#a855f7", "#22c55e", "#ec4899", "#38bdf8", "#f97316"]
FONT_URL = "https://fonts.googleapis.com/css2?family=Fira+Code:wght@400;500;600&family=Fira+Sans:wght@400;500;600;700;800&display=swap"
NUM = "'Fira Sans', system-ui, sans-serif"  # with tabular-nums so columns of figures line up


def esc(x: Any) -> str:
    return html.escape("" if x is None else str(x))


def icon(name: str, cls: str = "") -> str:
    """Material Symbols glyph (Streamlit ships the font). Decorative: hidden from screen readers."""
    return f"<span class='msr {cls}' aria-hidden='true'>{esc(name)}</span>"


def tone_of(x: float | None, flat: float = 0.0) -> str:
    if x is None or (isinstance(x, float) and math.isnan(x)):
        return "neutral"
    return "up" if x > flat else "down" if x < -flat else "neutral"


# --------------------------------------------------------------------------- CSS
def css() -> str:
    t = T
    return f"""<style>
@import url('{FONT_URL}');
:root {{
  --bg:{t['bg']}; --surface:{t['surface']}; --card:{t['card']}; --card2:{t['card2']};
  --border:{t['border']}; --border-strong:{t['border_strong']}; --text:{t['text']}; --strong:{t['strong']}; --muted:{t['muted']};
  --indigo:{t['indigo']}; --violet:{t['violet']}; --cyan:{t['cyan']}; --gold:{t['gold']}; --up:{t['up']}; --down:{t['down']};
  --grad: linear-gradient(135deg,{t['indigo_d']} 0%,{t['violet_d']} 100%);
  --grad-text: linear-gradient(92deg,#c7d2fe 0%,#67e8f9 45%,#f0abfc 100%);
  --radius:16px; --fast:160ms; --med:280ms; --ease:cubic-bezier(.2,.8,.2,1);
  --num:{NUM};
}}
/* ---------- canvas ---------- */
.stApp {{ background:
    radial-gradient(1200px 600px at 8% -10%, rgba(99,102,241,.20), transparent 60%),
    radial-gradient(900px 500px at 100% 0%, rgba(34,211,238,.10), transparent 60%),
    radial-gradient(900px 700px at 50% 110%, rgba(168,85,247,.10), transparent 60%), var(--bg) !important;
  background-attachment: fixed !important; }}
header[data-testid="stHeader"] {{ background: transparent !important; }}
.block-container {{ padding-top: 1.1rem; padding-bottom: 3rem; max-width: 1480px; }}
::selection {{ background: rgba(99,102,241,.45); }}
a {{ color: #a5b4fc; }} a:hover {{ color: #c7d2fe; }}
code {{ font-family: var(--num); }}
.msr {{ font-family: 'Material Symbols Rounded'; font-weight: normal; font-style: normal; line-height: 1; display: inline-block;
  letter-spacing: normal; text-transform: none; white-space: nowrap; direction: ltr; -webkit-font-smoothing: antialiased;
  font-feature-settings: 'liga'; vertical-align: -0.18em; }}

/* ---------- motion (skipped entirely for reduced-motion users) ---------- */
@keyframes rise {{ from {{ opacity:0; transform: translateY(10px); }} to {{ opacity:1; transform:none; }} }}
@keyframes pulse {{ 0% {{ box-shadow:0 0 0 0 rgba(34,197,94,.65); }} 70% {{ box-shadow:0 0 0 8px rgba(34,197,94,0); }} 100% {{ box-shadow:0 0 0 0 rgba(34,197,94,0); }} }}
@keyframes marquee {{ from {{ transform: translateX(0); }} to {{ transform: translateX(-50%); }} }}
@keyframes shimmer {{ from {{ background-position: 0% 50%; }} to {{ background-position: 200% 50%; }} }}
.rise {{ animation: rise 420ms var(--ease) both; }}
.rise-1 {{ animation-delay: 60ms; }} .rise-2 {{ animation-delay: 120ms; }} .rise-3 {{ animation-delay: 180ms; }}
.rise-4 {{ animation-delay: 240ms; }} .rise-5 {{ animation-delay: 300ms; }} .rise-6 {{ animation-delay: 360ms; }}
@media (prefers-reduced-motion: reduce) {{
  *, *::before, *::after {{ animation: none !important; transition: none !important; }}
  .ticker-track {{ transform: none !important; }}
}}

/* ---------- sidebar ---------- */
section[data-testid="stSidebar"] {{ background: linear-gradient(180deg,#0a1024 0%,#060a18 100%) !important;
  border-right: 1px solid var(--border); }}
section[data-testid="stSidebar"] h3 {{ font-size: .78rem !important; letter-spacing: .12em; text-transform: uppercase;
  color: var(--muted) !important; font-weight: 700 !important; margin-top: 1.2rem; }}
.brand {{ display:flex; align-items:center; gap:12px; padding: 4px 2px 14px 2px; }}
.brand .logo {{ width:42px; height:42px; border-radius:12px; background: var(--grad); display:grid; place-items:center;
  box-shadow: 0 6px 24px rgba(99,102,241,.45); flex: none; }}
.brand .name {{ font-weight:800; font-size:1.08rem; line-height:1.15; color: var(--strong); }}
.brand .tag {{ font-size:.74rem; color: var(--muted); letter-spacing:.02em; }}
.side-note {{ font-size:.78rem; color: var(--muted); border:1px dashed var(--border-strong); border-radius:12px; padding:10px 12px; }}

/* ---------- navigation (sidebar radio) + other button-like radios ---------- */
[data-testid="stElementContainer"]:has(> [data-testid="stRadio"]), [data-testid="stRadio"] {{ width:100% !important; }}
[data-testid="stRadioGroup"] {{ gap:6px; width:100% !important; }}
[data-testid="stRadioGroup"][aria-orientation="vertical"] {{ display:flex; flex-direction:column; }}
[data-testid="stRadioGroup"] > div {{ width:100%; }}
[data-testid="stRadioOption"] {{ width:100%; background: rgba(15,23,42,.55); border:1px solid var(--border); border-radius:12px;
  padding:10px 14px; cursor:pointer; transition: background var(--fast) var(--ease), border-color var(--fast) var(--ease), transform var(--fast) var(--ease); }}
[data-testid="stRadioOption"] > div > div:first-child {{ display:none; }}
[data-testid="stRadioOption"] p {{ font-size:.97rem !important; font-weight:600; color:#cbd5e1; margin:0; }}
[data-testid="stRadioOption"]:hover {{ border-color: rgba(129,140,248,.6); background: rgba(79,70,229,.14); transform: translateX(2px); }}
[data-testid="stRadioOption"][data-selected="true"] {{ background: var(--grad); border-color: transparent;
  box-shadow: 0 6px 22px rgba(99,102,241,.40), inset 0 1px 0 rgba(255,255,255,.15); }}
[data-testid="stRadioOption"][data-selected="true"] p {{ color:#fff; }}
[data-testid="stRadioOption"]:has(input:focus-visible) {{ outline:2px solid #a5b4fc; outline-offset:2px; }}
[data-testid="stRadioGroup"][aria-orientation="horizontal"] [data-testid="stRadioOption"] {{ width:auto; padding:7px 14px; }}

/* ---------- tabs as pills ---------- */
[role="tablist"] {{ flex-wrap:wrap; gap:8px; overflow:visible !important; padding:6px 0 12px 0; border-bottom:1px solid var(--border); }}
[data-testid="stTab"] {{ background: rgba(15,23,42,.6); border:1px solid var(--border); border-radius:999px; padding:8px 16px !important;
  margin:0 !important; height:auto; min-height:40px; cursor:pointer;
  transition: background var(--fast) var(--ease), border-color var(--fast) var(--ease), box-shadow var(--fast) var(--ease); }}
[data-testid="stTab"] p {{ font-size:.93rem !important; font-weight:600; color:#cbd5e1; margin:0; }}
[data-testid="stTab"]:hover {{ border-color: rgba(129,140,248,.6); background: rgba(79,70,229,.14); }}
[data-testid="stTab"][aria-selected="true"] {{ background: var(--grad); border-color: transparent; box-shadow: 0 4px 18px rgba(99,102,241,.40); }}
[data-testid="stTab"][aria-selected="true"] p {{ color:#fff; }}
[data-testid="stTab"]:focus-visible {{ outline:2px solid #a5b4fc; outline-offset:2px; }}
.react-aria-SelectionIndicator {{ display:none !important; }}

/* ---------- buttons ---------- */
.stButton > button, .stDownloadButton > button, .stFormSubmitButton > button, [data-testid="stPopover"] button {{
  border-radius:12px !important; font-weight:600 !important; min-height:42px; cursor:pointer;
  transition: transform var(--fast) var(--ease), box-shadow var(--fast) var(--ease), border-color var(--fast) var(--ease), background var(--fast) var(--ease) !important; }}
.stButton > button[kind="primary"], .stDownloadButton > button[kind="primary"], .stFormSubmitButton > button[kind="primary"] {{
  background: var(--grad) !important; border: 0 !important; color:#fff !important; box-shadow: 0 6px 20px rgba(99,102,241,.35); }}
.stButton > button:hover, .stDownloadButton > button:hover {{ transform: translateY(-1px); border-color: rgba(129,140,248,.7) !important; }}
.stButton > button[kind="primary"]:hover {{ box-shadow: 0 10px 28px rgba(99,102,241,.5); }}
.stButton > button:focus-visible {{ outline: 2px solid #a5b4fc !important; outline-offset: 2px; }}

/* ---------- native metrics → glass stat cards ---------- */
div[data-testid="stMetric"] {{ position:relative; overflow:hidden; background: linear-gradient(180deg, rgba(30,41,59,.55), rgba(15,23,42,.55));
  border:1px solid var(--border); border-radius: var(--radius); padding: 14px 16px; animation: rise 420ms var(--ease) both;
  transition: border-color var(--fast) var(--ease), transform var(--fast) var(--ease); }}
div[data-testid="stMetric"]::before {{ content:""; position:absolute; inset:0 0 auto 0; height:3px; background: var(--grad); opacity:.9; }}
div[data-testid="stMetric"]:hover {{ border-color: rgba(129,140,248,.45); transform: translateY(-2px); }}
div[data-testid="stMetricLabel"] p {{ color: var(--muted) !important; font-size:.8rem !important; text-transform: uppercase; letter-spacing:.06em; font-weight:600; }}
div[data-testid="stMetricValue"] {{ font-family: var(--num); font-size: 1.5rem; font-weight:600; color: var(--strong); font-variant-numeric: tabular-nums; }}
div[data-testid="stMetricDelta"] {{ font-family: var(--num); font-variant-numeric: tabular-nums; }}

/* ---------- charts, tables, expanders, alerts ---------- */
[data-testid="stPlotlyChart"] {{ background: linear-gradient(180deg, rgba(30,41,59,.45), rgba(15,23,42,.45)); border:1px solid var(--border);
  border-radius: var(--radius); padding: 6px 8px; animation: rise 460ms var(--ease) both; }}
[data-testid="stDataFrame"], [data-testid="stTable"] {{ border-radius: 14px; overflow: hidden; border:1px solid var(--border); }}
[data-testid="stExpander"] details {{ border-radius: 14px !important; border:1px solid var(--border) !important; background: rgba(15,23,42,.45); }}
[data-testid="stExpander"] summary:hover {{ color: #c7d2fe; }}
[data-testid="stAlert"] {{ border-radius: 14px; }}
div[data-baseweb="select"] > div, div[data-baseweb="input"] > div, .stTextInput input, .stNumberInput input {{ border-radius: 12px !important; }}
.stTextInput input, .stNumberInput input {{ font-family: inherit; }}
hr {{ border-color: var(--border) !important; }}
h1, h2, h3 {{ letter-spacing: -.01em; }}

/* ---------- never let a typed key be revealed on screen ---------- */
button[aria-label="Show password"], button[aria-label="Hide password"] {{ display:none !important; }}

/* ---------- page hero ---------- */
.hero {{ position:relative; border-radius: 22px; padding: 22px 24px; margin: 4px 0 14px 0; overflow:hidden;
  background: linear-gradient(135deg, rgba(79,70,229,.22) 0%, rgba(15,23,42,.65) 45%, rgba(8,145,178,.16) 100%);
  border:1px solid rgba(129,140,248,.28); animation: rise 380ms var(--ease) both; }}
.hero::after {{ content:""; position:absolute; right:-80px; top:-80px; width:260px; height:260px; border-radius:50%;
  background: radial-gradient(circle, rgba(34,211,238,.22), transparent 70%); pointer-events:none; }}
.hero .eyebrow {{ font-size:.74rem; letter-spacing:.16em; text-transform:uppercase; color:#a5b4fc; font-weight:700; display:flex; gap:8px; align-items:center; }}
.hero h1 {{ font-size: clamp(1.6rem, 2.6vw, 2.3rem); font-weight: 800; margin: 6px 0 4px 0; padding:0; line-height:1.15;
  background: var(--grad-text); -webkit-background-clip: text; background-clip: text; color: transparent; }}
.hero p {{ color:#cbd5e1; margin:0; max-width: 980px; font-size:.97rem; line-height:1.5; }}
.hero .ico {{ width:46px; height:46px; border-radius:14px; display:grid; place-items:center; background: var(--grad);
  box-shadow: 0 8px 26px rgba(99,102,241,.45); color:#fff; font-size: 26px; flex:none; }}
.hero .row {{ display:flex; gap:16px; align-items:center; }}

/* ---------- market ticker ---------- */
.ticker {{ position:relative; display:flex; align-items:center; gap:12px; border:1px solid var(--border); border-radius:14px;
  background: rgba(8,12,28,.75); padding: 8px 10px; margin-bottom: 12px; overflow:hidden; }}
.ticker .status {{ flex:none; display:flex; align-items:center; gap:8px; font-size:.76rem; font-weight:700; letter-spacing:.08em;
  text-transform:uppercase; color:#cbd5e1; padding: 6px 10px; border-radius:10px; background: rgba(30,41,59,.8); border:1px solid var(--border); }}
.ticker .status .live {{ width:8px; height:8px; border-radius:50%; background: var(--up); animation: pulse 1.8s infinite; }}
.ticker .status .closed {{ width:8px; height:8px; border-radius:50%; background: var(--muted); }}
.ticker .viewport {{ overflow:hidden; flex:1; mask-image: linear-gradient(90deg, transparent, #000 4%, #000 96%, transparent); }}
.ticker-track {{ display:flex; gap:10px; width:max-content; animation: marquee 75s linear infinite; }}
.ticker:hover .ticker-track {{ animation-play-state: paused; }}
.tk {{ display:flex; align-items:center; gap:8px; padding: 4px 12px; border-radius:10px; background: rgba(15,23,42,.8);
  border:1px solid var(--border); white-space:nowrap; }}
.tk .n {{ color: var(--muted); font-size:.78rem; font-weight:600; }}
.tk .v {{ font-family: var(--num); font-size:.86rem; color: var(--strong); font-variant-numeric: tabular-nums; }}
.tk .c {{ font-family: var(--num); font-size:.8rem; font-weight:600; font-variant-numeric: tabular-nums; }}
@media (prefers-reduced-motion: reduce) {{ .ticker .viewport {{ overflow-x:auto; }} }}

/* ---------- stat tiles / pills / chips ---------- */
.tiles {{ display:grid; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr)); gap:12px; margin: 4px 0 14px 0; }}
.tile {{ position:relative; overflow:hidden; border-radius: var(--radius); padding: 14px 16px; border:1px solid var(--border);
  background: linear-gradient(180deg, rgba(30,41,59,.55), rgba(15,23,42,.55));
  transition: transform var(--fast) var(--ease), border-color var(--fast) var(--ease); }}
.tile:hover {{ transform: translateY(-2px); border-color: rgba(129,140,248,.45); }}
.tile::before {{ content:""; position:absolute; inset:0 0 auto 0; height:3px; background: var(--accent, var(--grad)); }}
.tile .l {{ color: var(--muted); font-size:.74rem; text-transform: uppercase; letter-spacing:.08em; font-weight:700; display:flex; gap:6px; align-items:center; }}
.tile .v {{ font-family: var(--num); font-size: 1.45rem; font-weight:600; color: var(--strong); margin-top: 6px; font-variant-numeric: tabular-nums; white-space:nowrap; }}
.tile .d {{ font-family: var(--num); font-size:.82rem; margin-top: 2px; font-variant-numeric: tabular-nums; }}
.pill {{ display:inline-flex; align-items:center; gap:4px; font-family: var(--num); font-weight:600; font-size:.86rem;
  padding: 3px 10px; border-radius:999px; font-variant-numeric: tabular-nums; }}
.pill.up {{ color:#86efac; background: rgba(34,197,94,.14); border:1px solid rgba(34,197,94,.35); }}
.pill.down {{ color:#fca5a5; background: rgba(239,68,68,.14); border:1px solid rgba(239,68,68,.35); }}
.pill.neutral {{ color:#cbd5e1; background: rgba(100,116,139,.18); border:1px solid rgba(148,163,184,.3); }}
.chip {{ display:inline-flex; align-items:center; gap:6px; font-size:.78rem; font-weight:600; padding: 4px 10px; border-radius:999px;
  border:1px solid var(--border-strong); color:#e2e8f0; background: rgba(30,41,59,.7); margin: 0 6px 6px 0; }}
.chip.brand {{ border-color: rgba(129,140,248,.5); background: rgba(79,70,229,.18); color:#c7d2fe; }}
.chip.cyan {{ border-color: rgba(34,211,238,.45); background: rgba(8,145,178,.16); color:#a5f3fc; }}
.chip.gold {{ border-color: rgba(245,158,11,.45); background: rgba(245,158,11,.12); color:#fde68a; }}
.dot {{ display:inline-block; width:10px; height:10px; border-radius:50%; background: var(--c); box-shadow: 0 0 10px var(--c); vertical-align: 0; }}
.up-t {{ color:#4ade80; }} .down-t {{ color:#f87171; }} .neutral-t {{ color:#cbd5e1; }} .warn-t {{ color:#fbbf24; }}

/* ---------- stock hero ---------- */
.shero {{ display:grid; grid-template-columns: minmax(260px,1.3fr) minmax(240px,1fr) minmax(220px,.9fr); gap:18px; align-items:center;
  border-radius: 22px; padding: 20px 22px; margin: 6px 0 14px 0; border:1px solid rgba(129,140,248,.28);
  background: linear-gradient(135deg, rgba(79,70,229,.20) 0%, rgba(15,23,42,.70) 50%, rgba(8,145,178,.14) 100%); animation: rise 380ms var(--ease) both; }}
.shero h1 {{ font-size: clamp(1.4rem, 2.3vw, 2.05rem); font-weight: 800; margin: 0 0 6px 0; padding:0; line-height:1.15;
  background: var(--grad-text); -webkit-background-clip: text; background-clip: text; color: transparent; }}
.shero .sym {{ font-family: 'Fira Code', ui-monospace, monospace; font-size:.85rem; color:#c7d2fe; background: rgba(79,70,229,.22); border:1px solid rgba(129,140,248,.45);
  border-radius:8px; padding: 2px 8px; margin-left: 4px; }}
.shero .meta {{ color: var(--muted); font-size:.78rem; margin-top: 4px; }}
.shero .price {{ font-family: var(--num); font-size: clamp(1.8rem, 3vw, 2.5rem); font-weight:600; color: var(--strong); font-variant-numeric: tabular-nums; line-height:1.1; }}
.shero .sub {{ color: var(--muted); font-size:.78rem; margin-top: 6px; }}
.range {{ margin-top: 6px; }}
.range .bar {{ position:relative; height:8px; border-radius:999px; background: linear-gradient(90deg, rgba(239,68,68,.55), rgba(245,158,11,.55), rgba(34,197,94,.55)); }}
.range .mk {{ position:absolute; top:-5px; width:4px; height:18px; border-radius:3px; background:#fff; box-shadow: 0 0 10px rgba(255,255,255,.7); transform: translateX(-2px); }}
.range .ends {{ display:flex; justify-content:space-between; font-family: var(--num); font-size:.76rem; color: var(--muted); margin-top: 6px; }}
@media (max-width: 1100px) {{ .shero {{ grid-template-columns: 1fr; }} }}

/* ---------- score rings ---------- */
.rings {{ display:grid; grid-template-columns: repeat(auto-fit, minmax(200px,1fr)); gap:12px; margin: 2px 0 14px 0; }}
.ring-card {{ display:flex; gap:14px; align-items:center; border-radius: var(--radius); padding: 14px 16px; border:1px solid var(--border);
  background: linear-gradient(180deg, rgba(30,41,59,.55), rgba(15,23,42,.55)); transition: transform var(--fast) var(--ease), border-color var(--fast) var(--ease); }}
.ring-card:hover {{ transform: translateY(-2px); border-color: rgba(129,140,248,.45); }}
.ring {{ --p:0; --c:var(--indigo); width:76px; height:76px; flex:none; border-radius:50%; display:grid; place-items:center;
  background: conic-gradient(var(--c) calc(var(--p)*1%), rgba(148,163,184,.14) 0); box-shadow: 0 0 22px color-mix(in srgb, var(--c) 35%, transparent); }}
.ring > span {{ width:60px; height:60px; border-radius:50%; background: #0b1124; display:grid; place-items:center;
  font-family: var(--num); font-weight:600; font-size:1.05rem; color: var(--strong); font-variant-numeric: tabular-nums; }}
.ring-card .t {{ font-size:.78rem; color: var(--muted); text-transform: uppercase; letter-spacing:.07em; font-weight:700; }}
.ring-card .s {{ font-size:1rem; font-weight:700; margin-top: 2px; }}
.ring-card .h {{ font-size:.76rem; color: var(--muted); margin-top: 2px; }}

/* ---------- legacy cards used across views ---------- */
.card {{ background: linear-gradient(180deg, rgba(30,41,59,.55), rgba(15,23,42,.55)); border:1px solid var(--border);
  border-radius: 14px; padding: 14px 18px; margin-bottom: 12px; }}
.verdict {{ font-size:1.02rem; border-left: 4px solid var(--indigo); }}
.flag {{ color:#fca5a5; }} .ok {{ color:#86efac; }}
.hz-grid {{ display:grid; grid-template-columns: repeat(auto-fit, minmax(150px,1fr)); gap:10px; margin-bottom: 12px; }}
.hz-card {{ position:relative; overflow:hidden; border-radius: 14px; padding: 14px 10px 12px 10px; text-align:center; border:1px solid var(--border);
  background: linear-gradient(180deg, rgba(30,41,59,.55), rgba(15,23,42,.55)); transition: transform var(--fast) var(--ease); }}
.hz-card:hover {{ transform: translateY(-2px); }}
.hz-card::before {{ content:""; position:absolute; inset:0 0 auto 0; height:3px; background: var(--c, var(--grad)); }}
.hz-card .h {{ color: var(--muted); font-size:.78rem; text-transform: uppercase; letter-spacing:.07em; font-weight:700; }}
.hz-card .r {{ font-size: 1.1rem; font-weight: 800; white-space: nowrap; margin-top: 6px; color: var(--c, var(--strong)); }}
.hz-card .s {{ color: var(--muted); font-size:.76rem; margin-top: 4px; }}
.verdict-card {{ border-radius: 14px; padding: 14px 16px; border:1px solid var(--border); background: linear-gradient(180deg, rgba(30,41,59,.55), rgba(15,23,42,.55)); margin-bottom: 8px; }}
.verdict-card .h {{ color: var(--muted); font-size:.82rem; }} .verdict-card .v {{ font-size:1.2rem; font-weight:800; margin: 4px 0; }}
</style>"""


# --------------------------------------------------------------------------- components
def brand() -> str:
    logo = ("<svg width='24' height='24' viewBox='0 0 24 24' fill='none' aria-hidden='true'>"
            "<path d='M3 17l5-5 4 4 8-9' stroke='white' stroke-width='2.4' stroke-linecap='round' stroke-linejoin='round'/>"
            "<path d='M15 7h5v5' stroke='white' stroke-width='2.4' stroke-linecap='round' stroke-linejoin='round'/></svg>")
    return (f"<div class='brand'><div class='logo'>{logo}</div><div><div class='name'>Indian Stock Analyst</div>"
            "<div class='tag'>AI equity research · NSE</div></div></div>")


def hero(title: str, subtitle: str = "", icon_name: str = "", eyebrow: str = "") -> str:
    ico = f"<div class='ico'>{icon(icon_name)}</div>" if icon_name else ""
    eb = f"<div class='eyebrow'>{esc(eyebrow)}</div>" if eyebrow else ""
    sub = f"<p>{subtitle}</p>" if subtitle else ""
    return f"<div class='hero'><div class='row'>{ico}<div>{eb}<h1>{esc(title)}</h1>{sub}</div></div></div>"


def pill(pct: float | None, nd: int = 2, suffix: str = "%") -> str:
    if pct is None or (isinstance(pct, float) and math.isnan(pct)):
        return "<span class='pill neutral'>—</span>"
    tone = tone_of(pct)
    arrow = "▲" if tone == "up" else "▼" if tone == "down" else "■"
    return f"<span class='pill {tone}'>{arrow} {pct:+.{nd}f}{suffix}</span>"


def chip(text: str, kind: str = "") -> str:
    return f"<span class='chip {kind}'>{esc(text)}</span>" if text else ""


def dot(color: str) -> str:
    return f"<span class='dot' style='--c:{color}' aria-hidden='true'></span>"


def tiles(items: Iterable[dict[str, Any]]) -> str:
    """items: {label, value, delta (html or text), tone ('up'/'down'/'neutral'/'warn'), accent (css colour), icon}."""
    out = []
    for i, it in enumerate(items):
        acc = f" style='--accent:{it['accent']}'" if it.get("accent") else ""
        ico = icon(it["icon"]) if it.get("icon") else ""
        d = it.get("delta")
        d_html = f"<div class='d {it.get('tone', 'neutral')}-t'>{d}</div>" if d not in (None, "") else ""
        out.append(f"<div class='tile rise rise-{min(i + 1, 6)}'{acc}><div class='l'>{ico}{esc(it['label'])}</div>"
                   f"<div class='v'>{esc(it['value'])}</div>{d_html}</div>")
    return f"<div class='tiles'>{''.join(out)}</div>"


def spark(values: list[float], w: int = 220, h: int = 56, color: str | None = None) -> str:
    vals = [float(v) for v in values if v is not None and not (isinstance(v, float) and math.isnan(v))]
    if len(vals) < 2:
        return ""
    lo, hi = min(vals), max(vals)
    rng = (hi - lo) or 1.0
    color = color or (T["up"] if vals[-1] >= vals[0] else T["down"])
    pts = [(w * i / (len(vals) - 1), h - 4 - (h - 8) * (v - lo) / rng) for i, v in enumerate(vals)]
    line = " ".join(f"{x:.1f},{y:.1f}" for x, y in pts)
    gid = "g" + hashlib.md5((line + color).encode()).hexdigest()[:8]
    area = f"0,{h} " + line + f" {w},{h}"
    return (f"<svg width='100%' height='{h}' viewBox='0 0 {w} {h}' preserveAspectRatio='none' role='img' aria-label='price trend'>"
            f"<defs><linearGradient id='{gid}' x1='0' y1='0' x2='0' y2='1'><stop offset='0%' stop-color='{color}' stop-opacity='.35'/>"
            f"<stop offset='100%' stop-color='{color}' stop-opacity='0'/></linearGradient></defs>"
            f"<polygon points='{area}' fill='url(#{gid})'/><polyline points='{line}' fill='none' stroke='{color}' stroke-width='2' "
            f"stroke-linejoin='round' stroke-linecap='round' vector-effect='non-scaling-stroke'/></svg>")


def range_bar(lo: float, hi: float, cur: float, label_lo: str = "52W low", label_hi: str = "52W high") -> str:
    pos = 0.0 if hi <= lo else max(0.0, min(100.0, 100 * (cur - lo) / (hi - lo)))
    return (f"<div class='range'><div class='bar'><div class='mk' style='left:{pos:.1f}%'></div></div>"
            f"<div class='ends'><span>{label_lo} ₹{lo:,.0f}</span><span>{label_hi} ₹{hi:,.0f}</span></div></div>")


def stock_hero(company: str, symbol: str, chips_html: str, meta_line: str, price: float, chg_1d: float | None,
               closes: list[float], lo52: float, hi52: float, from_high_pct: float | None) -> str:
    fh = f"{from_high_pct:+.1f}% from 52-week high" if from_high_pct is not None else ""
    return (f"<div class='shero'><div><h1>{esc(company)} <span class='sym'>{esc(symbol)}</span></h1>"
            f"<div>{chips_html}</div><div class='meta'>{meta_line}</div></div>"
            f"<div><div style='display:flex;align-items:baseline;gap:12px;flex-wrap:wrap'><div class='price'>₹{price:,.2f}</div>{pill(chg_1d)}</div>"
            f"<div style='margin-top:8px'>{spark(closes)}</div><div class='sub'>last 6 months</div></div>"
            f"<div>{range_bar(lo52, hi52, price)}<div class='sub'>{esc(fh)}</div></div></div>")


def ring(value: float | None, title: str, label: str = "", hint: str = "", lo: float = 0, hi: float = 100) -> str:
    if value is None or (isinstance(value, float) and math.isnan(value)):
        p, txt, c = 0, "—", T["neutral"]
    else:
        p = max(0.0, min(100.0, 100 * (value - lo) / (hi - lo)))
        txt = f"{value:+.0f}" if lo < 0 else f"{value:.0f}"
        c = T["up"] if p >= 62 else T["down"] if p <= 38 else T["gold"]
    return (f"<div class='ring-card'><div class='ring' style='--p:{p:.0f};--c:{c}' role='img' aria-label='{esc(title)} {txt}'>"
            f"<span>{txt}</span></div><div><div class='t'>{esc(title)}</div><div class='s' style='color:{c}'>{esc(label)}</div>"
            f"<div class='h'>{esc(hint)}</div></div></div>")


def ticker(items: list[dict[str, Any]], live: bool, as_of: str) -> str:
    if not items:
        return ""
    cells = []
    for it in items:
        direction = tone_of(it.get("chg"))
        arrow = "▲" if direction == "up" else "▼" if direction == "down" else "■"
        tone = tone_of(-(it.get("chg") or 0)) if it.get("invert") else direction  # colour = good/bad: VIX up is stress
        chg = it.get("chg")
        c_txt = f"{arrow} {chg:+.2f}%" if chg is not None else "—"
        cells.append(f"<div class='tk'><span class='n'>{esc(it['name'])}</span><span class='v'>{it['value']:,.2f}</span>"
                     f"<span class='c {tone}-t'>{c_txt}</span><span style='width:64px;display:inline-block'>"
                     f"{spark(it.get('spark') or [], 64, 22)}</span></div>")
    row = "".join(cells)
    status = (f"<span class='live'></span>Live" if live else f"<span class='closed'></span>Closed")
    return (f"<div class='ticker' role='region' aria-label='Market indices'><div class='status' title='Prices as of {esc(as_of)}'>{status}"
            f"<span style='font-weight:500;letter-spacing:0;text-transform:none;color:#94a3b8'>{esc(as_of)}</span></div>"
            f"<div class='viewport'><div class='ticker-track'>{row}<div style='display:contents' aria-hidden='true'>{row}</div></div></div></div>")


def breadth_bar(adv: int, dec: int, flat: int = 0) -> str:
    tot = max(1, adv + dec + flat)
    a, d = 100 * adv / tot, 100 * dec / tot
    return (f"<div class='bb' role='img' aria-label='{adv} advancing, {dec} declining'>"
            f"<div class='bb-bar'><span style='width:{a:.1f}%;background:var(--up)'></span>"
            f"<span style='width:{100 - a - d:.1f}%;background:#475569'></span><span style='width:{d:.1f}%;background:var(--down)'></span></div>"
            f"<div class='bb-l'><span class='up-t'>▲ {adv} advancing</span><span class='down-t'>▼ {dec} declining</span></div></div>")


def movers(title: str, rows: list[dict[str, Any]], icon_name: str, accent: str) -> str:
    items = "".join(
        f"<div class='mv-row'><div class='mv-n'><b>{esc(r['symbol'])}</b><span>{esc(str(r.get('name', ''))[:28])}</span></div>"
        f"<div class='mv-s'>{spark(r.get('spark') or [], 90, 28)}</div>"
        f"<div class='mv-p'>₹{r['price']:,.2f}</div><div>{pill(r.get('chg'))}</div></div>" for r in rows)
    return (f"<div class='mv rise' style='--accent:{accent}'><div class='mv-h'>{icon(icon_name)} {esc(title)}</div>{items or '—'}</div>")


MOVERS_CSS = """<style>
.bb{margin:2px 0 14px 0} .bb-bar{display:flex;height:10px;border-radius:999px;overflow:hidden;background:#1e293b}
.bb-bar span{display:block;height:100%;transition:width .6s cubic-bezier(.2,.8,.2,1)}
.bb-l{display:flex;justify-content:space-between;font-size:.8rem;margin-top:6px;font-weight:600}
.mv{position:relative;overflow:hidden;border-radius:16px;padding:14px 16px 8px;border:1px solid rgba(148,163,184,.16);
  background:linear-gradient(180deg,rgba(30,41,59,.55),rgba(15,23,42,.55));margin-bottom:12px}
.mv::before{content:"";position:absolute;inset:0 0 auto 0;height:3px;background:var(--accent)}
.mv-h{font-size:.78rem;text-transform:uppercase;letter-spacing:.08em;font-weight:700;color:#94a3b8;margin-bottom:6px}
.mv-row{display:grid;grid-template-columns:minmax(0,1.4fr) 90px minmax(80px,.7fr) auto;gap:10px;align-items:center;padding:7px 0;
  border-top:1px solid rgba(148,163,184,.10)}
.mv-n{display:flex;flex-direction:column;min-width:0} .mv-n b{color:#f8fafc;font-size:.92rem}
.mv-n span{color:#94a3b8;font-size:.74rem;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.mv-p{font-variant-numeric:tabular-nums;color:#e2e8f0;text-align:right;font-size:.9rem}
@media (max-width: 700px){ .mv-row{grid-template-columns:minmax(0,1fr) auto} .mv-s,.mv-p{display:none} }
</style>"""
