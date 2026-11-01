---
name: india-initiating-coverage
description: Institutional-style initiating-coverage report on an Indian listed company — business and industry research, financial model, valuation (DCF/relative/SOTP or P/B for lenders), 20+ charts and a final DOCX/Markdown report. Runs the full pipeline with checkpoints instead of refusing multi-task requests. Use for "initiate coverage on <company>", "deep-dive report on <Indian company>", "full equity research report".
---

# India initiating coverage

Adapted from Anthropic's `initiating-coverage` skill. Changes, and why:

| Original | This version | Reason |
|---|---|---|
| Refuses to run more than one task per request | Runs all five stages with a **checkpoint after each** (summarise, ask "continue?", proceed) — or straight through if the user says so | The refusal forced five round-trips for a request users make in one sentence |
| US filings (10-K/10-Q), USD, Dec FY | NSE/BSE filings, annual report, ₹ crore, Apr–Mar FY, LODR timelines | Indian market |
| Model computes ratios/DCF in the spreadsheet by itself | Starts from the engine's fact pack; spreadsheet extends it | Removes arithmetic hallucination |
| BUY/HOLD/SELL + price target by default | Stance + model fair-value range unless the user is a SEBI-registered RA | SEBI RA regulations |
| No technical section | Adds multi-timeframe technical and liquidity section | Indian retail users expect it; liquidity matters in mid/small caps |
| Fixed page-count minimums (30+ pages) | Length scales to the company; completeness checklist instead | Page count is a poor proxy for quality |

Read `${CLAUDE_PLUGIN_ROOT}/references/india-research-standards.md` before starting.

## Stage 0 — Scope (ask once, in one message)
Company/symbol · output format (Markdown, DOCX via the `docx` skill, or both) · depth (standard ≈15 pages / deep ≈30) ·
run straight through or pause at checkpoints · user is/isn't SEBI-registered (decides rating language).

## Stage 1 — Company & industry research
1. `python -m isa.cli analyze <SYMBOL> --out <SYMBOL>.json` for the numeric base.
2. Research (cite every item): business model & segments, revenue mix (product/geography/channel), management &
   board, promoter group and pledge, capital-allocation history (acquisitions, raises, dividends), industry size and
   growth, competitive position vs listed Indian peers, regulation, key risks.
3. Deliverable: `<SYMBOL>_research.md` (thesis, 3–5 pillars, industry, competition, management, risks).
**Checkpoint.**

## Stage 2 — Financial model
- Build from the fact pack's `fundamentals.annual` + filings for older years/segments (use the `xlsx` skill).
- Tabs: Assumptions · P&L · Balance sheet · Cash flow · Ratios · Segments (if disclosed). 3–5 years history + 3–5 years forecast.
- Drivers explicit (volume × price, segment growth, margin bridge); formulas, not hard-coded outputs.
**Checkpoint.**

## Stage 3 — Valuation
- Non-financials: DCF (start from the engine's WACC block; show sensitivity WACC × g and reverse DCF), own-history
  multiple band, Indian peer multiples. Conglomerates: SOTP with holdco discount.
- Lenders: justified P/B vs ROE, residual income; insurers: P/EV.
- Reconcile to a **model fair-value range** with weights and reasoning; scenario table (bear/base/bull) with drivers.
**Checkpoint.**

## Stage 4 — Charts (20–30, PNG at 200 dpi or interactive HTML)
Use `isa.charts` where possible (price chart with indicators, trend matrix, radar, football field, DCF heatmap, P/E band,
peer scatter, relative strength) plus matplotlib for model-specific charts (revenue by segment stacked area,
margin bridge, working-capital days, ROCE vs WACC, scenario fan). One axis per chart — no dual-axis charts.
**Checkpoint.**

## Stage 5 — Report assembly
Page 1: thesis-led title, stance/rating box (per compliance), key metrics table, 3–4 thesis bullets, price chart.
Then: investment thesis · business · industry & competition · financial analysis · valuation · technical & liquidity ·
risks · catalysts · governance & ESG · appendix (financial statements, model assumptions, sources).
Evidence tags in analytical sections; sources list with links; disclaimer on the last page.

## Completeness checklist (replaces page-count minimums)
- [ ] Every number traceable to the fact pack, model or a cited filing
- [ ] Promoter holding/pledge and related-party review covered (or flagged as gap)
- [ ] Bear case and "what would change our view" included
- [ ] Valuation shows assumptions, sensitivity and reverse DCF/implied expectations
- [ ] Technical section gives levels + invalidation, not predictions
- [ ] Compliance language matches the user's registration status
