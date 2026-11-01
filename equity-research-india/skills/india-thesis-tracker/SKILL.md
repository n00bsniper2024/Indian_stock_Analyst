---
name: india-thesis-tracker
description: Create and maintain falsifiable investment theses for Indian stocks — pillars, kill-criteria, monitorables and a dated log — re-scored against fresh engine data each quarter. Use for "track my thesis on <stock>", "is my thesis on HDFCBANK still intact", "review my portfolio theses", "add this result to my thesis".
---

# India thesis tracker

Adapted from Anthropic's `thesis-tracker` skill. Theses live as files in `theses/<SYMBOL>.md` in the repo so they persist.
Read `${CLAUDE_PLUGIN_ROOT}/references/india-research-standards.md` first.

## Create
```
# <SYMBOL> — <one-line thesis>            (stance, horizon, date opened, entry context)
## Pillars (3–5, each measurable)
| Pillar | Metric | Threshold | Source/frequency |
## Kill criteria (any one = re-underwrite)
e.g. promoter pledge > 10%, CFO/PAT < 0.6 for 2 years, ROCE < WACC, close below <support> on weekly
## Valuation anchor
model fair-value range + assumptions (from the fact pack / reverse DCF)
## Log
| Date | Event | Pillar affected | Strengthens/Weakens | Conviction |
```
Kill criteria are mandatory — a thesis nothing can disprove is not a thesis.

## Update (each result, major event, or on request)
1. `python -m isa.cli analyze <SYMBOL> --out <SYMBOL>.json` → re-score each pillar from the fact pack
   (quarterly table, ratios, red flags, valuation, trend score). Pull filings for anything the engine lacks (pledge, guidance).
2. Scorecard: pillar · expected · actual · trend (↑/→/↓) · status (on track / watch / broken).
3. Log the event with date and source; update conviction (High/Medium/Low) and say why.
4. If any kill criterion is hit, say so first, in plain words.
5. Record disconfirming evidence as carefully as confirming evidence.

## Portfolio review
Loop over `theses/*.md`; produce a table of stance, conviction change, pillars at risk and upcoming catalysts
(link to `india-catalyst-calendar`). Disclaimer at the end.
