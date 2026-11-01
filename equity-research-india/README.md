# equity-research-india — Claude plugin

India-adapted, improved version of Anthropic's
[`equity-research`](https://github.com/anthropics/financial-services/tree/main/plugins/vertical-plugins/equity-research)
plugin (Apache-2.0). It shares one analysis engine with the dashboard in this repo, so Claude reads computed numbers
instead of doing arithmetic itself.

## Skills and commands

| Command | Skill | Replaces / adds |
|---|---|---|
| `/analyze TCS` | `india-stock-analysis` | **new** — one-shot fundamental + technical + valuation note |
| `/initiate INFY` | `india-initiating-coverage` | `initiating-coverage` |
| `/results HDFCBANK Q2 FY27` | `india-earnings-analysis` | `earnings-analysis` |
| `/screen "Nifty Midcap 150" quality` | `india-idea-generation` | `idea-generation` |
| `/sector cement` | `india-sector-overview` | `sector-overview` |
| `/catalysts TCS,INFY,WIPRO` | `india-catalyst-calendar` | `catalyst-calendar` |
| `/thesis SBIN` | `india-thesis-tracker` | `thesis-tracker` |

Not ported: `morning-note`, `model-update`, `earnings-preview` (sell-side desk workflows that rely on paid terminals);
their useful parts are folded into the results and catalyst skills.

## What was improved over the original

1. **Numbers come from code, not the model.** Every skill starts with `python -m isa.cli analyze <SYMBOL>`; the model
   interprets the fact pack. The dashboard additionally audits every figure in the AI note against the data.
2. **Evidence tags on every claim** — `[DATA]`, `[INFERENCE]`, `[ASSUMPTION]` — plus an explicit data-gaps section.
3. **Indian market context** — ₹ crore, Apr–Mar fiscal year, LODR result timelines, NSE/BSE filings, promoter
   pledge, related-party checks, lender metrics (NIM/GNPA/CASA), Indian macro & policy calendar.
4. **Technical analysis** across 1H / 4H / Daily / Weekly / Monthly with levels and invalidation (absent upstream).
5. **Valuation upgrades** — reverse DCF (what growth the price implies), justified P/B for lenders, own-history P/E band,
   Altman Z''-EM (emerging-market variant) and Piotroski F-score.
6. **No five-turn refusal loop** — initiation runs end-to-end with checkpoints.
7. **SEBI-aware language** — stance and model fair-value ranges instead of BUY/SELL ratings unless the user is a
   registered Research Analyst; AI-use disclosure reminder.

## Install in Claude Code
```bash
git clone https://github.com/n00bsniper2024/Indian_stock_Analyst.git
cd Indian_stock_Analyst
pip install -r requirements.txt
claude --plugin-dir ./equity-research-india
```
Run Claude from the repo root so `python -m isa.cli …` works.

## Attribution
Derived from Anthropic's `financial-services` repository, licensed under the Apache License 2.0. See `../NOTICE`.
