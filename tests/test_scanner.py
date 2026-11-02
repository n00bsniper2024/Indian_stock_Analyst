"""Breakout scanner: outcome labels on hand-built prices, rules, Chartink export."""
import numpy as np
import pandas as pd

from isa import scanner as S


def _frame(close, high=None, low=None, vol=1e6):
    idx = pd.bdate_range("2024-01-01", periods=len(close))
    close = np.asarray(close, float)
    high = close * 1.005 if high is None else np.asarray(high, float)
    low = close * 0.995 if low is None else np.asarray(low, float)
    return pd.DataFrame({"Open": close, "High": high, "Low": low, "Close": close, "Volume": vol}, index=idx)


def _labels(df, day):
    f = S.features(S.to_wide({"X": df}))
    brk, clean = S.outcomes(f)
    return brk["X"].iloc[day], clean["X"].iloc[day]


def test_clean_breakout():
    c = [100.0] * 80 + [101, 103, 106, 109, 112, 115] + [115] * 40
    assert _labels(_frame(c), 79) == (1.0, 1.0)


def test_breakout_that_fails():
    c = [100.0] * 80 + [101, 102, 95] + [95] * 40
    assert _labels(_frame(c), 79) == (1.0, 0.0)


def test_no_breakout():
    c = [100.0] * 80 + [99] * 45
    assert _labels(_frame(c), 79) == (0.0, 0.0)


def test_too_recent_is_unknown():
    c = [100.0] * 80
    b, cl = _labels(_frame(c), 79)
    assert np.isnan(b) and np.isnan(cl)


def test_scan_finds_stock_pressing_on_high():
    # steady uptrend for a year, then 10 days of wide swings just under the high
    up = list(np.linspace(60, 220, 280))
    swing = [214, 200, 190, 205, 213, 196, 210, 216, 211, 217]
    df = _frame(up + swing, vol=1e7)
    f = S.features(S.to_wide({"UP": df}))
    hits = S.scan_today(f, S.Rules())
    assert list(hits["Symbol"]) == ["UP"]
    assert hits.loc[0, "Gap to pivot %"] <= 2
    assert hits.loc[0, "Traded ₹ cr/day"] > 5
    # same stock fails the textbook tight-base preset (its 10-day swing is wide)
    assert S.scan_today(f, S.PRESETS["Textbook tight base / VCP (for comparison)"]).empty


def test_backtest_runs_on_demo_data(monkeypatch):
    monkeypatch.setattr(S, "DEMO_MODE", True)
    hist = S.load_history(["AAA", "BBB", "CCC", "DDD"], years=3)
    f = S.features(S.to_wide(hist))
    bt = S.backtest(f, S.Rules(min_6m_return_pct=0, near_52w_pct=0, min_10d_swing_pct=0, min_traded_cr=0, min_price=0))
    assert bt["signals"] > 0 and 0 <= bt["breakout_pct"] <= 100 and bt["base_breakout_pct"] is not None
    assert {"Signal date", "Symbol", "Outcome"} <= set(bt["recent"].columns)


def test_chartink_export():
    txt = S.chartink(S.Rules())
    assert txt.startswith("( {cash} (") and txt.rstrip().endswith(") )")
    assert "latest close >= 0.98 * latest max( 20 , latest high )" in txt
    assert "latest close >= 1.40 * 126 days ago close" in txt
    assert "latest sma( volume,20 ) * latest close > 50000000" in txt
    assert "sma( volume,10 )" not in txt
    assert "sma( volume,10 )" in S.chartink(S.PRESETS["Textbook tight base / VCP (for comparison)"])
