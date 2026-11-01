"""Server-side storage of API keys in the project's .env file.

Saved keys never go back to the browser: the sidebar only shows the last 4 characters.
The file is git-ignored and made readable by the owner only (chmod 600).
"""
from __future__ import annotations

import os
import re
from pathlib import Path

from .config import ROOT

ENV_FILE = ROOT / ".env"


def _read_lines(path: Path) -> list[str]:
    return path.read_text(encoding="utf-8").splitlines() if path.exists() else []


def save_key(name: str, value: str, path: Path = ENV_FILE) -> None:
    if not re.fullmatch(r"[A-Z][A-Z0-9_]*", name):
        raise ValueError("invalid variable name")
    value = value.strip().replace("\n", "").replace("\r", "")
    lines = [ln for ln in _read_lines(path) if not re.match(rf"^\s*{name}\s*=", ln)]
    lines.append(f"{name}={value}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    try:
        path.chmod(0o600)
    except OSError:
        pass
    os.environ[name] = value


def remove_key(name: str, path: Path = ENV_FILE) -> None:
    lines = [ln for ln in _read_lines(path) if not re.match(rf"^\s*{name}\s*=", ln)]
    if path.exists():
        path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")
    os.environ.pop(name, None)


def mask(value: str) -> str:
    return f"••••{value[-4:]}" if value and len(value) > 8 else "••••"
