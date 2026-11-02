# Design system

The look of the dashboard is defined in one place: `isa/theme.py` (tokens, CSS, HTML components) plus
`.streamlit/config.toml` (Streamlit's own theme) and the palette constants at the top of `isa/charts.py`.

Direction came from the [ui-ux-pro-max](https://github.com/nextlevelbuilder/ui-ux-pro-max-skill) skill
(`--design-system "fintech stock market analytics dashboard dark vibrant" --variance 6 --motion 4 --density 8`):
**Dark Mode (OLED) + Data-Dense Dashboard**, Fira Sans / Fira Code, green-up / red-down semantics. Its default accent
(plain green on slate) was swapped for the skill's Fintech palette accents (indigo/violet with cyan and gold) to make
it more vibrant, while keeping green/red only for gains and losses.

| Token | Value | Use |
|---|---|---|
| Background | `#050816` + soft indigo/cyan/violet glows | page canvas |
| Card | glass gradient `rgba(30,41,59,.55) → rgba(15,23,42,.55)`, 1px `rgba(148,163,184,.16)` border, 16px radius | every panel, chart, tile |
| Brand gradient | `#4f46e5 → #7c3aed` | selected nav, tabs, primary buttons, tile accents |
| Headline gradient | `#c7d2fe → #67e8f9 → #f0abfc` | page and stock titles |
| Up / down | `#22c55e` / `#ef4444` (cells with white text use `#15803d` / `#b91c1c`) | prices, returns, heatmaps |
| Text / muted | `#e2e8f0` / `#94a3b8` | body / labels (≥ 4.5:1 on the background) |
| Charts | `#6366f1 #22d3ee #f59e0b #a855f7 #22c55e #ec4899 #38bdf8 #f97316` | categorical series |

Rules followed
- Icons are Material Symbols (shipped with Streamlit), never emoji.
- Colour never carries meaning alone: changes always show ▲/▼ and a sign.
- Numbers use tabular figures so columns line up.
- Motion: 160–420 ms rise/hover transitions, a pausable ticker; all of it is switched off for users who set
  "reduce motion" in their operating system.
- Visible focus rings on every interactive element; minimum 40 px tap targets; the sidebar collapses on phones.
