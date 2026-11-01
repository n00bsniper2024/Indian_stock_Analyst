---
name: india-sector-overview
description: Sector or industry overview for the Indian market — structure, demand drivers, policy/regulation, cycle position, listed players compared on growth, returns, valuation and price trend, plus key monitorables. Use for "overview of Indian cement sector", "how is Nifty IT placed", "compare Indian private banks", "sector note on defence".
---

# India sector overview

Adapted from Anthropic's `sector-overview` skill. Read `${CLAUDE_PLUGIN_ROOT}/references/india-research-standards.md` first.

## Workflow
1. **Universe** — pick the matching NSE category (`python -m isa.cli categories`) or the industry bucket from the Nifty 500
   classification; confirm the list with the user if the sector is fuzzy (e.g. "EV", "railways").
2. **Market pulse** — `python -m isa.cli category "<name>"` → breadth (advancers, % above 200-DMA, % in uptrend),
   median returns, leaders/laggards, liquidity.
3. **Company comparison** — for the top 6–10 by traded value, run `analyze --no-peers` and tabulate: revenue/PAT CAGR,
   OPM, ROE/ROCE, D/E, CFO/PAT, P/E vs own median, EV/EBITDA, health score, trend score.
4. **Sector context (cite sources)** — industry size and growth, demand drivers, cost drivers (commodities, wages, power),
   regulation and policy (Budget, PLI, duties, RBI/IRDAI/TRAI rules), competitive structure (share, consolidation, imports),
   cycle position, global linkages (China, US tariffs, crude, INR).
5. **Synthesis** — where in the cycle, what the market is pricing (valuation vs history), who is best/worst positioned and
   why, 3–5 monitorables with data sources and frequency (e.g. SIAM monthly volumes, cement dispatches, credit growth).

## Output
Markdown or DOCX: summary · charts (category treemap/returns heatmap from `isa.charts`, peer scatter P/E vs ROE) ·
comparison table · context · positioning · monitorables · risks · disclaimer.
