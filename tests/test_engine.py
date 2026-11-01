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

    import isa.llm as L

    monkeypatch.setattr(L, "chat", lambda *a, **k: L._text("```json\n" + json.dumps(SAMPLE_REPORT) + "\n```", False))
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


# ---------------------------------------------------------------- zones, patterns, horizons, news
from isa import patterns as P  # noqa: E402
from isa.horizons import HORIZONS, daily_score_series, historical_check, label_for  # noqa: E402
from isa.news import summarise, tag  # noqa: E402


def _bars(closes, start="2025-01-01", spread=0.01, vol=1e6):
    idx = pd.bdate_range(start, periods=len(closes))
    c = np.asarray(closes, dtype=float)
    return pd.DataFrame({"Open": c, "High": c * (1 + spread), "Low": c * (1 - spread), "Close": c, "Volume": vol}, index=idx)


def test_zones_sit_on_correct_side_of_price():
    df = demo_prices("ZONE")
    z = P.zones(df.iloc[-250:], 5)
    px = df["Close"].iloc[-1]
    assert all(s["high"] < px for s in z["supports"]) and all(r["low"] > px for r in z["resistances"])
    assert all(s["low"] < s["high"] for s in z["supports"] + z["resistances"])


def test_range_breakout_detected_with_volume():
    rng = np.random.default_rng(1)
    flat = 100 + rng.uniform(-1, 1, 60)
    closes = np.r_[np.linspace(80, 100, 40), flat, [104, 105.5]]
    df = _bars(closes, spread=0.004)
    df.iloc[-2, df.columns.get_loc("Volume")] = 5e6
    pats = P.consolidation(df, recent=2)
    assert pats and pats[0]["pattern"] == "Range breakout" and pats[0]["status"] == "breakout confirmed"
    assert pats[0]["invalidation"] < pats[0]["trigger"] < pats[0]["target"]


def test_ascending_triangle_classified():
    i = np.arange(80)
    amp = np.linspace(14, 3, 80)                       # swings get smaller...
    closes = 110 - amp * (1 - np.cos(2 * np.pi * i / 16)) / 2   # ...tops stay at 110, bottoms rise
    df = _bars(closes, spread=0.002)
    pats = P.triangles(df, 3)
    assert pats and pats[0]["pattern"] == "Ascending triangle" and pats[0]["direction"] == "bullish"


def test_breakout_scan_shape_demo():
    res = P.breakout_scan(demo_stock("TCS"))
    assert set(res) == {"1H", "4H", "1D", "1W"}
    for tf in res.values():
        if tf.get("available"):
            assert tf["breakout_bias"] in ("bullish", "bearish", "neutral")
            for p in tf["patterns"]:
                assert {"pattern", "status", "trigger", "target", "invalidation", "direction"} <= set(p)


def test_closing_stub_merged():
    idx = pd.to_datetime(["2026-10-30 14:15", "2026-10-30 15:15", "2026-10-31 09:15"])
    df = pd.DataFrame({"Open": [1, 2, 3], "High": [2, 5, 4], "Low": [0.5, 1.5, 2.5], "Close": [1.5, 4, 3.5], "Volume": [10, 5, 7]}, index=idx)
    m = P.merge_closing_stub(df)
    assert len(m) == 2 and m.iloc[0]["High"] == 5 and m.iloc[0]["Volume"] == 15 and m.iloc[0]["Close"] == 4


def test_vectorised_score_matches_scalar():
    df = demo_prices("VEC")
    assert daily_score_series(df).iloc[-1] == T.trend_assessment(df, "Daily")["score"]


def test_historical_check_fields():
    h = historical_check(demo_prices("HIST"))
    assert h["available"]
    one = h["1 Week"]
    assert 0 <= one["pct_positive_similar"] <= 100 and one["samples"] >= 30


def test_horizon_ratings_complete():
    pack = build_fact_pack("INFY", with_peers=False)
    hv = pack["horizon_view"]
    assert set(hv["horizons"]) == set(HORIZONS)
    for h in hv["horizons"].values():
        if h.get("score") is not None:
            assert h["rating"] == label_for(h["score"]) and h["confidence"] in ("Low", "Medium", "High")
    assert hv["horizons"]["1 Week"]["confidence"] != "High"  # weekly calls are never high-confidence
    assert "suggestion" in hv


def test_news_tags():
    assert tag("Company has bagged an order worth Rs 500 crore") == ["Order/contract"]
    assert tag("in order to comply with Regulation 30") == ["Other"]
    assert tag("Trading Window closure pursuant to SEBI (PIT)") == ["Routine compliance"]
    assert tag("informed the Exchange about Certificate under SEBI (Depositories and Participants) Regulations, 2018") == ["Routine compliance"]
    assert "Promoter / pledge / SAST" in tag("Disclosure of pledge of shares by promoter")


def test_news_summary_next_results():
    from datetime import date, timedelta

    d = date.today() + timedelta(days=6)
    s = summarise({"announcements": [], "board_meetings": [{"date": str(d), "purpose": "x", "details": "results", "is_results": True}],
                   "corporate_actions": [], "news": [], "errors": []})
    assert s["days_to_results"] == 6


# ---------------------------------------------------------------- AI output robustness
def test_parse_json_repairs_cut_off_answer():
    from isa.llm import parse_json

    cut = '{"one_liner": "x", "fundamentals": {"growth": "[DATA] a", "assessment": "Average"}, "issue_structure": "[DATA] fresh issue. [INFERENCE] lowers interest co'
    d = parse_json(cut)
    assert d["_truncated"] and d["fundamentals"]["assessment"] == "Average" and "issue_structure" not in d
    assert parse_json('{"a": ["x", "y", "unfin') == {"a": ["x", "y"], "_truncated": True}


def test_chat_json_retries_once_when_truncated(monkeypatch):
    import isa.llm as L

    calls = []

    def fake(provider, key, model, messages, **kw):
        calls.append(messages)
        return L._text('{"a": 1, "b": "long', True) if len(calls) == 1 else L._text('{"a": 1, "b": "short"}', False)

    monkeypatch.setattr(L, "chat", fake)
    out = L.chat_json("DeepSeek", "k", "m", [{"role": "user", "content": "q"}])
    assert out == {"a": 1, "b": "short"} and len(calls) == 2 and "cut off" in calls[1][-1]["content"]


def test_as_points_splits_tagged_paragraphs():
    import ast
    import re as _re
    from pathlib import Path

    src = Path(__file__).resolve().parent.parent.joinpath("app.py").read_text()
    tree = ast.parse(src)
    ns = {"re": _re}
    for node in tree.body:
        if (isinstance(node, ast.Assign) and any(getattr(t, "id", "") == "_TAG_SPLIT" for t in node.targets)) or \
           (isinstance(node, ast.FunctionDef) and node.name == "as_points"):
            exec(compile(ast.Module([node], []), "app.py", "exec"), ns)
    pts = ns["as_points"]("[DATA] Revenue 1,267 crore. (INFERENCE) Thin margins. [ASSUMPTION] Cyclical.")
    assert pts == ["[DATA] Revenue 1,267 crore.", "(INFERENCE) Thin margins.", "[ASSUMPTION] Cyclical."]
    assert ns["as_points"]({"g": ["[DATA] a"], "p": "[DATA] b"}) == ["[DATA] a", "[DATA] b"]
    assert ns["as_points"](None) == []
