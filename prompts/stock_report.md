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
7. News, results and exchange announcements — what changed recently and what is scheduled.
8. Support/resistance zones and breakout patterns on 1H, 4H, 1D and 1W.
9. Horizon-wise ratings (1 Week → Long term) starting from the model ratings, and a best-horizon suggestion.
10. Catalysts and risks with an India lens; what would change your mind; a quarterly monitoring checklist.

LENGTH BUDGET (strict — longer answers get cut off and are lost): every paragraph at most 60 words; every list at
most 4 bullets of at most 30 words each; whole answer under 1,800 words. Prefer short tagged sentences over long ones.

Return ONE JSON object with exactly these keys (strings may use **bold**; every bullet starts with an evidence tag):

{{
  "verdict": {{
    "stance": "Bullish | Neutral | Bearish (overall, for the best-fit horizon)",
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
  "horizon_ratings": [
    {{"horizon": "1 Week | 4 Weeks | 3 Months | 6 Months | 1 Year | Long term (3Y+)",
      "model_rating": "copy from horizon_view", "ai_rating": "Strong Buy | Buy | Neutral | Sell | Strong Sell",
      "conviction": "Low | Medium | High",
      "rationale": "1-2 tagged sentences; if ai_rating differs from model_rating, say exactly why",
      "plan": "entry zone / stop / targets from horizon_view plan, or 'no attractive setup'"}}
  ],
  "investment_suggestion": {{
    "best_horizon": "the horizon with the best risk-adjusted case, or 'none — wait'",
    "summary": "3-4 tagged sentences: what to do over which duration and what to watch; no position sizing",
    "avoid_if": "conditions under which this suggestion does not apply (e.g. results miss, breakdown below ₹X)"
  }},
  "levels_and_breakouts": [
    {{"timeframe": "1 Hour | 4 Hour | 1 Day | 1 Week",
      "support_zones": ["₹low–₹high (touches, why it matters)"],
      "resistance_zones": ["₹low–₹high (touches)"],
      "patterns": ["pattern — status — trigger ₹ / target ₹ / invalidation ₹"],
      "read": "one tagged sentence: what a trader on this timeframe should watch next"}}
  ],
  "news_and_results": {{
    "latest_results": "tagged summary of the most recent results evidence (filings, quarterly table, headlines; flag conflicts)",
    "key_announcements": ["tagged bullets of material filings (orders, M&A, fund raising, pledge/SAST, rating, management, legal)"],
    "news_sentiment": "Positive | Mixed | Negative | Not enough news",
    "upcoming_events": ["results date, ex-dates, other scheduled events from the fact pack"]
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
