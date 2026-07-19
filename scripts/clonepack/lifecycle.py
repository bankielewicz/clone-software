from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .common import (
    ClonePackError,
    atomic_write_many,
    canonical_json,
    case_contract_sha256,
    contract_hashes_for_records,
    load_json,
    recover_atomic_transactions,
    resolve_inside,
    sha256_bytes,
    sha256_file,
)
from .constants import ID_PATTERNS, LEGAL_GAP_TRANSITIONS, TERMINAL_GAP_STATUSES
from .dossier import validate_gap_plan_record
from .schema import SchemaDefinitionError, validate_schema_file


SCHEMA_ROOT = Path(__file__).resolve().parents[2] / "assets" / "schemas"
GAP_EVIDENCE_KINDS = frozenset({"E", "ART", "CAP", "RUN", "PAR", "ASSURE", "FIND", "SBOM", "BUILD", "PROV"})
GAP_DECISION_KINDS = frozenset({"DEC", "ADR", "GAPDEC"})
RUN_COVERED_KINDS = frozenset({"REQ", "AC", "TEST"})
RUN_ORACLE_KINDS = frozenset({"E", "ART", "CAP"})
ARTIFACT_FIELDS = frozenset({"id", "path", "size", "media_type", "sha256"})


def _load_events(path: Path) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ClonePackError(f"invalid gap event at line {number}: {exc}", exit_code=4, diagnostic="GAP_EVENT_CHAIN") from exc
        if not isinstance(event, dict):
            raise ClonePackError(f"gap event at line {number} is not an object", exit_code=4, diagnostic="GAP_EVENT_CHAIN")
        events.append(event)
    return events


def _require_unique_ids(values: list[str], role: str) -> None:
    if len(values) != len(set(values)):
        raise ClonePackError(
            f"{role} IDs must be unique",
            exit_code=2,
            diagnostic="ARG_INVALID",
        )


def _records_by_id(index: dict[str, Any], manifest: dict[str, Any]) -> dict[str, dict[str, Any]]:
    if index.get("schema_version") != "clone-index/v2":
        raise ClonePackError("gap transition requires clone-index/v2", diagnostic="INDEX_INVALID")
    if index.get("pack_id") != manifest.get("pack_id") or index.get("pack_revision") != manifest.get("pack_revision"):
        raise ClonePackError("index identity/revision differs from the current manifest", diagnostic="PACK_ID_MISMATCH")
    raw_records = index.get("records")
    if not isinstance(raw_records, list):
        raise ClonePackError("index records must be an array", diagnostic="INDEX_INVALID")
    records: dict[str, dict[str, Any]] = {}
    for position, record in enumerate(raw_records):
        if not isinstance(record, dict) or not isinstance(record.get("id"), str):
            raise ClonePackError(f"index record {position} has no string ID", diagnostic="INDEX_INVALID")
        identifier = str(record["id"])
        if identifier in records:
            raise ClonePackError(f"index contains duplicate ID: {identifier}", diagnostic="ID_DUPLICATE")
        records[identifier] = record
    return records


def _verify_record_locator(pack: Path, identifier: str, record: dict[str, Any], verified: set[str]) -> None:
    if identifier in verified:
        return
    locator = record.get("locator")
    if not isinstance(locator, dict) or set(locator) != {"path", "anchor", "sha256"}:
        raise ClonePackError(f"index locator is invalid: {identifier}", diagnostic="HASH_ANCHOR_MISSING")
    path_value = locator.get("path")
    anchor = locator.get("anchor")
    expected = locator.get("sha256")
    if (
        not isinstance(path_value, str)
        or not isinstance(anchor, str)
        or not anchor
        or not isinstance(expected, str)
        or re.fullmatch(r"[0-9a-f]{64}", expected) is None
    ):
        raise ClonePackError(f"index locator is incomplete: {identifier}", diagnostic="HASH_ANCHOR_MISSING")
    path = resolve_inside(pack, path_value, must_exist=True)
    if not path.is_file():
        raise ClonePackError(f"index locator is not a file: {identifier}", diagnostic="HASH_ANCHOR_MISSING")
    try:
        lines = [line for line in path.read_text(encoding="utf-8").splitlines(keepends=True) if anchor in line]
    except (OSError, UnicodeError) as exc:
        raise ClonePackError(
            f"cannot read index locator for {identifier}: {exc}",
            exit_code=4,
            diagnostic="ARTIFACT_UNREADABLE",
        ) from exc
    if len(lines) != 1:
        raise ClonePackError(
            f"index anchor for {identifier} must occur exactly once; found {len(lines)}",
            diagnostic="HASH_ANCHOR_MISSING",
        )
    if sha256_bytes(lines[0].encode("utf-8")) != expected:
        raise ClonePackError(f"index anchor hash is stale: {identifier}", exit_code=4, diagnostic="HASH_MISMATCH")
    verified.add(identifier)


def _require_record(
    pack: Path,
    records: dict[str, dict[str, Any]],
    identifier: str,
    allowed_kinds: frozenset[str] | set[str],
    *,
    role: str,
    verified: set[str],
) -> dict[str, Any]:
    record = records.get(identifier)
    if record is None:
        raise ClonePackError(f"{role} is not defined in the current index: {identifier}", diagnostic="REF_UNDEFINED")
    kind = record.get("kind")
    if kind not in allowed_kinds:
        diagnostic = "GAP_DECISION_KIND_INVALID" if role == "decision evidence" else "GAP_EVIDENCE_KIND_INVALID"
        raise ClonePackError(
            f"{role} {identifier} has kind {kind!r}; allowed kinds: {', '.join(sorted(allowed_kinds))}",
            diagnostic=diagnostic,
        )
    pattern = ID_PATTERNS.get(str(kind))
    if pattern is None or re.fullmatch(pattern, identifier) is None:
        raise ClonePackError(f"ID prefix and record kind differ: {identifier} ({kind})", diagnostic="ID_KIND_MISMATCH")
    _verify_record_locator(pack, identifier, record, verified)
    return record


def _require_schema(instance: dict[str, Any], schema_name: str, owner: str, diagnostic: str) -> None:
    try:
        violations = validate_schema_file(instance, SCHEMA_ROOT / schema_name)
    except SchemaDefinitionError as exc:
        raise ClonePackError(f"packaged schema is invalid: {exc}", exit_code=70, diagnostic="SCHEMA_INVALID") from exc
    if violations:
        first = violations[0]
        pointer = first.pointer or "/"
        raise ClonePackError(f"{owner}{pointer}: {first.message}", diagnostic=diagnostic)


def _validate_artifact(pack: Path, artifact: Any, owner: str, *, required_prefix: str | None = None) -> None:
    if not isinstance(artifact, dict) or set(artifact) != ARTIFACT_FIELDS:
        raise ClonePackError(f"{owner} has an invalid artifact record", diagnostic="RESULT_INVALID")
    path_value = artifact.get("path")
    expected_hash = artifact.get("sha256")
    expected_size = artifact.get("size")
    if (
        not isinstance(path_value, str)
        or not isinstance(expected_hash, str)
        or re.fullmatch(r"[0-9a-f]{64}", expected_hash) is None
        or not isinstance(expected_size, int)
        or isinstance(expected_size, bool)
        or expected_size < 0
    ):
        raise ClonePackError(f"{owner} has an invalid artifact identity", diagnostic="RESULT_INVALID")
    if required_prefix is not None and not path_value.startswith(required_prefix.rstrip("/") + "/"):
        raise ClonePackError(f"{owner} artifact escapes its retained evidence directory: {path_value}", diagnostic="RESULT_INVALID")
    path = resolve_inside(pack, path_value, must_exist=True)
    if not path.is_file():
        raise ClonePackError(f"{owner} artifact is not a file: {path_value}", diagnostic="RESULT_INVALID")
    try:
        actual_size = path.stat().st_size
    except OSError as exc:
        raise ClonePackError(f"cannot stat artifact {path_value}: {exc}", exit_code=4, diagnostic="ARTIFACT_UNREADABLE") from exc
    if actual_size != expected_size:
        raise ClonePackError(f"artifact size mismatch: {path_value}", exit_code=4, diagnostic="ARTIFACT_HASH_MISMATCH")
    if sha256_file(path) != expected_hash:
        raise ClonePackError(f"artifact hash mismatch: {path_value}", exit_code=4, diagnostic="ARTIFACT_HASH_MISMATCH")


def _require_id_array(value: Any, owner: str) -> list[str]:
    if (
        not isinstance(value, list)
        or any(not isinstance(item, str) or not item for item in value)
        or len(value) != len(set(value))
    ):
        raise ClonePackError(f"{owner} must be a unique string-ID array", diagnostic="RESULT_INVALID")
    return [str(item) for item in value]


def _verify_run_evidence(
    pack: Path,
    manifest: dict[str, Any],
    records: dict[str, dict[str, Any]],
    run_id: str,
    *,
    require_pass: bool,
    verified: set[str],
) -> dict[str, Any]:
    record = _require_record(
        pack,
        records,
        run_id,
        frozenset({"RUN"}),
        role="run evidence",
        verified=verified,
    )
    runs_directory = resolve_inside(pack, str(manifest.get("runs_path", "runs")), must_exist=True)
    run_path = (runs_directory / f"{run_id}.json").resolve()
    try:
        relative_run_path = run_path.relative_to(pack).as_posix()
    except ValueError as exc:
        raise ClonePackError("runs_path escapes the pack", exit_code=4, diagnostic="PATH_ESCAPE") from exc
    if record.get("locator", {}).get("path") != relative_run_path:
        raise ClonePackError(f"RUN index locator does not name its canonical result: {run_id}", diagnostic="RUN_LOCATOR_MISMATCH")
    run = load_json(run_path)
    _require_schema(run, "clone-run-v2.schema.json", relative_run_path, "RUN_INVALID")
    if run.get("run_id") != run_id:
        raise ClonePackError(f"run identity differs from its evidence ID: {run_id}", diagnostic="RUN_ID_INVALID")
    if run.get("pack_id") != manifest.get("pack_id") or run.get("pack_revision") != manifest.get("pack_revision"):
        raise ClonePackError(f"run pack identity/revision is stale: {run_id}", diagnostic="RUN_STALE_REVISION")
    if run.get("reference_baseline_id") != manifest.get("reference_baseline_id"):
        raise ClonePackError(f"run reference baseline is stale: {run_id}", diagnostic="RUN_STALE_REFERENCE")
    repository_state = manifest.get("repository_state")
    if not isinstance(repository_state, dict) or repository_state.get("revision") in {None, "", "UNRESOLVED"}:
        raise ClonePackError("current repository state is unresolved", diagnostic="REPOSITORY_STATE_UNRESOLVED")
    if (
        run.get("clone_revision") != repository_state.get("revision")
        or run.get("clone_diff_sha256") != repository_state.get("diff_sha256")
    ):
        raise ClonePackError(f"run repository revision/diff is stale: {run_id}", diagnostic="RUN_STALE_REVISION")
    if require_pass and run.get("result") != "PASS":
        raise ClonePackError(f"gap transition requires a current passing run: {run_id}", diagnostic="GAP_EVIDENCE_MISSING")
    if record.get("state") != run.get("result") or record.get("attributes", {}).get("result") != run.get("result"):
        raise ClonePackError(f"RUN index state differs from retained result: {run_id}", diagnostic="RUN_STATUS_DIVERGENCE")

    environment_id = run.get("environment_id")
    if not isinstance(environment_id, str):
        raise ClonePackError(f"run lacks a pinned environment: {run_id}", diagnostic="RUN_ENVIRONMENT_INVALID")
    _require_record(pack, records, environment_id, frozenset({"ENV"}), role="run environment", verified=verified)
    covered_ids = _require_id_array(run.get("covered_ids"), f"{run_id} covered_ids")
    oracle_ids = _require_id_array(run.get("oracle_ids"), f"{run_id} oracle_ids")
    if not covered_ids:
        raise ClonePackError(f"run has no governed coverage: {run_id}", diagnostic="RUN_COVERAGE_INVALID")
    if not oracle_ids:
        raise ClonePackError(f"run has no independent oracle: {run_id}", diagnostic="RUN_ORACLE_INVALID")
    for identifier in covered_ids:
        _require_record(pack, records, identifier, RUN_COVERED_KINDS, role="run covered evidence", verified=verified)
    for identifier in oracle_ids:
        _require_record(pack, records, identifier, RUN_ORACLE_KINDS, role="run oracle evidence", verified=verified)
    gate_id = run.get("gate_id")
    governing_ids = [environment_id, *covered_ids, *oracle_ids]
    if run.get("schema_version") == "clone-run/v2":
        if not isinstance(gate_id, str):
            raise ClonePackError(f"automated run lacks a gate: {run_id}", diagnostic="RUN_GATE_INVALID")
        _require_record(pack, records, gate_id, frozenset({"GATE"}), role="run gate", verified=verified)
        governing_ids.append(gate_id)
    elif gate_id != "MANUAL":
        raise ClonePackError(f"manual run must use the MANUAL pseudo-gate: {run_id}", diagnostic="RUN_GATE_INVALID")
    expected_contract_hashes = contract_hashes_for_records(records, governing_ids)
    if run.get("contract_hashes") != expected_contract_hashes:
        raise ClonePackError(f"run governing contracts are stale: {run_id}", diagnostic="RUN_CONTRACT_STALE")
    artifacts = run.get("artifacts")
    if not isinstance(artifacts, list) or not artifacts:
        raise ClonePackError(f"run has no retained artifacts: {run_id}", diagnostic="RUN_INVALID")
    artifact_prefix = f"{str(manifest.get('runs_path', 'runs')).rstrip('/')}/artifacts/{run_id}"
    for artifact in artifacts:
        _validate_artifact(pack, artifact, run_id, required_prefix=artifact_prefix)
    return run


def _plan_case(
    pack: Path,
    manifest: dict[str, Any],
    plan_name: str,
    case_id: str,
) -> tuple[dict[str, Any], dict[str, Any], str]:
    plans = manifest.get("plans")
    plan_path_value = plans.get(plan_name) if isinstance(plans, dict) else None
    if not isinstance(plan_path_value, str):
        raise ClonePackError(f"manifest has no {plan_name} plan", diagnostic="PLAN_INVALID")
    plan_path = resolve_inside(pack, plan_path_value, must_exist=True)
    plan = load_json(plan_path)
    schema_name = "parity-plan-v2.schema.json" if plan_name == "parity" else "assurance-plan-v2.schema.json"
    _require_schema(plan, schema_name, plan_path_value, "PLAN_INVALID")
    if plan.get("pack_id") != manifest.get("pack_id") or plan.get("pack_revision") != manifest.get("pack_revision"):
        raise ClonePackError(f"{plan_name} plan identity/revision is stale", diagnostic=f"{plan_name.upper()}_STALE_REVISION")
    cases = plan.get("cases")
    matches = [case for case in cases if isinstance(case, dict) and case.get("id") == case_id]
    if len(matches) != 1:
        qualifier = "missing" if not matches else "duplicated"
        raise ClonePackError(f"{plan_name} case is {qualifier}: {case_id}", diagnostic="GAP_EVIDENCE_MISSING")
    return plan, matches[0], plan_path_value


def _verify_plan_evidence(
    pack: Path,
    manifest: dict[str, Any],
    plan_name: str,
    case_id: str,
    *,
    require_pass: bool,
) -> dict[str, Any]:
    _, case, plan_path_value = _plan_case(pack, manifest, plan_name, case_id)
    result_pointer = case.get("result")
    if not isinstance(result_pointer, dict) or set(result_pointer) != {"status", "path", "sha256"}:
        raise ClonePackError(f"{plan_name} case has no retained result: {case_id}", diagnostic="GAP_EVIDENCE_MISSING")
    expected_path = f"evidence/{plan_name}/{case_id}/result.json"
    if result_pointer.get("path") != expected_path:
        raise ClonePackError(f"{plan_name} result path is not canonical: {case_id}", diagnostic="RESULT_INVALID")
    expected_hash = result_pointer.get("sha256")
    if not isinstance(expected_hash, str) or re.fullmatch(r"[0-9a-f]{64}", expected_hash) is None:
        raise ClonePackError(f"{plan_name} result has no valid hash: {case_id}", diagnostic="RESULT_INVALID")
    result_path = resolve_inside(pack, expected_path, must_exist=True)
    if sha256_file(result_path) != expected_hash:
        raise ClonePackError(f"{plan_name} result hash mismatch: {case_id}", exit_code=4, diagnostic="ARTIFACT_HASH_MISMATCH")
    retained = load_json(result_path)
    prefix = plan_name.upper()
    expected_schema = f"clone-{plan_name}-result/v2"
    identity_field = f"{plan_name}_id"
    if retained.get("schema_version") != expected_schema or retained.get(identity_field) != case_id:
        raise ClonePackError(f"{plan_name} retained-result identity is invalid: {case_id}", diagnostic="RESULT_IDENTITY_MISMATCH")
    if retained.get("pack_id") != manifest.get("pack_id") or retained.get("pack_revision") != manifest.get("pack_revision"):
        raise ClonePackError(f"{plan_name} result pack identity/revision is stale: {case_id}", diagnostic=f"{prefix}_STALE_REVISION")
    if retained.get("reference_baseline_id") != manifest.get("reference_baseline_id"):
        raise ClonePackError(f"{plan_name} result reference baseline is stale: {case_id}", diagnostic=f"{prefix}_STALE_REFERENCE")
    repository_state = manifest.get("repository_state")
    if not isinstance(repository_state, dict):
        raise ClonePackError("current repository state is invalid", diagnostic="REPOSITORY_STATE_UNRESOLVED")
    if (
        retained.get("clone_revision") != repository_state.get("revision")
        or retained.get("clone_diff_sha256") != repository_state.get("diff_sha256")
    ):
        raise ClonePackError(f"{plan_name} result repository state is stale: {case_id}", diagnostic=f"{prefix}_STALE_REVISION")
    if retained.get("case_sha256") != case_contract_sha256(case):
        raise ClonePackError(f"{plan_name} retained PASS does not match the current case: {case_id}", diagnostic=f"{prefix}_CONTRACT_STALE")
    if retained.get("status") != result_pointer.get("status"):
        raise ClonePackError(f"{plan_name} result status differs from its plan pointer: {case_id}", diagnostic="RESULT_STATUS_MISMATCH")
    if require_pass and retained.get("status") != "PASS":
        raise ClonePackError(f"required {plan_name} case is not PASS: {case_id}", diagnostic=f"{prefix}_NOT_PASS")
    if plan_name == "parity":
        if (
            retained.get("reference_capture_id") != case.get("reference_capture_id")
            or retained.get("clone_capture_id") != case.get("clone_capture_id")
            or retained.get("comparator") != case.get("comparator")
            or retained.get("normalizations") != case.get("normalizations")
            or retained.get("options") != case.get("options", {})
        ):
            raise ClonePackError(f"parity result fields differ from the current case: {case_id}", diagnostic="PARITY_CONTRACT_STALE")
    elif retained.get("kind") != case.get("kind"):
        raise ClonePackError(f"assurance result kind differs from the current case: {case_id}", diagnostic="ASSURANCE_CONTRACT_STALE")
    artifacts = retained.get("artifacts")
    if not isinstance(artifacts, list):
        raise ClonePackError(f"{plan_name} result artifacts must be an array: {case_id}", diagnostic="RESULT_INVALID")
    if plan_name == "assurance" and retained.get("status") == "PASS" and not artifacts:
        raise ClonePackError(f"passing assurance has no retained artifacts: {case_id}", diagnostic="RESULT_INVALID")
    artifact_prefix = f"evidence/{plan_name}/{case_id}"
    for artifact in artifacts:
        _validate_artifact(pack, artifact, case_id, required_prefix=artifact_prefix)
    return retained


def _validated_gap_history(
    events: list[dict[str, Any]],
    gap_id: str,
    current_status: str,
    records: dict[str, dict[str, Any]],
) -> dict[str, Any] | None:
    previous_hashes: dict[str, str] = {}
    previous_states: dict[str, str] = {}
    previous_timestamps: dict[str, datetime] = {}
    sequences: dict[str, int] = {}
    event_ids: set[str] = set()
    last_for_gap: dict[str, Any] | None = None
    for number, event in enumerate(events, 1):
        _require_schema(event, "clone-gap-event-v2.schema.json", f"gap history line {number}", "GAP_EVENT_CHAIN")
        event_gap = str(event["gap_id"])
        event_id = str(event["event_id"])
        if event_id in event_ids:
            raise ClonePackError(f"duplicate gap event ID at line {number}: {event_id}", exit_code=4, diagnostic="GAP_EVENT_CHAIN")
        event_ids.add(event_id)
        if event_gap not in records or records[event_gap].get("kind") != "GAP":
            raise ClonePackError(f"gap event names an undefined gap at line {number}: {event_gap}", exit_code=4, diagnostic="GAP_EVENT_CHAIN")
        expected_sequence = sequences.get(event_gap, 0) + 1
        if event.get("sequence") != expected_sequence:
            raise ClonePackError(f"gap event sequence is invalid at line {number}", exit_code=4, diagnostic="GAP_EVENT_CHAIN")
        if event.get("previous_event_sha256") != previous_hashes.get(event_gap, ""):
            raise ClonePackError(f"gap event previous hash is invalid at line {number}", exit_code=4, diagnostic="GAP_EVENT_CHAIN")
        hash_input = dict(event)
        supplied_hash = hash_input.pop("event_sha256", None)
        if supplied_hash != sha256_bytes(canonical_json(hash_input).encode("utf-8")):
            raise ClonePackError(f"gap event hash is invalid at line {number}", exit_code=4, diagnostic="GAP_EVENT_CHAIN")
        from_status = event.get("from")
        to_status = event.get("to")
        if expected_sequence == 1 and from_status != "OPEN":
            raise ClonePackError(f"gap event history must begin at OPEN at line {number}", exit_code=4, diagnostic="GAP_HISTORY_INCOMPLETE")
        if (from_status, to_status) not in LEGAL_GAP_TRANSITIONS:
            raise ClonePackError(f"gap event has an illegal transition at line {number}", exit_code=4, diagnostic="GAP_EVENT_CHAIN")
        if event_gap in previous_states and from_status != previous_states[event_gap]:
            raise ClonePackError(f"gap event state chain is invalid at line {number}", exit_code=4, diagnostic="GAP_EVENT_CHAIN")
        try:
            event_timestamp = datetime.fromisoformat(str(event["timestamp"]).replace("Z", "+00:00"))
        except ValueError as exc:
            raise ClonePackError(f"gap event timestamp is invalid at line {number}", exit_code=4, diagnostic="GAP_EVENT_CHAIN") from exc
        prior_timestamp = previous_timestamps.get(event_gap)
        if prior_timestamp is not None and event_timestamp < prior_timestamp:
            raise ClonePackError(f"gap event timestamp regresses at line {number}", exit_code=4, diagnostic="GAP_EVENT_CHAIN")
        for identifier in event.get("evidence_ids", []):
            if identifier not in records or records[identifier].get("kind") not in GAP_EVIDENCE_KINDS:
                raise ClonePackError(f"gap event evidence is invalid at line {number}: {identifier}", exit_code=4, diagnostic="GAP_EVENT_CHAIN")
        for identifier in event.get("decision_ids", []):
            if identifier not in records or records[identifier].get("kind") not in GAP_DECISION_KINDS:
                raise ClonePackError(f"gap event decision is invalid at line {number}: {identifier}", exit_code=4, diagnostic="GAP_EVENT_CHAIN")
        sequences[event_gap] = expected_sequence
        previous_hashes[event_gap] = str(supplied_hash)
        previous_states[event_gap] = str(to_status)
        previous_timestamps[event_gap] = event_timestamp
        if event_gap == gap_id:
            last_for_gap = event
    if last_for_gap is not None and last_for_gap.get("to") != current_status:
        raise ClonePackError("gap history state differs from the current index", exit_code=4, diagnostic="GAP_STATUS_DIVERGENCE")
    if last_for_gap is None and current_status != "OPEN":
        raise ClonePackError("noninitial gap status requires complete history", exit_code=4, diagnostic="GAP_HISTORY_MISSING")
    return last_for_gap


def _gap_link_ids(gap: dict[str, Any], relation: str) -> list[str]:
    links = gap.get("links")
    value = links.get(relation, []) if isinstance(links, dict) else []
    if (
        not isinstance(value, list)
        or any(not isinstance(item, str) or not item for item in value)
        or len(value) != len(set(value))
    ):
        raise ClonePackError(
            f"gap {relation} links must be a unique string-ID array",
            diagnostic="GAP_LINK_INVALID",
        )
    return [str(item) for item in value]


def transition_gap(
    pack: Path,
    gap_id: str,
    to_status: str,
    *,
    actor: str,
    reason: str,
    evidence_ids: list[str],
    decision_ids: list[str],
    timestamp: str | None = None,
) -> dict[str, Any]:
    pack = pack.expanduser().resolve()
    recover_atomic_transactions(pack)
    manifest = load_json(pack / "clone_pack.json")
    index_path = resolve_inside(pack, str(manifest["index_path"]), must_exist=True)
    history_path = resolve_inside(pack, str(manifest["history_path"]), must_exist=True)
    gaps_path = resolve_inside(pack, "gaps_analysis.md", must_exist=True)
    index = load_json(index_path)
    records = _records_by_id(index, manifest)
    gap = records.get(gap_id)
    if gap is None or gap.get("kind") != "GAP":
        raise ClonePackError(f"unknown gap: {gap_id}", exit_code=2, diagnostic="CASE_UNKNOWN")
    verified_locators: set[str] = set()
    if re.fullmatch(ID_PATTERNS["GAP"], gap_id) is None:
        raise ClonePackError(f"gap ID does not match GAP-###: {gap_id}", diagnostic="ID_KIND_MISMATCH")
    _verify_record_locator(pack, gap_id, gap, verified_locators)
    attributes = gap.get("attributes")
    if not isinstance(attributes, dict):
        raise ClonePackError(f"gap attributes are invalid: {gap_id}", diagnostic="GAP_STATUS_INVALID")
    from_status = attributes.get("status")
    if (from_status, to_status) not in LEGAL_GAP_TRANSITIONS:
        raise ClonePackError(
            f"illegal gap transition: {from_status} -> {to_status}", diagnostic="GAP_ILLEGAL_TRANSITION"
        )
    if not isinstance(actor, str) or not isinstance(reason, str) or not actor.strip() or not reason.strip():
        raise ClonePackError("gap transition requires actor and reason", exit_code=2, diagnostic="ARG_INVALID")
    _require_unique_ids(evidence_ids, "evidence")
    _require_unique_ids(decision_ids, "decision")
    for identifier in evidence_ids:
        _require_record(
            pack,
            records,
            identifier,
            GAP_EVIDENCE_KINDS,
            role="transition evidence",
            verified=verified_locators,
        )
    for identifier in decision_ids:
        _require_record(
            pack,
            records,
            identifier,
            GAP_DECISION_KINDS,
            role="decision evidence",
            verified=verified_locators,
        )

    dependencies = _gap_link_ids(gap, "dependencies")
    for dependency in dependencies:
        _require_record(
            pack,
            records,
            dependency,
            frozenset({"GAP"}),
            role="gap dependency",
            verified=verified_locators,
        )
    if to_status == "IN_PROGRESS":
        if attributes.get("readiness") != "READY":
            raise ClonePackError("gap must be READY before IN_PROGRESS", diagnostic="GAP_NOT_READY")
        unsatisfied = [
            dependency
            for dependency in dependencies
            if records.get(dependency, {}).get("attributes", {}).get("status") != "VERIFIED"
        ]
        if unsatisfied:
            raise ClonePackError(
                "unverified gap dependencies: " + ", ".join(unsatisfied), diagnostic="GAP_DEP_UNSATISFIED"
            )

    run_ids = [identifier for identifier in evidence_ids if records[identifier].get("kind") == "RUN"]
    runs: list[dict[str, Any]] = []
    if to_status in {"IMPLEMENTED", "VERIFIED"} and not run_ids:
        raise ClonePackError(f"{to_status} requires passing RUN evidence", diagnostic="GAP_EVIDENCE_MISSING")
    for run_id in run_ids:
        runs.append(
            _verify_run_evidence(
                pack,
                manifest,
                records,
                run_id,
                require_pass=to_status in {"IMPLEMENTED", "VERIFIED"},
                verified=verified_locators,
            )
        )

    required_acceptance = _gap_link_ids(gap, "acceptance")
    required_parity = _gap_link_ids(gap, "parity")
    required_assurance = _gap_link_ids(gap, "assurance")
    for identifier in required_acceptance:
        _require_record(
            pack,
            records,
            identifier,
            frozenset({"AC"}),
            role="gap acceptance evidence",
            verified=verified_locators,
        )
    for identifier in required_parity:
        _require_record(
            pack,
            records,
            identifier,
            frozenset({"PAR"}),
            role="gap parity evidence",
            verified=verified_locators,
        )
    for identifier in required_assurance:
        _require_record(
            pack,
            records,
            identifier,
            frozenset({"ASSURE"}),
            role="gap assurance evidence",
            verified=verified_locators,
        )

    supplied_parity = [identifier for identifier in evidence_ids if records[identifier].get("kind") == "PAR"]
    supplied_assurance = [identifier for identifier in evidence_ids if records[identifier].get("kind") == "ASSURE"]
    for identifier in supplied_parity:
        _verify_plan_evidence(pack, manifest, "parity", identifier, require_pass=to_status == "VERIFIED")
    for identifier in supplied_assurance:
        _verify_plan_evidence(pack, manifest, "assurance", identifier, require_pass=to_status == "VERIFIED")

    if to_status == "VERIFIED":
        covered = {str(item) for run in runs for item in run.get("covered_ids", [])}
        missing = sorted(set(required_acceptance) - covered)
        if missing:
            raise ClonePackError(
                "gap acceptance lacks passing run coverage: " + ", ".join(missing),
                diagnostic="AC_UNCOVERED",
            )
        if not set(required_parity).issubset(evidence_ids) or not set(required_assurance).issubset(evidence_ids):
            raise ClonePackError("gap verification lacks required parity or assurance evidence", diagnostic="GAP_EVIDENCE_MISSING")
    if to_status == "DECLINED" and not decision_ids:
        raise ClonePackError("DECLINED requires a decision ID", diagnostic="GAP_DECISION_MISSING")
    if from_status == "VERIFIED" and to_status == "OPEN" and (not evidence_ids or not decision_ids):
        raise ClonePackError(
            "reopening VERIFIED requires contrary evidence and a supersession decision",
            diagnostic="GAP_SUPERSESSION_REQUIRED",
        )

    events = _load_events(history_path)
    previous_event = _validated_gap_history(events, gap_id, str(from_status), records)
    gap_events = [event for event in events if event.get("gap_id") == gap_id]
    previous_hash = str(previous_event.get("event_sha256", "")) if previous_event else ""
    sequence = len(gap_events) + 1
    if timestamp:
        try:
            parsed = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
        except ValueError as exc:
            raise ClonePackError("timestamp must be ISO-8601", exit_code=2, diagnostic="ARG_INVALID") from exc
        if parsed.tzinfo is None:
            raise ClonePackError("timestamp must include an offset", exit_code=2, diagnostic="ARG_INVALID")
        recorded_at = parsed.astimezone(timezone.utc).isoformat(timespec="seconds")
    else:
        recorded_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
        parsed = datetime.fromisoformat(recorded_at)
    if previous_event is not None:
        previous_timestamp = datetime.fromisoformat(str(previous_event["timestamp"]).replace("Z", "+00:00"))
        if parsed.astimezone(timezone.utc) < previous_timestamp.astimezone(timezone.utc):
            raise ClonePackError(
                "gap event timestamp precedes the prior event",
                diagnostic="GAP_EVENT_TIME_REGRESSION",
            )
    event: dict[str, Any] = {
        "schema_version": "clone-gap-event/v2",
        "event_id": f"GAPEVT-{gap_id.removeprefix('GAP-')}-{sequence:03d}",
        "gap_id": gap_id,
        "sequence": sequence,
        "from": from_status,
        "to": to_status,
        "timestamp": recorded_at,
        "actor": actor,
        "evidence_ids": evidence_ids,
        "decision_ids": decision_ids,
        "reason": reason,
        "previous_event_sha256": previous_hash,
    }
    event["event_sha256"] = sha256_bytes(canonical_json(event).encode("utf-8"))
    events.append(event)
    attributes["status"] = to_status
    links = gap.setdefault("links", {})
    if not isinstance(links, dict):
        raise ClonePackError("gap links must be an object", diagnostic="GAP_LINK_INVALID")
    existing_runs = links.setdefault("runs", [])
    if not isinstance(existing_runs, list) or any(not isinstance(item, str) for item in existing_runs):
        raise ClonePackError("gap run links must be a string-ID array", diagnostic="GAP_LINK_INVALID")
    for run_id in run_ids:
        if run_id not in existing_runs:
            existing_runs.append(run_id)

    dossier = attributes.get("dossier")
    if isinstance(dossier, dict) and isinstance(dossier.get("closure"), dict):
        closure = dossier["closure"]
        repository_state = manifest.get("repository_state")
        revision = repository_state.get("revision") if isinstance(repository_state, dict) else None
        residual_ids = closure.get("residual_gap_ids", [])
        if not isinstance(residual_ids, list):
            residual_ids = []
        if to_status in {"OPEN", "BLOCKED"}:
            closure.update(
                {
                    "state": "NOT_STARTED",
                    "implemented_revision": None,
                    "run_ids": [],
                    "parity_ids": [],
                    "assurance_ids": [],
                    "residual_gap_ids": residual_ids,
                }
            )
        elif to_status == "IN_PROGRESS":
            closure.update(
                {
                    "state": "IN_PROGRESS",
                    "implemented_revision": None,
                    "run_ids": [],
                    "parity_ids": [],
                    "assurance_ids": [],
                    "residual_gap_ids": residual_ids,
                }
            )
        elif to_status in {"IMPLEMENTED", "VERIFIED"}:
            closure.update(
                {
                    "state": to_status,
                    "implemented_revision": revision,
                    "run_ids": sorted(run_ids),
                    "parity_ids": sorted(supplied_parity) if to_status == "VERIFIED" else [],
                    "assurance_ids": sorted(supplied_assurance) if to_status == "VERIFIED" else [],
                    "residual_gap_ids": residual_ids,
                }
            )
        elif to_status == "DECLINED":
            closure.update(
                {
                    "state": "DECLINED",
                    "implemented_revision": None,
                    "run_ids": [],
                    "parity_ids": [],
                    "assurance_ids": [],
                    "residual_gap_ids": residual_ids,
                }
            )
        dossier_problems = validate_gap_plan_record(pack, manifest, records, gap_id, gap)
        if dossier_problems:
            first = dossier_problems[0]
            raise ClonePackError(first.message, diagnostic=first.code)

    gaps_text = gaps_path.read_text(encoding="utf-8")
    nonterminal = [
        record
        for record in records.values()
        if record.get("kind") == "GAP" and record.get("attributes", {}).get("status") not in TERMINAL_GAP_STATUSES
    ]
    no_open = not nonterminal
    if re.search(r"^- `?NO-OPEN-GAPS`?:\s*(?:true|false)\s*$", gaps_text, flags=re.MULTILINE):
        gaps_text = re.sub(
            r"^- `?NO-OPEN-GAPS`?:\s*(?:true|false)\s*$",
            f"- `NO-OPEN-GAPS`: {'true' if no_open else 'false'}",
            gaps_text,
            flags=re.MULTILINE,
        )
    history_text = "".join(canonical_json(item).replace("\n", "") + "\n" for item in events)
    atomic_write_many(
        {
            index_path: canonical_json(index),
            history_path: history_text,
            gaps_path: gaps_text,
        },
        transaction_root=pack,
        operation=f"gap-transition:{gap_id}:{from_status}->{to_status}",
    )
    return event
