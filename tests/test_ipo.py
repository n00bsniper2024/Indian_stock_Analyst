"""IPO module tests (offline)."""
import os

os.environ["ISA_DEMO"] = "1"

import json  # noqa: E402

import pytest  # noqa: E402

from isa import ipo  # noqa: E402

BCSSL = {  # figures copied from the BCSSL RHP restated statements (₹ million)
    "unit": "million",
    "periods": [
        {"period": "FY24", "is_full_year": True, "revenue_from_operations": 7552.59, "profit_after_tax": 211.38, "net_worth": 543.59,
         "non_current_borrowings": 406.91, "current_borrowings": 1934.69},
        {"period": "FY25", "is_full_year": True, "revenue_from_operations": 10557.07, "profit_after_tax": 286.72, "net_worth": 830.47,
         "non_current_borrowings": 392.25, "current_borrowings": 2377.36},
        {"period": "FY26", "is_full_year": True, "revenue_from_operations": 12668.18, "profit_after_tax": 305.39, "net_worth": 1215.81,
         "non_current_borrowings": 522.89, "current_borrowings": 2861.65},
        {"period": "Jun-26 (3M)", "is_full_year": False, "revenue_from_operations": 3970.80, "profit_after_tax": 150.75, "net_worth": 1366.15},
    ],
    "equity_share_capital_latest": 405.00, "face_value_per_share": 10,
    "peers": [{"name": "A", "pe": 14.98}, {"name": "B", "pe": 31.03}, {"name": "C", "pe": 98.54}],
}


def test_price_band_and_amounts():
    assert ipo.price_band("Rs.78 to Rs.82") == (78.0, 82.0)
    a = ipo.parse_issue_amounts("Initial Public Offer comprising of Fresh Issue aggregating upto Rs. 1,830.57 million")
    assert a["fresh_issue_cr"] == pytest.approx(183.06, abs=0.01) and a["structure"].startswith("Fresh issue only")
    b = ipo.parse_issue_amounts("Fresh Issue of Rs. 400 crore and an Offer for Sale aggregating up to Rs 250 crore")
    assert b["fresh_issue_cr"] == 400 and b["structure"] == "Fresh issue + offer for sale"


def test_subscription_ignores_zero_offered_rows():
    rows = [{"sr": "1", "category": "Qualified Institutional Buyers(QIBs)", "offered": 0, "bid": 0, "times": None},
            {"sr": "3", "category": "Individual Investors (IND category bidding for 2 Lots)", "offered": 100, "bid": 250, "times": 2.5},
            {"sr": None, "category": "Total", "offered": 300, "bid": 900, "times": 3.0}]
    s = ipo.subscription_summary(rows)
    assert s["qib"] is None and s["retail"] == 2.5 and s["total"] == 3.0


def test_compute_financials_matches_hand_calculation():
    f = ipo.compute_financials(BCSSL, price_high=82, fresh_issue_cr=183.057)
    assert f["latest_full_year"] == "FY26"
    assert f["roe_pct"] == pytest.approx(25.1, abs=0.1)          # RHP states 25.12%
    assert f["debt_to_equity"] == pytest.approx(2.78, abs=0.01)
    assert f["revenue_cagr_pct"] == pytest.approx(29.5, abs=0.1)
    assert f["post_issue_shares"] == pytest.approx(40_500_000 + 1830.57e6 / 82, rel=1e-3)
    assert f["pe_at_upper_band"] == pytest.approx(16.9, abs=0.1)
    assert f["peer_median_pe"] == 31.0 and f["pe_premium_to_peers_pct"] < 0
    json.dumps(f)  # no NaN objects


def test_verify_numbers_flags_figures_not_in_source():
    src = "Revenue from operations 12,668.18 10,557.07 Profit 305.39"
    v = ipo.verify_numbers({"a": 12668.18, "b": 305.39, "c": 999.99}, src)
    assert v["checked"] == 3 and v["not_found_in_rhp"] == ["c=999.99"]


def test_heading_detection_is_strict():
    assert ipo._is_heading("239\n\nOUR BUSINESS\n\nSome of the information", r"(OUR BUSINESS|BUSINESS OVERVIEW)")
    assert ipo._is_heading("81\nSECTION V - CAPITAL STRUCTURE\nThe Equity", r"\bCAPITAL STRUCTURE\b")
    assert not ipo._is_heading("22\na timely manner, which could affect our business and results", r"(OUR BUSINESS|BUSINESS OVERVIEW)")


def test_scorecard_and_demo_fact_pack():
    card = ipo.list_ipos()[0]
    pack = ipo.ipo_fact_pack(card, BCSSL)
    sc = pack["listing_scorecard"]
    assert 0 <= sc["score"] <= 100 and sc["factors"]
    assert pack["ipo"]["min_investment_rs"] == 150 * 100
    assert pack["financials_computed"]["pe_at_upper_band"] > 0
    assert pack["market_mood"]["available"]


def test_subscription_chart_labels_nii_buckets_correctly():
    from isa.charts import ipo_subscription

    rows = [{"category": "Non Institutional Investors(Bid amount of more than Ten Lakh Rupees)", "offered": 10, "times": 1.23},
            {"category": "Non Institutional Investors(Bid amount of more than Two Lakh Rupees upto Ten Lakh Rupees)", "offered": 10, "times": 2.94}]
    bar = ipo_subscription(rows).data[0]
    assert dict(zip(bar.y, bar.x)) == {"NII (> ₹10 lakh)": 1.23, "NII (₹2–10 lakh)": 2.94}
