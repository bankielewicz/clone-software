from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from . import TOOL_VERSION
from .common import (
    ClonePackError,
    atomic_write_many,
    atomic_write_json,
    atomic_write_text,
    case_contract_sha256,
    canonical_json,
    clean_line,
    contract_hashes_for_records,
    exact_keys,
    gate_execution_contract,
    load_json,
    parse_frontmatter,
    recover_atomic_transactions,
    render_template,
    resolve_inside,
    safe_relative_path,
    sha256_bytes,
    sha256_file,
    slugify,
)
from .constants import (
    EXIT_CONTRACT,
    EXIT_HOLD,
    EXIT_INTEGRITY,
    EXIT_UNSUPPORTED,
    GAP_STATUSES,
    ID_PATTERNS,
    LEGAL_GAP_TRANSITIONS,
    ENHANCEMENT_PLAN_FILES,
    OPTIONAL_PLAN_FILES,
    PLAN_FILES,
    PLAYBOOKS,
    PRODUCT_TYPES,
    PROFILES,
    RECORD_KINDS,
    TERMINAL_GAP_STATUSES,
    V2_DOCUMENTS,
    V2_SCHEMA,
    profile_requires,
)
from .dossier import validate_gap_plan_record
from .full_stack_qa import validate_full_stack_qa_plan
from .schema import SchemaDefinitionError, validate_schema_file


MANIFEST_REQUIRED_FIELDS = {
    "schema_version",
    "pack_id",
    "pack_revision",
    "state",
    "product_name",
    "product_type",
    "playbooks",
    "reference_source",
    "reference_baseline_id",
    "created_at",
    "repository_root",
    "repository_state",
    "required_capabilities",
    "documents",
    "plans",
    "index_path",
    "runs_path",
    "history_path",
    "seal_path",
    "supersedes",
    "migration",
}
MANIFEST_OPTIONAL_FIELDS = {"workstream"}
MANIFEST_FIELDS = MANIFEST_REQUIRED_FIELDS | MANIFEST_OPTIONAL_FIELDS

INDEX_FIELDS = {"schema_version", "pack_id", "pack_revision", "records"}
RECORD_FIELDS = {"id", "kind", "locator", "links", "applicability", "state", "attributes"}

LINK_KINDS: dict[str, set[str]] = {
    "baselines": {"BASE"},
    "blockers": {"BLOCK", "PROVBLOCK"},
    "environments": {"ENV"},
    "artifacts": {"ART"},
    "evidence": {"E"},
    "decisions": {"DEC", "ADR", "GAPDEC"},
    "actors": {"ACT"},
    "requirements": {"REQ"},
    "acceptance": {"AC"},
    "tests": {"TEST"},
    "runs": {"RUN"},
    "gaps": {"GAP"},
    "exclusions": {"EXC"},
    "surfaces": {"SURF"},
    "workflows": {"WF"},
    "interfaces": {"IF"},
    "data": {"DATA"},
    "security": {"SEC"},
    "nonfunctional": {"NFR"},
    "dependencies": {"GAP", "DEP", "COMP"},
    "oracles": {"E", "ART", "CAP"},
    "gates": {"GATE"},
    "captures": {"CAP"},
    "parity": {"PAR"},
    "assurance": {"ASSURE"},
    "assets": {"ASSET", "ART"},
    "threats": {"THREAT"},
    "controls": {"CTRL"},
    "findings": {"FIND"},
    "components": {"COMP"},
    "sboms": {"SBOM"},
    "builds": {"BUILD"},
    "provenance": {"PROV"},
    "conflicts": {"CONFLICT"},
    "scaffolds": {"SCF"},
    "stacks": {"STACK"},
    "invariants": {"INV"},
    "changes": {"CHANGE"},
    "steps": {"STEP"},
    "slices": {"SLICE"},
    "halts": {"HALT"},
    "migrations": {"MIG"},
    "enhancements": {"ENH"},
    "preservations": {"PRES"},
    "snapshots": {"SNAP"},
    "scopes": {"SCOPE"},
}

CAPABILITY_DISPOSITIONS = {
    "EQUIVALENT",
    "MISSING",
    "PARTIAL",
    "DIVERGENT",
    "EXCLUDED",
    "UNVERIFIED",
}

# (source kinds, forward relation, target kinds, reciprocal relation).  Relation
# names alone are not reciprocal: REQ.tests points to TEST while RUN.tests also
# points to TEST, and those targets use different back-link relations.
RECIPROCAL_TRACE_RULES: tuple[tuple[set[str], str, set[str], str], ...] = (
    ({"REQ"}, "evidence", {"E"}, "requirements"),
    ({"REQ"}, "decisions", {"DEC", "ADR", "GAPDEC"}, "requirements"),
    ({"REQ"}, "acceptance", {"AC"}, "requirements"),
    ({"REQ"}, "tests", {"TEST"}, "requirements"),
    ({"TEST"}, "gates", {"GATE"}, "tests"),
    ({"RUN"}, "requirements", {"REQ"}, "runs"),
    ({"RUN"}, "acceptance", {"AC"}, "runs"),
    ({"RUN"}, "tests", {"TEST"}, "runs"),
    ({"RUN"}, "oracles", {"E", "ART", "CAP"}, "runs"),
    ({"RUN"}, "gates", {"GATE"}, "runs"),
    ({"ENH"}, "requirements", {"REQ"}, "enhancements"),
    ({"ENH"}, "invariants", {"INV"}, "enhancements"),
    ({"ENH"}, "changes", {"CHANGE"}, "enhancements"),
    ({"ENH"}, "preservations", {"PRES"}, "enhancements"),
    ({"ENH"}, "gates", {"GATE"}, "enhancements"),
    ({"ENH"}, "decisions", {"DEC", "ADR", "GAPDEC"}, "enhancements"),
    ({"ENH"}, "snapshots", {"SNAP"}, "enhancements"),
    ({"ENH"}, "scopes", {"SCOPE"}, "enhancements"),
    ({"ENH"}, "assurance", {"ASSURE"}, "enhancements"),
    ({"ENH"}, "gaps", {"GAP"}, "enhancements"),
)

PROFILE_DOCUMENTS = {
    "baseline-ready": {"clone_brief.md", "evidence_ledger.md"},
    "spec-ready": {"clone_brief.md", "evidence_ledger.md", "clone_specification.md", "acceptance_matrix.md"},
    "build-ready": set(V2_DOCUMENTS),
    "verified-mvp": set(V2_DOCUMENTS),
    "gap-plan": {"clone_brief.md", "evidence_ledger.md", "clone_specification.md", "acceptance_matrix.md", "gaps_analysis.md", "gap_implementation_plan.md"},
    "gap-closure": set(V2_DOCUMENTS),
    "closed": set(V2_DOCUMENTS),
    "repository-adopted": set(),
    "enhancement-ready": set(),
    "implementation": set(),
    "verified-enhancement": set(),
}

AMBIGUOUS_PROSE = (
    ("placeholder token", re.compile(r"\b(?:TBD|TODO|TBC|FIXME|TK)\b|\?\?\?", re.IGNORECASE)),
    ("non-normative modal", re.compile(r"\b(?:should|could|may|might|maybe|ideally|eventually)\b")),
    ("unbounded timing", re.compile(r"\bas needed\b")),
)

SCHEMA_ROOT = Path(__file__).resolve().parents[2] / "assets" / "schemas"
SCHEMA_FILES = {
    "manifest": "clone-pack-v2.schema.json",
    "index": "clone-index-v2.schema.json",
    "capture": "capture-plan-v2.schema.json",
    "parity": "parity-plan-v2.schema.json",
    "scaffold": "scaffold-plan-v2.schema.json",
    "assurance": "assurance-plan-v2.schema.json",
    "run": "clone-run-v2.schema.json",
    "gap_event": "clone-gap-event-v2.schema.json",
    "seal": "clone-seal-v2.schema.json",
    "repository_inventory": "repository-inventory-v2.schema.json",
    "enhancement": "enhancement-plan-v2.schema.json",
    "full_stack_qa": "full-stack-qa-plan-v1.schema.json",
}


@dataclass(order=True, frozen=True)
class Diagnostic:
    path: str
    code: str
    message: str
    record_id: str = ""
    severity: str = "ERROR"

    def as_dict(self) -> dict[str, str]:
        return {
            "code": self.code,
            "severity": self.severity,
            "path": self.path,
            "record_id": self.record_id,
            "message": self.message,
        }


@dataclass
class ValidationResult:
    diagnostics: list[Diagnostic] = field(default_factory=list)
    hold_reasons: list[Diagnostic] = field(default_factory=list)

    def add(self, path: str, code: str, message: str, record_id: str = "") -> None:
        self.diagnostics.append(Diagnostic(path, code, message, record_id))

    def hold(self, path: str, code: str, message: str, record_id: str = "") -> None:
        self.hold_reasons.append(Diagnostic(path, code, message, record_id, "HOLD"))

    def sorted_all(self) -> list[Diagnostic]:
        return sorted([*self.diagnostics, *self.hold_reasons])

    @property
    def exit_code(self) -> int:
        if any(
            d.code.startswith(("HASH_", "PATH_", "SEAL_", "ARTIFACT_", "GAP_HISTORY", "GAP_EVENT_CHAIN", "TRANSACTION_"))
            for d in self.diagnostics
        ):
            return EXIT_INTEGRITY
        if self.diagnostics:
            return EXIT_CONTRACT
        if self.hold_reasons:
            return EXIT_HOLD
        return 0


def _add_schema_diagnostics(
    result: ValidationResult,
    artifact_path: str,
    instance: Any,
    schema_name: str,
) -> None:
    try:
        violations = validate_schema_file(instance, SCHEMA_ROOT / SCHEMA_FILES[schema_name])
    except (KeyError, SchemaDefinitionError) as exc:
        result.add(artifact_path, "SCHEMA_INVALID", f"packaged schema is unavailable: {exc}")
        return
    for violation in violations:
        result.add(
            f"{artifact_path}#{violation.pointer}",
            "SCHEMA_INVALID",
            violation.message,
        )


def _lintable_prose(text: str) -> str:
    text = re.sub(r"<!--.*?-->", "", text, flags=re.DOTALL)
    text = re.sub(r"^\s*```.*?^\s*```\s*$", "", text, flags=re.MULTILINE | re.DOTALL)
    return re.sub(r"`[^`\n]*`", "", text)


def _validate_json_artifact_schema(
    pack: Path,
    result: ValidationResult,
    artifact_path: str,
    schema_name: str,
) -> dict[str, Any] | None:
    try:
        instance = load_json(resolve_inside(pack, artifact_path, must_exist=True))
    except ClonePackError as exc:
        result.add(artifact_path, exc.diagnostic, str(exc))
        return None
    _add_schema_diagnostics(result, artifact_path, instance, schema_name)
    return instance


def utc_now(timestamp: str | None = None) -> tuple[str, str]:
    if timestamp:
        try:
            parsed = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
        except ValueError as exc:
            raise ClonePackError("--timestamp must be ISO-8601", exit_code=2, diagnostic="ARG_INVALID") from exc
        if parsed.tzinfo is None:
            raise ClonePackError("--timestamp must include an offset", exit_code=2, diagnostic="ARG_INVALID")
        parsed = parsed.astimezone(timezone.utc)
    else:
        parsed = datetime.now(timezone.utc)
    return parsed.isoformat(timespec="seconds"), parsed.date().isoformat()


def initialize_v2(
    *,
    skill_root: Path,
    product_name: str,
    product_type: str,
    playbooks: list[str],
    source_description: str,
    repo_root: Path,
    output_dir: Path,
    timestamp: str | None = None,
) -> Path:
    product_name = clean_line("product name", product_name)
    source_description = clean_line("source description", source_description)
    if product_type not in PRODUCT_TYPES:
        raise ClonePackError(f"unsupported product type: {product_type}", exit_code=2, diagnostic="ARG_INVALID")
    selected = list(dict.fromkeys(playbooks or ([] if product_type == "hybrid" else [product_type])))
    invalid = sorted(set(selected) - PLAYBOOKS)
    if invalid:
        raise ClonePackError(f"unsupported playbook(s): {', '.join(invalid)}", exit_code=2, diagnostic="ARG_INVALID")
    if product_type == "hybrid" and len(selected) < 2:
        raise ClonePackError("hybrid requires at least two --playbook values", exit_code=2, diagnostic="ARG_INVALID")
    if product_type != "hybrid" and product_type not in selected:
        selected.insert(0, product_type)

    root = repo_root.expanduser().resolve()
    if not root.is_dir():
        raise ClonePackError(f"repository root is not a directory: {root}", exit_code=2, diagnostic="ARG_INVALID")
    destination = output_dir.expanduser()
    if not destination.is_absolute():
        destination = root / destination
    destination = destination.resolve()
    try:
        destination.relative_to(root)
    except ValueError as exc:
        raise ClonePackError("output directory must remain inside repository root", exit_code=2, diagnostic="PATH_ESCAPE") from exc
    if destination == root:
        raise ClonePackError("output directory must not be the repository root", exit_code=2, diagnostic="PATH_UNSAFE")
    if destination.exists():
        raise ClonePackError(f"refusing to overwrite existing destination: {destination}", exit_code=2, diagnostic="OUTPUT_EXISTS")

    created_at, baseline_date = utc_now(timestamp)
    identity_seed = "\u0000".join((product_name, source_description, created_at)).encode("utf-8")
    pack_id = f"clone-{slugify(product_name)}-{baseline_date}-{sha256_bytes(identity_seed)[:12]}"
    template_dir = skill_root / "assets" / "templates-v2"
    replacements = {
        "{{PRODUCT_NAME}}": product_name,
        "{{PRODUCT_NAME_JSON}}": json.dumps(product_name, ensure_ascii=False),
        "{{PRODUCT_SLUG}}": slugify(product_name),
        "{{PRODUCT_TYPE}}": product_type,
        "{{SOURCE_DESCRIPTION}}": source_description,
        "{{SOURCE_DESCRIPTION_JSON}}": json.dumps(source_description, ensure_ascii=False),
        "{{BASELINE_DATE}}": baseline_date,
        "{{CREATED_AT}}": created_at,
        "{{REPOSITORY_ROOT}}": root.as_posix(),
        "{{PACK_ID}}": pack_id,
    }
    required_templates = [*V2_DOCUMENTS, *PLAN_FILES.values()]
    rendered: dict[str, str] = {}
    for name in required_templates:
        template = template_dir / name
        if not template.is_file():
            raise ClonePackError(f"missing v2 template: {template}", diagnostic="TEMPLATE_MISSING")
        rendered[name] = render_template(template.read_text(encoding="utf-8"), replacements)

    destination.mkdir(parents=True)
    try:
        for name, content in rendered.items():
            atomic_write_text(destination / name, content)
        (destination / "history").mkdir()
        (destination / "runs").mkdir()
        for directory in (
            "evidence/captures",
            "evidence/parity",
            "evidence/assurance",
            "evidence/sbom",
            "evidence/provenance",
        ):
            (destination / directory).mkdir(parents=True)
        atomic_write_text(destination / "history" / "gap_events.jsonl", "")
        index = {
            "schema_version": "clone-index/v2",
            "pack_id": pack_id,
            "pack_revision": 1,
            "records": [],
        }
        atomic_write_json(destination / "clone_index.json", index)
        documents = [
            {
                "role": path.removesuffix(".md"),
                "path": path,
                "schema_version": schema,
                "state": "draft",
                "applicability": "REQUIRED",
                "sha256": None,
            }
            for path, schema in V2_DOCUMENTS.items()
        ]
        manifest = {
            "schema_version": V2_SCHEMA,
            "pack_id": pack_id,
            "pack_revision": 1,
            "state": "draft",
            "product_name": product_name,
            "product_type": product_type,
            "playbooks": selected,
            "reference_source": source_description,
            "reference_baseline_id": "UNRESOLVED",
            "created_at": created_at,
            "repository_root": root.as_posix(),
            "repository_state": {"kind": "unresolved", "revision": "UNRESOLVED", "diff_sha256": None},
            "required_capabilities": [],
            "workstream": {"kind": "clone-mvp"},
            "documents": documents,
            "plans": dict(PLAN_FILES),
            "index_path": "clone_index.json",
            "runs_path": "runs",
            "history_path": "history/gap_events.jsonl",
            "seal_path": "seal.json",
            "supersedes": None,
            "migration": None,
        }
        atomic_write_json(destination / "clone_pack.json", manifest)
    except BaseException:
        # The caller supplied a previously absent, pack-specific destination. Cleanup is
        # bounded to that exact directory and only occurs for a failed initialization.
        import shutil

        shutil.rmtree(destination, ignore_errors=True)
        raise
    return destination


def detect_schema(pack: Path) -> str:
    manifest = load_json(pack / "clone_pack.json")
    schema = manifest.get("schema_version")
    if not isinstance(schema, str):
        raise ClonePackError("manifest schema_version is missing", exit_code=EXIT_UNSUPPORTED, diagnostic="SCHEMA_UNSUPPORTED")
    return schema


def _record_kind_for_id(identifier: str) -> str | None:
    for kind, pattern in ID_PATTERNS.items():
        if re.fullmatch(pattern, identifier):
            return kind
    return None


def _hash_anchor(path: Path, anchor: str) -> tuple[str | None, str | None]:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        return None, str(exc)
    matches = [line for line in text.splitlines(keepends=True) if anchor in line]
    if len(matches) != 1:
        return None, f"anchor must occur exactly once; found {len(matches)}"
    return sha256_bytes(matches[0].encode("utf-8")), None


def _validate_result_artifact(pack: Path, result: ValidationResult, owner: str, artifact: Any) -> bool:
    if not isinstance(artifact, dict):
        result.add(owner, "RESULT_INVALID", "result artifact must be an object")
        return False
    path_value = artifact.get("path")
    expected = artifact.get("sha256")
    if not isinstance(path_value, str) or not isinstance(expected, str):
        result.add(owner, "RESULT_INVALID", "result artifact requires path and sha256")
        return False
    try:
        path = resolve_inside(pack, path_value, must_exist=True)
        actual = sha256_file(path)
    except ClonePackError as exc:
        result.add(owner, exc.diagnostic, str(exc))
        return False
    if actual != expected:
        result.add(owner, "ARTIFACT_HASH_MISMATCH", f"artifact hash mismatch: {path_value}")
        return False
    return True


RUN_COVERED_KINDS = {"REQ", "AC", "TEST"}
RUN_ORACLE_KINDS = {"E", "ART", "CAP"}


def _run_ids(value: Any, run_path: str, result: ValidationResult, field: str, run_id: str) -> list[str]:
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        result.add(run_path, "RUN_INVALID", f"{field} must be a record-ID array", run_id)
        return []
    if len(value) != len(set(value)):
        result.add(run_path, "RUN_INVALID", f"{field} must not contain duplicates", run_id)
    return sorted(set(value))


def _run_reference(
    records: dict[str, dict[str, Any]],
    identifier: Any,
    allowed_kinds: set[str],
    role: str,
    run_path: str,
    result: ValidationResult,
    run_id: str,
) -> dict[str, Any] | None:
    if not isinstance(identifier, str) or not identifier:
        result.add(run_path, "RUN_REFERENCE_INVALID", f"{role} is missing", run_id)
        return None
    record = records.get(identifier)
    if record is None:
        result.add(run_path, "REF_UNDEFINED", f"{role} references undefined ID: {identifier}", run_id)
        return None
    if record.get("kind") not in allowed_kinds:
        result.add(
            run_path,
            "REF_WRONG_KIND",
            f"{role} {identifier} has kind {record.get('kind')}; expected {', '.join(sorted(allowed_kinds))}",
            run_id,
        )
        return None
    return record


def _current_link_ids(record: dict[str, Any], relation: str) -> list[str]:
    links = record.get("links") if isinstance(record.get("links"), dict) else {}
    values = links.get(relation, [])
    return sorted(set(values)) if isinstance(values, list) and all(isinstance(item, str) for item in values) else []


def _run_index_links(
    records: dict[str, dict[str, Any]],
    covered_ids: list[str],
    oracle_ids: list[str],
    gate_id: str | None,
) -> dict[str, list[str]]:
    links = {
        "tests": sorted(identifier for identifier in covered_ids if records.get(identifier, {}).get("kind") == "TEST"),
        "acceptance": sorted(identifier for identifier in covered_ids if records.get(identifier, {}).get("kind") == "AC"),
        "oracles": sorted(oracle_ids),
        "requirements": sorted(identifier for identifier in covered_ids if records.get(identifier, {}).get("kind") == "REQ"),
    }
    if gate_id is not None:
        links["gates"] = [gate_id]
    return links


def _validate_run_contract(
    run_path: str,
    run: dict[str, Any],
    run_id: str,
    records: dict[str, dict[str, Any]],
    result: ValidationResult,
) -> tuple[list[str], list[str], str | None]:
    covered_ids = _run_ids(run.get("covered_ids"), run_path, result, "covered_ids", run_id)
    oracle_ids = _run_ids(run.get("oracle_ids"), run_path, result, "oracle_ids", run_id)
    for identifier in covered_ids:
        _run_reference(records, identifier, RUN_COVERED_KINDS, "covered ID", run_path, result, run_id)
    for identifier in oracle_ids:
        _run_reference(records, identifier, RUN_ORACLE_KINDS, "oracle ID", run_path, result, run_id)

    environment_id = run.get("environment_id")
    _run_reference(records, environment_id, {"ENV"}, "environment", run_path, result, run_id)
    manual = run.get("schema_version") == "clone-manual-run/v2"
    gate_id: str | None = None
    expected_covered = covered_ids
    expected_oracles = oracle_ids
    expected_environment = environment_id

    if manual:
        if run.get("gate_id") != "MANUAL":
            result.add(run_path, "RUN_GATE_INVALID", "manual run gate_id must be MANUAL", run_id)
        tests = [identifier for identifier in covered_ids if records.get(identifier, {}).get("kind") == "TEST"]
        if len(tests) != 1:
            result.add(run_path, "RUN_TEST_INVALID", "manual run must cover exactly one TEST record", run_id)
        else:
            test = records[tests[0]]
            expected_covered = sorted(
                {tests[0], *_current_link_ids(test, "acceptance"), *_current_link_ids(test, "requirements")}
            )
            expected_oracles = _current_link_ids(test, "oracles")
            attributes = test.get("attributes") if isinstance(test.get("attributes"), dict) else {}
            expected_environment = attributes.get("environment_id")
            stale_fields: list[str] = []
            if covered_ids != expected_covered:
                stale_fields.append("covered_ids")
            if oracle_ids != expected_oracles:
                stale_fields.append("oracle_ids")
            if environment_id != expected_environment:
                stale_fields.append("environment_id")
            expected_procedure = attributes.get("manual_procedure_sha256")
            attestation = run.get("manual_attestation") if isinstance(run.get("manual_attestation"), dict) else {}
            procedure_artifacts = [
                artifact
                for artifact in run.get("artifacts", [])
                if isinstance(artifact, dict) and str(artifact.get("path", "")).endswith("/procedure.md")
            ] if isinstance(run.get("artifacts"), list) else []
            if (
                not isinstance(expected_procedure, str)
                or not re.fullmatch(r"[0-9a-f]{64}", expected_procedure)
                or attestation.get("procedure_sha256") != expected_procedure
                or len(procedure_artifacts) != 1
                or procedure_artifacts[0].get("sha256") != expected_procedure
            ):
                stale_fields.append("manual_procedure_sha256")
            if stale_fields:
                result.add(
                    run_path,
                    "RUN_CONTRACT_STALE",
                    "manual run differs from current TEST contract: " + ", ".join(stale_fields),
                    run_id,
                )
    else:
        gate_id_value = run.get("gate_id")
        gate = _run_reference(records, gate_id_value, {"GATE"}, "gate", run_path, result, run_id)
        gate_id = gate_id_value if isinstance(gate_id_value, str) else None
        if gate is not None:
            attributes = gate.get("attributes") if isinstance(gate.get("attributes"), dict) else {}
            current_covered = sorted(attributes.get("covered_ids", [])) if isinstance(attributes.get("covered_ids", []), list) else []
            current_oracles = sorted(attributes.get("oracle_ids", [])) if isinstance(attributes.get("oracle_ids", []), list) else []
            expected_covered = current_covered
            expected_oracles = current_oracles
            comparisons = {
                "covered_ids": (covered_ids, current_covered),
                "oracle_ids": (oracle_ids, current_oracles),
                "argv": (run.get("argv"), attributes.get("argv")),
                "expected_exit": (run.get("expected_exit"), attributes.get("expected_exit", 0)),
                "normalizations": (run.get("normalizations"), attributes.get("normalizations", [])),
                "redactions": (run.get("redactions"), attributes.get("redactions", [])),
            }
            retained_execution_contract = run.get("execution_contract")
            if retained_execution_contract is not None:
                comparisons["execution_contract"] = (
                    retained_execution_contract,
                    gate_execution_contract(attributes),
                )
            elif run.get("runner_version") == TOOL_VERSION:
                comparisons["execution_contract"] = (None, gate_execution_contract(attributes))
            stale_fields = [name for name, (observed, current) in comparisons.items() if observed != current]
            if stale_fields:
                result.add(
                    run_path,
                    "RUN_CONTRACT_STALE",
                    "run differs from current GATE contract: " + ", ".join(stale_fields),
                    run_id,
                )

    governing_ids = [identifier for identifier in [gate_id, expected_environment, *expected_covered, *expected_oracles] if isinstance(identifier, str)]
    try:
        expected_hashes = contract_hashes_for_records(records, governing_ids)
    except ClonePackError as exc:
        result.add(run_path, exc.diagnostic, str(exc), run_id)
    else:
        if run.get("contract_hashes") != expected_hashes:
            result.add(
                run_path,
                "RUN_CONTRACT_STALE",
                "contract_hashes do not exactly match current governing record locators",
                run_id,
            )
    return covered_ids, oracle_ids, gate_id


def _validate_run_index_counterpart(
    run_path: str,
    run: dict[str, Any],
    run_id: str,
    records: dict[str, dict[str, Any]],
    covered_ids: list[str],
    oracle_ids: list[str],
    gate_id: str | None,
    result: ValidationResult,
) -> None:
    counterpart = records.get(run_id)
    if counterpart is None:
        result.add(run_path, "RUN_INDEX_MISSING", "run file lacks a RUN index counterpart", run_id)
        return
    if counterpart.get("kind") != "RUN":
        result.add(run_path, "RUN_INDEX_INVALID", "run counterpart does not have kind RUN", run_id)
        return
    locator = counterpart.get("locator") if isinstance(counterpart.get("locator"), dict) else {}
    expected_anchor = f'"run_id": "{run_id}"'
    mismatches: list[str] = []
    if locator.get("path") != run_path or locator.get("anchor") != expected_anchor:
        mismatches.append("locator")
    if counterpart.get("links") != _run_index_links(records, covered_ids, oracle_ids, gate_id):
        mismatches.append("links")
    if counterpart.get("applicability") != "MVP":
        mismatches.append("applicability")
    if counterpart.get("state") != run.get("result"):
        mismatches.append("state")
    attributes = counterpart.get("attributes") if isinstance(counterpart.get("attributes"), dict) else {}
    for name, expected in (
        ("result", run.get("result")),
        ("gate_id", run.get("gate_id")),
        ("environment_id", run.get("environment_id")),
    ):
        if attributes.get(name) != expected:
            mismatches.append(f"attributes.{name}")
    if mismatches:
        result.add(
            run_path,
            "RUN_INDEX_INVALID",
            "RUN index counterpart differs in: " + ", ".join(mismatches),
            run_id,
        )


def _load_runs(
    pack: Path,
    result: ValidationResult,
    manifest: dict[str, Any],
    records: dict[str, dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    runs: dict[str, dict[str, Any]] = {}
    try:
        directory = resolve_inside(pack, str(manifest.get("runs_path", "runs")), must_exist=True)
    except ClonePackError as exc:
        result.add("clone_pack.json", exc.diagnostic, str(exc))
        return runs
    if not directory.is_dir():
        result.add(str(manifest.get("runs_path")), "RUNS_PATH_INVALID", "runs_path must name a directory")
        return runs
    for path in sorted(directory.glob("RUN-*.json")):
        try:
            run = load_json(path)
        except ClonePackError as exc:
            result.add(path.relative_to(pack).as_posix(), exc.diagnostic, str(exc))
            continue
        run_path = path.relative_to(pack).as_posix()
        _add_schema_diagnostics(result, run_path, run, "run")
        run_id = run.get("run_id")
        if not isinstance(run_id, str) or not re.fullmatch(ID_PATTERNS["RUN"], run_id):
            result.add(run_path, "RUN_ID_INVALID", "run_id must match RUN-###")
            continue
        if path.stem != run_id:
            result.add(run_path, "RUN_IDENTITY_MISMATCH", "run_id differs from its filename", run_id)
        if run_id in runs:
            result.add(run_path, "ID_DUPLICATE", f"duplicate run ID: {run_id}", run_id)
            continue
        if run.get("pack_id") != manifest.get("pack_id") or run.get("pack_revision") != manifest.get("pack_revision"):
            result.add(run_path, "RUN_STALE_REVISION", "run pack identity/revision is stale", run_id)
        if run.get("reference_baseline_id") != manifest.get("reference_baseline_id"):
            result.add(run_path, "RUN_STALE_REFERENCE", "run reference baseline is stale", run_id)
        repository_state = manifest.get("repository_state", {})
        if run.get("clone_revision") != repository_state.get("revision"):
            result.add(run_path, "RUN_STALE_REVISION", "run clone revision is stale", run_id)
        if run.get("clone_diff_sha256") != repository_state.get("diff_sha256"):
            result.add(run_path, "RUN_STALE_REVISION", "run clone diff/tree hash is stale", run_id)
        covered_ids, oracle_ids, gate_id = _validate_run_contract(
            run_path,
            run,
            run_id,
            records,
            result,
        )
        _validate_run_index_counterpart(
            run_path,
            run,
            run_id,
            records,
            covered_ids,
            oracle_ids,
            gate_id,
            result,
        )
        artifacts = run.get("artifacts")
        if not isinstance(artifacts, list):
            result.add(run_path, "RUN_INVALID", "run artifacts must be an array", run_id)
        else:
            for artifact in artifacts:
                _validate_result_artifact(pack, result, run_path, artifact)
        if run.get("result") == "PASS" and not run.get("oracle_ids"):
            result.add(run_path, "RUN_ORACLE_INVALID", "passing run requires independent oracle IDs", run_id)
        runs[run_id] = run
    for identifier, record in sorted(records.items()):
        if (
            record.get("kind") == "RUN"
            and identifier not in runs
            and record.get("applicability") != "MIGRATION_RECONCILIATION"
        ):
            result.add(
                "clone_index.json",
                "RUN_FILE_MISSING",
                "RUN index record lacks a retained run file",
                identifier,
            )
    return runs


def _load_gap_events(
    pack: Path,
    result: ValidationResult,
    manifest: dict[str, Any],
    records: dict[str, dict[str, Any]],
) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    try:
        path = resolve_inside(pack, str(manifest.get("history_path", "history/gap_events.jsonl")), must_exist=True)
        lines = path.read_text(encoding="utf-8").splitlines()
    except (ClonePackError, OSError) as exc:
        code = exc.diagnostic if isinstance(exc, ClonePackError) else "HISTORY_UNREADABLE"
        result.add(str(manifest.get("history_path")), code, str(exc))
        return grouped
    previous_by_gap: dict[str, str] = {}
    sequence_by_gap: dict[str, int] = {}
    state_by_gap: dict[str, str] = {}
    timestamp_by_gap: dict[str, datetime] = {}
    event_ids: set[str] = set()
    for number, line in enumerate(lines, start=1):
        if not line.strip():
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError as exc:
            result.add(path.relative_to(pack).as_posix(), "GAP_EVENT_INVALID", f"line {number}: {exc}")
            continue
        if not isinstance(event, dict):
            result.add(path.relative_to(pack).as_posix(), "GAP_EVENT_INVALID", f"line {number}: event must be an object")
            continue
        _add_schema_diagnostics(
            result,
            f"{path.relative_to(pack).as_posix()}:{number}",
            event,
            "gap_event",
        )
        gap_id = event.get("gap_id")
        if not isinstance(gap_id, str):
            result.add(path.relative_to(pack).as_posix(), "GAP_EVENT_INVALID", f"line {number}: gap_id missing")
            continue
        event_id = event.get("event_id")
        if not isinstance(event_id, str) or event_id in event_ids:
            result.add(path.relative_to(pack).as_posix(), "ID_DUPLICATE", f"line {number}: duplicate or invalid event_id", gap_id)
        else:
            event_ids.add(event_id)
        if gap_id not in records or records[gap_id].get("kind") != "GAP":
            result.add(path.relative_to(pack).as_posix(), "REF_UNDEFINED", f"line {number}: undefined gap", gap_id)
        expected_sequence = sequence_by_gap.get(gap_id, 0) + 1
        if event.get("sequence") != expected_sequence:
            result.add(path.relative_to(pack).as_posix(), "GAP_EVENT_SEQUENCE", f"{gap_id} expected sequence {expected_sequence}", gap_id)
        if event.get("previous_event_sha256") != previous_by_gap.get(gap_id, ""):
            result.add(path.relative_to(pack).as_posix(), "GAP_EVENT_CHAIN", f"{gap_id} previous hash mismatch", gap_id)
        hash_input = dict(event)
        supplied = hash_input.pop("event_sha256", None)
        calculated = sha256_bytes(canonical_json(hash_input).encode("utf-8"))
        if supplied != calculated:
            result.add(path.relative_to(pack).as_posix(), "GAP_EVENT_CHAIN", f"{gap_id} event hash mismatch", gap_id)
        from_status = event.get("from")
        to_status = event.get("to")
        if expected_sequence == 1 and from_status != "OPEN":
            result.add(path.relative_to(pack).as_posix(), "GAP_HISTORY_INCOMPLETE", f"{gap_id} history must begin at OPEN", gap_id)
        if gap_id in state_by_gap and from_status != state_by_gap[gap_id]:
            result.add(path.relative_to(pack).as_posix(), "GAP_EVENT_STATE", f"{gap_id} from-state breaks history", gap_id)
        if (from_status, to_status) not in LEGAL_GAP_TRANSITIONS:
            result.add(path.relative_to(pack).as_posix(), "GAP_ILLEGAL_TRANSITION", f"illegal event transition: {from_status} -> {to_status}", gap_id)
        try:
            event_timestamp = datetime.fromisoformat(str(event.get("timestamp", "")).replace("Z", "+00:00"))
        except ValueError:
            result.add(path.relative_to(pack).as_posix(), "GAP_EVENT_CHAIN", f"line {number}: invalid timestamp", gap_id)
        else:
            previous_timestamp = timestamp_by_gap.get(gap_id)
            if previous_timestamp is not None and event_timestamp < previous_timestamp:
                result.add(path.relative_to(pack).as_posix(), "GAP_EVENT_CHAIN", f"line {number}: timestamp regression", gap_id)
            timestamp_by_gap[gap_id] = event_timestamp
        for identifier in event.get("evidence_ids", []):
            if identifier not in records or records[identifier].get("kind") not in {"E", "ART", "CAP", "RUN", "PAR", "ASSURE", "FIND", "SBOM", "BUILD", "PROV"}:
                result.add(path.relative_to(pack).as_posix(), "REF_UNDEFINED", f"line {number}: invalid evidence {identifier}", gap_id)
        for identifier in event.get("decision_ids", []):
            if identifier not in records or records[identifier].get("kind") not in {"DEC", "ADR", "GAPDEC"}:
                result.add(path.relative_to(pack).as_posix(), "REF_UNDEFINED", f"line {number}: invalid decision {identifier}", gap_id)
        previous_by_gap[gap_id] = str(supplied or "")
        sequence_by_gap[gap_id] = expected_sequence
        state_by_gap[gap_id] = str(to_status)
        grouped.setdefault(gap_id, []).append(event)
    return grouped


def _validate_plan_results(
    pack: Path,
    result: ValidationResult,
    plan_name: str,
    plan_path: str,
    manifest: dict[str, Any],
) -> None:
    try:
        plan = load_json(resolve_inside(pack, plan_path, must_exist=True))
    except ClonePackError as exc:
        result.add(plan_path, exc.diagnostic, str(exc))
        return
    cases = plan.get("cases", [])
    if not isinstance(cases, list):
        result.add(plan_path, "PLAN_INVALID", "cases must be an array")
        return
    for case in cases:
        if not isinstance(case, dict):
            result.add(plan_path, "PLAN_INVALID", "case must be an object")
            continue
        required = case.get("required", True) is True
        case_id = str(case.get("id", "unknown"))
        artifact = case.get("result")
        if artifact is None:
            if required:
                result.hold(plan_path, f"{plan_name.upper()}_BLOCKED", f"required case has no result: {case_id}", case_id)
            continue
        if not isinstance(artifact, dict):
            result.add(plan_path, "RESULT_INVALID", "case result pointer must be an object or null", case_id)
            if required:
                result.hold(plan_path, f"{plan_name.upper()}_BLOCKED", f"required case is not PASS: {case_id}", case_id)
            continue
        if required and artifact.get("status") != "PASS":
            result.hold(plan_path, f"{plan_name.upper()}_BLOCKED", f"required case is not PASS: {case_id}", case_id)
        if not _validate_result_artifact(pack, result, plan_path, artifact):
            continue
        try:
            retained_result = load_json(resolve_inside(pack, str(artifact.get("path")), must_exist=True))
        except ClonePackError as exc:
            result.add(plan_path, exc.diagnostic, str(exc), case_id)
            continue
        if retained_result.get("status") != artifact.get("status"):
            result.add(plan_path, "RESULT_STATUS_MISMATCH", "plan pointer status differs from retained result", case_id)
        identity_field = {
            "capture": "capture_id",
            "parity": "parity_id",
            "assurance": "assurance_id",
        }.get(plan_name)
        if identity_field and retained_result.get(identity_field) != case_id:
            result.add(plan_path, "RESULT_IDENTITY_MISMATCH", f"retained {identity_field} differs from case ID", case_id)
        if (
            retained_result.get("pack_id") != manifest.get("pack_id")
            or retained_result.get("pack_revision") != manifest.get("pack_revision")
        ):
            result.add(plan_path, "RESULT_IDENTITY_MISMATCH", "retained result pack identity/revision is stale", case_id)
        if retained_result.get("reference_baseline_id") != manifest.get("reference_baseline_id"):
            result.add(
                plan_path,
                f"{plan_name.upper()}_REFERENCE_STALE",
                "retained result uses a different reference baseline",
                case_id,
            )
        expected_case_sha256 = case_contract_sha256(case)
        if plan_name in {"capture", "parity", "assurance"} and retained_result.get("case_sha256") != expected_case_sha256:
            result.add(
                plan_path,
                f"{plan_name.upper()}_CONTRACT_STALE",
                "retained result does not match the current case contract",
                case_id,
            )
        repository_state = manifest.get("repository_state", {})
        binds_clone = (
            plan_name in {"parity", "assurance"}
            or (plan_name == "capture" and case.get("side") == "clone")
        )
        if binds_clone and (
            "clone_revision" not in retained_result
            or "clone_diff_sha256" not in retained_result
            or retained_result.get("clone_revision") != repository_state.get("revision")
            or retained_result.get("clone_diff_sha256") != repository_state.get("diff_sha256")
        ):
            result.add(
                plan_path,
                f"{plan_name.upper()}_CLONE_STALE",
                "retained result uses a different clone repository revision or diff",
                case_id,
            )
        if plan_name == "capture" and case.get("side") == "reference" and (
            "clone_revision" not in retained_result
            or "clone_diff_sha256" not in retained_result
            or retained_result.get("clone_revision") is not None
            or retained_result.get("clone_diff_sha256") is not None
        ):
            result.add(
                plan_path,
                "CAPTURE_RESULT_INVALID",
                "reference capture must record null clone_revision and clone_diff_sha256",
                case_id,
            )
        if plan_name == "assurance" and retained_result.get("kind") != case.get("kind"):
            result.add(plan_path, "RESULT_IDENTITY_MISMATCH", "retained assurance kind differs from its case", case_id)
        nested_artifacts = retained_result.get("artifacts", [])
        if not isinstance(nested_artifacts, list):
            result.add(plan_path, "RESULT_INVALID", "retained result artifacts must be an array", case_id)
            continue
        for nested in nested_artifacts:
            _validate_result_artifact(pack, result, str(artifact.get("path")), nested)


def _validate_plan_case_index(
    result: ValidationResult,
    plan_name: str,
    plan_path: str,
    plan: dict[str, Any],
    records: dict[str, dict[str, Any]],
    capture_plan: dict[str, Any],
) -> None:
    expected_kind = {"capture": "CAP", "parity": "PAR", "assurance": "ASSURE"}[plan_name]
    cases = plan.get("cases")
    if not isinstance(cases, list):
        return
    case_ids = [case.get("id") for case in cases if isinstance(case, dict) and isinstance(case.get("id"), str)]
    duplicates = sorted({case_id for case_id in case_ids if case_ids.count(case_id) > 1})
    for case_id in duplicates:
        result.add(plan_path, "ID_DUPLICATE", f"duplicate {plan_name} case ID: {case_id}", str(case_id))
    capture_cases = {
        case.get("id"): case
        for case in capture_plan.get("cases", [])
        if isinstance(case, dict) and isinstance(case.get("id"), str)
    }

    def link_ids(links: dict[str, Any], relation: str) -> list[str]:
        values = links.get(relation, [])
        if not isinstance(values, list) or any(not isinstance(value, str) for value in values):
            return []
        return sorted(values)

    def rule_authority_ids(rules: Any) -> list[str]:
        if not isinstance(rules, list):
            return []
        return sorted(
            {
                str(authority_id)
                for rule in rules
                if isinstance(rule, dict) and isinstance(rule.get("authority_ids"), list)
                for authority_id in rule["authority_ids"]
                if isinstance(authority_id, str)
            }
        )

    for case in cases:
        if not isinstance(case, dict) or not isinstance(case.get("id"), str):
            continue
        case_id = str(case["id"])
        counterpart = records.get(case_id)
        if counterpart is None:
            result.add(
                "clone_index.json",
                "PLAN_CASE_INDEX_MISSING",
                f"{plan_name} case lacks a {expected_kind} index counterpart",
                case_id,
            )
            continue
        if counterpart.get("kind") != expected_kind:
            result.add(
                "clone_index.json",
                "PLAN_CASE_INDEX_KIND",
                f"{plan_name} case counterpart must have kind {expected_kind}",
                case_id,
            )
            continue
        attributes = counterpart.get("attributes") if isinstance(counterpart.get("attributes"), dict) else {}
        if attributes.get("case_sha256") != case_contract_sha256(case):
            result.add(
                "clone_index.json",
                "PLAN_CASE_INDEX_STALE",
                f"{plan_name} counterpart case_sha256 differs from the current plan case",
                case_id,
            )
        links = counterpart.get("links") if isinstance(counterpart.get("links"), dict) else {}
        if plan_name == "capture":
            environment_id = case.get("environment_id")
            environment = records.get(str(environment_id))
            if environment is None:
                result.add(plan_path, "REF_UNDEFINED", f"capture environment is undefined: {environment_id}", case_id)
            elif environment.get("kind") != "ENV":
                result.add(plan_path, "REF_WRONG_KIND", f"capture environment must be ENV: {environment_id}", case_id)
            authority_ids = case.get("authorization_decision_ids")
            authority_ids = authority_ids if isinstance(authority_ids, list) else []
            authority_ids = sorted(
                {str(authority_id) for authority_id in authority_ids if isinstance(authority_id, str)}
                | set(rule_authority_ids(case.get("redactions")))
            )
            for authority_id in authority_ids:
                authority = records.get(str(authority_id))
                if authority is None:
                    result.add(plan_path, "REF_UNDEFINED", f"capture authority is undefined: {authority_id}", case_id)
                elif authority.get("kind") not in {"DEC", "ADR", "GAPDEC"}:
                    result.add(plan_path, "REF_WRONG_KIND", f"capture authority must be DEC/ADR/GAPDEC: {authority_id}", case_id)
            if link_ids(links, "environments") != [environment_id]:
                result.add(
                    "clone_index.json",
                    "PLAN_CASE_INDEX_TRACE_INVALID",
                    "CAP counterpart environments must exactly match the capture case",
                    case_id,
                )
            if link_ids(links, "decisions") != sorted(authority_ids):
                result.add(
                    "clone_index.json",
                    "PLAN_CASE_INDEX_TRACE_INVALID",
                    "CAP counterpart decisions must exactly match the union of authorization_decision_ids and redaction authority_ids",
                    case_id,
                )
        elif plan_name == "parity":
            capture_ids = [case.get("reference_capture_id"), case.get("clone_capture_id")]
            for capture_id, expected_side in zip(capture_ids, ("reference", "clone"), strict=True):
                capture_case = capture_cases.get(capture_id)
                if capture_case is None:
                    result.add(plan_path, "REF_UNDEFINED", f"parity capture case is undefined: {capture_id}", case_id)
                elif capture_case.get("side") != expected_side:
                    result.add(plan_path, "RUN_ORACLE_INVALID", f"parity {expected_side} capture has the wrong side", case_id)
                capture_record = records.get(str(capture_id))
                if capture_record is None:
                    result.add(plan_path, "REF_UNDEFINED", f"parity CAP index record is undefined: {capture_id}", case_id)
                elif capture_record.get("kind") != "CAP":
                    result.add(plan_path, "REF_WRONG_KIND", f"parity capture index record must be CAP: {capture_id}", case_id)
            if link_ids(links, "captures") != sorted(capture_ids):
                result.add(
                    "clone_index.json",
                    "PLAN_CASE_INDEX_TRACE_INVALID",
                    "PAR counterpart captures must exactly match the parity case",
                    case_id,
                )
            normalization_authorities = rule_authority_ids(case.get("normalizations"))
            for authority_id in normalization_authorities:
                authority = records.get(authority_id)
                if authority is None:
                    result.add(plan_path, "REF_UNDEFINED", f"parity normalization authority is undefined: {authority_id}", case_id)
                elif authority.get("kind") not in {"DEC", "ADR", "GAPDEC"}:
                    result.add(plan_path, "REF_WRONG_KIND", f"parity normalization authority must be DEC/ADR/GAPDEC: {authority_id}", case_id)
            if link_ids(links, "decisions") != normalization_authorities:
                result.add(
                    "clone_index.json",
                    "PLAN_CASE_INDEX_TRACE_INVALID",
                    "PAR counterpart decisions must exactly match normalization authority_ids",
                    case_id,
                )


def validate_v2(pack: Path, profile: str, *, require_seal: bool = True) -> ValidationResult:
    result = ValidationResult()
    pack = pack.expanduser().resolve()
    if profile not in PROFILES:
        result.add("", "PROFILE_INVALID", f"unknown validation profile: {profile}")
        return result
    try:
        manifest = load_json(pack / "clone_pack.json")
    except ClonePackError as exc:
        result.add("clone_pack.json", exc.diagnostic, str(exc))
        return result
    transaction_root = pack / ".clonepack-transactions"
    if transaction_root.exists():
        result.add(
            ".clonepack-transactions",
            "TRANSACTION_PENDING",
            "a prepared transaction must be recovered by the next mutating command",
        )
    _add_schema_diagnostics(result, "clone_pack.json", manifest, "manifest")
    for message in [
        *exact_keys(manifest, MANIFEST_FIELDS, context="clone_pack.json"),
        *[
            f"clone_pack.json: missing required field {key}"
            for key in sorted(MANIFEST_REQUIRED_FIELDS - set(manifest))
        ],
    ]:
        result.add("clone_pack.json", "MANIFEST_INVALID", message)
    if manifest.get("schema_version") != V2_SCHEMA:
        result.add("clone_pack.json", "SCHEMA_UNSUPPORTED", f"schema_version must be {V2_SCHEMA}")
        return result
    if manifest.get("product_type") not in PRODUCT_TYPES:
        result.add("clone_pack.json", "PRODUCT_TYPE_INVALID", "unknown product_type")
    playbooks = manifest.get("playbooks")
    if not isinstance(playbooks, list) or not playbooks or any(item not in PLAYBOOKS for item in playbooks):
        result.add("clone_pack.json", "PLAYBOOK_INVALID", "playbooks must contain controlled values")
    elif manifest.get("product_type") == "hybrid" and len(set(playbooks)) < 2:
        result.add("clone_pack.json", "PLAYBOOK_INVALID", "hybrid requires at least two playbooks")
    elif manifest.get("product_type") != "hybrid" and manifest.get("product_type") not in playbooks:
        result.add("clone_pack.json", "PLAYBOOK_INVALID", "primary product_type must occur in playbooks")

    docs = manifest.get("documents")
    document_paths: set[str] = set()
    if not isinstance(docs, list):
        result.add("clone_pack.json", "MANIFEST_INVALID", "documents must be an array")
        docs = []
    for entry in docs:
        if not isinstance(entry, dict):
            result.add("clone_pack.json", "MANIFEST_INVALID", "document entry must be an object")
            continue
        path_value = entry.get("path")
        if not isinstance(path_value, str):
            result.add("clone_pack.json", "MANIFEST_INVALID", "document path must be a string")
            continue
        if path_value in document_paths:
            result.add("clone_pack.json", "ID_DUPLICATE", f"duplicate document path: {path_value}")
            continue
        document_paths.add(path_value)
        expected_schema = V2_DOCUMENTS.get(path_value)
        if expected_schema is None:
            result.add(path_value, "DOCUMENT_UNKNOWN", "document is not part of clone-pack/v2")
            continue
        if entry.get("schema_version") != expected_schema:
            result.add(path_value, "DOCUMENT_SCHEMA", f"schema_version must be {expected_schema}")
        try:
            path = resolve_inside(pack, path_value, must_exist=True)
            text = path.read_text(encoding="utf-8")
        except (ClonePackError, OSError) as exc:
            code = exc.diagnostic if isinstance(exc, ClonePackError) else "DOCUMENT_UNREADABLE"
            result.add(path_value, code, str(exc))
            continue
        try:
            metadata = parse_frontmatter(text)
        except ClonePackError as exc:
            result.add(path_value, exc.diagnostic, str(exc))
            continue
        if metadata.get("schema_version") != expected_schema:
            result.add(path_value, "DOCUMENT_SCHEMA", f"frontmatter schema_version must be {expected_schema}")
        if metadata.get("pack_id") != manifest.get("pack_id"):
            result.add(path_value, "PACK_ID_MISMATCH", "frontmatter pack_id differs from manifest")
        if metadata.get("pack_revision") != str(manifest.get("pack_revision")):
            result.add(path_value, "PACK_REVISION_MISMATCH", "frontmatter pack_revision differs from manifest")
        if metadata.get("document_state") != entry.get("state"):
            result.add(path_value, "DOCUMENT_STATE_MISMATCH", "frontmatter document_state differs from manifest")
        expected_hash = entry.get("sha256")
        if expected_hash is not None and sha256_file(path) != expected_hash:
            result.add(path_value, "HASH_DOCUMENT_MISMATCH", "document hash differs from manifest")
        if path_value in PROFILE_DOCUMENTS.get(profile, set()) and re.search(r"\[\[(?:REQUIRED|MIGRATION_REQUIRED):[^\]]*\]\]", text):
            result.add(path_value, "MARKER_UNRESOLVED", "unresolved required marker")
        if path_value in PROFILE_DOCUMENTS.get(profile, set()):
            prose = _lintable_prose(text)
            for label, pattern in AMBIGUOUS_PROSE:
                match = pattern.search(prose)
                if match:
                    result.add(
                        path_value,
                        "AMBIGUOUS_LANGUAGE",
                        f"{label} is forbidden in a ready document: {match.group(0)!r}",
                    )
    missing_docs = sorted(set(V2_DOCUMENTS) - document_paths)
    for path_value in missing_docs:
        result.add(path_value, "DOCUMENT_MISSING", "required v2 document is absent from manifest")

    workstream = manifest.get("workstream")
    workstream_kind = workstream.get("kind") if isinstance(workstream, dict) else "clone-mvp"
    is_enhancement = workstream_kind == "brownfield-enhancement"
    if workstream_kind not in {"clone-mvp", "brownfield-enhancement"}:
        result.add("clone_pack.json", "WORKSTREAM_INVALID", "workstream.kind is not controlled")
    if profile in {"repository-adopted", "enhancement-ready", "implementation", "verified-enhancement"} and not is_enhancement:
        result.add("clone_pack.json", "PROFILE_WORKSTREAM_MISMATCH", "enhancement profile requires a brownfield-enhancement workstream")
    if is_enhancement and profile not in {
        "scaffold",
        "repository-adopted",
        "enhancement-ready",
        "implementation",
        "verified-enhancement",
    }:
        result.add("clone_pack.json", "PROFILE_WORKSTREAM_MISMATCH", "clone-MVP and gap profiles do not apply to a brownfield-enhancement workstream")

    required_plans = {**PLAN_FILES, **ENHANCEMENT_PLAN_FILES} if is_enhancement else dict(PLAN_FILES)
    plans = manifest.get("plans")
    expected_plans = dict(required_plans)
    if isinstance(plans, dict) and "full_stack_qa" in plans:
        expected_plans.update(OPTIONAL_PLAN_FILES)
    if not isinstance(plans, dict) or plans != expected_plans:
        result.add(
            "clone_pack.json",
            "PLAN_MANIFEST_INVALID",
            "plans must exactly match the selected v2 workstream plan manifest",
        )
        plans = expected_plans
    plan_instances: dict[str, dict[str, Any]] = {}
    for plan_name, plan_path in plans.items():
        if not isinstance(plan_path, str):
            result.add("clone_pack.json", "PLAN_MANIFEST_INVALID", f"plan path must be a string: {plan_name}")
            continue
        try:
            plan_instance = load_json(resolve_inside(pack, plan_path, must_exist=True))
        except ClonePackError as exc:
            result.add(plan_path, exc.diagnostic, str(exc))
            continue
        plan_instances[plan_name] = plan_instance
        if plan_instance.get("pack_id") != manifest.get("pack_id"):
            result.add(plan_path, "PACK_ID_MISMATCH", "plan pack_id differs from manifest")
        if plan_instance.get("pack_revision") != manifest.get("pack_revision"):
            result.add(plan_path, "PACK_REVISION_MISMATCH", "plan pack_revision differs from manifest")

    plan_schema_thresholds = {
        "capture": "baseline-ready",
        "parity": "spec-ready",
        "scaffold": "build-ready",
        "assurance": "build-ready",
        "full_stack_qa": "build-ready",
    }
    for plan_name, threshold in plan_schema_thresholds.items():
        if plan_name not in plans:
            continue
        requires_plan_schema = (
            profile_requires(
                profile,
                "enhancement-ready" if plan_name == "full_stack_qa" else "repository-adopted",
            )
            if is_enhancement
            else profile_requires(profile, threshold)
        )
        if requires_plan_schema:
            plan_path = plans.get(plan_name)
            plan_instance = plan_instances.get(plan_name)
            if isinstance(plan_path, str) and plan_instance is not None:
                _add_schema_diagnostics(result, plan_path, plan_instance, plan_name)
    if is_enhancement:
        enhancement_thresholds = {
            "repository_inventory": "repository-adopted",
            "enhancement": "enhancement-ready",
        }
        for plan_name, threshold in enhancement_thresholds.items():
            if profile_requires(profile, threshold):
                plan_path = plans.get(plan_name)
                plan_instance = plan_instances.get(plan_name)
                if isinstance(plan_path, str) and plan_instance is not None:
                    _add_schema_diagnostics(result, plan_path, plan_instance, plan_name)

    try:
        index_path = resolve_inside(pack, str(manifest.get("index_path")), must_exist=True)
        index = load_json(index_path)
    except ClonePackError as exc:
        result.add(str(manifest.get("index_path", "clone_index.json")), exc.diagnostic, str(exc))
        return result
    _add_schema_diagnostics(result, "clone_index.json", index, "index")
    for message in [
        *exact_keys(index, INDEX_FIELDS, context="clone_index.json"),
        *[f"clone_index.json: missing required field {key}" for key in sorted(INDEX_FIELDS - set(index))],
    ]:
        result.add("clone_index.json", "INDEX_INVALID", message)
    if index.get("schema_version") != "clone-index/v2":
        result.add("clone_index.json", "INDEX_SCHEMA", "schema_version must be clone-index/v2")
    if index.get("pack_id") != manifest.get("pack_id") or index.get("pack_revision") != manifest.get("pack_revision"):
        result.add("clone_index.json", "PACK_ID_MISMATCH", "index identity/revision differs from manifest")
    records_raw = index.get("records")
    if not isinstance(records_raw, list):
        result.add("clone_index.json", "INDEX_INVALID", "records must be an array")
        records_raw = []
    records: dict[str, dict[str, Any]] = {}
    for position, record in enumerate(records_raw):
        context = f"clone_index.json#/records/{position}"
        if not isinstance(record, dict):
            result.add("clone_index.json", "RECORD_INVALID", f"record {position} must be an object")
            continue
        for message in [
            *exact_keys(record, RECORD_FIELDS, context=context),
            *[f"{context}: missing required field {key}" for key in sorted(RECORD_FIELDS - set(record))],
        ]:
            result.add("clone_index.json", "RECORD_INVALID", message)
        identifier = record.get("id")
        kind = record.get("kind")
        if not isinstance(identifier, str) or kind not in RECORD_KINDS or _record_kind_for_id(identifier) != kind:
            result.add("clone_index.json", "ID_KIND_INVALID", f"record {position} has invalid id/kind")
            continue
        if identifier in records:
            result.add("clone_index.json", "ID_DUPLICATE", f"duplicate record ID: {identifier}", identifier)
            continue
        records[identifier] = record
        locator = record.get("locator")
        if not isinstance(locator, dict) or set(locator) != {"path", "anchor", "sha256"}:
            result.add("clone_index.json", "LOCATOR_INVALID", "locator requires path, anchor, sha256", identifier)
        else:
            try:
                location = resolve_inside(pack, str(locator.get("path")), must_exist=True)
                actual, error = _hash_anchor(location, str(locator.get("anchor")))
            except ClonePackError as exc:
                result.add("clone_index.json", exc.diagnostic, str(exc), identifier)
            else:
                if error:
                    result.add("clone_index.json", "LOCATOR_INVALID", error, identifier)
                elif locator.get("sha256") not in {None, actual}:
                    result.add("clone_index.json", "HASH_ANCHOR_MISMATCH", "anchored definition hash differs", identifier)
                elif profile != "scaffold" and locator.get("sha256") is None:
                    result.add("clone_index.json", "HASH_ANCHOR_MISSING", "non-scaffold record requires definition hash", identifier)

    for identifier, record in records.items():
        links = record.get("links")
        if not isinstance(links, dict):
            result.add("clone_index.json", "LINKS_INVALID", "links must be an object", identifier)
            continue
        for relation, targets in links.items():
            if relation not in LINK_KINDS or not isinstance(targets, list) or any(not isinstance(item, str) for item in targets):
                result.add("clone_index.json", "LINKS_INVALID", f"invalid relation: {relation}", identifier)
                continue
            for target in targets:
                target_record = records.get(target)
                if target_record is None:
                    result.add("clone_index.json", "REF_UNDEFINED", f"undefined reference: {target}", identifier)
                elif target_record.get("kind") not in LINK_KINDS[relation]:
                    result.add("clone_index.json", "REF_WRONG_KIND", f"{relation} cannot target {target_record.get('kind')}", identifier)

    case_index_thresholds = {
        "capture": "baseline-ready",
        "parity": "spec-ready",
        "assurance": "build-ready",
    }
    capture_plan = plan_instances.get("capture", {})
    for plan_name, threshold in case_index_thresholds.items():
        plan_path = plans.get(plan_name)
        plan = plan_instances.get(plan_name)
        if (
            profile_requires(profile, threshold)
            and isinstance(plan_path, str)
            and isinstance(plan, dict)
        ):
            _validate_plan_case_index(result, plan_name, plan_path, plan, records, capture_plan)

    if profile_requires(profile, "spec-ready"):
        # Draft documents outside the requested readiness profile still contain
        # illustrative IDs. They enter the graph when that document becomes
        # governed by the selected profile, not while it remains an unresolved
        # scaffold.
        for path_value in sorted(PROFILE_DOCUMENTS.get(profile, set())):
            try:
                text = resolve_inside(pack, path_value, must_exist=True).read_text(encoding="utf-8")
            except (ClonePackError, OSError):
                continue
            cited = set(re.findall(r"\b(?:REQ-GAP-\d{3,}-\d{2,}|AC-GAP-\d{3,}-\d{2,}|TEST-GAP-\d{3,}-\d{2,}|STEP-GAP-\d{3,}-\d{2,}|CHANGE-GAP-\d{3,}-\d{2,}|[A-Z]+(?:-[A-Z]+)*-\d{3,})\b", text))
            for cited_id in sorted(cited):
                if _record_kind_for_id(cited_id) and cited_id not in records:
                    result.add(path_value, "REF_UNDEFINED", f"Markdown cites undefined ID: {cited_id}", cited_id)

    if profile_requires(profile, "spec-ready"):
        if not records:
            result.add("clone_index.json", "INDEX_EMPTY", "spec-ready pack requires records")
        for identifier, record in records.items():
            kind = record.get("kind")
            links = record.get("links", {})
            attributes = record.get("attributes", {}) if isinstance(record.get("attributes"), dict) else {}
            if kind in {"SURF", "WF"}:
                disposition = attributes.get("disposition")
                if disposition not in CAPABILITY_DISPOSITIONS:
                    result.add(
                        "clone_index.json",
                        "CAPABILITY_DISPOSITION_INVALID",
                        "SURF/WF attributes.disposition must use the controlled capability vocabulary",
                        identifier,
                    )
                else:
                    disposition_relations = {
                        name for name in ("requirements", "gaps", "exclusions") if links.get(name)
                    }
                    expected_relation = (
                        "requirements"
                        if disposition == "EQUIVALENT"
                        else "exclusions"
                        if disposition == "EXCLUDED"
                        else "gaps"
                    )
                    if disposition_relations != {expected_relation}:
                        result.add(
                            "clone_index.json",
                            "CAPABILITY_DISPOSITION_TRACE_INVALID",
                            f"{disposition} requires only a non-empty {expected_relation} disposition link",
                            identifier,
                        )
                    if disposition == "EQUIVALENT":
                        proof_ids = [*links.get("parity", []), *links.get("runs", [])]
                        if not proof_ids or not any(records.get(proof_id, {}).get("state") == "PASS" for proof_id in proof_ids):
                            result.add(
                                "clone_index.json",
                                "CAPABILITY_PROOF_MISSING",
                                "EQUIVALENT requires a linked PASS PAR or RUN record",
                                identifier,
                            )
                    elif disposition in {"MISSING", "PARTIAL", "DIVERGENT"}:
                        if not any(links.get(name) for name in ("evidence", "parity", "runs")):
                            result.add(
                                "clone_index.json",
                                "CAPABILITY_PROOF_MISSING",
                                f"{disposition} requires linked evidence, parity, or run evidence",
                                identifier,
                            )
                    elif disposition == "EXCLUDED" and not links.get("decisions"):
                        result.add(
                            "clone_index.json",
                            "CAPABILITY_AUTHORITY_MISSING",
                            "EXCLUDED requires an authority decision link",
                            identifier,
                        )
                    elif disposition == "UNVERIFIED":
                        invalid_gaps = [
                            gap_id
                            for gap_id in links.get("gaps", [])
                            if records.get(gap_id, {}).get("attributes", {}).get("class") != "EVIDENCE_GAP"
                            or records.get(gap_id, {}).get("attributes", {}).get("status") != "BLOCKED"
                        ]
                        if invalid_gaps:
                            result.add(
                                "clone_index.json",
                                "CAPABILITY_EVIDENCE_GAP_INVALID",
                                "UNVERIFIED requires only BLOCKED EVIDENCE_GAP links: " + ", ".join(sorted(invalid_gaps)),
                                identifier,
                            )
            if kind == "REQ":
                if not links.get("evidence") and not links.get("decisions"):
                    result.add("clone_index.json", "REQ_SOURCE_MISSING", "requirement lacks evidence or decision", identifier)
                if not links.get("acceptance"):
                    result.add("clone_index.json", "AC_UNCOVERED", "requirement lacks acceptance criteria", identifier)
                if not links.get("tests"):
                    result.add("clone_index.json", "TEST_UNCOVERED", "requirement lacks tests", identifier)
                if not attributes.get("implementation_locator"):
                    result.add("clone_index.json", "IMPLEMENTATION_LOCATOR_MISSING", "requirement lacks implementation locator", identifier)
            if kind == "AC" and (not links.get("requirements") or not links.get("tests")):
                result.add("clone_index.json", "AC_TRACE_INCOMPLETE", "acceptance requires requirements and tests", identifier)
            if kind == "TEST":
                if not links.get("requirements") or not links.get("acceptance"):
                    result.add("clone_index.json", "TEST_TRACE_INCOMPLETE", "test requires requirements and acceptance", identifier)
                if not links.get("oracles"):
                    result.add("clone_index.json", "RUN_ORACLE_INVALID", "test requires an independent oracle", identifier)
                if not links.get("gates") and not attributes.get("manual_procedure"):
                    result.add("clone_index.json", "TEST_GATE_MISSING", "test requires a gate or manual procedure", identifier)
            if kind == "E" and not attributes.get("investigation_only") and not links.get("requirements"):
                result.add("clone_index.json", "EVIDENCE_ORPHAN", "evidence requires a requirement link or investigation_only", identifier)

        for source_kinds, forward_relation, target_kinds, reciprocal_relation in RECIPROCAL_TRACE_RULES:
            for identifier, record in records.items():
                if record.get("kind") not in source_kinds:
                    continue
                links = record.get("links", {}) if isinstance(record.get("links"), dict) else {}
                for target_id in links.get(forward_relation, []):
                    target = records.get(target_id, {})
                    if target.get("kind") not in target_kinds:
                        continue
                    target_links = target.get("links", {}) if isinstance(target.get("links"), dict) else {}
                    if identifier not in target_links.get(reciprocal_relation, []):
                        result.add(
                            "clone_index.json",
                            "TRACE_NOT_BIDIRECTIONAL",
                            f"{target_id}.{reciprocal_relation} does not link back to {identifier}",
                            identifier,
                        )
            for target_id, target in records.items():
                if target.get("kind") not in target_kinds:
                    continue
                target_links = target.get("links", {}) if isinstance(target.get("links"), dict) else {}
                for source_id in target_links.get(reciprocal_relation, []):
                    source = records.get(source_id, {})
                    if source.get("kind") not in source_kinds:
                        continue
                    source_links = source.get("links", {}) if isinstance(source.get("links"), dict) else {}
                    if target_id not in source_links.get(forward_relation, []):
                        result.add(
                            "clone_index.json",
                            "TRACE_NOT_BIDIRECTIONAL",
                            f"{source_id}.{forward_relation} does not link back to {target_id}",
                            target_id,
                        )

    if profile_requires(profile, "baseline-ready"):
        if manifest.get("reference_baseline_id") in {None, "", "UNRESOLVED"}:
            result.add("clone_pack.json", "BASELINE_UNRESOLVED", "reference_baseline_id must be frozen")
        if not any(record.get("kind") == "ENV" for record in records.values()):
            result.add("clone_index.json", "ENVIRONMENT_MISSING", "baseline-ready pack requires an ENV record")

    if profile_requires(profile, "build-ready"):
        repository_state = manifest.get("repository_state")
        if not isinstance(repository_state, dict) or repository_state.get("revision") in {None, "", "UNRESOLVED"}:
            result.add("clone_pack.json", "REPOSITORY_STATE_UNRESOLVED", "build-ready pack requires a pinned repository revision")
        elif repository_state.get("kind") == "working-tree" and not re.fullmatch(
            r"[0-9a-f]{64}", str(repository_state.get("diff_sha256", ""))
        ):
            result.add(
                "clone_pack.json",
                "REPOSITORY_STATE_UNRESOLVED",
                "working-tree state requires a lowercase SHA-256 diff or full-tree inventory hash",
            )
        try:
            assurance = load_json(resolve_inside(pack, plans["assurance"], must_exist=True))
        except ClonePackError:
            assurance = {}
        risk_profile = assurance.get("risk_profile")
        risk_requirements = {
            "local-evaluation": {"threat-model", "provenance"},
            "internal": {"threat-model", "provenance", "sast", "secret", "dependency", "license", "sbom"},
            "customer": {"threat-model", "provenance", "sast", "secret", "dependency", "license", "sbom", "dast", "slsa", "independent-review", "rollback-recovery"},
            "public": {"threat-model", "provenance", "sast", "secret", "dependency", "license", "sbom", "dast", "slsa", "independent-review", "rollback-recovery"},
            "production": {"threat-model", "provenance", "sast", "secret", "dependency", "license", "sbom", "dast", "slsa", "independent-review", "rollback-recovery"},
        }
        if risk_profile not in risk_requirements:
            result.add(plans["assurance"], "ASSURANCE_PROFILE_INVALID", "risk_profile is not controlled")
        else:
            actual_kinds = {
                case.get("kind")
                for case in assurance.get("cases", [])
                if isinstance(case, dict) and case.get("required", True)
            }
            missing_kinds = sorted(risk_requirements[risk_profile] - actual_kinds)
            if missing_kinds:
                result.add(plans["assurance"], "ASSURANCE_INCOMPLETE", "required assurance kinds missing: " + ", ".join(missing_kinds))
        provenance_records = [record for record in records.values() if record.get("kind") == "PROV"]
        if not provenance_records:
            result.add("clone_index.json", "PROVENANCE_MISSING", "build-ready pack requires provenance records")
        for record in provenance_records:
            identifier = str(record.get("id"))
            attributes = record.get("attributes", {}) if isinstance(record.get("attributes"), dict) else {}
            required_provenance = {"origin", "version", "sha256", "license", "rights_basis", "disposition", "separation_profile"}
            missing_provenance = sorted(key for key in required_provenance if attributes.get(key) in {None, ""})
            if missing_provenance:
                result.add("clone_index.json", "PROVENANCE_INCOMPLETE", "missing fields: " + ", ".join(missing_provenance), identifier)
            separation = attributes.get("separation_profile")
            if separation not in {"non-separated", "strict-separated"}:
                result.add("clone_index.json", "CLEAN_ROOM_PROFILE_INVALID", "separation_profile is not controlled", identifier)
            elif separation == "strict-separated":
                observer = attributes.get("observer_id")
                implementer = attributes.get("implementer_id")
                if not observer or not implementer or observer == implementer or attributes.get("contamination_status") not in {"none", "resolved"}:
                    result.add("clone_index.json", "CLEAN_ROOM_EVIDENCE_MISSING", "strict separation requires distinct identities and resolved contamination status", identifier)

    runs = _load_runs(pack, result, manifest, records)
    full_stack_qa = plan_instances.get("full_stack_qa")
    if isinstance(full_stack_qa, dict):
        qa_ready = (
            profile_requires(profile, "enhancement-ready")
            if is_enhancement
            else profile_requires(profile, "build-ready")
        )
        qa_verified = (
            profile == "verified-enhancement"
            if is_enhancement
            else profile in {"verified-mvp", "gap-closure", "closed"}
        )
        repository_root = Path(str(manifest.get("repository_root", "")))
        for issue in validate_full_stack_qa_plan(
            pack=pack,
            repository=repository_root,
            plan=full_stack_qa,
            records=records,
            runs=runs,
            require_ready=qa_ready,
            require_verified=qa_verified,
        ):
            if issue.hold:
                result.hold(issue.path, issue.code, issue.message, issue.record_id)
            else:
                result.add(issue.path, issue.code, issue.message, issue.record_id)
    events = _load_gap_events(pack, result, manifest, records)
    _validate_existing_seal_schema(pack, manifest, result)
    gap_records = {identifier: record for identifier, record in records.items() if record.get("kind") == "GAP"}
    for gap_id, record in gap_records.items():
        attributes = record.get("attributes", {}) if isinstance(record.get("attributes"), dict) else {}
        status = attributes.get("status")
        if status not in GAP_STATUSES:
            result.add("clone_index.json", "GAP_STATUS_INVALID", "gap has invalid status", gap_id)
            continue
        history = events.get(gap_id, [])
        if status != "OPEN" and not history:
            result.add("history/gap_events.jsonl", "GAP_HISTORY_MISSING", "noninitial gap status requires complete history", gap_id)
        if history and history[-1].get("to") != status:
            result.add("history/gap_events.jsonl", "GAP_STATUS_DIVERGENCE", "event state differs from index", gap_id)
        dependencies = record.get("links", {}).get("dependencies", [])
        if status == "IN_PROGRESS":
            for dependency in dependencies:
                dependency_record = gap_records.get(dependency, {})
                dependency_status = dependency_record.get("attributes", {}).get("status") if isinstance(dependency_record.get("attributes"), dict) else None
                if dependency_status != "VERIFIED":
                    result.add("clone_index.json", "GAP_DEP_UNSATISFIED", f"dependency is not VERIFIED: {dependency}", gap_id)
        if status in {"IMPLEMENTED", "VERIFIED"} and not record.get("links", {}).get("runs"):
            result.add("clone_index.json", "GAP_EVIDENCE_MISSING", f"{status} gap lacks run evidence", gap_id)

    if profile in {"gap-plan", "gap-closure", "closed"}:
        try:
            gaps_text = resolve_inside(pack, "gaps_analysis.md", must_exist=True).read_text(encoding="utf-8")
        except (ClonePackError, OSError) as exc:
            code = exc.diagnostic if isinstance(exc, ClonePackError) else "DOCUMENT_UNREADABLE"
            result.add("gaps_analysis.md", code, str(exc))
        else:
            flag_match = re.search(
                r"^- `?NO-OPEN-GAPS`?:\s*(true|false)\s*$",
                gaps_text,
                flags=re.MULTILINE,
            )
            expected_no_open = all(
                record.get("attributes", {}).get("status") in TERMINAL_GAP_STATUSES
                for record in gap_records.values()
            )
            if flag_match is None:
                result.add("gaps_analysis.md", "GAP_FLAG_MISSING", "NO-OPEN-GAPS derived flag is missing")
            elif (flag_match.group(1) == "true") != expected_no_open:
                result.add(
                    "gaps_analysis.md",
                    "GAP_FLAG_DIVERGENCE",
                    f"NO-OPEN-GAPS must be {'true' if expected_no_open else 'false'} for current lifecycle state",
                )

    if profile in {"verified-mvp", "gap-closure", "closed"}:
        successful_coverage: set[str] = set()
        for run in runs.values():
            if run.get("result") == "PASS" and run.get("oracle_ids"):
                successful_coverage.update(str(item) for item in run.get("covered_ids", []))
        mvp_requirements = {
            identifier: record
            for identifier, record in records.items()
            if record.get("kind") == "REQ"
            and isinstance(record.get("attributes"), dict)
            and record["attributes"].get("mvp") is True
        }
        if not mvp_requirements:
            result.hold(
                "clone_index.json",
                "MVP_EMPTY",
                "verified-mvp requires at least one attributes.mvp=true REQ record",
            )
        for identifier, record in records.items():
            attributes = record.get("attributes", {}) if isinstance(record.get("attributes"), dict) else {}
            if record.get("kind") != "REQ" or not attributes.get("mvp", False):
                continue
            acceptance = set(record.get("links", {}).get("acceptance", []))
            missing = sorted(acceptance - successful_coverage)
            if missing:
                result.hold("clone_index.json", "AC_UNCOVERED", f"current passing runs do not cover: {', '.join(missing)}", identifier)
        for plan_name, plan_path in plans.items():
            if plan_name in {"capture", "parity", "assurance"}:
                _validate_plan_results(pack, result, plan_name, plan_path, manifest)
        capture_cases = plan_instances.get("capture", {}).get("cases", [])
        capture_cases = capture_cases if isinstance(capture_cases, list) else []
        passing_reference_captures = {
            str(case.get("id"))
            for case in capture_cases
            if isinstance(case, dict)
            and case.get("required") is True
            and case.get("side") == "reference"
            and isinstance(case.get("result"), dict)
            and case["result"].get("status") == "PASS"
        }
        passing_clone_captures = {
            str(case.get("id"))
            for case in capture_cases
            if isinstance(case, dict)
            and case.get("required") is True
            and case.get("side") == "clone"
            and isinstance(case.get("result"), dict)
            and case["result"].get("status") == "PASS"
        }
        if not passing_reference_captures:
            result.hold(
                plans["capture"],
                "CAPTURE_BLOCKED",
                "verified-mvp requires a current PASS required reference capture",
            )
        if not passing_clone_captures:
            result.hold(
                plans["capture"],
                "CAPTURE_BLOCKED",
                "verified-mvp requires a current PASS required clone capture",
            )
        parity_cases = plan_instances.get("parity", {}).get("cases", [])
        parity_cases = parity_cases if isinstance(parity_cases, list) else []
        passing_paired_parity = [
            case
            for case in parity_cases
            if isinstance(case, dict)
            and case.get("required") is True
            and isinstance(case.get("result"), dict)
            and case["result"].get("status") == "PASS"
            and case.get("reference_capture_id") in passing_reference_captures
            and case.get("clone_capture_id") in passing_clone_captures
        ]
        if not passing_paired_parity:
            result.hold(
                plans["parity"],
                "PARITY_BLOCKED",
                "verified-mvp requires a current PASS required parity case over required PASS reference and clone captures",
            )
        complete_chain = False
        for requirement_id, requirement in mvp_requirements.items():
            requirement_links = requirement.get("links", {}) if isinstance(requirement.get("links"), dict) else {}
            acceptance_ids = set(requirement_links.get("acceptance", []))
            for test_id in requirement_links.get("tests", []):
                test = records.get(test_id, {})
                test_links = test.get("links", {}) if isinstance(test.get("links"), dict) else {}
                shared_acceptance = acceptance_ids.intersection(test_links.get("acceptance", []))
                if not shared_acceptance:
                    continue
                gate_ids = set(test_links.get("gates", []))
                for run_id, run in runs.items():
                    covered_ids = set(run.get("covered_ids", [])) if isinstance(run.get("covered_ids"), list) else set()
                    if (
                        run.get("result") == "PASS"
                        and run.get("oracle_ids")
                        and run.get("gate_id") in gate_ids
                        and {requirement_id, test_id}.issubset(covered_ids)
                        and shared_acceptance.intersection(covered_ids)
                        and run_id in test_links.get("runs", [])
                        and run_id in records.get(str(run.get("gate_id")), {}).get("links", {}).get("runs", [])
                    ):
                        complete_chain = True
                        break
                if complete_chain:
                    break
            if complete_chain:
                break
        if not complete_chain:
            result.hold(
                "clone_index.json",
                "MVP_PROOF_CHAIN_MISSING",
                "verified-mvp requires a current PASS REQ -> AC -> TEST -> GATE -> RUN chain",
            )
        nonverified_blockers = [
            gap_id
            for gap_id, record in gap_records.items()
            if record.get("attributes", {}).get("class") == "MVP_BLOCKER"
            and record.get("attributes", {}).get("status") != "VERIFIED"
        ]
        if nonverified_blockers:
            result.hold("clone_index.json", "MVP_BLOCKED", "non-verified MVP blockers: " + ", ".join(sorted(nonverified_blockers)))

    if profile in {"gap-plan", "gap-closure"}:
        ready = {
            gap_id
            for gap_id, record in gap_records.items()
            if record.get("attributes", {}).get("readiness") == "READY"
            and record.get("attributes", {}).get("status") not in TERMINAL_GAP_STATUSES
        }
        selected_records = [
            (gap_id, record)
            for gap_id, record in gap_records.items()
            if record.get("attributes", {}).get("selected", False)
        ]
        selected_records.sort(key=lambda item: item[1].get("attributes", {}).get("plan_order", 10**9))
        selected = [gap_id for gap_id, _ in selected_records]
        all_actionable = any(record.get("attributes", {}).get("plan_scope") == "all_actionable" for _, record in selected_records)
        for gap_id, record in sorted(gap_records.items()):
            attributes = record.get("attributes", {}) if isinstance(record.get("attributes"), dict) else {}
            if profile == "gap-plan" and attributes.get("status") in TERMINAL_GAP_STATUSES:
                continue
            for problem in validate_gap_plan_record(pack, manifest, records, gap_id, record):
                result.add("clone_index.json", problem.code, problem.message, gap_id)
        if ready and not selected:
            result.add("clone_index.json", "PLAN_INCOMPLETE", "gap-plan requires selected READY gaps")
        if all_actionable and set(selected) != ready:
            result.add("clone_index.json", "PLAN_INCOMPLETE", "all_actionable plan must contain every READY nonterminal gap")
        for index_position, gap_id in enumerate(selected):
            dependencies = gap_records.get(gap_id, {}).get("links", {}).get("dependencies", [])
            earlier = set(selected[:index_position])
            for dependency in dependencies:
                dep_status = gap_records.get(dependency, {}).get("attributes", {}).get("status")
                if dependency not in earlier and dep_status != "VERIFIED":
                    result.add("clone_index.json", "PLAN_NOT_TOPOLOGICAL", f"{gap_id} precedes dependency {dependency}", gap_id)
        if profile == "gap-closure":
            nonterminal_selected = sorted(
                gap_id
                for gap_id, record in selected_records
                if record.get("attributes", {}).get("status") not in TERMINAL_GAP_STATUSES
            )
            if nonterminal_selected:
                result.hold(
                    "clone_index.json",
                    "GAP_CLOSURE_INCOMPLETE",
                    "selected gaps are nonterminal: " + ", ".join(nonterminal_selected),
                )

    if profile == "closed":
        for gap_id, record in sorted(gap_records.items()):
            for problem in validate_gap_plan_record(pack, manifest, records, gap_id, record):
                result.add("clone_index.json", problem.code, problem.message, gap_id)
        nonterminal = sorted(
            gap_id
            for gap_id, record in gap_records.items()
            if record.get("attributes", {}).get("status") not in TERMINAL_GAP_STATUSES
        )
        if nonterminal:
            result.hold("clone_index.json", "GAPS_OPEN", "nonterminal gaps remain: " + ", ".join(nonterminal))

    if is_enhancement and profile in {
        "repository-adopted",
        "enhancement-ready",
        "implementation",
        "verified-enhancement",
    }:
        enhancement_plan = plan_instances.get("enhancement")
        if isinstance(enhancement_plan, dict):
            from .enhancement import enhancement_profile_diagnostics

            for problem in enhancement_profile_diagnostics(
                pack,
                manifest,
                enhancement_plan,
                index,
                profile,
                require_seal=require_seal,
            ):
                add = result.hold if problem.get("severity") == "HOLD" else result.add
                add(
                    problem["path"],
                    problem["code"],
                    problem["message"],
                    problem.get("record_id", ""),
                )

    if profile in {"verified-mvp", "gap-closure", "closed", "verified-enhancement"} and require_seal:
        _validate_seal(pack, manifest, profile, result)
    return result


def _seal_file_paths(
    pack: Path,
    manifest: dict[str, Any],
    *,
    extra_paths: set[str] | None = None,
) -> list[str]:
    plan_paths = {
        str(value)
        for value in manifest["plans"].values()
        if isinstance(value, str) and value
    }
    included = {"clone_pack.json", str(manifest["index_path"]), *plan_paths}
    included.update(str(entry["path"]) for entry in manifest["documents"])
    included.add(str(manifest["history_path"]))
    for root_name in (str(manifest["runs_path"]), "evidence", "history"):
        root = resolve_inside(pack, root_name, must_exist=True)
        included.update(path.relative_to(pack).as_posix() for path in root.rglob("*") if path.is_file())
    included.update(extra_paths or set())
    return sorted(included)


def _seal_files(
    pack: Path,
    manifest: dict[str, Any],
    *,
    pending: dict[Path, str] | None = None,
    extra_paths: set[str] | None = None,
) -> dict[str, str]:
    pending_resolved = {path.resolve(): content for path, content in (pending or {}).items()}
    files: dict[str, str] = {}
    for relative in _seal_file_paths(pack, manifest, extra_paths=extra_paths):
        path = resolve_inside(pack, relative)
        if path.resolve() in pending_resolved:
            files[relative] = sha256_bytes(pending_resolved[path.resolve()].encode("utf-8"))
        else:
            path = resolve_inside(pack, relative, must_exist=True)
            if path.is_file():
                files[relative] = sha256_file(path)
    return files


def _assert_successor_revision_bindings(pack: Path, manifest: dict[str, Any], revision: int) -> None:
    mismatches: list[str] = []
    index_path = str(manifest["index_path"])
    index = load_json(resolve_inside(pack, index_path, must_exist=True))
    if index.get("pack_revision") != revision:
        mismatches.append(index_path)
    for plan_path in manifest["plans"].values():
        if not isinstance(plan_path, str) or not plan_path:
            continue
        plan = load_json(resolve_inside(pack, str(plan_path), must_exist=True))
        if plan.get("pack_revision") != revision:
            mismatches.append(str(plan_path))
    for entry in manifest["documents"]:
        document_path = str(entry["path"])
        text = resolve_inside(pack, document_path, must_exist=True).read_text(encoding="utf-8")
        if parse_frontmatter(text).get("pack_revision") != str(revision):
            mismatches.append(document_path)
    if mismatches:
        raise ClonePackError(
            "successor pack_revision is not bound across: " + ", ".join(sorted(mismatches)),
            diagnostic="SEAL_REVISION_BINDING",
        )


def create_seal(pack: Path, profile: str, timestamp: str | None = None) -> dict[str, Any]:
    pack = pack.expanduser().resolve()
    recover_atomic_transactions(pack)
    manifest = load_json(pack / "clone_pack.json")
    seal_path = resolve_inside(pack, str(manifest["seal_path"]))
    prior_bytes: bytes | None = None
    prior_digest: str | None = None
    prior_revision: int | None = None
    current_revision = manifest.get("pack_revision")
    if (
        not seal_path.exists()
        and isinstance(current_revision, int)
        and not isinstance(current_revision, bool)
        and current_revision > 1
    ):
        raise ClonePackError(
            "higher-revision sealing requires the retained predecessor seal",
            exit_code=EXIT_INTEGRITY,
            diagnostic="SEAL_PREDECESSOR_MISSING",
        )
    if seal_path.exists():
        prior_bytes = seal_path.read_bytes()
        prior_digest = sha256_bytes(prior_bytes)
        prior_seal = load_json(seal_path)
        try:
            prior_violations = validate_schema_file(prior_seal, SCHEMA_ROOT / SCHEMA_FILES["seal"])
        except SchemaDefinitionError as exc:
            raise ClonePackError(f"packaged seal schema is invalid: {exc}", exit_code=70, diagnostic="SCHEMA_INVALID") from exc
        if prior_violations:
            first = prior_violations[0]
            raise ClonePackError(
                f"existing predecessor seal is invalid at {first.pointer or '/'}: {first.message}",
                exit_code=EXIT_INTEGRITY,
                diagnostic="SEAL_INVALID",
            )
        prior_files = prior_seal.get("files")
        if (
            prior_seal.get("verdict") != "PASS"
            or not isinstance(prior_files, dict)
            or prior_seal.get("manifest_sha256") != prior_files.get("clone_pack.json")
        ):
            raise ClonePackError(
                "existing predecessor seal has invalid verdict or manifest binding",
                exit_code=EXIT_INTEGRITY,
                diagnostic="SEAL_INVALID",
            )
        if prior_seal.get("pack_id") != manifest.get("pack_id"):
            raise ClonePackError(
                "existing seal belongs to a different pack_id",
                exit_code=EXIT_INTEGRITY,
                diagnostic="SEAL_IDENTITY",
            )
        current_revision = manifest.get("pack_revision")
        prior_revision_value = prior_seal.get("pack_revision")
        if (
            not isinstance(current_revision, int)
            or isinstance(current_revision, bool)
            or not isinstance(prior_revision_value, int)
            or isinstance(prior_revision_value, bool)
        ):
            raise ClonePackError("seal revisions must be integers", diagnostic="SEAL_REVISION_INVALID")
        prior_revision = prior_revision_value
        if current_revision <= prior_revision:
            raise ClonePackError(
                f"successor pack_revision {current_revision} must be greater than prior seal revision {prior_revision}",
                diagnostic="SEAL_REVISION_NOT_ADVANCED",
            )
        expected_supersedes = {
            "schema_version": str(manifest.get("schema_version")),
            "pack_id": str(prior_seal.get("pack_id")),
            "pack_revision": prior_revision,
            "manifest_sha256": str(prior_seal.get("manifest_sha256")),
            "seal_sha256": prior_digest,
        }
        supersedes = manifest.get("supersedes")
        if supersedes is None:
            raise ClonePackError(
                "successor manifest must identify its predecessor seal",
                diagnostic="SEAL_SUPERSEDES_REQUIRED",
            )
        if supersedes != expected_supersedes:
            raise ClonePackError(
                "successor supersedes identity differs from the predecessor seal",
                exit_code=EXIT_INTEGRITY,
                diagnostic="SEAL_SUPERSEDES_MISMATCH",
            )
    preliminary = validate_v2(pack, profile, require_seal=False)
    if preliminary.exit_code:
        messages = "; ".join(item.message for item in preliminary.sorted_all()[:5])
        raise ClonePackError(f"cannot seal invalid pack: {messages}", exit_code=preliminary.exit_code, diagnostic="SEAL_PRECONDITION")
    manifest = load_json(pack / "clone_pack.json")
    pending: dict[Path, str] = {}
    extra_paths: set[str] = set()
    if prior_bytes is not None and prior_digest is not None and prior_revision is not None:
        _assert_successor_revision_bindings(pack, manifest, int(manifest["pack_revision"]))
        archive_path = pack / "history" / "seals" / f"revision-{prior_revision}-{prior_digest[:16]}.json"
        if archive_path.exists() and archive_path.read_bytes() != prior_bytes:
            raise ClonePackError(
                f"seal archive collision: {archive_path.relative_to(pack).as_posix()}",
                exit_code=EXIT_INTEGRITY,
                diagnostic="SEAL_ARCHIVE_COLLISION",
            )
        archive_relative = archive_path.relative_to(pack).as_posix()
        extra_paths.add(archive_relative)
        if not archive_path.exists():
            try:
                prior_text = prior_bytes.decode("utf-8")
            except UnicodeDecodeError as exc:
                raise ClonePackError(
                    "existing seal is not UTF-8 JSON",
                    exit_code=EXIT_INTEGRITY,
                    diagnostic="SEAL_INVALID",
                ) from exc
            pending[archive_path] = prior_text
    document_state = "closed" if profile == "closed" else "active"
    for entry in manifest["documents"]:
        document_path = resolve_inside(pack, entry["path"], must_exist=True)
        document_text = document_path.read_text(encoding="utf-8")
        document_text, count = re.subn(
            r"^document_state:\s*\S+\s*$",
            f"document_state: {document_state}",
            document_text,
            count=1,
            flags=re.MULTILINE,
        )
        if count != 1:
            raise ClonePackError(f"document lacks document_state frontmatter: {entry['path']}", diagnostic="SEAL_PRECONDITION")
        pending[document_path] = document_text
        entry["state"] = document_state
    manifest["state"] = "sealed" if profile != "closed" else "closed"
    for entry in manifest["documents"]:
        document_path = resolve_inside(pack, entry["path"], must_exist=True)
        entry["sha256"] = sha256_bytes(pending[document_path].encode("utf-8"))
    manifest_path = pack / "clone_pack.json"
    pending[manifest_path] = canonical_json(manifest)
    files = _seal_files(pack, manifest, pending=pending, extra_paths=extra_paths)
    created_at, _ = utc_now(timestamp)
    seal = {
        "schema_version": "clone-seal/v2",
        "pack_id": manifest["pack_id"],
        "pack_revision": manifest["pack_revision"],
        "profile": profile,
        "created_at": created_at,
        "verdict": "PASS",
        "tool_version": TOOL_VERSION,
        "files": files,
        "manifest_sha256": files["clone_pack.json"],
    }
    if prior_digest is not None:
        seal["predecessor_seal_sha256"] = prior_digest
    if profile == "verified-enhancement":
        from .enhancement import build_enhancement_seal_bindings

        seal["enhancement_bindings"] = build_enhancement_seal_bindings(pack, manifest)
    pending[seal_path] = canonical_json(seal)
    atomic_write_many(
        pending,
        transaction_root=pack,
        operation=f"seal:{profile}:revision-{manifest['pack_revision']}",
    )
    return seal


def _validate_seal(pack: Path, manifest: dict[str, Any], profile: str, result: ValidationResult) -> None:
    seal_path = str(manifest.get("seal_path", "seal.json"))
    try:
        seal = load_json(resolve_inside(pack, seal_path, must_exist=True))
    except ClonePackError as exc:
        result.add(seal_path, "SEAL_MISSING", str(exc))
        return
    if seal.get("pack_id") != manifest.get("pack_id") or seal.get("pack_revision") != manifest.get("pack_revision"):
        result.add(seal_path, "SEAL_IDENTITY", "seal identity/revision differs from manifest")
    if seal.get("profile") != profile or seal.get("verdict") != "PASS":
        result.add(seal_path, "SEAL_PROFILE", "seal profile/verdict differs from requested validation")
    expected_files = seal.get("files")
    if not isinstance(expected_files, dict):
        result.add(seal_path, "SEAL_INVALID", "seal files must be an object")
        return
    try:
        actual_file_set = _seal_files(pack, manifest)
    except ClonePackError as exc:
        result.add(seal_path, "SEAL_TAMPERED", str(exc))
        return
    missing_entries = sorted(set(actual_file_set) - set(expected_files))
    unexpected_entries = sorted(set(expected_files) - set(actual_file_set))
    if missing_entries:
        result.add(seal_path, "SEAL_TAMPERED", "seal omits governed files: " + ", ".join(missing_entries))
    if unexpected_entries:
        result.add(seal_path, "SEAL_TAMPERED", "seal names non-governed files: " + ", ".join(unexpected_entries))
    for relative, expected in expected_files.items():
        try:
            actual = sha256_file(resolve_inside(pack, relative, must_exist=True))
        except ClonePackError as exc:
            result.add(seal_path, "SEAL_TAMPERED", str(exc))
            continue
        if actual != expected:
            result.add(seal_path, "SEAL_TAMPERED", f"sealed file changed: {relative}")
    manifest_digest = expected_files.get("clone_pack.json")
    if seal.get("manifest_sha256") != manifest_digest:
        result.add(seal_path, "SEAL_TAMPERED", "manifest_sha256 does not match the sealed manifest entry")
    supersedes = manifest.get("supersedes")
    if supersedes is not None:
        predecessor_digest = seal.get("predecessor_seal_sha256")
        if not isinstance(predecessor_digest, str) or re.fullmatch(r"[0-9a-f]{64}", predecessor_digest) is None:
            result.add(seal_path, "SEAL_TAMPERED", "successor seal lacks predecessor_seal_sha256")
        elif isinstance(supersedes, dict) and isinstance(supersedes.get("pack_revision"), int):
            archive_relative = (
                f"history/seals/revision-{supersedes['pack_revision']}-{predecessor_digest[:16]}.json"
            )
            try:
                archive = resolve_inside(pack, archive_relative, must_exist=True)
            except ClonePackError as exc:
                result.add(seal_path, "SEAL_TAMPERED", str(exc))
            else:
                if sha256_file(archive) != predecessor_digest:
                    result.add(seal_path, "SEAL_TAMPERED", "archived predecessor seal hash differs")
                else:
                    try:
                        predecessor = load_json(archive)
                    except ClonePackError as exc:
                        result.add(seal_path, "SEAL_TAMPERED", str(exc))
                    else:
                        expected_supersedes = {
                            "schema_version": manifest.get("schema_version"),
                            "pack_id": predecessor.get("pack_id"),
                            "pack_revision": predecessor.get("pack_revision"),
                            "manifest_sha256": predecessor.get("manifest_sha256"),
                        }
                        if "seal_sha256" in supersedes:
                            expected_supersedes["seal_sha256"] = predecessor_digest
                        if supersedes != expected_supersedes:
                            result.add(seal_path, "SEAL_TAMPERED", "supersedes does not match archived predecessor")


def _validate_existing_seal_schema(pack: Path, manifest: dict[str, Any], result: ValidationResult) -> None:
    seal_path = str(manifest.get("seal_path", "seal.json"))
    try:
        path = resolve_inside(pack, seal_path)
    except ClonePackError as exc:
        result.add(seal_path, exc.diagnostic, str(exc))
        return
    if not path.exists():
        return
    _validate_json_artifact_schema(pack, result, seal_path, "seal")
