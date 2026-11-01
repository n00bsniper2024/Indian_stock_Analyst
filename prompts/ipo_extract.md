You are extracting figures from excerpts of an Indian IPO Red Herring Prospectus (RHP) for **{company}**.

Rules:
- Copy numbers EXACTLY as printed (no rounding, no unit conversion, no arithmetic). Remove commas only.
- If a figure is not in the excerpts, use null. Never estimate.
- Restated financial statements are usually in ₹ lakhs or ₹ million — report the unit printed in the table header.
- Periods: list them oldest → newest. Mark stub periods (e.g. "three months ended June 30, 2026") with is_full_year=false.
- "post_issue_shares" = number of equity shares outstanding AFTER the issue (look in Capital Structure / The Issue /
  Basis for Issue Price). If only pre-issue shares and fresh-issue shares are given, return both and leave post_issue_shares null.
- Borrowings: copy non-current and current borrowings separately exactly as printed (do NOT add them up).
- Always copy "Equity share capital" from the latest restated balance sheet (same unit) and the face value per share.
- Peers: copy the listed-peer comparison table from "Basis for Issue Price" (name, P/E, RoNW %) if present.
- For each list item (objects, risks, litigation) write ONE short factual line in your own words, with the RHP page if visible.

Return ONE JSON object:
{{
  "unit": "lakhs | million | crore",
  "periods": [{{"period": "FY2024 / Mar-25 / Jun-26 (3M)", "is_full_year": true,
               "revenue_from_operations": 0, "total_income": 0, "ebitda": 0, "profit_after_tax": 0,
               "net_worth": 0, "non_current_borrowings": 0, "current_borrowings": 0, "total_assets": 0, "basic_eps": 0, "cash_from_operations": 0}}],
  "pre_issue_shares": 0, "fresh_issue_shares": 0, "ofs_shares": 0, "post_issue_shares": 0,
  "equity_share_capital_latest": 0, "face_value_per_share": 0,
  "promoter_holding_pre_issue_pct": 0, "promoter_holding_post_issue_pct": 0,
  "ipo_pe_upper_band_as_stated": 0, "ronw_latest_pct_as_stated": 0, "nav_per_share_as_stated": 0,
  "peers": [{{"name": "", "pe": 0, "ronw_pct": 0}}],
  "objects_of_issue": ["what the fresh-issue money will be used for, with ₹ amounts as printed"],
  "business_summary": "3-4 factual sentences: what the company makes/does, customers, plants/locations, revenue mix",
  "industry_summary": "2-3 sentences on the industry from the RHP",
  "key_risks": ["top 6 risks specific to this company (not generic boilerplate)"],
  "litigation_summary": "count/amount of material litigation against company/promoters if stated, else null",
  "contingent_liabilities": "as printed, else null",
  "related_party_notes": "material related-party dependence, else null",
  "promoters": ["promoter names"]
}}

RHP EXCERPTS (section name and PDF pages in brackets):
{excerpts}
