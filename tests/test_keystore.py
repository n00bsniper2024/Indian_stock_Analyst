import os
import stat

from isa.keystore import mask, remove_key, save_key


def test_save_replace_remove(tmp_path, monkeypatch):
    env = tmp_path / ".env"
    env.write_text("OTHER=1\nDEEPSEEK_API_KEY=old\n")
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    save_key("DEEPSEEK_API_KEY", " sk-new-123456789 \n", env)
    text = env.read_text()
    assert "DEEPSEEK_API_KEY=sk-new-123456789" in text and "old" not in text and "OTHER=1" in text
    assert os.environ["DEEPSEEK_API_KEY"] == "sk-new-123456789"
    assert stat.S_IMODE(env.stat().st_mode) == 0o600          # owner-only
    remove_key("DEEPSEEK_API_KEY", env)
    assert "DEEPSEEK_API_KEY" not in env.read_text() and "OTHER=1" in env.read_text()
    assert "DEEPSEEK_API_KEY" not in os.environ


def test_mask_never_reveals_more_than_last_4():
    assert mask("sk-abcdefghijWXYZ") == "••••WXYZ"
    assert mask("short") == "••••"


def test_rejects_bad_variable_names(tmp_path):
    import pytest

    with pytest.raises(ValueError):
        save_key("BAD NAME\nINJECT", "x", tmp_path / ".env")
