"""Dependency-free command entry point."""

from __future__ import annotations

import argparse
import json
from collections.abc import Sequence


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="{{PRODUCT_SLUG}}")
    parser.add_argument("--name", default="{{PRODUCT_NAME}}")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    print(json.dumps({"name": args.name, "status": "ready"}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
