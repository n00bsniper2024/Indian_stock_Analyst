Produce a complete research note on **{company} ({symbol})** using the FACT PACK below.

Methodology (adapted from the Anthropic equity-research plugin's initiating-coverage, earnings-analysis
and thesis-tracker workflows):
1. Lead with the conclusion — a thesis-focused one-liner, not a description of the company.
2. Business & health: what drives the economics, how strong the balance sheet and cash conversion are.
3. Fundamentals: growth, profitability, balance sheet, cash flow, earnings quality — with trends, not snapshots.
4. Valuation: reconcile the lenses (own P/E history, peers, DCF/reverse-DCF or justified P/B). The reverse
   DCF tells you what growth the market already prices in — use it to judge expectations.
5. Technicals across timeframes with key levels and invalidation.
6. Bull case vs bear case — both must be falsifiable and specific.
7. Catalysts and risks with an India lens; what would change your mind.
8. A monitoring checklist the reader can track each quarter.

Return ONE JSON object with exactly these keys (strings may use **bold**; every bullet starts with an evidence tag):

{{
  "verdict": {{
    "stance": "Bullish | Neutral | Bearish",
    "conviction": "Low | Medium | High",
    "time_horizon": "e.g. 12-24 months (fundamental) / 2-6 weeks (technical)",
    "one_liner": "thesis in <= 30 words"
  }},
  "executive_summary": ["3-5 tagged bullets, most important first"],
  "business_overview": "2-4 sentences on what the company does and what drives its economics",
  "company_health": {{
    "assessment": "Excellent | Good | Average | Weak | Distressed",
    "summary": "2-3 sentences",
    "strengths": ["tagged bullets"],
    "red_flags": ["tagged bullets — include the deterministic red flags if any, and your own concerns"]
  }},
  "fundamentals": {{
    "growth": "tagged paragraph",
    "profitability": "tagged paragraph",
    "balance_sheet": "tagged paragraph",
    "cash_flow_and_earnings_quality": "tagged paragraph",
    "recent_quarters": "tagged paragraph on the latest quarterly trend (YoY/QoQ)"
  }},
  "valuation": {{
    "assessment": "Undervalued | Fairly valued | Overvalued | Not determinable",
    "summary": "tagged paragraph reconciling the lenses",
    "market_implied_expectations": "what the reverse DCF / multiples say the market expects",
    "model_fair_value_range": "₹X – ₹Y under the fact-pack assumptions, or 'not determinable'",
    "key_assumptions": ["tagged bullets"]
  }},
  "technical": {{
    "summary": "tagged paragraph",
    "short_term": "1H/4H/Daily read (traders)",
    "medium_term": "Daily/Weekly read (swing/positional)",
    "long_term": "Monthly read (investors)",
    "key_levels": {{"support": ["₹ levels with reason"], "resistance": ["₹ levels with reason"]}},
    "invalidation": "level or condition that would negate the current technical view",
    "chart_observations": ["tagged bullets: events, divergences, candlesticks, channel position, volume"]
  }},
  "bull_case": ["3-4 tagged, falsifiable bullets"],
  "bear_case": ["3-4 tagged, falsifiable bullets"],
  "catalysts": ["tagged bullets with rough timing (e.g. next quarterly results, Budget, RBI policy)"],
  "risks": ["tagged bullets, India-specific where relevant"],
  "what_would_change_my_mind": ["specific, observable triggers"],
  "monitoring_checklist": ["metrics/levels to check every quarter"],
  "data_gaps": ["what is missing from the fact pack that matters for this stock"]
}}

FACT PACK (JSON):
{fact_pack}
