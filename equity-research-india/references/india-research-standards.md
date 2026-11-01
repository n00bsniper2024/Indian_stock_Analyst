# India research standards (shared by every skill in this plugin)

## 1. Evidence discipline
- Get numbers from the engine: `python -m isa.cli analyze <SYMBOL> --out <SYMBOL>.json` (run from the repo root).
  Read the JSON; never compute ratios, CAGRs, DCFs or levels yourself when the engine already has them.
- Tag every claim `[DATA]` (from the fact pack or a cited filing), `[INFERENCE]` (your reasoning — say from what)
  or `[ASSUMPTION]` (general knowledge). Keep `[ASSUMPTION]` rare.
- Anything from outside the fact pack (exchange filings, concall transcripts, news) needs a source link and date.
- List data gaps explicitly instead of filling them with plausible numbers.

## 2. Units and calendar
- Money in ₹ crore (1 cr = 10 million); per-share values in ₹.
- Fiscal year = April–March. FY26 = year ended 31-Mar-2026. Quarters: Q1 Apr–Jun, Q2 Jul–Sep, Q3 Oct–Dec, Q4 Jan–Mar.
- Results deadlines (SEBI LODR Reg 33): 45 days after Q1–Q3 quarter end, 60 days after Q4 (audited).
- Prefer consolidated numbers; say when only standalone is available.

## 3. Primary sources to cite (in order of authority)
1. NSE / BSE corporate filings — results, shareholding pattern (quarterly), pledge disclosures (SAST),
   insider trading (PIT), investor presentations, concall transcripts/recordings, credit-rating actions.
2. Annual report — segment data, related-party transactions, contingent liabilities, auditor's report (CARO).
3. Regulators — RBI (banks/NBFCs), IRDAI (insurers), SEBI (orders), TRAI, CERC/SERC (power), DGCA (aviation).
4. Industry data — SIAM (autos, monthly), CEA (power), JPC (steel), cement dispatches, AMFI (MF flows).

## 4. India checklist (apply what is relevant)
| Area | What to check |
|---|---|
| Promoter | holding level & 8-quarter trend, **pledge %**, creeping acquisitions, OFS/stake sales |
| Governance | related-party transactions as % of revenue, auditor resignations/qualifications, frequent equity raises, group cross-holdings, SEBI orders |
| Earnings quality | CFO/PAT, receivable & inventory days, other income as % of PBT, capitalised interest, exceptional items |
| Lenders | NIM, GNPA/NNPA, PCR, credit cost, CASA, CAR/CET-1, ALM, unsecured-loan mix |
| Cyclicals | position in commodity cycle; don't capitalise peak margins; use mid-cycle EV/EBITDA or P/B |
| Policy | Union Budget, PLI, GST rate changes, customs duty, RBI policy, state elections (power/infra), anti-dumping |
| Macro | monsoon/rural demand, crude, INR/USD (exporters/importers), US tariffs & visa rules (IT/pharma), China+1 |
| Market structure | liquidity (avg traded value), F&O inclusion/ban list, ASM/GSM surveillance, index inclusion flows, FII vs DII ownership |

## 5. Valuation conventions
- Use own-history P/E or EV/EBITDA bands and Indian peers first; global peers only as a cross-check.
- DCF in INR nominal terms: risk-free = 10Y G-Sec, equity risk premium for India (mature ERP + country risk),
  terminal growth below WACC and typically 4–6% nominal. Always show the reverse DCF (implied growth).
- Lenders: P/B vs ROE (justified P/B = (ROE − g)/(Ke − g)), not FCF DCF. Insurers: P/EV. Holdcos: SOTP with a 20–50% holdco discount.

## 6. Compliance language (non-negotiable)
- This plugin produces **educational research**, not investment advice. Unless the user states they are a
  SEBI-registered Research Analyst publishing under their registration, do not issue BUY/SELL/HOLD ratings or price
  targets. Use stance (Bullish / Neutral / Bearish), conviction, and a *model fair-value range under stated assumptions*.
- SEBI expects registered IAs/RAs that use AI tools to disclose that use to clients; if the user is registered,
  remind them to add the disclosure.
- End every deliverable with the disclaimer: "Educational research, not investment advice. Not prepared by a
  SEBI-registered Research Analyst. Investments in securities markets are subject to market risks."
