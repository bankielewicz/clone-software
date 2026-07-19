from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .common import ClonePackError, canonical_json
from .constants import (
    CHANGE_TYPES,
    EXIT_INTERNAL,
    EXIT_MIGRATION,
    EXIT_UNSUPPORTED,
    PLAYBOOKS,
    PRODUCT_TYPES,
    PROFILES,
    V2_SCHEMA,
)
from .evolution import diff_packs, migrate_v1, migration_check
from .enhancement import (
    initialize_enhancement_v2,
    rehash_targets,
    run_preservation_baseline,
    run_preservation_regression,
    transition_enhancement,
    verify_enhancement_scope,
)
from .lifecycle import transition_gap
from .operations import (
    execute_assurance,
    execute_capture,
    execute_capture_batch,
    execute_parity,
    record_manual,
    record_run,
)
from .pack import create_seal, detect_schema, initialize_v2, validate_v2
from .repository import repository_snapshot
from .scaffold import apply_scaffold


def _add_timestamp(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--timestamp", help="Pinned ISO-8601 timestamp for deterministic fixtures.")


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description="Create, capture, verify, migrate, and close clone-pack/v2 packs.")
    commands = root.add_subparsers(dest="command", required=True)

    init = commands.add_parser("init", help="Create a non-overwriting clone-pack/v2 scaffold.")
    init.add_argument("--product-name", required=True)
    init.add_argument("--product-type", choices=sorted(PRODUCT_TYPES), required=True)
    init.add_argument("--playbook", action="append", choices=sorted(PLAYBOOKS), default=[])
    init.add_argument("--source-description", required=True)
    init.add_argument("--repo-root", type=Path, default=Path.cwd())
    init.add_argument("--output-dir", type=Path, default=Path("docs/clone"))
    _add_timestamp(init)

    enhancement_init = commands.add_parser(
        "enhancement-init",
        help="Create a non-overwriting brownfield enhancement workstream pack.",
    )
    enhancement_init.add_argument("--product-name", required=True)
    enhancement_init.add_argument("--product-type", choices=sorted(PRODUCT_TYPES), required=True)
    enhancement_init.add_argument("--playbook", action="append", choices=sorted(PLAYBOOKS), default=[])
    enhancement_init.add_argument("--enhancement-id", required=True)
    enhancement_init.add_argument("--title", required=True)
    enhancement_init.add_argument("--change-type", action="append", choices=sorted(CHANGE_TYPES), required=True)
    enhancement_init.add_argument("--request-file", type=Path, required=True)
    enhancement_init.add_argument("--repo-root", type=Path, required=True)
    enhancement_init.add_argument("--output-dir", type=Path, required=True)
    enhancement_init.add_argument("--adopt-dirty", action="store_true")
    _add_timestamp(enhancement_init)

    validate = commands.add_parser("validate", help="Validate a v1 or v2 clone pack.")
    validate.add_argument("pack", type=Path)
    validate.add_argument("--profile", choices=PROFILES, default="scaffold")
    validate.add_argument("--format", choices=("text", "json"), default="text")
    validate.add_argument("--max-problems", type=int, default=100)

    migrate = commands.add_parser("migrate", help="Inspect or migrate clone-pack/v1 to v2.")
    migrate.add_argument("source", type=Path)
    migrate.add_argument("--output", type=Path)
    migrate.add_argument("--mapping", type=Path)
    migrate.add_argument("--check", action="store_true")
    _add_timestamp(migrate)

    capture = commands.add_parser("capture", help="Execute pinned capture cases with atomic evidence promotion.")
    capture.add_argument("pack", type=Path)
    capture_selection = capture.add_mutually_exclusive_group(required=True)
    capture_selection.add_argument("--case")
    capture_selection.add_argument("--all", action="store_true")
    capture.add_argument("--resume", action="store_true")
    _add_timestamp(capture)

    parity = commands.add_parser("parity", help="Execute one independent parity case.")
    parity.add_argument("pack", type=Path)
    parity.add_argument("--case", required=True)

    scaffold = commands.add_parser("scaffold", help="Preview or apply a pinned greenfield scaffold.")
    scaffold.add_argument("pack", type=Path)
    scaffold.add_argument("--apply", action="store_true")

    run = commands.add_parser("record-run", help="Execute one pinned GATE record and retain evidence.")
    run.add_argument("pack", type=Path)
    run.add_argument("--gate", required=True)
    run.add_argument("--environment", required=True)
    _add_timestamp(run)

    manual = commands.add_parser("record-manual", help="Record an evidenced manual verification.")
    manual.add_argument("pack", type=Path)
    manual.add_argument("--test", required=True)
    manual.add_argument("--procedure", type=Path, required=True)
    manual.add_argument("--observer", required=True)
    manual.add_argument("--authority", required=True)
    manual.add_argument("--artifact", action="append", default=[], required=True)
    _add_timestamp(manual)

    gap = commands.add_parser("gap-transition", help="Apply one legal, evidenced gap transition.")
    gap.add_argument("pack", type=Path)
    gap.add_argument("gap_id")
    gap.add_argument("--to", required=True)
    gap.add_argument("--actor", required=True)
    gap.add_argument("--reason", required=True)
    gap.add_argument("--evidence", action="append", default=[])
    gap.add_argument("--decision", action="append", default=[])
    _add_timestamp(gap)

    assure = commands.add_parser("assure", help="Run required assurance cases without installing tools.")
    assure.add_argument("pack", type=Path)
    assure_selection = assure.add_mutually_exclusive_group()
    assure_selection.add_argument("--case", action="append", default=[])
    assure_selection.add_argument("--all", action="store_true")

    snapshot = commands.add_parser("repo-snapshot", help="Record or check an adopted/candidate repository snapshot.")
    snapshot.add_argument("pack", type=Path)
    snapshot.add_argument("--role", choices=("adopted", "candidate"), required=True)
    snapshot_operation = snapshot.add_mutually_exclusive_group(required=True)
    snapshot_operation.add_argument("--record", action="store_true")
    snapshot_operation.add_argument("--check", action="store_true")
    snapshot.add_argument("--include", action="append", default=[])

    for command_name, command_help in (
        ("baseline-run", "Execute and retain immutable preservation baselines."),
        ("regression", "Execute preservation cases against the candidate snapshot."),
    ):
        preservation = commands.add_parser(command_name, help=command_help)
        preservation.add_argument("pack", type=Path)
        preservation_selection = preservation.add_mutually_exclusive_group(required=True)
        preservation_selection.add_argument("--case")
        preservation_selection.add_argument("--all", action="store_true")

    scope = commands.add_parser("verify-scope", help="Compare adopted/candidate deltas with declared CHANGE records.")
    scope.add_argument("pack", type=Path)
    scope.add_argument("--enhancement", required=True)

    enhancement_transition = commands.add_parser(
        "enhancement-transition",
        help="Apply one legal, evidenced enhancement transition.",
    )
    enhancement_transition.add_argument("pack", type=Path)
    enhancement_transition.add_argument("enhancement_id")
    enhancement_transition.add_argument("--to", required=True)
    enhancement_transition.add_argument("--actor", required=True)
    enhancement_transition.add_argument("--reason", required=True)
    enhancement_transition.add_argument("--evidence", action="append", default=[])
    enhancement_transition.add_argument("--decision", action="append", default=[])
    _add_timestamp(enhancement_transition)

    rehash = commands.add_parser("rehash", help="Refresh only explicitly selected definition/case hashes.")
    rehash.add_argument("pack", type=Path)
    rehash.add_argument("--record", action="append", default=[])
    rehash.add_argument("--case", action="append", default=[])

    seal = commands.add_parser("seal", help="Derive and seal a passing v2 verdict.")
    seal.add_argument("pack", type=Path)
    seal.add_argument("--profile", choices=("verified-mvp", "gap-closure", "closed", "verified-enhancement"), required=True)
    _add_timestamp(seal)

    diff = commands.add_parser("diff", help="Compare canonical record identities across packs.")
    diff.add_argument("left", type=Path)
    diff.add_argument("right", type=Path)
    diff.add_argument("--format", choices=("text", "json"), default="text")
    return root


def _print_validation(pack: Path, profile: str, output_format: str, max_problems: int) -> int:
    schema = detect_schema(pack.expanduser().resolve())
    if schema == "clone-pack/v1":
        if profile in {"verified-mvp", "gap-closure", "closed"}:
            message = "MIGRATION_REQUIRED: v1 packs cannot receive evidence-backed v2 certification"
            if output_format == "json":
                print(canonical_json({"schema_version": schema, "profile": profile, "status": "UNSUPPORTED", "diagnostics": [{"code": "MIGRATION_REQUIRED", "message": message}]}), end="")
            else:
                print(message, file=sys.stderr)
            return EXIT_UNSUPPORTED
        from .legacy_v1 import validate_pack

        problems = validate_pack(pack.expanduser().resolve(), False)
        if output_format == "json":
            print(canonical_json({"schema_version": schema, "profile": "legacy-structural", "status": "FAIL" if problems else "PASS", "diagnostics": [{"code": "LEGACY_V1", "path": str(problem.path), "line": problem.line, "message": problem.message} for problem in problems]}), end="")
        elif problems:
            print(f"FAIL: {len(problems)} validation problem(s)", file=sys.stderr)
            shown = problems if max_problems == 0 else problems[:max_problems]
            for problem in shown:
                print(f"  {problem.format()}", file=sys.stderr)
        else:
            print(f"PASS: legacy clone-pack/v1 is structurally valid: {pack.expanduser().resolve()}")
            print("Legacy v1 status claims are not evidence-backed v2 certification.")
        return 1 if problems else 0
    if schema != V2_SCHEMA:
        raise ClonePackError(f"unsupported schema version: {schema}", exit_code=EXIT_UNSUPPORTED, diagnostic="SCHEMA_UNSUPPORTED")
    result = validate_v2(pack, profile)
    diagnostics = result.sorted_all()
    if output_format == "json":
        print(canonical_json({"schema_version": schema, "profile": profile, "status": "PASS" if result.exit_code == 0 else ("HOLD" if result.exit_code == 5 else "FAIL"), "diagnostics": [item.as_dict() for item in diagnostics]}), end="")
    elif result.exit_code:
        if profile == "scaffold":
            label = "STRUCTURAL HOLD" if result.exit_code == 5 else "STRUCTURAL FAIL"
        else:
            label = "HOLD" if result.exit_code == 5 else "FAIL"
        print(f"{label}: {len(diagnostics)} problem(s)", file=sys.stderr)
        shown = diagnostics if max_problems == 0 else diagnostics[:max_problems]
        for item in shown:
            identity = f" [{item.record_id}]" if item.record_id else ""
            print(f"  {item.path}: {item.code}{identity}: {item.message}", file=sys.stderr)
    elif profile == "scaffold":
        print(f"STRUCTURAL PASS: clone-pack/v2 passes the scaffold structure profile: {pack.expanduser().resolve()}")
        print(
            "NON-CERTIFICATION: this result does not establish source accuracy, evidence readiness, "
            "specification completeness, implementation, parity, assurance, security, or release readiness."
        )
    else:
        print(f"PASS: clone-pack/v2 satisfies profile {profile}: {pack.expanduser().resolve()}")
    return result.exit_code


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    skill_root = Path(__file__).resolve().parents[2]
    try:
        if args.command == "init":
            destination = initialize_v2(
                skill_root=skill_root,
                product_name=args.product_name,
                product_type=args.product_type,
                playbooks=args.playbook,
                source_description=args.source_description,
                repo_root=args.repo_root,
                output_dir=args.output_dir,
                timestamp=args.timestamp,
            )
            print(f"Created clone-pack/v2 scaffold: {destination}")
            print("Complete required markers, populate clone_index.json, then validate --profile baseline-ready.")
            return 0
        if args.command == "enhancement-init":
            result = initialize_enhancement_v2(
                skill_root=skill_root,
                product_name=args.product_name,
                product_type=args.product_type,
                playbooks=args.playbook,
                enhancement_id=args.enhancement_id,
                title=args.title,
                change_types=args.change_type,
                request_file=args.request_file,
                repo_root=args.repo_root,
                output_dir=args.output_dir,
                adopt_dirty=args.adopt_dirty,
                timestamp=args.timestamp,
            )
            print(canonical_json(result), end="")
            return 0
        if args.command == "validate":
            if args.max_problems < 0:
                raise ClonePackError("--max-problems must be non-negative", exit_code=2, diagnostic="ARG_INVALID")
            return _print_validation(args.pack, args.profile, args.format, args.max_problems)
        if args.command == "migrate":
            if args.check:
                check = migration_check(args.source, args.mapping)
                print(canonical_json(check), end="")
                return 0 if check["migratable"] else EXIT_MIGRATION
            if args.output is None:
                raise ClonePackError("migration requires --output unless --check is used", exit_code=2, diagnostic="ARG_INVALID")
            destination = migrate_v1(skill_root=skill_root, source=args.source, output=args.output, mapping_path=args.mapping, timestamp=args.timestamp)
            print(f"Created non-overwriting clone-pack/v2 successor: {destination}")
            return 0
        if args.command == "capture":
            if args.all:
                result, exit_code = execute_capture_batch(args.pack, args.timestamp, resume=args.resume)
            else:
                result, exit_code = execute_capture(args.pack, args.case, args.timestamp, resume=args.resume)
            print(canonical_json(result), end="")
            return exit_code
        if args.command == "parity":
            result, exit_code = execute_parity(args.pack, args.case)
            print(canonical_json(result), end="")
            return exit_code
        if args.command == "scaffold":
            print(canonical_json(apply_scaffold(skill_root, args.pack, apply=args.apply)), end="")
            return 0
        if args.command == "record-run":
            result, exit_code = record_run(args.pack, args.gate, args.environment, args.timestamp)
            print(canonical_json(result), end="")
            return exit_code
        if args.command == "record-manual":
            print(canonical_json(record_manual(args.pack, args.test, args.procedure, args.observer, args.authority, args.artifact, args.timestamp)), end="")
            return 0
        if args.command == "gap-transition":
            print(canonical_json(transition_gap(args.pack, args.gap_id, args.to, actor=args.actor, reason=args.reason, evidence_ids=args.evidence, decision_ids=args.decision, timestamp=args.timestamp)), end="")
            return 0
        if args.command == "assure":
            result, exit_code = execute_assurance(args.pack, args.case, all_cases=args.all)
            print(canonical_json(result), end="")
            return exit_code
        if args.command == "repo-snapshot":
            result, exit_code = repository_snapshot(
                args.pack,
                args.role,
                record=args.record,
                check=args.check,
                includes=args.include,
            )
            print(canonical_json(result), end="")
            return exit_code
        if args.command == "baseline-run":
            result, exit_code = run_preservation_baseline(
                args.pack,
                [args.case] if args.case else [],
                all_cases=args.all,
            )
            print(canonical_json(result), end="")
            return exit_code
        if args.command == "regression":
            result, exit_code = run_preservation_regression(
                args.pack,
                [args.case] if args.case else [],
                all_cases=args.all,
            )
            print(canonical_json(result), end="")
            return exit_code
        if args.command == "verify-scope":
            result, exit_code = verify_enhancement_scope(args.pack, args.enhancement)
            print(canonical_json(result), end="")
            return exit_code
        if args.command == "enhancement-transition":
            result = transition_enhancement(
                args.pack,
                args.enhancement_id,
                args.to,
                actor=args.actor,
                reason=args.reason,
                evidence_ids=args.evidence,
                decision_ids=args.decision,
                timestamp=args.timestamp,
            )
            print(canonical_json(result), end="")
            return 0
        if args.command == "rehash":
            result = rehash_targets(args.pack, record_ids=args.record, case_ids=args.case)
            print(canonical_json(result), end="")
            return 0
        if args.command == "seal":
            print(canonical_json(create_seal(args.pack, args.profile, args.timestamp)), end="")
            return 0
        if args.command == "diff":
            value = diff_packs(args.left, args.right)
            if args.format == "json":
                print(canonical_json(value), end="")
            else:
                print(f"Added: {', '.join(value['added_ids']) or 'none'}")
                print(f"Removed: {', '.join(value['removed_ids']) or 'none'}")
                print(f"Changed: {', '.join(value['changed_ids']) or 'none'}")
            return 0
        raise ClonePackError(f"unsupported command: {args.command}", exit_code=2, diagnostic="ARG_INVALID")
    except ClonePackError as exc:
        print(f"{exc.diagnostic}: {exc}", file=sys.stderr)
        return exc.exit_code
    except KeyboardInterrupt:
        print("INTERRUPTED: operation cancelled", file=sys.stderr)
        return 130
    except Exception as exc:  # pragma: no cover - defensive command boundary
        print(f"INTERNAL_ERROR: {type(exc).__name__}: {exc}", file=sys.stderr)
        return EXIT_INTERNAL
