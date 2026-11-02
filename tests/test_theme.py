"""Design-system helpers: escaping, signs/arrows alongside colour, ticker accessibility."""
from isa import theme


def test_pill_shows_sign_and_arrow_not_just_colour():
    assert "▲ +1.50%" in theme.pill(1.5) and "up" in theme.pill(1.5)
    assert "▼ -2.00%" in theme.pill(-2) and "down" in theme.pill(-2)
    assert "—" in theme.pill(None)


def test_text_is_escaped():
    html = theme.tiles([{"label": "<script>", "value": "a&b"}])
    assert "<script>" not in html and "&lt;script&gt;" in html and "a&amp;b" in html
    assert "&lt;b&gt;" in theme.hero("<b>", "")


def test_ring_clamps_and_handles_missing():
    assert "--p:100" in theme.ring(150, "x")
    assert "--p:0" in theme.ring(-5, "x")
    assert ">—<" in theme.ring(None, "x")
    assert "--p:50" in theme.ring(0, "t", lo=-100, hi=100)


def test_ticker_duplicate_row_hidden_from_screen_readers_and_vix_inverted():
    items = [{"name": "Nifty 50", "value": 100.0, "chg": 1.0, "spark": [1, 2, 3]},
             {"name": "India VIX", "value": 15.0, "chg": 2.0, "spark": [1, 2], "invert": True}]
    html = theme.ticker(items, live=False, as_of="02 Nov")
    assert html.count("Nifty 50") == 2 and "aria-hidden='true'>" in html
    vix = html.split("India VIX")[1]
    assert "▲ +2.00%" in vix and "down-t" in vix.split("▲")[0]  # rising VIX: up arrow, warning colour


def test_spark_needs_two_points():
    assert theme.spark([1]) == ""
    assert "<polyline" in theme.spark([1, 2, 3])
