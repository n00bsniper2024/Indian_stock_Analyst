---
name: india-stock-analysis
description: Full analysis of one NSE/BSE-listed Indian stock — company health, fundamentals, valuation, multi-timeframe technical analysis and chart reading — with charts, using numbers computed by the Indian Stock Analyst engine. Use when the user asks to "analyse RELIANCE", "is TCS fundamentally strong", "technical view on SBIN", "what's the trend in Tata Steel", "should I look at <Indian stock>", or names any NSE symbol.
---

# India stock analysis

The one-stop workflow behind the dashboard, for use inside Claude. It replaces the US-centric multi-task
initiation flow for everyday questions: one request → one complete, evidence-tagged note.

Read `${CLAUDE_PLUGIN_ROOT}/references/india-research-standards.md` first — it holds the evidence, units,
source and compliance rules every step below relies on.

## Step 1 — Resolve the symbol
- Accept company names or symbols; map to the NSE symbol (e.g. "Tata Motors PV" → `TMPV`, "Zomato" → `ETERNAL`).
- If ambiguous (group companies, demergers), ask once with the candidate symbols.

## Step 2 — Get the fact pack (do not skip, do not hand-compute)
From the repository root:
```bash
pip install -r requirements.txt        # first time only
python -m isa.cli analyze <SYMBOL> --out <SYMBOL>.json
```
Read the JSON. Key blocks: `scores`, `technical.timeframes`, `technical.support_resistance`,
`fundamentals.annual|quarterly|piotroski|altman_z_em|red_flags|health`, `valuation.multiples|dcf|pe_history|peers|football_field`,
`meta.warnings`, plus `classification` (NSE sector, industry, cap bucket, indices), `breakouts.<1H|4H|1D|1W>`
(support/resistance zones and patterns with trigger/target/invalidation), `news` (NSE filings, next results date,
corporate actions, headlines) and `horizon_view` (model rating per horizon 1 Week → Long term, drivers, trade plan,
and the historical check of how this stock behaved after similar setups). If the command fails with a rate-limit message, wait and retry once; if the symbol has no data,
say so — never substitute remembered numbers.

## Step 3 — Fill the gaps the engine cannot see (only if web access is available)
Search NSE/BSE filings and reputable press for: latest shareholding pattern (promoter %, **pledge %**, FII/DII trend),
the latest quarterly result and concall highlights, guidance, major orders/approvals, rating actions, regulatory orders.
Cite each with link + date and tag `[DATA]`. If you cannot verify, list it under data gaps.

## Step 4 — Analyse (in this order; lead with the conclusion)
1. **Verdict** — stance (Bullish/Neutral/Bearish), conviction, horizon, ≤30-word thesis.
2. **Company health** — interpret `fundamentals.health.components`, Piotroski checks, Altman Z''-EM zone and every
   rule-based red flag. Disagree with the mechanical score when evidence warrants (cyclical peak, one-offs, lender).
3. **Fundamentals** — growth (CAGR + latest quarters YoY/QoQ), profitability (margins, ROE/ROCE trend),
   balance sheet, cash conversion (CFO/PAT, FCF, working-capital days).
4. **Valuation** — reconcile own P/E band, peer medians, DCF and the **reverse DCF** (what growth the price implies)
   or justified P/B for lenders. State the model fair-value range and its key assumptions.
5. **Technicals** — read each timeframe (1H/4H traders, Daily/Weekly swing, Monthly investors); note alignment or
   conflict; use only the supplied levels, Fibonacci, regression channel, events, candlestick shapes; give an
   invalidation level (e.g. close below support or 2×ATR). Do not invent chart patterns.
6. **Bull vs bear** — 3–4 falsifiable points each.
7. **Horizon ratings** — start from `horizon_view`; move a rating at most one notch with a cited reason;
   say when the historical check shows no edge; give the plan (entry zone / stop / targets) only if reward/risk ≥ 1.5.
8. **Levels & breakouts per timeframe** — zones and patterns for 1H, 4H, 1D, 1W with status and invalidation.
9. **News & results** — material filings first, headlines second; flag conflicting numbers and upcoming results.
10. **Catalysts, risks (India lens), what would change the view, quarterly monitoring checklist, data gaps.**

## Step 5 — Visuals
If the user wants charts and the dashboard is not running, generate them with the engine's Plotly helpers:
```python
from isa.data import get_stock; from isa import charts
sd = get_stock("<SYMBOL>")
charts.price_chart(sd.daily, "<SYMBOL> daily").write_html("<SYMBOL>_price.html")
```
(`trend_matrix`, `football_field`, `dcf_heatmap`, `radar`, `peer_scatter`, `pe_band` are also available.)
Or tell the user to run `streamlit run app.py` for the interactive dashboard.

## Step 6 — Output
A concise markdown note (≈800–1,500 words) with the sections above, evidence tags on every bullet,
a scores table from `scores`, and the compliance disclaimer from the standards file. No BUY/SELL ratings.

## Quality bar
- Every number traceable to the fact pack or a cited filing.
- Both sides argued; the bear case is not a strawman.
- Data gaps listed (pledge, segment mix, bank asset quality, guidance) rather than guessed.
