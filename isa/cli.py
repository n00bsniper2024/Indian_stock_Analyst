"""Command-line access to the engine (also used by the Claude plugin skills).

Examples
  python -m isa.cli analyze TCS                 # fact pack JSON to stdout
  python -m isa.cli analyze HDFCBANK --out hdfc.json --no-peers
  python -m isa.cli categories                  # list category names
  python -m isa.cli category "Nifty IT"         # screener table (markdown)
  python -m isa.cli report INFY --provider DeepSeek --model deepseek-flash   # AI note (key from .env)
"""
from __future__ import annotations

import argparse
import json
import sys

from .analysis import build_fact_pack, fact_pack_json


def _resolve_symbol(text: str) -> str | None:
    """Accept names, old symbols and small typos; stop and list choices when the text fits several companies."""
    from .search import resolve, search

    try:
        best = resolve(text)
        if best:
            if best.reason != "symbol":
                print(f"using {best.label} ({best.reason})", file=sys.stderr)
            return best.symbol
        matches = search(text)
    except Exception:
        matches = []
    if not matches:
        return text.strip().upper()
    print(f"'{text}' fits several companies; run again with one of:", file=sys.stderr)
    for m in matches:
        print(f"  {m.label}", file=sys.stderr)
    return None


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="isa", description="Indian Stock Analyst engine")
    sub = ap.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("analyze", help="compute the fact pack for one NSE symbol")
    a.add_argument("symbol")
    a.add_argument("--no-peers", action="store_true")
    a.add_argument("--out")
    sub.add_parser("categories", help="list available categories")
    sub.add_parser("refresh-classification", help="rebuild data/classification.csv (sector/industry/cap for ~750 stocks; slow)")
    c = sub.add_parser("category", help="screener snapshot for a category")
    c.add_argument("name")
    c.add_argument("--csv", action="store_true")
    r = sub.add_parser("report", help="generate an AI research note")
    r.add_argument("symbol")
    r.add_argument("--provider", default="DeepSeek")
    r.add_argument("--model", required=True)
    r.add_argument("--out")
    args = ap.parse_args(argv)
    if getattr(args, "symbol", None):
        args.symbol = _resolve_symbol(args.symbol)
        if not args.symbol:
            return 2

    if args.cmd == "analyze":
        pack = build_fact_pack(args.symbol, with_peers=not args.no_peers)
        text = fact_pack_json(pack, compact=False)
        if args.out:
            open(args.out, "w", encoding="utf-8").write(text)
            print(f"wrote {args.out}", file=sys.stderr)
        else:
            print(text)
    elif args.cmd == "categories":
        from .universe import CATEGORIES

        for group, cats in CATEGORIES.items():
            print(f"# {group}")
            for name in cats:
                print(f"  {name}")
    elif args.cmd == "refresh-classification":
        from .classify import build_classification

        df = build_classification(progress=lambda i, n, s: print(f"\r{i}/{n} {s:<15}", end="", file=sys.stderr, flush=True))
        print(f"\nwrote data/classification.csv with {len(df)} stocks", file=sys.stderr)
    elif args.cmd == "category":
        from .data import get_batch_prices
        from .overview import breadth, category_snapshot
        from .universe import flat_categories, load_index

        slug = flat_categories().get(args.name)
        if not slug:
            print(f"Unknown category. Run `python -m isa.cli categories`.", file=sys.stderr)
            return 2
        meta, src = load_index(slug)
        snap = category_snapshot(get_batch_prices(meta["Symbol"].tolist()), meta)
        print(f"<!-- constituents source: {src}; breadth: {json.dumps(breadth(snap))} -->")
        print(snap.to_csv(index=False) if args.csv else snap.to_markdown(index=False))
    elif args.cmd == "report":
        from .ai import generate_report
        from .llm import default_key
        from .report import to_markdown

        pack = build_fact_pack(args.symbol)
        rep = generate_report(pack, args.provider, default_key(args.provider), args.model)
        md = to_markdown(rep, pack)
        if args.out:
            open(args.out, "w", encoding="utf-8").write(md)
            print(f"wrote {args.out}", file=sys.stderr)
        else:
            print(md)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
