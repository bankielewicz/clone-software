#!/usr/bin/env python3
"""Create a non-overwriting software-clone specification pack."""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path


PRODUCT_TYPES = (
    "website",
    "web-app-saas",
    "api-service-server",
    "client-app",
    "library-sdk",
    "cli",
    "hybrid",
)

DOCUMENTS = (
    "clone_brief.md",
    "evidence_ledger.md",
    "clone_specification.md",
    "mvp_build_plan.md",
    "acceptance_matrix.md",
    "gaps_analysis.md",
    "gap_implementation_plan.md",
)


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    if not slug:
        raise ValueError("product name must contain at least one letter or digit")
    return slug[:80].rstrip("-")


def clean_single_line(field: str, value: str) -> str:
    cleaned = value.strip()
    if not cleaned:
        raise ValueError(f"{field} must not be empty")
    if any(character in cleaned for character in ("\r", "\n")):
        raise ValueError(f"{field} must be a single line")
    if any(ord(character) < 32 for character in cleaned):
        raise ValueError(f"{field} must not contain control characters")
    return cleaned


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Initialize an evidence-grounded clone specification pack."
    )
    parser.add_argument("--product-name", required=True)
    parser.add_argument("--product-type", choices=PRODUCT_TYPES, required=True)
    parser.add_argument(
        "--source-description",
        required=True,
        help="Authorized reference product plus version, build, or dated snapshot.",
    )
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=Path.cwd(),
        help="Destination repository root; defaults to the working directory.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("docs/clone"),
        help="Pack directory inside repo-root; defaults to docs/clone.",
    )
    return parser.parse_args()


def resolve_output(repo_root: Path, requested: Path) -> tuple[Path, Path]:
    root = repo_root.expanduser().resolve()
    if not root.is_dir():
        raise ValueError(f"repository root is not a directory: {root}")

    output = requested.expanduser()
    if not output.is_absolute():
        output = root / output
    output = output.resolve()

    try:
        output.relative_to(root)
    except ValueError as exc:
        raise ValueError(
            f"output directory must remain inside repository root: {output}"
        ) from exc
    if output == root:
        raise ValueError("output directory must not be the repository root")
    return root, output


def render_templates(
    template_dir: Path,
    product_name: str,
    product_type: str,
    source_description: str,
    repo_root: Path,
    baseline_date: str,
) -> dict[str, str]:
    replacements = {
        "{{PRODUCT_NAME}}": product_name,
        "{{PRODUCT_NAME_YAML}}": json.dumps(product_name, ensure_ascii=False),
        "{{PRODUCT_SLUG}}": slugify(product_name),
        "{{PRODUCT_TYPE}}": product_type,
        "{{SOURCE_DESCRIPTION}}": source_description,
        "{{SOURCE_DESCRIPTION_YAML}}": json.dumps(source_description, ensure_ascii=False),
        "{{BASELINE_DATE}}": baseline_date,
        "{{REPOSITORY_ROOT}}": repo_root.as_posix(),
    }
    rendered: dict[str, str] = {}
    for name in DOCUMENTS:
        path = template_dir / name
        if not path.is_file():
            raise ValueError(f"missing skill template: {path}")
        text = path.read_text(encoding="utf-8")
        for marker, value in replacements.items():
            text = text.replace(marker, value)
        unresolved_base = re.findall(r"\{\{[A-Z0-9_]+\}\}", text)
        if unresolved_base:
            raise ValueError(
                f"template {name} contains unresolved generator markers: "
                + ", ".join(sorted(set(unresolved_base)))
            )
        rendered[name] = text
    return rendered


def main() -> int:
    args = parse_args()
    try:
        product_name = clean_single_line("product name", args.product_name)
        source_description = clean_single_line("source description", args.source_description)
        repo_root, output_dir = resolve_output(args.repo_root, args.output_dir)
        now = datetime.now(timezone.utc)
        baseline_date = now.date().isoformat()
        template_dir = Path(__file__).resolve().parents[1] / "assets" / "templates"
        rendered = render_templates(
            template_dir=template_dir,
            product_name=product_name,
            product_type=args.product_type,
            source_description=source_description,
            repo_root=repo_root,
            baseline_date=baseline_date,
        )

        intended = [output_dir / name for name in DOCUMENTS]
        manifest_path = output_dir / "clone_pack.json"
        collisions = [path for path in (*intended, manifest_path) if path.exists()]
        if collisions:
            joined = "\n  ".join(str(path) for path in collisions)
            raise ValueError(f"refusing to overwrite existing pack files:\n  {joined}")

        output_dir.mkdir(parents=True, exist_ok=True)
        for name, text in rendered.items():
            (output_dir / name).write_text(text, encoding="utf-8", newline="\n")

        manifest = {
            "schema_version": "clone-pack/v1",
            "pack_id": f"clone-{slugify(product_name)}-{baseline_date}",
            "product_name": product_name,
            "product_type": args.product_type,
            "reference_source": source_description,
            "created_at": now.isoformat(timespec="seconds"),
            "repository_root": repo_root.as_posix(),
            "documents": list(DOCUMENTS),
        }
        manifest_path.write_text(
            json.dumps(manifest, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
            newline="\n",
        )
    except (OSError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    print(f"Created clone pack: {output_dir}")
    for name in (*DOCUMENTS, "clone_pack.json"):
        print(f"  {name}")
    print("The pack is scaffolding. Replace every [[REQUIRED: ...]] marker before validation.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
