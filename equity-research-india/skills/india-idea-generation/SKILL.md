---
name: india-idea-generation
description: Screen Indian stocks for new ideas — quality, value, growth, momentum/technical-breakout and red-flag (avoid) screens across Nifty indices, sectors or market-cap buckets, then shortlist with one-paragraph pitches. Use for "find good Indian stocks in <sector>", "screen Nifty Midcap 150", "stocks near 52-week high with strong fundamentals", "pitch me ideas".
---

# India idea generation

Adapted from Anthropic's `idea-generation` skill; screens run on real data through the engine, then Claude adds judgement.
Read `${CLAUDE_PLUGIN_ROOT}/references/india-research-standards.md` first.

## Step 1 — Parameters (ask only what is missing)
Universe (category from `python -m isa.cli categories`) · style (quality / value / growth / momentum / turnaround / avoid-list) ·
horizon · liquidity floor (default ≥ ₹10 cr average daily traded value; small caps below this are hard to exit).

## Step 2 — Technical/price pass (whole universe, one batched download)
```bash
python -m isa.cli category "Nifty Midcap 150 (Mid cap)" --csv > universe.csv
```
Columns: returns (1D–1Y), RSI, distance from 52W high, above 200-DMA, daily trend score, turnover.
Typical filters — Momentum: trend score ≥ 60, within 10% of 52W high, RSI 55–75. Pullback-in-uptrend: above 200-DMA,
RSI 35–50, 1M return < 0. Avoid: below 200-DMA and trend score ≤ −60.

## Step 3 — Fundamental pass (shortlist only — keeps Yahoo requests low)
For the top 10–15 survivors: `python -m isa.cli analyze <SYMBOL> --no-peers --out <SYMBOL>.json`, then apply:

| Screen | Rules (from the fact pack) |
|---|---|
| Quality | ROCE > 15% (ROE > 15% for lenders), CFO/PAT 3y avg > 0.8, D/E < 0.5, Piotroski ≥ 6, no red flags |
| Value | P/E below own 5-yr median and peer median, earnings yield > 10Y G-Sec, positive FCF, PEG < 1.5 |
| Growth | revenue CAGR > 15%, PAT CAGR > 18%, last 2 quarters profit YoY positive, margins stable/expanding |
| Turnaround | latest-year ROA up, margin expansion, leverage falling (Piotroski checks), price above 200-DMA |
| Avoid list | ≥ 2 red flags, Altman Z''-EM in distress, CFO/PAT < 0.5, rising receivable days, promoter < 25% |

## Step 4 — Shortlist & pitch
For 3–5 names: one-paragraph thesis, the 2–3 numbers that matter, the key risk, valuation context, technical setup
(trend + nearest support/resistance), and what would invalidate it. Evidence-tag every line.

## Step 5 — Output
Ranked table + pitches + a "what the screen cannot see" section (governance, pledge, concall tone, one-offs).
Disclaimer at the end. Screens find candidates; they are not recommendations.
