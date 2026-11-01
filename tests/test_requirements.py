"""Every third-party package imported by the app must be listed in requirements.txt."""
import ast
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PIP_NAME = {"dotenv": "python-dotenv", "yaml": "pyyaml", "PIL": "pillow"}


def test_all_imports_are_declared():
    declared = {re.split(r"[<>=!~\[ ]", ln.strip())[0].lower() for ln in (ROOT / "requirements.txt").read_text().splitlines()
                if ln.strip() and not ln.startswith("#")}
    stdlib = set(sys.stdlib_module_names) | {"__future__"}
    missing = set()
    for f in [ROOT / "app.py", *(ROOT / "isa").glob("*.py")]:
        for node in ast.walk(ast.parse(f.read_text())):
            names = [a.name for a in node.names] if isinstance(node, ast.Import) else \
                    [node.module] if isinstance(node, ast.ImportFrom) and node.module and node.level == 0 else []
            for n in names:
                top = n.split(".")[0]
                if top in stdlib or top == "isa":
                    continue
                if PIP_NAME.get(top, top).lower() not in declared:
                    missing.add(f"{top} (in {f.name})")
    assert not missing, f"add to requirements.txt: {sorted(missing)}"
