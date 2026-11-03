"""Central configuration. Values can be overridden with environment variables or a .env file."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

try:
    from dotenv import load_dotenv

    load_dotenv(ROOT / ".env")  # the project's .env, whatever folder the app was started from
except Exception:  # dotenv is optional
    pass

DATA_DIR = ROOT / "data"
PROMPTS_DIR = ROOT / "prompts"
CACHE_DIR = Path(os.getenv("ISA_CACHE_DIR", ROOT / ".cache"))

# Public mode = one server shared by many visitors (e.g. Streamlit Community Cloud, which runs apps from /mount/src).
# Keys typed in the browser then stay in that browser tab only and are never written to the server.
PUBLIC_MODE = os.getenv("ISA_PUBLIC", "").strip().lower() in ("1", "true", "yes") or Path("/mount/src").is_dir()


def _f(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, default))
    except ValueError:
        return default


@dataclass
class ValuationDefaults:
    # India 10Y G-Sec was ~7.18% on 28-Sep-2026 (Trading Economics). Edit in the UI or .env.
    risk_free: float = field(default_factory=lambda: _f("ISA_RISK_FREE", 0.071))
    # Equity risk premium for India (mature-market ERP + country risk premium). Editable.
    equity_risk_premium: float = field(default_factory=lambda: _f("ISA_ERP", 0.070))
    # Long-run nominal INR growth used in terminal value. Must stay below WACC.
    terminal_growth: float = field(default_factory=lambda: _f("ISA_TERMINAL_G", 0.055))
    # New-regime corporate tax rate incl. surcharge & cess (Sec 115BAA).
    tax_rate: float = field(default_factory=lambda: _f("ISA_TAX_RATE", 0.2517))
    forecast_years: int = 10


DEMO_MODE = os.getenv("ISA_DEMO", "0") == "1"
BENCHMARK = "^NSEI"  # Nifty 50 index on Yahoo
CRORE = 1e7
