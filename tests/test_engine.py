"""Engine tests on deterministic synthetic data (no network needed)."""
import os

os.environ["ISA_DEMO"] = "1"

import json  # noqa: E402

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
import pytest  # noqa: E402

from isa import technicals as T  # noqa: E402
from isa.ai import audit_numbers, report_messages  # noqa: E402
from isa.analysis import build_fact_pack, fact_pack_json, overall_signal  # noqa: E402
from isa.demo import demo_prices, demo_stock  # noqa: E402
from isa.fundamentals import annual_table, piotroski  # noqa: E402
from isa.llm import parse_json  # noqa: E402
from isa.overview import category_snapshot  # noqa: E402
from isa.valuation import DCFInputs, dcf_value, reverse_dcf  # noqa: E402


def trend_series(n=400, slope=0.002):
    idx = pd.bdate_range("2024-01-01", periods=n)
    c = 100 * np.exp(slope * np.arange(n))
    return pd.DataFrame({"Open": c * 0.998, "High": c * 1.01, "Low": c * 0.99, "Close": c, "Volume": 1e6}, index=idx)


def test_rsi_bounds_and_extremes():
    up = T.rsi(trend_series()["Close"])
    assert up.dropna().between(0, 100).all()
    assert up.iloc[-1] > 95  # monotonic rise -> RSI near 100


def test_trend_assessment_direction():
    assert T.trend_assessment(trend_series(slope=0.003), "Daily")["score"] == 100
    # in a smooth exponential decline the MACD line converges, so its histogram can turn positive
    down = T.trend_assessment(trend_series(slope=-0.003), "Daily")
    assert down["score"] <= -60 and down["trend"] == "Strong downtrend"


def test_supertrend_follows_trend():
    st = T.supertrend(trend_series(slope=0.003))
    assert st["ST_dir"].iloc[-1] == 1


def test_support_resistance_sides():
    df = demo_prices("TEST")
    sr = T.support_resistance(df)
    px = df["Close"].iloc[-1]
    assert all(s["level"] < px for s in sr["supports"])
    assert all(r["level"] > px for r in sr["resistances"])


def test_dcf_and_reverse_dcf_consistency():
    p = DCFInputs(base_fcf=100.0, growth_1=0.12, terminal_g=0.05, wacc=0.11, years=10, net_debt=0.0, shares=10.0)
    value = dcf_value(p)
    assert value > 0
    implied = reverse_dcf(p, value)
    assert implied == pytest.approx(12.0, abs=0.2)


def test_dcf_rejects_g_above_wacc():
    p = DCFInputs(100, 0.1, 0.12, 0.11, 10, 0, 10)
    assert np.isnan(dcf_value(p))


def test_piotroski_range():
    t = annual_table(demo_stock("TCS"))
    res = piotroski(t)
    assert 0 <= res["score"] <= res["evaluated"] <= 9


def test_fact_pack_is_json_and_complete():
    pack = build_fact_pack("INFY", with_peers=True)
    s = fact_pack_json(pack)
    back = json.loads(s)
    for key in ("meta", "scores", "technical", "fundamentals", "valuation"):
        assert key in back
    assert "NaN" not in s
    assert back["meta"]["data_source"].startswith("DEMO")


def test_overall_signal_labels():
    assert overall_signal(90, 80, 80)["label"].startswith("Strong positive")
    assert overall_signal(None, None, None)["score"] is None


def test_category_snapshot():
    meta = pd.DataFrame({"Symbol": ["AAA", "BBB"], "Company Name": ["A", "B"], "Industry": ["X", "Y"]})
    snap = category_snapshot({s: demo_prices(s, days=300) for s in meta["Symbol"]}, meta)
    assert len(snap) == 2 and {"1D %", "RSI", "Trend score"} <= set(snap.columns)


def test_audit_flags_invented_numbers():
    pack = build_fact_pack("TCS", with_peers=False)
    price = pack["technical"]["performance"]["last_close"]
    rep = {"executive_summary": [f"[DATA] price ₹{price}", "[DATA] order book ₹98,765 crore"]}
    a = audit_numbers(rep, pack)
    assert "98,765" in a["unverified"] and a["figures_checked"] == 2


def test_parse_json_tolerates_fences_and_think_blocks():
    assert parse_json('<think>hmm</think>```json\n{"a": 1}\n```') == {"a": 1}
    assert parse_json('Sure! {"b": 2} done') == {"b": 2}


def test_prompt_builds():
    msgs = report_messages(build_fact_pack("SBIN", with_peers=False))
    assert msgs[0]["role"] == "system" and "FACT PACK" in msgs[1]["content"]


SAMPLE_REPORT = {
    "verdict": {"stance": "Neutral", "conviction": "Medium", "time_horizon": "12 months", "one_liner": "Quality franchise, fair price."},
    "executive_summary": ["[DATA] Health score is high.", "[INFERENCE] Valuation leaves little margin of safety."],
    "business_overview": "Demo company.",
    "company_health": {"assessment": "Good", "summary": "[DATA] Strong.", "strengths": ["[DATA] ROCE high"], "red_flags": []},
    "fundamentals": {"growth": "[DATA] ok", "profitability": "[DATA] ok", "balance_sheet": "[DATA] ok",
                     "cash_flow_and_earnings_quality": "[DATA] ok", "recent_quarters": "[DATA] ok"},
    "valuation": {"assessment": "Fairly valued", "summary": "[INFERENCE] fair", "market_implied_expectations": "[DATA] x",
                  "model_fair_value_range": "₹1 – ₹2", "key_assumptions": ["[ASSUMPTION] stable rates"]},
    "technical": {"summary": "[DATA] down", "short_term": "a", "medium_term": "b", "long_term": "c",
                  "key_levels": {"support": ["₹1"], "resistance": ["₹2"]}, "invalidation": "close above ₹2",
                  "chart_observations": ["[DATA] volume spike"]},
    "bull_case": ["[INFERENCE] a"], "bear_case": ["[INFERENCE] b"], "catalysts": ["[ASSUMPTION] results"],
    "risks": ["[ASSUMPTION] rates"], "what_would_change_my_mind": ["x"], "monitoring_checklist": ["y"], "data_gaps": ["pledge"],
}


def test_generate_report_and_exports(monkeypatch):
    import isa.ai as ai
    from isa.report import to_html, to_markdown

    monkeypatch.setattr(ai, "chat", lambda *a, **k: "```json\n" + json.dumps(SAMPLE_REPORT) + "\n```")
    pack = build_fact_pack("TCS", with_peers=False)
    rep = ai.generate_report(pack, "DeepSeek", "key", "deepseek-flash")
    assert rep["verdict"]["stance"] == "Neutral" and "_audit" in rep
    md = to_markdown(rep, pack)
    assert "Bull case" in md and "SEBI" in md
    html = to_html(rep, pack, [])
    assert '<span class="tag data">DATA</span>' in html


def test_app_renders_report_without_errors():
    from streamlit.testing.v1 import AppTest

    at = AppTest.from_file("../app.py", default_timeout=120)
    at.session_state["report::ADANIENT::DeepSeek::deepseek-flash"] = dict(SAMPLE_REPORT, _audit={"figures_checked": 3, "unverified": [], "unverified_count": 0, "traced_pct": 100.0})
    at.run()
    assert not at.exception, [e.value for e in at.exception]
    assert any("Bull case" in (m.value or "") for m in at.subheader)
