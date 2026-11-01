Analyse the Indian IPO of **{company} ({symbol}, {board})** using ONLY the IPO FACT PACK below
(NSE issue data, live subscription, ratios computed in code from RHP figures, RHP extracts, and recent
IPO listing outcomes). Write for a retail investor deciding whether to apply.

Evidence rules: tag every claim [DATA] (from the fact pack), [INFERENCE] (your reasoning — say from what) or
[ASSUMPTION] (general knowledge, use sparingly). Do not invent grey-market premium (GMP), anchor names,
analyst views or numbers. If subscription is still in progress, say the verdict may change at close.

How to judge each horizon:
- **Listing gains** (sell on listing day): driven by demand and pricing — QIB and NII subscription
  (institutions and HNIs are the most informed money), total subscription, issue size, pricing vs listed
  peers, offer-for-sale share, and recent IPO market mood. Strong business ≠ listing pop, and vice versa.
  Use `listing_scorecard` as the starting point and explain where you disagree.
- **Short term** (1–6 months after listing): post-listing supply (anchor lock-in expiry 30/90 days),
  valuation vs peers, momentum of the sector, quality of demand (institutional vs retail-only).
- **Long term** (2–3 years+): business quality and moat, growth and margins, return on equity,
  balance sheet, cash conversion, use of IPO money (growth capex vs debt repayment vs promoters selling),
  promoter holding after issue, governance/litigation, valuation you pay vs what you get.
- SME issues: smaller, illiquid, with large minimum tickets; be more conservative and say so.

Verdict vocabulary (exactly one per horizon):
- listing_gains: "Apply" | "Apply with caution" | "Avoid"
- short_term: "Hold after listing" | "Wait and watch" | "Avoid"
- long_term: "Good long-term candidate" | "Wait for a better price" | "Avoid"

LENGTH BUDGET (strict — longer answers get cut off and are lost):
- Every list: at most 4 bullets. Every bullet: one claim, at most 30 words, starting with its tag.
- No paragraphs: everything except one_liner and verdicts is a list of short tagged bullets.
- Whole answer: under 1,200 words.

Return ONE JSON object:
{{
  "one_liner": "<= 30 words: the essence of this IPO (no tag)",
  "suggestions": {{
    "listing_gains": {{"verdict": "...", "confidence": "Low | Medium | High", "reasons": ["2-3 tagged bullets"]}},
    "short_term": {{"verdict": "...", "confidence": "Low | Medium | High", "reasons": ["2-3 tagged bullets"]}},
    "long_term": {{"verdict": "...", "confidence": "Low | Medium | High", "reasons": ["2-3 tagged bullets"]}}
  }},
  "company_position": ["what it does, market position, scale vs peers, competitive edge — tagged bullets"],
  "fundamentals": {{
    "assessment": "Strong | Decent | Average | Weak | Not enough data",
    "growth": ["tagged bullets"], "profitability": ["tagged bullets"],
    "balance_sheet": ["tagged bullets"], "cash_flows": ["tagged bullets"]
  }},
  "valuation": {{"assessment": "Cheap | Fair | Expensive | Not determinable", "points": ["P/E, market cap/sales, vs peers — tagged bullets"]}},
  "issue_structure": ["fresh vs OFS, use of proceeds, promoter holding, lead managers — tagged bullets"],
  "demand": ["subscription by category and what it signals — tagged bullets"],
  "strengths": ["tagged bullets"],
  "risks": ["tagged bullets — company-specific, India-specific"],
  "red_flags": ["tagged bullets, or empty list"],
  "what_to_check_before_applying": ["short bullets"],
  "data_gaps": ["short bullets"]
}}

IPO FACT PACK (JSON):
{fact_pack}
