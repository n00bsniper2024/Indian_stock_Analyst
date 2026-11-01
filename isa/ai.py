"""AI report generation + a numeric audit that catches hallucinated figures."""
from __future__ import annotations

import re
from typing import Any

import numpy as np

from .analysis import fact_pack_json
from .config import PROMPTS_DIR
from .llm import chat, chat_json, parse_json


def _prompt(name: str) -> str:
    return (PROMPTS_DIR / name).read_text(encoding="utf-8")


def report_messages(pack: dict[str, Any]) -> list[dict[str, str]]:
    m = pack["meta"]
    user = _prompt("stock_report.md").format(company=m["company"], symbol=m["symbol"], fact_pack=fact_pack_json(pack))
    return [{"role": "system", "content": _prompt("system_analyst.md")}, {"role": "user", "content": user}]


def qa_messages(pack: dict[str, Any], history: list[dict[str, str]], report: dict[str, Any] | None = None) -> list[dict[str, str]]:
    m = pack["meta"]
    sys = _prompt("system_analyst.md") + "\n\n" + _prompt("qa.md").format(company=m["company"], symbol=m["symbol"], fact_pack=fact_pack_json(pack))
    if report:
        import json

        sys += "\n\nEARLIER RESEARCH NOTE (JSON):\n" + json.dumps(report, ensure_ascii=False)[:12000]
    return [{"role": "system", "content": sys}] + history[-12:]


def generate_report(pack: dict[str, Any], provider: str, api_key: str, model: str, base_url: str | None = None) -> dict[str, Any]:
    report = chat_json(provider, api_key, model, report_messages(pack), temperature=0.2, max_tokens=16000, base_url=base_url)
    report["_audit"] = audit_numbers(report, pack)
    return report


# --------------------------------------------------------------------------- numeric audit
_NUM = re.compile(r"(?<![A-Za-z])[-+]?\d[\d,]*\.?\d*")


def _flatten_numbers(o: Any, out: list[float]) -> None:
    if isinstance(o, dict):
        for v in o.values():
            _flatten_numbers(v, out)
    elif isinstance(o, list):
        for v in o:
            _flatten_numbers(v, out)
    elif isinstance(o, (int, float)) and not isinstance(o, bool):
        out.append(float(o))
    elif isinstance(o, str):
        for tok in _NUM.findall(o):
            try:
                out.append(float(tok.replace(",", "")))
            except ValueError:
                pass


def _texts(o: Any) -> list[str]:
    if isinstance(o, dict):
        return [t for k, v in o.items() if not str(k).startswith("_") for t in _texts(v)]
    if isinstance(o, list):
        return [t for v in o for t in _texts(v)]
    return [o] if isinstance(o, str) else []


def audit_numbers(report: dict[str, Any], pack: dict[str, Any]) -> dict[str, Any]:
    """Check each figure the AI wrote against every number in the fact pack (±1.5% or ±0.06)."""
    ref: list[float] = []
    _flatten_numbers(pack, ref)
    arr = np.array(sorted(set(ref)))
    fractions = arr[np.abs(arr) <= 1.5]  # e.g. 0.42 in the pack may be written as 42%
    derived = np.concatenate([arr, np.abs(arr), fractions * 100]) if len(arr) else arr
    checked, unverified = 0, []
    for text in _texts(report):
        clean = re.sub(r"FY\d{2}(–|-)?(FY)?\d{0,2}|Q[1-4]\s?FY\d{2}|\b(19|20)\d{2}\b|\d+\s*(months|month|weeks|week|years|year|days|day|bars|tests)", " ", text, flags=re.I)
        for tok in _NUM.findall(clean):
            try:
                x = float(tok.replace(",", ""))
            except ValueError:
                continue
            if abs(x) < 10 and "." not in tok:  # small integers (counts, list numbering) are not audited
                continue
            checked += 1
            tol = max(0.01 * abs(x), 0.06)
            if len(derived) == 0 or np.min(np.abs(derived - x)) > tol:
                unverified.append(tok)
    uniq = sorted(set(unverified), key=unverified.index)
    return {"figures_checked": checked, "unverified": uniq[:25], "unverified_count": len(unverified),
            "traced_pct": round(100 * (1 - len(unverified) / checked), 1) if checked else None}


# --------------------------------------------------------------------------- IPO
def ipo_excerpts(rhp: dict[str, Any], budget: int = 90000) -> str:
    order = ["financial_summary", "basis_price", "capital_structure", "objects", "business", "mdna", "risk_factors",
             "industry", "litigation", "summary_doc"]
    parts, used = [], 0
    for k in order:
        sec = rhp.get("sections", {}).get(k)
        if not sec:
            continue
        chunk = f"\n\n### [{k} | PDF pages {sec['pdf_pages']}]\n{sec['text']}"
        if used + len(chunk) > budget:
            chunk = chunk[: max(0, budget - used)]
        parts.append(chunk)
        used += len(chunk)
        if used >= budget:
            break
    return "".join(parts)


def extract_ipo_financials(company: str, rhp: dict[str, Any], provider: str, api_key: str, model: str,
                           base_url: str | None = None) -> dict[str, Any]:
    from .ipo import verify_numbers

    excerpts = ipo_excerpts(rhp)
    msgs = [{"role": "system", "content": "You extract data from Indian IPO prospectuses with exact fidelity. Output JSON only."},
            {"role": "user", "content": _prompt("ipo_extract.md").format(company=company, excerpts=excerpts)}]
    ex = chat_json(provider, api_key, model, msgs, temperature=0.0, max_tokens=12000, base_url=base_url)
    if ex.get("_parse_error"):
        return ex
    ex["_verification"] = verify_numbers({k: v for k, v in ex.items() if not k.startswith("_")}, excerpts)
    return ex


def generate_ipo_analysis(pack: dict[str, Any], provider: str, api_key: str, model: str, base_url: str | None = None) -> dict[str, Any]:
    import json

    ipo = pack["ipo"]
    slim = json.loads(json.dumps(pack, default=str))
    ver = slim.get("rhp_extract", {}).pop("_verification", None)
    if ver:
        slim["extraction_check"] = ver
    user = _prompt("ipo_analysis.md").format(company=ipo["company"], symbol=ipo["symbol"], board=ipo["board"],
                                             fact_pack=json.dumps(slim, ensure_ascii=False, separators=(",", ":")))
    msgs = [{"role": "system", "content": _prompt("system_ipo.md")}, {"role": "user", "content": user}]
    rep = chat_json(provider, api_key, model, msgs, temperature=0.2, max_tokens=16000, base_url=base_url)
    rep["_audit"] = audit_numbers(rep, slim)
    return rep
