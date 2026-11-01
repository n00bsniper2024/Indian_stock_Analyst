---
name: india-earnings-analysis
description: Analyse an Indian company's quarterly results (SEBI LODR Reg 33 filing) — beat/miss vs consensus or own run-rate, YoY/QoQ drivers, margins, segment trends, management commentary from the concall, and the impact on the thesis and valuation. Use for "Q2 results of <company>", "how were INFY results", "earnings update", "results review".
---

# India quarterly results review

Adapted from Anthropic's `earnings-analysis` skill for Indian disclosure practice.
Read `${CLAUDE_PLUGIN_ROOT}/references/india-research-standards.md` first.

## Inputs
1. Engine data: `python -m isa.cli analyze <SYMBOL> --no-peers --out <SYMBOL>.json` → `fundamentals.quarterly`
   (revenue, operating profit, net profit, OPM, QoQ/YoY), valuation and price reaction (`technical.performance`).
2. Filings (cite each): results PDF on NSE/BSE (consolidated), investor presentation, concall transcript/recording,
   press release. Note the filing date/time — Indian companies often file during or after market hours.
3. Expectations: consensus if the user supplies it or a cited source has it; otherwise compare with the company's own
   run-rate (last 4 quarters) and guidance — and say that is the benchmark used.

## Workflow
1. **Headline (lead with the call):** "<Company> Q2 FY27: <what mattered> — <thesis impact>". No generic titles.
2. **Scorecard table:** Revenue · EBITDA · EBITDA margin · PAT · EPS — actual, YoY, QoQ, vs expectation (₹ cr and %).
3. **Drivers:** volume vs price/mix, segment and geography, cost lines (raw material, employee, other expenses),
   other income and exceptional items (strip one-offs to get core PAT), tax-rate changes.
4. **Quality checks:** cash flow/working capital if half-year balance sheet is out (H1/H2), receivables, inventory,
   debt movement; for lenders NIM, GNPA/NNPA, credit cost, CASA, loan growth.
5. **Management commentary:** guidance changes, demand outlook, capex, pricing, order book — quote ≤15 words, cite.
6. **Estimate & valuation impact:** which assumptions change; re-run valuation lenses if material (>5% EPS change).
7. **Technical reaction:** price/volume on result day vs supports/resistances from the fact pack.
8. **Thesis check:** which pillar strengthened/weakened (link to `india-thesis-tracker` if a thesis exists).

## Output
1–3 page markdown note (or DOCX on request) with the scorecard, a quarterly trend chart
(`isa.charts.bars` on `fundamentals.quarterly`) and the disclaimer. Be fast and focused — this is not an initiation.

## Common mistakes
- Comparing standalone with consolidated, or Q-o-Q for seasonal businesses without saying so.
- Calling a beat that came from other income, tax write-backs or exceptional gains.
- Ignoring the Q4 = audited, 60-day timeline (Q4 numbers may restate prior quarters).
