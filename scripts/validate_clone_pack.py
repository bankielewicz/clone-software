#!/usr/bin/env python3
"""Compatibility dispatcher for legacy v1 and current v2 clone packs."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from clonepack.cli import main as v2_main
from clonepack.common import ClonePackError, load_json
from clonepack.legacy_v1 import main as legacy_main


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate a v1 or v2 clone pack.")
    parser.add_argument("pack_directory", type=Path)
    parser.add_argument("--require-verified-mvp", action="store_true")
    parser.add_argument("--max-problems", type=int, default=100)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        manifest = load_json(args.pack_directory.expanduser().resolve() / "clone_pack.json")
    except ClonePackError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return exc.exit_code
    if manifest.get("schema_version") == "clone-pack/v1":
        if args.require_verified_mvp:
            print("MIGRATION_REQUIRED: v1 packs cannot receive evidence-backed v2 verified-mvp certification", file=sys.stderr)
            return 3
        sys.argv = [sys.argv[0], str(args.pack_directory), "--max-problems", str(args.max_problems)]
        return legacy_main()
    profile = "verified-mvp" if args.require_verified_mvp else "scaffold"
    return v2_main(["validate", str(args.pack_directory), "--profile", profile, "--max-problems", str(args.max_problems)])


if __name__ == "__main__":
    raise SystemExit(main())

