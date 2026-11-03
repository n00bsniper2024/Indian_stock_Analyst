"""On a shared server (ISA_PUBLIC=1) a visitor's API key must never be written to disk or reach other visitors."""
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

SCRIPT = r"""
import os, sys
from pathlib import Path
from streamlit.testing.v1 import AppTest
env = Path('.env'); before = env.read_text() if env.exists() else None
at = AppTest.from_file('app.py', default_timeout=120); at.run()
assert not any(c.key == 'remember_key' for c in at.checkbox), 'remember box shown in public mode'
box = next(t for t in at.text_input if (t.key or '').startswith('key_in::'))
box.input('sk-visitor-secret-1234567890').run()
after = env.read_text() if env.exists() else None
assert before == after, '.env was modified'
assert 'sk-visitor-secret-1234567890' not in os.environ.values(), 'key leaked into the server environment'
assert any('this browser tab only' in i.value for i in at.info), 'tab-only notice missing'
# a second visitor (fresh session) must not see the first visitor's key
at2 = AppTest.from_file('app.py', default_timeout=120); at2.run()
assert not any('tab only' in i.value for i in at2.info)
print('public mode OK')
"""


def test_public_mode_never_saves_visitor_keys():
    env = {**os.environ, "ISA_PUBLIC": "1", "ISA_DEMO": "1"}
    for k in ("DEEPSEEK_API_KEY", "GEMINI_API_KEY", "OPENAI_API_KEY", "ANTHROPIC_API_KEY"):
        env.pop(k, None)
    r = subprocess.run([sys.executable, "-c", SCRIPT], cwd=ROOT, env=env, capture_output=True, text=True, timeout=300)
    assert r.returncode == 0, r.stdout[-2000:] + r.stderr[-3000:]
    assert "public mode OK" in r.stdout
