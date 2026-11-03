"""Windows reads/writes text as cp1252 unless told otherwise, which breaks on ₹ and other symbols.
Every text read/write in the app must name its encoding."""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_text_io_always_names_an_encoding():
    bad = []
    for f in [ROOT / "app.py", *sorted((ROOT / "isa").glob("*.py"))]:
        for i, line in enumerate(f.read_text(encoding="utf-8").splitlines(), 1):
            if re.search(r"\.(read_text|write_text)\(", line) and "encoding" not in line:
                bad.append(f"{f.name}:{i}: {line.strip()}")
            if re.search(r"(?<![\w.])open\([^)]*\)", line) and "encoding" not in line and "'rb'" not in line \
                    and '"rb"' not in line and '"wb"' not in line and "'wb'" not in line:
                bad.append(f"{f.name}:{i}: {line.strip()}")
    assert not bad, "\n".join(bad)
