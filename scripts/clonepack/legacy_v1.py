#!/usr/bin/env python3
"""Validate legacy clone-pack/v1 structure and ambiguity residue."""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path


DOCUMENT_SCHEMAS = {
    "clone_brief.md": "clone-brief/v1",
    "evidence_ledger.md": "clone-evidence/v1",
    "clone_specification.md": "clone-spec/v1",
    "mvp_build_plan.md": "clone-mvp-plan/v1",
    "acceptance_matrix.md": "clone-acceptance/v1",
    "gaps_analysis.md": "clone-gaps/v1",
    "gap_implementation_plan.md": "clone-gap-plan/v1",
}

REQUIRED_HEADINGS = {
    "clone_brief.md": (
        "## Authority and authorization",
        "## Frozen reference baseline",
        "## Product outcome",
        "## MVP boundary",
        "## Fidelity decisions",
        "## Explicit exclusions",
        "## Decision ledger",
        "## Blockers",
    ),
    "evidence_ledger.md": (
        "## Capture environment",
        "## Evidence records",
        "## Surface inventory",
        "## Workflow observations",
        "## Conflicts and unknowns",
        "## Artifact integrity",
    ),
    "clone_specification.md": (
        "## Authority and baseline",
        "## Product contract",
        "## Actors and permissions",
        "## MVP workflows",
        "## Surface inventory",
        "## Behavioral requirements",
        "## Interface contracts",
        "## Data and state contracts",
        "## Security and privacy",
        "## Non-functional contracts",
        "## Architecture and repository map",
        "## Configuration and operations",
        "## MVP exclusions and gap mapping",
        "## Readiness result",
    ),
    "mvp_build_plan.md": (
        "## Execution contract",
        "## Dependency order",
        "## File-level change map",
        "## Implementation sequence",
        "## Test specification",
        "## Gate commands",
        "## Migration, rollout, and rollback",
        "## Non-goals and prohibited shortcuts",
        "## HALT conditions",
        "## Completion record",
    ),
    "acceptance_matrix.md": (
        "## Acceptance criteria",
        "## Requirement verification",
        "## Verification runs",
        "## MVP verdict",
    ),
    "gaps_analysis.md": (
        "## Current-truth basis",
        "## Gap classification and lifecycle",
        "## Capability coverage",
        "## Gap register",
        "## Dependency order",
    ),
    "gap_implementation_plan.md": (
        "## Execution contract",
        "## Pinned invariants",
        "## Dependencies and prerequisites",
        "## Requirement and change trace",
        "## File-level change map",
        "## Test-first execution sequence",
        "## Verification commands",
        "## Rollout and recovery",
        "## Non-goals and prohibited work",
        "## HALT ledger",
        "## Completion record",
    ),
}

GAP_HEADINGS = (
    "### Classification",
    "### Current-state evidence and discrepancy",
    "### Target behavior",
    "### Constraints and applicability",
    "### Scope and non-goals",
    "### File-level change map",
    "### Implementation sequence",
    "### Test specification",
    "### Acceptance criteria",
    "### Rollout, compatibility, and recovery",
    "### Uncertainty and HALT ledger",
    "### Closure evidence",
    "### Status history",
)

GAP_CLASSES = {"MVP_BLOCKER", "PARITY_GAP", "QUALITY_GAP", "EVIDENCE_GAP"}
GAP_STATUSES = {"OPEN", "BLOCKED", "IN_PROGRESS", "IMPLEMENTED", "VERIFIED", "DECLINED"}
TRUTH_LABELS = {"VERIFIED", "USER_PINNED", "INFERRED", "UNKNOWN_BLOCKER"}
PRODUCT_TYPES = {
    "website",
    "web-app-saas",
    "api-service-server",
    "client-app",
    "library-sdk",
    "cli",
    "hybrid",
}

UNRESOLVED_PATTERNS = (
    ("required marker", re.compile(r"\[\[REQUIRED:[^\]]*\]\]")),
    ("generator marker", re.compile(r"\{\{[A-Z0-9_]+\}\}")),
    ("placeholder token", re.compile(r"\b(?:TBD|TODO|TBC|FIXME|TK)\b")),
    ("question placeholder", re.compile(r"\?\?\?")),
)

AMBIGUOUS_PATTERNS = (
    ("should", re.compile(r"\bshould\b")),
    ("could", re.compile(r"\bcould\b")),
    ("may", re.compile(r"\bmay\b")),
    ("might", re.compile(r"\bmight\b")),
    ("ideally", re.compile(r"\bideally\b")),
    ("eventually", re.compile(r"\beventually\b")),
    ("as needed", re.compile(r"\bas needed\b")),
    ("and so on", re.compile(r"\band so on\b")),
    ("etcetera", re.compile(r"\betc\.(?:\s|$)")),
)


@dataclass(frozen=True)
class Problem:
    path: Path
    line: int
    message: str

    def format(self) -> str:
        location = f"{self.path}:{self.line}" if self.line else str(self.path)
        return f"{location}: {self.message}"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate an initialized and completed clone specification pack."
    )
    parser.add_argument("pack_directory", type=Path)
    parser.add_argument(
        "--require-verified-mvp",
        action="store_true",
        help="Also require every MVP requirement and the final verdict to be verified.",
    )
    parser.add_argument(
        "--max-problems",
        type=int,
        default=100,
        help="Maximum detailed problems to print; defaults to 100 (0 prints all).",
    )
    return parser.parse_args()


def frontmatter(text: str) -> dict[str, str]:
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}
    try:
        end = next(i for i in range(1, len(lines)) if lines[i].strip() == "---")
    except StopIteration:
        return {}
    result: dict[str, str] = {}
    for line in lines[1:end]:
        match = re.match(r"^([A-Za-z0-9_-]+):\s*(.*?)\s*$", line)
        if match:
            raw_value = match.group(2).strip()
            if len(raw_value) >= 2 and raw_value.startswith('"') and raw_value.endswith('"'):
                try:
                    value = json.loads(raw_value)
                except json.JSONDecodeError:
                    value = raw_value
            elif len(raw_value) >= 2 and raw_value.startswith("'") and raw_value.endswith("'"):
                value = raw_value[1:-1].replace("''", "'")
            else:
                value = raw_value
            result[match.group(1)] = value
    return result


def line_number(text: str, offset: int) -> int:
    return text.count("\n", 0, offset) + 1


def strip_comments_and_fences(text: str) -> str:
    def blank(match: re.Match[str]) -> str:
        return re.sub(r"[^\n]", " ", match.group(0))

    text = re.sub(r"<!--.*?-->", blank, text, flags=re.DOTALL)
    text = re.sub(r"```.*?```", blank, text, flags=re.DOTALL)
    return text


def exact_heading_present(text: str, heading: str) -> bool:
    return re.search(rf"^{re.escape(heading)}\s*$", text, flags=re.MULTILINE) is not None


def duplicate_ids(ids: list[str]) -> set[str]:
    seen: set[str] = set()
    dupes: set[str] = set()
    for item in ids:
        if item in seen:
            dupes.add(item)
        seen.add(item)
    return dupes


def markdown_rows(text: str, id_pattern: str) -> list[list[str]]:
    def split_row(line: str) -> list[str]:
        body = line.strip()
        if body.startswith("|"):
            body = body[1:]
        if body.endswith("|"):
            body = body[:-1]
        cells: list[str] = []
        current: list[str] = []
        escaped = False
        for character in body:
            if character == "|" and not escaped:
                cells.append("".join(current).strip())
                current = []
            else:
                current.append(character)
            if character == "\\" and not escaped:
                escaped = True
            else:
                escaped = False
        cells.append("".join(current).strip())
        return cells

    rows: list[list[str]] = []
    matcher = re.compile(id_pattern)
    for line in text.splitlines():
        if not line.startswith("|"):
            continue
        cells = split_row(line)
        if cells and matcher.fullmatch(cells[0]):
            rows.append(cells)
    return rows


def dependency_cycle(graph: dict[str, set[str]]) -> list[str]:
    visiting: set[str] = set()
    visited: set[str] = set()
    path: list[str] = []

    def visit(node: str) -> list[str]:
        if node in visiting:
            start = path.index(node)
            return path[start:] + [node]
        if node in visited:
            return []
        visiting.add(node)
        path.append(node)
        for dependency in graph.get(node, set()):
            cycle = visit(dependency)
            if cycle:
                return cycle
        path.pop()
        visiting.remove(node)
        visited.add(node)
        return []

    for node in graph:
        cycle = visit(node)
        if cycle:
            return cycle
    return []


def gap_blocks(text: str) -> dict[str, str]:
    matches = list(re.finditer(r"^## (GAP-\d{3,})\b.*$", text, flags=re.MULTILINE))
    blocks: dict[str, str] = {}
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        blocks[match.group(1)] = text[match.start() : end]
    return blocks


def section_body(text: str, heading: str) -> str:
    match = re.search(rf"^{re.escape(heading)}\s*$", text, flags=re.MULTILINE)
    if not match:
        return ""
    next_heading = re.search(r"^##\s+", text[match.end() :], flags=re.MULTILINE)
    end = match.end() + next_heading.start() if next_heading else len(text)
    return text[match.end() : end]


def validate_pack(pack: Path, require_verified: bool) -> list[Problem]:
    problems: list[Problem] = []
    if not pack.is_dir():
        return [Problem(pack, 0, "pack directory does not exist")]

    manifest_path = pack / "clone_pack.json"
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return [Problem(manifest_path, 0, "required manifest is missing")]
    except (OSError, json.JSONDecodeError) as exc:
        return [Problem(manifest_path, 0, f"manifest is not valid JSON: {exc}")]

    if manifest.get("schema_version") != "clone-pack/v1":
        problems.append(Problem(manifest_path, 0, "schema_version must be clone-pack/v1"))
    pack_id = manifest.get("pack_id")
    if not isinstance(pack_id, str) or not pack_id:
        problems.append(Problem(manifest_path, 0, "pack_id must be a non-empty string"))
    if manifest.get("documents") != list(DOCUMENT_SCHEMAS):
        problems.append(
            Problem(manifest_path, 0, "documents must exactly match the v1 document manifest")
        )
    for field in ("product_name", "reference_source", "repository_root", "created_at"):
        if not isinstance(manifest.get(field), str) or not manifest[field].strip():
            problems.append(Problem(manifest_path, 0, f"{field} must be a non-empty string"))
    if manifest.get("product_type") not in PRODUCT_TYPES:
        problems.append(Problem(manifest_path, 0, "product_type is not a controlled clone-pack value"))

    texts: dict[str, str] = {}
    for name, schema in DOCUMENT_SCHEMAS.items():
        path = pack / name
        try:
            text = path.read_text(encoding="utf-8")
        except FileNotFoundError:
            problems.append(Problem(path, 0, "required document is missing"))
            continue
        except OSError as exc:
            problems.append(Problem(path, 0, f"cannot read document: {exc}"))
            continue
        texts[name] = text

        metadata = frontmatter(text)
        if metadata.get("schema_version") != schema:
            problems.append(Problem(path, 1, f"schema_version must be {schema}"))
        if metadata.get("pack_id") != pack_id:
            problems.append(Problem(path, 1, "pack_id does not match clone_pack.json"))
        if metadata.get("product_name") != manifest.get("product_name"):
            problems.append(Problem(path, 1, "product_name does not match clone_pack.json"))
        if "product_type" in metadata and metadata["product_type"] != manifest.get("product_type"):
            problems.append(Problem(path, 1, "product_type does not match clone_pack.json"))
        source_key = "reference_baseline" if name == "gaps_analysis.md" else "reference_source"
        if source_key in metadata and metadata[source_key] != manifest.get("reference_source"):
            problems.append(Problem(path, 1, f"{source_key} does not match clone_pack.json"))
        if metadata.get("document_state") not in {"validated", "active", "closed", "superseded"}:
            problems.append(
                Problem(path, 1, "document_state must be validated, active, closed, or superseded")
            )

        for heading in REQUIRED_HEADINGS[name]:
            if not exact_heading_present(text, heading):
                problems.append(Problem(path, 0, f"missing required heading: {heading}"))

        for label, pattern in UNRESOLVED_PATTERNS:
            for match in pattern.finditer(text):
                problems.append(
                    Problem(path, line_number(text, match.start()), f"unresolved {label}: {match.group(0)}")
                )

        prose = strip_comments_and_fences(text)
        for label, pattern in AMBIGUOUS_PATTERNS:
            for match in pattern.finditer(prose):
                problems.append(
                    Problem(path, line_number(text, match.start()), f"ambiguous wording is forbidden: {label}")
                )

        for match in re.finditer(r"\|[ \t]*\|", text):
            problems.append(
                Problem(path, line_number(text, match.start()), "empty Markdown table cell is forbidden")
            )

    if len(texts) != len(DOCUMENT_SCHEMAS):
        return problems

    evidence_text = texts["evidence_ledger.md"]
    evidence_rows = markdown_rows(evidence_text, r"E-\d{3,}")
    evidence_ids = [row[0] for row in evidence_rows]
    if not evidence_ids:
        problems.append(Problem(pack / "evidence_ledger.md", 0, "at least one E-### record is required"))
    for duplicate in sorted(duplicate_ids(evidence_ids)):
        problems.append(Problem(pack / "evidence_ledger.md", 0, f"duplicate evidence record: {duplicate}"))
    for row in evidence_rows:
        if len(row) < 9:
            problems.append(Problem(pack / "evidence_ledger.md", 0, f"{row[0]} evidence row has too few columns"))
        elif row[1] not in TRUTH_LABELS:
            problems.append(Problem(pack / "evidence_ledger.md", 0, f"{row[0]} has invalid truth label: {row[1]}"))

    spec_text = texts["clone_specification.md"]
    requirement_ids = re.findall(r"^### (REQ-\d{3,})\b", spec_text, flags=re.MULTILINE)
    if not requirement_ids:
        problems.append(Problem(pack / "clone_specification.md", 0, "at least one REQ-### packet is required"))
    for duplicate in sorted(duplicate_ids(requirement_ids)):
        problems.append(Problem(pack / "clone_specification.md", 0, f"duplicate requirement packet: {duplicate}"))
    requirement_matches = list(re.finditer(r"^### (REQ-\d{3,})\b", spec_text, flags=re.MULTILINE))
    for index, match in enumerate(requirement_matches):
        end = requirement_matches[index + 1].start() if index + 1 < len(requirement_matches) else len(spec_text)
        packet = spec_text[match.start() : end]
        req_id = match.group(1)
        if not re.search(r"\b(?:E|DEC)-\d{3,}\b", packet):
            problems.append(Problem(pack / "clone_specification.md", 0, f"{req_id} lacks evidence or decision IDs"))
        if not re.search(r"\bAC-\d{3,}\b", packet):
            problems.append(Problem(pack / "clone_specification.md", 0, f"{req_id} lacks acceptance IDs"))
        if not re.search(r"\bTEST-\d{3,}\b", packet):
            problems.append(Problem(pack / "clone_specification.md", 0, f"{req_id} lacks planned test IDs"))

    acceptance_text = texts["acceptance_matrix.md"]
    acceptance_rows = markdown_rows(acceptance_text, r"REQ-\d{3,}")
    acceptance_req_ids = [row[0] for row in acceptance_rows]
    if set(requirement_ids) != set(acceptance_req_ids):
        missing = sorted(set(requirement_ids) - set(acceptance_req_ids))
        extra = sorted(set(acceptance_req_ids) - set(requirement_ids))
        if missing:
            problems.append(
                Problem(pack / "acceptance_matrix.md", 0, f"requirements missing verification rows: {', '.join(missing)}")
            )
        if extra:
            problems.append(
                Problem(pack / "acceptance_matrix.md", 0, f"verification rows lack specification packets: {', '.join(extra)}")
            )

    status_by_req: dict[str, str] = {}
    for row in acceptance_rows:
        if len(row) < 7:
            problems.append(Problem(pack / "acceptance_matrix.md", 0, f"{row[0]} verification row has too few columns"))
            continue
        status = row[4]
        if status not in {"NOT_STARTED", "IMPLEMENTED_UNVERIFIED", "VERIFIED", "BLOCKED"}:
            problems.append(
                Problem(pack / "acceptance_matrix.md", 0, f"{row[0]} has no controlled verification status")
            )
        else:
            status_by_req[row[0]] = status
    verdict_match = re.search(
        r"^- Verdict:\s*(VERIFIED_MVP|HOLD)\s*$", acceptance_text, flags=re.MULTILINE
    )
    verdict = verdict_match.group(1) if verdict_match else ""
    if not verdict:
        problems.append(
            Problem(pack / "acceptance_matrix.md", 0, "Verdict must be exactly VERIFIED_MVP or HOLD")
        )
    nonverified_requirements = sorted(
        req for req, status in status_by_req.items() if status != "VERIFIED"
    )
    if verdict == "VERIFIED_MVP" and nonverified_requirements:
        problems.append(
            Problem(
                pack / "acceptance_matrix.md",
                0,
                "VERIFIED_MVP conflicts with non-verified requirements: "
                + ", ".join(nonverified_requirements),
            )
        )
    if require_verified:
        if nonverified_requirements:
            problems.append(
                Problem(
                    pack / "acceptance_matrix.md",
                    0,
                    f"MVP requirements are not VERIFIED: {', '.join(nonverified_requirements)}",
                )
            )
        if verdict != "VERIFIED_MVP":
            problems.append(
                Problem(pack / "acceptance_matrix.md", 0, "--require-verified-mvp requires Verdict: VERIFIED_MVP")
            )

    gaps_path = pack / "gaps_analysis.md"
    gaps_text = texts["gaps_analysis.md"]
    no_open_match = re.search(r"^- NO-OPEN-GAPS:\s*(true|false)\s*$", gaps_text, flags=re.MULTILINE)
    if not no_open_match:
        problems.append(Problem(gaps_path, 0, "NO-OPEN-GAPS must be exactly true or false"))
        no_open = False
    else:
        no_open = no_open_match.group(1) == "true"

    register_rows = markdown_rows(gaps_text, r"GAP-\d{3,}")
    register_ids = [row[0] for row in register_rows]
    register_by_id = {row[0]: row for row in register_rows}
    blocks = gap_blocks(gaps_text)
    if set(register_ids) != set(blocks):
        missing = sorted(set(register_ids) - set(blocks))
        extra = sorted(set(blocks) - set(register_ids))
        if missing:
            problems.append(Problem(gaps_path, 0, f"registered gaps lack dossiers: {', '.join(missing)}"))
        if extra:
            problems.append(Problem(gaps_path, 0, f"gap dossiers lack register rows: {', '.join(extra)}"))
    for duplicate in sorted(duplicate_ids(register_ids)):
        problems.append(Problem(gaps_path, 0, f"duplicate gap register row: {duplicate}"))

    dependency_graph: dict[str, set[str]] = {}
    nonterminal_gaps: list[str] = []
    for row in register_rows:
        gap_id = row[0]
        if len(row) < 8:
            problems.append(Problem(gaps_path, 0, f"{gap_id} register row has too few columns"))
            continue
        if row[2] not in GAP_CLASSES:
            problems.append(Problem(gaps_path, 0, f"{gap_id} register row has invalid class: {row[2]}"))
        if row[4] not in GAP_STATUSES:
            problems.append(Problem(gaps_path, 0, f"{gap_id} register row has invalid status: {row[4]}"))
        elif row[4] not in {"VERIFIED", "DECLINED"}:
            nonterminal_gaps.append(gap_id)
        if row[7] not in {"READY", "BLOCKED"}:
            problems.append(Problem(gaps_path, 0, f"{gap_id} register row has invalid readiness: {row[7]}"))
        dependencies = set(re.findall(r"\bGAP-\d{3,}\b", row[5]))
        dependency_graph[gap_id] = dependencies
        unresolved = sorted(dependencies - set(register_ids))
        if unresolved:
            problems.append(Problem(gaps_path, 0, f"{gap_id} has unknown dependencies: {', '.join(unresolved)}"))
    if no_open and nonterminal_gaps:
        problems.append(
            Problem(gaps_path, 0, f"NO-OPEN-GAPS true conflicts with nonterminal gaps: {', '.join(nonterminal_gaps)}")
        )
    if not no_open and not nonterminal_gaps:
        problems.append(Problem(gaps_path, 0, "NO-OPEN-GAPS false requires at least one nonterminal gap"))
    if require_verified or verdict == "VERIFIED_MVP":
        mvp_blockers = [
            row[0]
            for row in register_rows
            if len(row) >= 8 and row[2] == "MVP_BLOCKER" and row[4] != "VERIFIED"
        ]
        if mvp_blockers:
            problems.append(
                Problem(gaps_path, 0, f"verified MVP is blocked by gaps: {', '.join(mvp_blockers)}")
            )
    cycle = dependency_cycle(dependency_graph)
    if cycle:
        problems.append(Problem(gaps_path, 0, f"gap dependency cycle: {' -> '.join(cycle)}"))

    coverage_rows = markdown_rows(
        section_body(gaps_text, "## Capability coverage"),
        r"(?:SURF|WF|REQ)-[A-Za-z0-9-]+",
    )
    for row in coverage_rows:
        if len(row) < 6:
            problems.append(Problem(gaps_path, 0, f"{row[0]} coverage row has too few columns"))
            continue
        coverage = row[3]
        if coverage not in {"EQUIVALENT", "MISSING", "PARTIAL", "DIVERGENT", "EXCLUDED", "UNVERIFIED"}:
            problems.append(Problem(gaps_path, 0, f"{row[0]} has invalid coverage: {coverage}"))
        if coverage in {"MISSING", "PARTIAL", "DIVERGENT", "UNVERIFIED"} and not re.search(
            r"\bGAP-\d{3,}\b", row[4]
        ):
            problems.append(Problem(gaps_path, 0, f"{row[0]} {coverage} coverage lacks a gap ID"))

    for gap_id, block in blocks.items():
        for heading in GAP_HEADINGS:
            if not exact_heading_present(block, heading):
                problems.append(Problem(gaps_path, 0, f"{gap_id} missing required heading: {heading}"))

        class_match = re.search(r"^- Class:\s*(\S+)\s*$", block, flags=re.MULTILINE)
        status_match = re.search(r"^- Status:\s*(\S+)\s*$", block, flags=re.MULTILINE)
        readiness_match = re.search(
            r"^- Implementation readiness:\s*(READY|BLOCKED)\s*$", block, flags=re.MULTILINE
        )
        gap_class = class_match.group(1) if class_match else ""
        status = status_match.group(1) if status_match else ""
        readiness = readiness_match.group(1) if readiness_match else ""
        if gap_class not in GAP_CLASSES:
            problems.append(Problem(gaps_path, 0, f"{gap_id} has invalid or missing class"))
        if status not in GAP_STATUSES:
            problems.append(Problem(gaps_path, 0, f"{gap_id} has invalid or missing status"))
        if not readiness:
            problems.append(Problem(gaps_path, 0, f"{gap_id} has invalid or missing implementation readiness"))
        if gap_class == "EVIDENCE_GAP" and (status != "BLOCKED" or readiness != "BLOCKED"):
            problems.append(Problem(gaps_path, 0, f"{gap_id} EVIDENCE_GAP must be BLOCKED"))
        register_row = register_by_id.get(gap_id)
        if register_row and len(register_row) >= 8:
            if register_row[2] != gap_class:
                problems.append(Problem(gaps_path, 0, f"{gap_id} class differs between register and dossier"))
            if register_row[4] != status:
                problems.append(Problem(gaps_path, 0, f"{gap_id} status differs between register and dossier"))
            if register_row[7] != readiness:
                problems.append(Problem(gaps_path, 0, f"{gap_id} readiness differs between register and dossier"))

        if readiness == "READY":
            required_prefixes = (
                f"REQ-{gap_id}-",
                f"STEP-{gap_id}-",
                f"TEST-{gap_id}-",
                f"AC-{gap_id}-",
            )
            for prefix in required_prefixes:
                if prefix not in block:
                    problems.append(Problem(gaps_path, 0, f"{gap_id} READY dossier lacks {prefix} mapping"))
            if re.search(r"GAPDEC-\d+\s*\|.*?\|\s*pending\s*\|", block, flags=re.MULTILINE):
                problems.append(Problem(gaps_path, 0, f"{gap_id} READY dossier has a pending decision"))

    plan_gap_ids = set(re.findall(r"\bGAP-\d{3,}\b", texts["gap_implementation_plan.md"]))
    unknown_plan_gaps = sorted(plan_gap_ids - set(register_ids))
    if unknown_plan_gaps:
        problems.append(
            Problem(
                pack / "gap_implementation_plan.md",
                0,
                f"implementation plan references unregistered gaps: {', '.join(unknown_plan_gaps)}",
            )
        )

    return problems


def main() -> int:
    args = parse_args()
    if args.max_problems < 0:
        print("ERROR: --max-problems must be zero or greater", file=sys.stderr)
        return 2
    pack = args.pack_directory.expanduser().resolve()
    problems = validate_pack(pack, args.require_verified_mvp)
    if problems:
        print(f"FAIL: {len(problems)} validation problem(s)", file=sys.stderr)
        shown = problems if args.max_problems == 0 else problems[: args.max_problems]
        for problem in shown:
            print(f"  {problem.format()}", file=sys.stderr)
        hidden = len(problems) - len(shown)
        if hidden:
            print(f"  ... {hidden} additional problem(s); use --max-problems 0 to print all", file=sys.stderr)
        return 1
    print(f"PASS: clone pack is structurally valid: {pack}")
    if args.require_verified_mvp:
        print("PASS: every MVP requirement is VERIFIED and verdict is VERIFIED_MVP")
    print("Semantic fidelity and evidence quality still require manual review.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
