"""Search behaviour on a small fixed index (no network)."""
import pytest

from isa import search as S


@pytest.fixture(autouse=True)
def fake_index(monkeypatch):
    rows = {
        "BOROLTD": "Borosil Limited", "BORORENEW": "Borosil Renewables Limited", "BOROSCI": "Borosil Scientific Limited",
        "INFY": "Infosys Limited", "SBIN": "State Bank of India", "SBILIFE": "SBI Life Insurance Company Limited",
        "RELIANCE": "Reliance Industries Limited", "RPOWER": "Reliance Power Limited", "ETERNAL": "Eternal Limited",
        "MANYAVAR": "Vedant Fashions Limited", "LT": "Larsen & Toubro Limited", "M&M": "Mahindra & Mahindra Limited",
        "TATASTEEL": "Tata Steel Limited", "BAJAJ-AUTO": "Bajaj Auto Limited",
    }
    data = {"rows": {k: {"name": v, "board": "Mainboard"} for k, v in rows.items()},
            "old_syms": {"BOROSIL": "BORORENEW", "ZOMATO": "ETERNAL"},
            "old_names": [("Borosil Glass Works Limited", "BORORENEW"), ("Zomato Limited", "ETERNAL")]}
    monkeypatch.setattr(S, "DEMO_MODE", False)
    monkeypatch.setattr(S, "_cached", lambda key, ttl, fn: data)
    S._index.cache_clear()
    yield
    S._index.cache_clear()


def syms(q, n=5):
    return [m.symbol for m in S.search(q, n)]


@pytest.mark.parametrize("q", ["Borosil", "borosil", "BOROSIL", "  borosil  "])
def test_borosil_any_case_lists_all_three(q):
    assert set(syms(q)[:3]) == {"BOROLTD", "BORORENEW", "BOROSCI"}
    assert S.resolve(q) is None  # ambiguous: the user must choose


def test_exact_symbol_and_company_name():
    assert syms("infy")[0] == "INFY"
    assert syms("infosys")[0] == "INFY"
    assert syms("vedant fashions")[0] == "MANYAVAR"
    assert syms("tata steel")[0] == "TATASTEEL"
    assert syms("bajaj auto")[0] == "BAJAJ-AUTO"


def test_short_forms_and_symbols_with_punctuation():
    assert S.resolve("sbi").symbol == "SBIN"
    assert S.resolve("zomato").symbol == "ETERNAL"
    assert S.resolve("l&t").symbol == "LT"
    assert S.resolve("m&m").symbol == "M&M"
    assert S.resolve("mm").symbol == "M&M"


def test_old_symbol_and_former_name():
    assert "BORORENEW" in syms("borosil glass")
    assert S.search("borosil glass")[0].reason.startswith("formerly")


def test_typos():
    assert syms("relaince")[0] == "RELIANCE"
    assert syms("infosis")[0] == "INFY"


def test_nothing_similar():
    assert syms("xyzzqq") == []
    assert S.search("") == []
