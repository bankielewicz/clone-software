from __future__ import annotations

import copy
import json
import os
import re
import shutil
import stat
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from . import TOOL_VERSION
from .common import (
    ClonePackError,
    atomic_write_many,
    canonical_json,
    case_contract_sha256,
    clean_line,
    load_json,
    recover_atomic_transactions,
    render_template,
    resolve_inside,
    safe_relative_path,
    sha256_bytes,
    sha256_file,
)
from .constants import (
    CHANGE_TYPES,
    ENHANCEMENT_PLAN_FILES,
    ENHANCEMENT_STATUSES,
    ID_PATTERNS,
    LEGAL_ENHANCEMENT_TRANSITIONS,
    PLAN_FILES,
    PLAYBOOKS,
    PRODUCT_TYPES,
)
from .operations import _run_process
from .pack import initialize_v2, utc_now
from .repository import (
    check_repository_snapshot,
    inventory_repository,
    repository_snapshot,
    retained_snapshot,
    write_transaction,
)
from .schema import SchemaDefinitionError, validate_schema_file


SCHEMA_ROOT = Path(__file__).resolve().parents[2] / "assets" / "schemas"
DECISION_KINDS = frozenset({"DEC", "ADR", "GAPDEC"})
EVIDENCE_KINDS = frozenset(
    {"E", "ART", "CAP", "RUN", "PAR", "ASSURE", "FIND", "SBOM", "BUILD", "PROV", "SNAP", "SCOPE", "PRES"}
)
FINAL_EVIDENCE_KINDS = frozenset({"RUN", "CAP", "PAR", "ASSURE", "SNAP", "SCOPE", "PRES"})


def _require_schema(instance: dict[str, Any], filename: str, diagnostic: str) -> None:
    try:
        violations = validate_schema_file(instance, SCHEMA_ROOT / filename)
    except SchemaDefinitionError as exc:
        raise ClonePackError(f"packaged schema is invalid: {exc}", exit_code=70, diagnostic="SCHEMA_INVALID") from exc
    if violations:
        first = violations[0]
        raise ClonePackError(
            f"{first.pointer or '/'}: {first.message}",
            diagnostic=diagnostic,
        )


def _record_map(index: dict[str, Any]) -> dict[str, dict[str, Any]]:
    records = index.get("records")
    if not isinstance(records, list):
        raise ClonePackError("clone index records must be an array", diagnostic="INDEX_INVALID")
    mapped: dict[str, dict[str, Any]] = {}
    for record in records:
        if not isinstance(record, dict) or not isinstance(record.get("id"), str):
            raise ClonePackError("clone index contains a record without an ID", diagnostic="INDEX_INVALID")
        identifier = str(record["id"])
        if identifier in mapped:
            raise ClonePackError(f"duplicate record ID: {identifier}", diagnostic="ID_DUPLICATE")
        mapped[identifier] = record
    return mapped


def _next_id(existing: Iterable[str], prefix: str) -> str:
    numbers = [
        int(identifier.rsplit("-", 1)[1])
        for identifier in existing
        if re.fullmatch(rf"{re.escape(prefix)}-[0-9]+", identifier)
    ]
    return f"{prefix}-{max(numbers, default=0) + 1:03d}"


def _load_enhancement_pack(pack: Path) -> tuple[Path, dict[str, Any], Path, dict[str, Any], Path, dict[str, Any]]:
    root = pack.expanduser().resolve()
    # Every mutating brownfield command enters through this loader. Recover a
    # prepared journal before reading any file so callers never validate a
    # partially promoted before/after image.
    recover_atomic_transactions(root)
    manifest_path = root / "clone_pack.json"
    manifest = load_json(manifest_path)
    if manifest.get("schema_version") != "clone-pack/v2":
        raise ClonePackError("brownfield commands require clone-pack/v2", exit_code=3, diagnostic="SCHEMA_UNSUPPORTED")
    workstream = manifest.get("workstream")
    if not isinstance(workstream, dict) or workstream.get("kind") != "brownfield-enhancement":
        raise ClonePackError("pack is not a brownfield enhancement workstream", exit_code=3, diagnostic="WORKSTREAM_UNSUPPORTED")
    plans = manifest.get("plans")
    if not isinstance(plans, dict) or plans.get("enhancement") != "enhancement_plan.json":
        raise ClonePackError("manifest enhancement plan path is invalid", diagnostic="PLAN_INVALID")
    plan_path = resolve_inside(root, "enhancement_plan.json", must_exist=True)
    plan = load_json(plan_path)
    index_path = resolve_inside(root, str(manifest.get("index_path", "clone_index.json")), must_exist=True)
    index = load_json(index_path)
    return root, manifest, plan_path, plan, index_path, index


def _request_bytes(repository: Path, request_file: Path) -> tuple[str, bytes]:
    supplied = request_file.expanduser()
    if not supplied.is_absolute():
        supplied = repository / supplied
    try:
        lexical = supplied.absolute()
        relative = lexical.relative_to(repository).as_posix()
    except ValueError as exc:
        raise ClonePackError("request file must be beneath the repository root", exit_code=2, diagnostic="REQUEST_OUTSIDE_REPOSITORY") from exc
    current = repository
    for part in Path(relative).parts:
        current = current / part
        try:
            metadata = current.lstat()
        except OSError as exc:
            raise ClonePackError("request file is unavailable", exit_code=2, diagnostic="REQUEST_INVALID") from exc
        if stat.S_ISLNK(metadata.st_mode):
            raise ClonePackError("request file and its ancestors must not be symlinks", exit_code=2, diagnostic="REQUEST_SYMLINK")
    before = supplied.lstat()
    if not stat.S_ISREG(before.st_mode):
        raise ClonePackError("request file must be a regular file", exit_code=2, diagnostic="REQUEST_INVALID")
    try:
        value = supplied.read_bytes()
        text = value.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ClonePackError("request file must be UTF-8", exit_code=2, diagnostic="REQUEST_NOT_UTF8") from exc
    except OSError as exc:
        raise ClonePackError("request file is unreadable", exit_code=4, diagnostic="REQUEST_UNREADABLE") from exc
    after = supplied.lstat()
    identity = lambda item: (item.st_dev, item.st_ino, item.st_mode, item.st_size, item.st_mtime_ns, item.st_ctime_ns)
    if identity(before) != identity(after):
        raise ClonePackError("request file changed during initialization", exit_code=4, diagnostic="REQUEST_CONCURRENT_MUTATION")
    if not text.strip():
        raise ClonePackError("request file must not be empty", exit_code=2, diagnostic="REQUEST_EMPTY")
    return relative, value


def _inventory_contract(
    inventory: dict[str, Any],
    *,
    pack_id: str,
    enhancement_id: str,
    created_at: str,
    protected_dirty_paths: list[str],
) -> dict[str, Any]:
    entries = list(inventory["entries"])
    agents_files = list(inventory["agents_files"])
    verification_commands: list[dict[str, Any]] = []
    return {
        "schema_version": "clone-repository-inventory/v2",
        "pack_id": pack_id,
        "pack_revision": 1,
        "enhancement_id": enhancement_id,
        "inspected_at": created_at,
        "repository_root": inventory["root"],
        "repository_kind": inventory["kind"],
        "git": inventory["git"],
        "entries": entries,
        "dirty_paths": list(inventory["dirty_paths"]),
        "protected_dirty_paths": protected_dirty_paths,
        "agents_files": agents_files,
        "scope_roots": ["."],
        "exclusions": [],
        "instructions": agents_files,
        "components": [],
        "entrypoints": [],
        "public_interfaces": [],
        "data_stores": [],
        "configuration": [],
        "background_jobs": [],
        "manifests": [],
        "lockfiles": [],
        "ci_surfaces": [],
        "deployment_surfaces": [],
        "telemetry": [],
        "verification_commands": verification_commands,
        "unknowns": [],
        "adoption_blockers": [],
    }


def _draft_enhancement_plan(
    *,
    pack_id: str,
    enhancement_id: str,
    title: str,
    change_types: list[str],
    request_source: str,
    request_evidence: str,
    request_sha256: str,
    protected_dirty_paths: list[str],
) -> dict[str, Any]:
    return {
        "schema_version": "clone-enhancement-plan/v2",
        "pack_id": pack_id,
        "pack_revision": 1,
        "enhancement_id": enhancement_id,
        "title": title,
        "status": "DRAFT",
        "authority": {
            "kind": "user-supplied-request",
            "evidence_path": request_evidence,
            "sha256": request_sha256,
        },
        "authority_ids": [],
        "request": {
            "source_path": request_source,
            "evidence_path": request_evidence,
            "sha256": request_sha256,
        },
        "change_types": change_types,
        "target_requirements": [],
        "invariants": [],
        "impact_edges": [],
        "affected_surfaces": [],
        "compatibility": [],
        "delivery_strategy": "in-place",
        "feature_flag": None,
        "expand_contract": None,
        "scope": {
            "allowed_paths": [],
            "forbidden_paths": [],
            "generated_paths": [],
            "rename_policy": "forbid",
            "declared_renames": [],
            "protected_dirty_paths": protected_dirty_paths,
        },
        "preservation_cases": [],
        "change_map": [],
        "slices": [],
        "gates": [],
        "assurance": {"required_ids": [], "result_ids": []},
        "security": {"baseline_findings": [], "candidate_findings": [], "unavailable_data": []},
        "dependency": {"baseline_findings": [], "candidate_findings": [], "unavailable_data": []},
        "migration": {"framework": None, "applied_history": [], "planned": [], "validation_commands": []},
        "observability": {"existing_stack": [], "telemetry_changes": []},
        "rollout": {"strategy": "verified-code-handoff", "steps": [], "deployment_permitted": False},
        "rollback": {"application": [], "data": []},
        "recovery": {"steps": [], "verification_commands": []},
        "halts": [],
        "snapshots": {"adopted": None, "candidate": None},
        "scope_result": None,
        "residual_gap_ids": [],
        "result_references": {"run_ids": [], "preservation_ids": [], "assurance_ids": [], "scope_ids": []},
        "blocked_prior_state": None,
        "verified_revision": None,
    }


def initialize_enhancement_v2(
    *,
    skill_root: Path,
    product_name: str,
    product_type: str,
    playbooks: list[str],
    enhancement_id: str,
    title: str,
    change_types: list[str],
    request_file: Path,
    repo_root: Path,
    output_dir: Path,
    adopt_dirty: bool = False,
    timestamp: str | None = None,
) -> dict[str, Any]:
    product_name = clean_line("product name", product_name)
    title = clean_line("enhancement title", title)
    if product_type not in PRODUCT_TYPES:
        raise ClonePackError("product type is not controlled", exit_code=2, diagnostic="ARG_INVALID")
    selected_playbooks = list(dict.fromkeys(playbooks or ([] if product_type == "hybrid" else [product_type])))
    if any(item not in PLAYBOOKS for item in selected_playbooks):
        raise ClonePackError("playbook is not controlled", exit_code=2, diagnostic="ARG_INVALID")
    if product_type == "hybrid" and len(selected_playbooks) < 2:
        raise ClonePackError("hybrid requires at least two playbooks", exit_code=2, diagnostic="ARG_INVALID")
    if product_type != "hybrid" and product_type not in selected_playbooks:
        selected_playbooks.insert(0, product_type)
    if re.fullmatch(ID_PATTERNS["ENH"], enhancement_id) is None:
        raise ClonePackError("enhancement ID must match ENH-###", exit_code=2, diagnostic="ARG_INVALID")
    selected_change_types = list(dict.fromkeys(change_types))
    if not selected_change_types or any(item not in CHANGE_TYPES for item in selected_change_types):
        raise ClonePackError("change type is not controlled", exit_code=2, diagnostic="ARG_INVALID")

    repository = repo_root.expanduser().resolve()
    if not repository.is_dir():
        raise ClonePackError("repository root is not a directory", exit_code=2, diagnostic="ARG_INVALID")
    request_relative, request_value = _request_bytes(repository, request_file)
    destination = output_dir.expanduser()
    if not destination.is_absolute():
        destination = repository / destination
    destination = destination.resolve()
    try:
        destination.relative_to(repository)
    except ValueError as exc:
        raise ClonePackError("output directory must remain inside repository", exit_code=2, diagnostic="PATH_ESCAPE") from exc
    if destination == repository or destination.exists():
        diagnostic = "OUTPUT_EXISTS" if destination.exists() else "PATH_UNSAFE"
        raise ClonePackError("output directory must be absent and below the repository root", exit_code=2, diagnostic=diagnostic)

    discovered = inventory_repository(repository, pack_root=None)
    dirty_paths = list(discovered["dirty_paths"])
    if discovered["kind"] == "git" and dirty_paths and not adopt_dirty:
        raise ClonePackError(
            "repository has staged, unstaged, untracked, renamed, or deleted paths",
            exit_code=4,
            diagnostic="REPOSITORY_DIRTY",
        )
    protected_dirty_paths = dirty_paths if adopt_dirty else []
    created_at, _ = utc_now(timestamp)
    created = initialize_v2(
        skill_root=skill_root,
        product_name=product_name,
        product_type=product_type,
        playbooks=selected_playbooks,
        source_description=f"Authorized brownfield request {enhancement_id}: {request_relative}",
        repo_root=repository,
        output_dir=destination,
        timestamp=timestamp,
    )
    try:
        manifest_path = created / "clone_pack.json"
        manifest = load_json(manifest_path)
        manifest["workstream"] = {
            "kind": "brownfield-enhancement",
            "mode": "enhancement-plan",
            "enhancement_id": enhancement_id,
            "scaffold_sentinel": "clone-pack/v2-brownfield-enhancement",
        }
        manifest["plans"] = {**PLAN_FILES, **ENHANCEMENT_PLAN_FILES}
        request_evidence = f"evidence/requests/{enhancement_id}/{Path(request_relative).name}"
        inventory = _inventory_contract(
            discovered,
            pack_id=str(manifest["pack_id"]),
            enhancement_id=enhancement_id,
            created_at=created_at,
            protected_dirty_paths=protected_dirty_paths,
        )
        plan = _draft_enhancement_plan(
            pack_id=str(manifest["pack_id"]),
            enhancement_id=enhancement_id,
            title=title,
            change_types=selected_change_types,
            request_source=request_relative,
            request_evidence=request_evidence,
            request_sha256=sha256_bytes(request_value),
            protected_dirty_paths=protected_dirty_paths,
        )
        plan_text = canonical_json(plan)
        anchor = f'"enhancement_id": "{enhancement_id}"'
        anchor_lines = [line for line in plan_text.splitlines(keepends=True) if anchor in line]
        if len(anchor_lines) != 1:
            raise ClonePackError("enhancement plan identity anchor is ambiguous", exit_code=70, diagnostic="INTERNAL_CONTRACT")
        index_path = created / "clone_index.json"
        index = load_json(index_path)
        index["records"].append(
            {
                "id": enhancement_id,
                "kind": "ENH",
                "locator": {
                    "path": "enhancement_plan.json",
                    "anchor": anchor,
                    "sha256": sha256_bytes(anchor_lines[0].encode("utf-8")),
                },
                "links": {
                    "requirements": [],
                    "invariants": [],
                    "changes": [],
                    "preservations": [],
                    "gates": [],
                    "decisions": [],
                    "snapshots": [],
                    "scopes": [],
                    "assurance": [],
                    "gaps": [],
                },
                "applicability": "REQUIRED",
                "state": "DRAFT",
                "attributes": {
                    "status": "DRAFT",
                    "title": title,
                    "change_types": selected_change_types,
                },
            }
        )
        history_path = created / "history" / "enhancement_events.jsonl"
        writes = {
            manifest_path: canonical_json(manifest),
            index_path: canonical_json(index),
            created / "repository_inventory.json": canonical_json(inventory),
            created / "enhancement_plan.json": plan_text,
            created / request_evidence: request_value.decode("utf-8"),
            history_path: "",
        }
        atomic_write_many(writes, transaction_root=created, operation=f"enhancement-init:{enhancement_id}")
    except BaseException:
        shutil.rmtree(created, ignore_errors=True)
        raise
    return {
        "schema_version": "clone-enhancement-init-result/v2",
        "enhancement_id": enhancement_id,
        "pack_path": created.as_posix(),
        "status": "DRAFT",
        "workstream": "brownfield-enhancement",
    }


def _case_contract(case: dict[str, Any]) -> dict[str, Any]:
    return {
        key: value
        for key, value in case.items()
        if key not in {"result", "baseline_result", "regression_result"}
    }


def _case_sha256(case: dict[str, Any]) -> str:
    return sha256_bytes(canonical_json(_case_contract(case)).encode("utf-8"))


def _selected_preservation_cases(
    plan: dict[str, Any],
    case_ids: list[str],
    *,
    all_cases: bool,
) -> list[dict[str, Any]]:
    cases = plan.get("preservation_cases")
    if not isinstance(cases, list) or any(not isinstance(case, dict) for case in cases):
        raise ClonePackError("preservation_cases must be an object array", diagnostic="PLAN_INVALID")
    if len(case_ids) != len(set(case_ids)):
        raise ClonePackError("preservation case selectors must be unique", exit_code=2, diagnostic="ARG_INVALID")
    if all_cases and case_ids:
        raise ClonePackError("--all and --case are mutually exclusive", exit_code=2, diagnostic="ARG_CONFLICT")
    if case_ids:
        requested = set(case_ids)
        selected = [case for case in cases if case.get("id") in requested]
        if {str(case.get("id")) for case in selected} != requested:
            raise ClonePackError("unknown preservation case requested", exit_code=2, diagnostic="CASE_UNKNOWN")
    elif all_cases:
        selected = list(cases)
    else:
        raise ClonePackError("baseline-run/regression requires --case or --all", exit_code=2, diagnostic="ARG_INVALID")
    selected.sort(key=lambda case: str(case.get("id")))
    if not selected:
        raise ClonePackError("preservation selection is empty", diagnostic="CASE_SELECTION_EMPTY")
    for case in selected:
        case_id = case.get("id")
        argv = case.get("argv")
        if not isinstance(case_id, str) or re.fullmatch(ID_PATTERNS["PRES"], case_id) is None:
            raise ClonePackError("preservation case ID must match PRES-###", diagnostic="PLAN_INVALID")
        if not isinstance(argv, list) or not argv or any(not isinstance(item, str) or not item for item in argv):
            raise ClonePackError(f"{case_id} argv must be a non-empty string array", diagnostic="PLAN_INVALID")
        if not isinstance(case.get("expected_exit"), int) or isinstance(case.get("expected_exit"), bool):
            raise ClonePackError(f"{case_id} expected_exit must be an integer", diagnostic="PLAN_INVALID")
        timeout = case.get("timeout_seconds", 300)
        if isinstance(timeout, bool) or not isinstance(timeout, (int, float)) or timeout <= 0 or timeout > 86400:
            raise ClonePackError(f"{case_id} timeout_seconds is invalid", diagnostic="PLAN_INVALID")
        for field in ("artifact_paths", "normalizations"):
            if not isinstance(case.get(field, []), list):
                raise ClonePackError(f"{case_id} {field} must be an array", diagnostic="PLAN_INVALID")
    return selected


def _decision_records(records: dict[str, dict[str, Any]], identifiers: list[str], role: str) -> None:
    if len(identifiers) != len(set(identifiers)):
        raise ClonePackError(f"{role} authority IDs must be unique", diagnostic="PLAN_INVALID")
    for identifier in identifiers:
        record = records.get(identifier)
        if record is None or record.get("kind") not in DECISION_KINDS:
            raise ClonePackError(f"{role} authority is undefined or wrong-kind: {identifier}", diagnostic="REF_UNDEFINED")


def _redact_bytes(value: bytes, rules: list[dict[str, Any]], role: str, records: dict[str, dict[str, Any]]) -> bytes:
    if not rules:
        return value
    try:
        text = value.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ClonePackError(
            f"binary {role} cannot be retained when redaction is required",
            diagnostic="BINARY_REDACTION_UNSUPPORTED",
        ) from exc
    for rule in rules:
        if not isinstance(rule, dict):
            raise ClonePackError(f"{role} redaction must be an object", diagnostic="PLAN_INVALID")
        pattern = rule.get("pattern")
        replacement = rule.get("replacement")
        authorities = rule.get("authority_ids", [])
        if not isinstance(pattern, str) or not isinstance(replacement, str) or not isinstance(authorities, list):
            raise ClonePackError(f"{role} redaction is incomplete", diagnostic="PLAN_INVALID")
        _decision_records(records, [str(item) for item in authorities], f"{role} redaction")
        try:
            text = re.sub(pattern, replacement, text)
        except re.error as exc:
            raise ClonePackError(f"invalid {role} redaction regex: {exc}", diagnostic="PLAN_INVALID") from exc
    return text.encode("utf-8")


def _launch_environment(case: dict[str, Any]) -> dict[str, str]:
    environment = {
        key: os.environ[key]
        for key in ("PATH", "SYSTEMROOT", "WINDIR", "COMSPEC", "PATHEXT", "TMP", "TEMP")
        if key in os.environ
    }
    raw = case.get("environment", {})
    if not isinstance(raw, dict):
        raise ClonePackError("preservation environment must be an object", diagnostic="PLAN_INVALID")
    for key, value in raw.items():
        if not isinstance(key, str) or not isinstance(value, str):
            raise ClonePackError("preservation environment must contain strings", diagnostic="PLAN_INVALID")
        if value.startswith("env:"):
            source = value.removeprefix("env:")
            if source not in os.environ:
                raise ClonePackError(f"required environment variable is unavailable: {source}", exit_code=7, diagnostic="ENVIRONMENT_MISSING")
            environment[key] = os.environ[source]
        else:
            if any(term in key.upper() for term in ("TOKEN", "KEY", "SECRET", "PASSWORD", "AUTH", "COOKIE", "CREDENTIAL")):
                raise ClonePackError(f"secret-like environment key must use env:NAME: {key}", diagnostic="SECRET_LITERAL_FORBIDDEN")
            environment[key] = value
    return environment


def _artifact_record(pack: Path, path: Path, identifier: str, name: str) -> dict[str, Any]:
    return {
        "id": identifier,
        "name": name,
        "path": path.relative_to(pack).as_posix(),
        "size": path.stat().st_size,
        "media_type": "application/octet-stream",
        "sha256": sha256_file(path),
    }


def _run_preservation_process(
    repository: Path,
    case: dict[str, Any],
    records: dict[str, dict[str, Any]],
) -> tuple[int | None, bytes, bytes, dict[str, str] | None]:
    cwd_value = str(case.get("cwd", "."))
    cwd = repository if cwd_value == "." else resolve_inside(repository, cwd_value, must_exist=True)
    if not cwd.is_dir():
        raise ClonePackError("preservation cwd must be a directory", diagnostic="PLAN_INVALID")
    try:
        completed = _run_process(
            [str(item) for item in case["argv"]],
            cwd,
            _launch_environment(case),
            float(case.get("timeout_seconds", 300)),
        )
    except ClonePackError as exc:
        return None, b"", b"", {"code": exc.diagnostic, "message": str(exc)}
    rules = case.get("redactions", [])
    if not isinstance(rules, list):
        raise ClonePackError("preservation redactions must be an array", diagnostic="PLAN_INVALID")
    return (
        completed.returncode,
        _redact_bytes(completed.stdout, rules, "stdout", records),
        _redact_bytes(completed.stderr, rules, "stderr", records),
        None,
    )


def _write_preservation_result(
    pack: Path,
    plan_path: Path,
    plan: dict[str, Any],
    case: dict[str, Any],
    phase: str,
    result: dict[str, Any],
    artifact_values: list[tuple[str, bytes]],
) -> str:
    case_id = str(case["id"])
    output = pack / "evidence" / "preservation" / case_id / phase
    if phase == "regression":
        candidate_id = result.get("candidate_snapshot_id")
        if not isinstance(candidate_id, str) or re.fullmatch(ID_PATTERNS["SNAP"], candidate_id) is None:
            raise ClonePackError("regression result lacks a candidate snapshot ID", exit_code=70, diagnostic="INTERNAL_CONTRACT")
        output = output / candidate_id
    result_path = output / "result.json"
    if output.exists():
        raise ClonePackError(f"preservation evidence already exists: {case_id}/{phase}", diagnostic="OUTPUT_EXISTS")
    writes: dict[Path, str | bytes] = {}
    artifacts: list[dict[str, Any]] = []
    for position, (name, value) in enumerate(artifact_values, 1):
        path = output / name
        writes[path] = value
        artifacts.append(
            {
                "id": f"ART-{case_id}-{phase.upper()}-{position:02d}",
                "name": name,
                "path": path.relative_to(pack).as_posix(),
                "size": len(value),
                "media_type": "application/octet-stream",
                "sha256": sha256_bytes(value),
            }
        )
    result["artifacts"] = artifacts
    _require_schema(result, "preservation-result-v2.schema.json", "PRESERVATION_RESULT_INVALID")
    result_text = canonical_json(result)
    writes[result_path] = result_text
    pointer = {
        "status": result["status"],
        "path": result_path.relative_to(pack).as_posix(),
        "sha256": sha256_bytes(result_text.encode("utf-8")),
    }
    pointer_field = "baseline_result" if phase == "baseline" else "regression_result"
    case[pointer_field] = pointer
    result_holder = case.get("result")
    if isinstance(result_holder, dict):
        result_holder[phase] = pointer
    references = plan.setdefault("result_references", {})
    if not isinstance(references, dict):
        raise ClonePackError("result_references must be an object", diagnostic="PLAN_INVALID")
    preservation_ids = references.setdefault("preservation_ids", [])
    if not isinstance(preservation_ids, list):
        raise ClonePackError("result_references.preservation_ids must be an array", diagnostic="PLAN_INVALID")
    references["preservation_ids"] = sorted(set([str(item) for item in preservation_ids] + [case_id]))
    writes[plan_path] = canonical_json(plan)
    atomic_write_many(
        writes,
        transaction_root=pack,
        operation=f"{phase}-run:{case_id}",
    )
    return pointer["path"]


def _preflight_preservation(
    pack: Path,
    manifest: dict[str, Any],
    plan: dict[str, Any],
    index: dict[str, Any],
    selected: list[dict[str, Any]],
    *,
    phase: str,
) -> dict[str, dict[str, Any]]:
    records = _record_map(index)
    repository = Path(str(manifest.get("repository_root", ""))).resolve()
    expected_state = "READY" if phase == "baseline" else "IMPLEMENTED"
    if plan.get("status") != expected_state:
        raise ClonePackError(
            f"{phase} execution requires enhancement state {expected_state}",
            diagnostic="ENHANCEMENT_STATE_REQUIRED",
        )
    current_candidate_id: str | None = None
    if phase == "regression":
        candidate_pointer, _ = retained_snapshot(pack, "candidate")
        current_candidate_id = str(candidate_pointer["snapshot_id"])
    for case in selected:
        case_id = str(case["id"])
        record = records.get(case_id)
        if record is None or record.get("kind") != "PRES":
            raise ClonePackError(f"preservation case lacks a PRES index record: {case_id}", diagnostic="REF_UNDEFINED")
        attributes = record.get("attributes") if isinstance(record.get("attributes"), dict) else {}
        current_hash = _case_sha256(case)
        legacy_hash = sha256_bytes(
            canonical_json({key: value for key, value in case.items() if key != "result"}).encode("utf-8")
        )
        if attributes.get("case_sha256") not in {current_hash, legacy_hash}:
            raise ClonePackError(f"preservation case hash is stale: {case_id}", exit_code=4, diagnostic="PRESERVATION_CONTRACT_STALE")
        for rule in case.get("normalizations", []):
            authority_ids = rule.get("authority_ids") if isinstance(rule, dict) else None
            if (
                not isinstance(authority_ids, list)
                or not authority_ids
                or any(not isinstance(item, str) or not item for item in authority_ids)
            ):
                raise ClonePackError(f"normalization lacks authority IDs: {case_id}", diagnostic="NORMALIZATION_UNAUTHORIZED")
            _decision_records(records, authority_ids, "normalization")
        known_failure = case.get("known_failure")
        if known_failure is not None:
            if not isinstance(known_failure, dict) or not isinstance(known_failure.get("decision_ids"), list):
                raise ClonePackError(f"known failure is incomplete: {case_id}", diagnostic="KNOWN_FAILURE_INVALID")
            _decision_records(records, [str(item) for item in known_failure["decision_ids"]], "known failure")
        pointer = case.get("baseline_result" if phase == "baseline" else "regression_result")
        if pointer is not None:
            if phase == "baseline":
                raise ClonePackError(f"{phase} result already exists: {case_id}", diagnostic="BASELINE_IMMUTABLE")
            _, prior = _load_pointer(pack, pointer, "regression")
            if prior.get("candidate_snapshot_id") == current_candidate_id:
                raise ClonePackError(f"regression result already exists for {current_candidate_id}: {case_id}", diagnostic="REGRESSION_IMMUTABLE")
        output = pack / "evidence" / "preservation" / case_id / phase
        if phase == "regression" and current_candidate_id is not None:
            output = output / current_candidate_id
        if output.exists() or output.is_symlink():
            raise ClonePackError(f"{phase} evidence already exists: {case_id}", diagnostic="OUTPUT_EXISTS")
        for raw_path in case.get("artifact_paths", []):
            if not isinstance(raw_path, str):
                raise ClonePackError(f"artifact path must be a string: {case_id}", diagnostic="PLAN_INVALID")
            safe_relative_path(raw_path)
        cwd_value = str(case.get("cwd", "."))
        if cwd_value != ".":
            cwd = resolve_inside(repository, cwd_value, must_exist=True)
            if not cwd.is_dir():
                raise ClonePackError(f"preservation cwd is not a directory: {case_id}", diagnostic="PLAN_INVALID")
    return records


def _retained_artifact_values(
    repository: Path,
    case: dict[str, Any],
    records: dict[str, dict[str, Any]],
    stdout: bytes,
    stderr: bytes,
) -> tuple[list[tuple[str, bytes]], dict[str, str] | None]:
    values: list[tuple[str, bytes]] = [("stdout.bin", stdout), ("stderr.bin", stderr)]
    rules = case.get("redactions", [])
    try:
        for position, raw_path in enumerate(case.get("artifact_paths", []), 1):
            relative = safe_relative_path(str(raw_path))
            path = repository.joinpath(*relative.parts)
            metadata = path.lstat()
            if path.is_symlink() or not stat.S_ISREG(metadata.st_mode) or metadata.st_nlink != 1:
                raise ClonePackError(f"preservation artifact must be a direct regular file: {raw_path}", diagnostic="PRESERVATION_ARTIFACT_INVALID")
            value = path.read_bytes()
            value = _redact_bytes(value, rules, f"artifact {raw_path}", records)
            values.append((f"artifact-{position:02d}-{path.name}", value))
    except (ClonePackError, OSError) as exc:
        if isinstance(exc, ClonePackError):
            return values, {"code": exc.diagnostic, "message": str(exc)}
        return values, {"code": "PRESERVATION_ARTIFACT_UNAVAILABLE", "message": str(exc)}
    return values, None


def _load_pointer(pack: Path, pointer: Any, role: str) -> tuple[Path, dict[str, Any]]:
    if not isinstance(pointer, dict) or set(pointer) != {"status", "path", "sha256"}:
        raise ClonePackError(f"{role} result pointer is invalid", diagnostic="RESULT_INVALID")
    path = resolve_inside(pack, str(pointer["path"]), must_exist=True)
    if sha256_file(path) != pointer["sha256"]:
        raise ClonePackError(f"{role} result pointer hash is stale", exit_code=4, diagnostic="ARTIFACT_HASH_MISMATCH")
    return path, load_json(path)


def _preservation_result_base(
    manifest: dict[str, Any],
    plan: dict[str, Any],
    case: dict[str, Any],
    *,
    phase: str,
    adopted_id: str,
    candidate_id: str | None,
    baseline_path: str | None,
    started_at: str,
    ended_at: str,
    observed_exit: int | None,
    status: str,
    diagnostic: dict[str, str] | None,
    details: list[str],
) -> dict[str, Any]:
    return {
        "schema_version": "clone-preservation-result/v2",
        "preservation_id": case["id"],
        "phase": phase,
        "pack_id": manifest["pack_id"],
        "pack_revision": manifest["pack_revision"],
        "enhancement_id": plan["enhancement_id"],
        "case_sha256": _case_sha256(case),
        "adopted_snapshot_id": adopted_id,
        "candidate_snapshot_id": candidate_id,
        "baseline_result_path": baseline_path,
        "started_at": started_at,
        "ended_at": ended_at,
        "argv": list(case["argv"]),
        "cwd": str(case.get("cwd", ".")),
        "expected_exit": int(case["expected_exit"]),
        "observed_exit": observed_exit,
        "status": status,
        "comparator": str(case.get("comparator", "exact")),
        "normalizations": list(case.get("normalizations", [])),
        "known_failure": case.get("known_failure"),
        "diagnostic": diagnostic,
        "details": details,
        "artifacts": [],
        "runner_version": TOOL_VERSION,
    }


def _single_or_batch(results: list[dict[str, Any]], phase: str, exit_code: int) -> dict[str, Any]:
    if len(results) == 1:
        return results[0]
    return {
        "schema_version": "clone-preservation-batch-result/v2",
        "phase": phase,
        "selected_case_ids": [str(result["case_id"]) for result in results],
        "status": "BLOCKED" if exit_code == 7 else "FAIL" if exit_code == 5 else "PASS",
        "exit_code": exit_code,
        "results": results,
    }


def run_preservation_baseline(
    pack: Path,
    case_ids: list[str],
    *,
    all_cases: bool = False,
    timestamp: str | None = None,
) -> tuple[dict[str, Any], int]:
    root, manifest, plan_path, plan, _, index = _load_enhancement_pack(pack)
    recover_atomic_transactions(root)
    selected = _selected_preservation_cases(plan, case_ids, all_cases=all_cases)
    records = _preflight_preservation(root, manifest, plan, index, selected, phase="baseline")
    adopted_pointer, _ = retained_snapshot(root, "adopted")
    check, check_exit = check_repository_snapshot(root, "adopted")
    if check_exit:
        raise ClonePackError(
            f"live repository differs from adopted snapshot: {check['actual_sha256']}",
            exit_code=4,
            diagnostic="ADOPTED_SNAPSHOT_STALE",
        )
    repository = Path(str(manifest["repository_root"])).resolve()
    command_results: list[dict[str, Any]] = []
    exits: list[int] = []
    for case in selected:
        started_at, _ = utc_now(timestamp)
        observed_exit, stdout, stderr, diagnostic = _run_preservation_process(repository, case, records)
        artifact_values, artifact_diagnostic = _retained_artifact_values(repository, case, records, stdout, stderr)
        diagnostic = diagnostic or artifact_diagnostic
        details: list[str] = []
        if diagnostic is not None:
            status = "BLOCKED"
            case_exit = 7
        else:
            known_failure = case.get("known_failure")
            if known_failure is not None:
                matches = (
                    observed_exit == known_failure.get("expected_exit")
                    and sha256_bytes(stdout) == known_failure.get("expected_stdout_sha256")
                    and sha256_bytes(stderr) == known_failure.get("expected_stderr_sha256")
                )
                if matches:
                    status = "PASS"
                    case_exit = 0
                    details.append("authority-approved known failure matched exactly")
                else:
                    status = "FAIL"
                    case_exit = 5
                    diagnostic = {"code": "KNOWN_FAILURE_MISMATCH", "message": "observed failure differs from the authority-approved baseline"}
            elif observed_exit == case["expected_exit"]:
                status = "PASS"
                case_exit = 0
            else:
                status = "FAIL"
                case_exit = 5
                diagnostic = {"code": "BASELINE_EXIT_MISMATCH", "message": f"observed exit {observed_exit}; expected {case['expected_exit']}"}
        ended_at, _ = utc_now(timestamp)
        result = _preservation_result_base(
            manifest,
            plan,
            case,
            phase="baseline",
            adopted_id=str(adopted_pointer["snapshot_id"]),
            candidate_id=None,
            baseline_path=None,
            started_at=started_at,
            ended_at=ended_at,
            observed_exit=observed_exit,
            status=status,
            diagnostic=diagnostic,
            details=details,
        )
        result_path = _write_preservation_result(root, plan_path, plan, case, "baseline", result, artifact_values)
        command_results.append(
            {
                "case_id": case["id"],
                "status": status,
                "adopted_snapshot_id": adopted_pointer["snapshot_id"],
                "result_path": result_path,
            }
        )
        exits.append(case_exit)
    exit_code = 7 if 7 in exits else 5 if 5 in exits else 0
    return _single_or_batch(command_results, "baseline", exit_code), exit_code


def _json_pointer_remove(value: Any, pointer: str) -> None:
    if not pointer.startswith("/"):
        raise ClonePackError("JSON normalization path must be a JSON pointer", diagnostic="PLAN_INVALID")
    parts = [part.replace("~1", "/").replace("~0", "~") for part in pointer[1:].split("/")]
    parent = value
    for part in parts[:-1]:
        if isinstance(parent, dict) and part in parent:
            parent = parent[part]
        elif isinstance(parent, list) and part.isdigit() and int(part) < len(parent):
            parent = parent[int(part)]
        else:
            return
    final = parts[-1] if parts else ""
    if isinstance(parent, dict):
        parent.pop(final, None)
    elif isinstance(parent, list) and final.isdigit() and int(final) < len(parent):
        parent.pop(int(final))


def _normalized_artifact(name: str, value: bytes, case: dict[str, Any]) -> bytes:
    current = value
    for rule in case.get("normalizations", []):
        if name not in rule.get("artifact_names", []):
            continue
        kind = rule.get("kind")
        try:
            text = current.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise ClonePackError(f"normalization requires textual artifact: {name}", diagnostic="NORMALIZATION_BINARY") from exc
        if kind == "regex-replace":
            try:
                text = re.sub(str(rule["pattern"]), str(rule["replacement"]), text)
            except re.error as exc:
                raise ClonePackError(f"invalid normalization regex: {exc}", diagnostic="PLAN_INVALID") from exc
            current = text.encode("utf-8")
        elif kind == "json-pointer-remove":
            try:
                document = json.loads(text)
            except json.JSONDecodeError as exc:
                raise ClonePackError(f"JSON normalization requires JSON artifact: {name}", diagnostic="NORMALIZATION_INVALID") from exc
            _json_pointer_remove(document, str(rule["path"]))
            current = canonical_json(document).encode("utf-8")
        else:
            raise ClonePackError(f"unsupported normalization kind: {kind}", diagnostic="PLAN_INVALID")
    return current


def _json_equal(left: Any, right: Any, tolerance: float) -> bool:
    if isinstance(left, bool) or isinstance(right, bool):
        return left is right
    if isinstance(left, (int, float)) and isinstance(right, (int, float)):
        return abs(float(left) - float(right)) <= tolerance
    if type(left) is not type(right):
        return False
    if isinstance(left, dict):
        return set(left) == set(right) and all(_json_equal(left[key], right[key], tolerance) for key in left)
    if isinstance(left, list):
        return len(left) == len(right) and all(_json_equal(a, b, tolerance) for a, b in zip(left, right, strict=True))
    return left == right


def _compare_artifact(name: str, expected: bytes, actual: bytes, case: dict[str, Any]) -> bool:
    expected = _normalized_artifact(name, expected, case)
    actual = _normalized_artifact(name, actual, case)
    comparator = case.get("comparator", "exact")
    options = case.get("options", {})
    if not isinstance(options, dict):
        raise ClonePackError("preservation comparator options must be an object", diagnostic="PLAN_INVALID")
    if comparator == "exact":
        if options:
            raise ClonePackError("exact comparator accepts no options", diagnostic="PLAN_INVALID")
        return expected == actual
    if comparator == "text":
        try:
            left = expected.decode("utf-8")
            right = actual.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise ClonePackError("text comparator requires UTF-8 artifacts", diagnostic="COMPARATOR_INPUT_INVALID") from exc
        allowed = {"normalize_line_endings", "strip_trailing_whitespace"}
        if set(options) - allowed or any(not isinstance(value, bool) for value in options.values()):
            raise ClonePackError("text comparator options are invalid", diagnostic="PLAN_INVALID")
        if options.get("normalize_line_endings", False):
            left = left.replace("\r\n", "\n").replace("\r", "\n")
            right = right.replace("\r\n", "\n").replace("\r", "\n")
        if options.get("strip_trailing_whitespace", False):
            left = "\n".join(line.rstrip() for line in left.splitlines())
            right = "\n".join(line.rstrip() for line in right.splitlines())
        return left == right
    if comparator == "json":
        if set(options) - {"numeric_tolerance"}:
            raise ClonePackError("JSON comparator options are invalid", diagnostic="PLAN_INVALID")
        tolerance = options.get("numeric_tolerance", 0)
        if isinstance(tolerance, bool) or not isinstance(tolerance, (int, float)) or tolerance < 0:
            raise ClonePackError("numeric_tolerance must be non-negative", diagnostic="PLAN_INVALID")
        try:
            return _json_equal(json.loads(expected), json.loads(actual), float(tolerance))
        except json.JSONDecodeError as exc:
            raise ClonePackError("JSON comparator requires JSON artifacts", diagnostic="COMPARATOR_INPUT_INVALID") from exc
    raise ClonePackError(f"unsupported preservation comparator: {comparator}", diagnostic="PLAN_INVALID")


def run_preservation_regression(
    pack: Path,
    case_ids: list[str],
    *,
    all_cases: bool = False,
    timestamp: str | None = None,
) -> tuple[dict[str, Any], int]:
    root, manifest, plan_path, plan, _, index = _load_enhancement_pack(pack)
    recover_atomic_transactions(root)
    selected = _selected_preservation_cases(plan, case_ids, all_cases=all_cases)
    records = _preflight_preservation(root, manifest, plan, index, selected, phase="regression")
    adopted_pointer, _ = retained_snapshot(root, "adopted")
    candidate_pointer, _ = retained_snapshot(root, "candidate")
    check, check_exit = check_repository_snapshot(root, "candidate")
    if check_exit:
        raise ClonePackError(
            f"live repository differs from candidate snapshot: {check['actual_sha256']}",
            exit_code=4,
            diagnostic="CANDIDATE_SNAPSHOT_STALE",
        )
    repository = Path(str(manifest["repository_root"])).resolve()
    command_results: list[dict[str, Any]] = []
    exits: list[int] = []
    for case in selected:
        baseline_path, baseline = _load_pointer(root, case.get("baseline_result"), "baseline")
        if baseline.get("status") != "PASS" or baseline.get("case_sha256") != _case_sha256(case):
            raise ClonePackError(f"baseline is not a current accepted result: {case['id']}", exit_code=4, diagnostic="BASELINE_STALE")
        baseline_artifacts: dict[str, bytes] = {}
        for artifact in baseline.get("artifacts", []):
            if not isinstance(artifact, dict) or not isinstance(artifact.get("name"), str):
                raise ClonePackError("baseline artifact record is invalid", exit_code=4, diagnostic="RESULT_INVALID")
            artifact_path = resolve_inside(root, str(artifact.get("path")), must_exist=True)
            if sha256_file(artifact_path) != artifact.get("sha256"):
                raise ClonePackError("baseline artifact hash is stale", exit_code=4, diagnostic="ARTIFACT_HASH_MISMATCH")
            baseline_artifacts[str(artifact["name"])] = artifact_path.read_bytes()
        started_at, _ = utc_now(timestamp)
        observed_exit, stdout, stderr, diagnostic = _run_preservation_process(repository, case, records)
        artifact_values, artifact_diagnostic = _retained_artifact_values(repository, case, records, stdout, stderr)
        diagnostic = diagnostic or artifact_diagnostic
        details: list[str] = []
        if diagnostic is not None:
            status = "BLOCKED"
            case_exit = 7
        else:
            candidate_artifacts = dict(artifact_values)
            mismatches: list[str] = []
            if observed_exit != baseline.get("observed_exit"):
                mismatches.append("observed_exit")
            if set(candidate_artifacts) != set(baseline_artifacts):
                mismatches.append("artifact_set")
            for name in sorted(set(candidate_artifacts).intersection(baseline_artifacts)):
                if not _compare_artifact(name, baseline_artifacts[name], candidate_artifacts[name], case):
                    mismatches.append(name)
            if mismatches:
                status = "FAIL"
                case_exit = 5
                details = [f"mismatch: {name}" for name in mismatches]
                diagnostic = {"code": "PRESERVATION_MISMATCH", "message": ", ".join(mismatches)}
            else:
                status = "PASS"
                case_exit = 0
        ended_at, _ = utc_now(timestamp)
        result = _preservation_result_base(
            manifest,
            plan,
            case,
            phase="regression",
            adopted_id=str(adopted_pointer["snapshot_id"]),
            candidate_id=str(candidate_pointer["snapshot_id"]),
            baseline_path=baseline_path.relative_to(root).as_posix(),
            started_at=started_at,
            ended_at=ended_at,
            observed_exit=observed_exit,
            status=status,
            diagnostic=diagnostic,
            details=details,
        )
        result_path = _write_preservation_result(root, plan_path, plan, case, "regression", result, artifact_values)
        command_results.append(
            {
                "case_id": case["id"],
                "status": status,
                "candidate_snapshot_id": candidate_pointer["snapshot_id"],
                "baseline_result_path": baseline_path.relative_to(root).as_posix(),
                "result_path": result_path,
            }
        )
        exits.append(case_exit)
    exit_code = 7 if 7 in exits else 5 if 5 in exits else 0
    return _single_or_batch(command_results, "regression", exit_code), exit_code


def _entry_map(snapshot: dict[str, Any], role: str) -> dict[str, dict[str, Any]]:
    raw_entries = snapshot.get("entries")
    if not isinstance(raw_entries, list):
        raise ClonePackError(f"{role} snapshot entries are invalid", exit_code=4, diagnostic="SNAPSHOT_INVALID")
    entries: dict[str, dict[str, Any]] = {}
    for entry in raw_entries:
        path = entry.get("path") if isinstance(entry, dict) else None
        if not isinstance(path, str) or path in entries:
            raise ClonePackError(f"{role} snapshot contains an invalid or duplicate path", exit_code=4, diagnostic="SNAPSHOT_INVALID")
        entries[path] = entry
    return entries


def _path_in_fence(path: str, fences: Any, role: str) -> bool:
    if not isinstance(fences, list) or any(not isinstance(item, str) for item in fences):
        raise ClonePackError(f"scope {role} must be a path array", diagnostic="PLAN_INVALID")
    for raw in fences:
        if raw.endswith("/"):
            prefix = safe_relative_path(raw[:-1]).as_posix().rstrip("/")
            if path.startswith(prefix + "/"):
                return True
        elif path == safe_relative_path(raw).as_posix():
            return True
    return False


def _declared_rename_pairs(scope: dict[str, Any]) -> list[tuple[str, str, str]]:
    raw = scope.get("declared_renames", [])
    if not isinstance(raw, list):
        raise ClonePackError("scope declared_renames must be an array", diagnostic="PLAN_INVALID")
    pairs: list[tuple[str, str, str]] = []
    for item in raw:
        if not isinstance(item, dict) or set(item) != {"from", "to", "change_id"}:
            raise ClonePackError("declared rename requires exactly from, to, and change_id", diagnostic="PLAN_INVALID")
        source = safe_relative_path(str(item["from"])).as_posix()
        target = safe_relative_path(str(item["to"])).as_posix()
        change_id = str(item["change_id"])
        if source == target or any(source == old and target == new for old, new, _ in pairs):
            raise ClonePackError("declared rename is duplicated or self-referential", diagnostic="PLAN_INVALID")
        pairs.append((source, target, change_id))
    return pairs


def _scope_change_records(
    plan: dict[str, Any], records: dict[str, dict[str, Any]], enhancement_id: str
) -> list[dict[str, Any]]:
    raw = plan.get("change_map")
    if not isinstance(raw, list) or any(not isinstance(item, dict) for item in raw):
        raise ClonePackError("enhancement change_map must be an object array", diagnostic="PLAN_INVALID")
    changes: list[dict[str, Any]] = []
    seen: set[str] = set()
    enhancement = records.get(enhancement_id)
    if enhancement is None or enhancement.get("kind") != "ENH":
        raise ClonePackError(f"enhancement record is undefined: {enhancement_id}", diagnostic="REF_UNDEFINED")
    linked_changes = set(enhancement.get("links", {}).get("changes", []))
    for change in raw:
        identifier = change.get("id")
        operation = change.get("operation")
        paths = change.get("paths")
        if (
            not isinstance(identifier, str)
            or re.fullmatch(ID_PATTERNS["CHANGE"], identifier) is None
            or identifier in seen
            or operation not in {"create", "modify", "delete", "rename", "generate"}
            or not isinstance(paths, list)
            or not paths
            or any(not isinstance(path, str) for path in paths)
        ):
            raise ClonePackError("change_map contains an invalid change contract", diagnostic="PLAN_INVALID")
        normalized = [safe_relative_path(path).as_posix() for path in paths]
        if len(normalized) != len(set(normalized)) or (operation == "rename" and len(normalized) != 2):
            raise ClonePackError(f"change paths are invalid: {identifier}", diagnostic="PLAN_INVALID")
        if operation != "rename" and len(normalized) != 1:
            raise ClonePackError(f"non-rename change must name one exact path: {identifier}", diagnostic="PLAN_INVALID")
        record = records.get(identifier)
        if record is None or record.get("kind") != "CHANGE" or identifier not in linked_changes:
            raise ClonePackError(f"change is not reciprocally linked to {enhancement_id}: {identifier}", diagnostic="REF_UNDEFINED")
        if enhancement_id not in record.get("links", {}).get("enhancements", []):
            raise ClonePackError(f"change lacks enhancement backlink: {identifier}", diagnostic="TRACE_NOT_BIDIRECTIONAL")
        changes.append({**change, "paths": normalized})
        seen.add(identifier)
    if linked_changes != seen:
        raise ClonePackError("ENH change links differ from enhancement_plan.change_map", diagnostic="PLAN_INDEX_DIVERGENCE")
    return changes


def _delta_operation(path: str, added: set[str], removed: set[str], modified: set[str]) -> str:
    if path in added:
        return "create"
    if path in removed:
        return "delete"
    if path in modified:
        return "modify"
    raise ClonePackError(f"path is not a repository delta: {path}", exit_code=70, diagnostic="INTERNAL_CONTRACT")


def _plan_contract_sha256(plan: dict[str, Any]) -> str:
    mutable = {
        "scope_result",
        "result_references",
        "status",
        "verified_revision",
        "blocked_prior_state",
    }
    contract = copy.deepcopy({key: value for key, value in plan.items() if key not in mutable})
    for case in contract.get("preservation_cases", []):
        if isinstance(case, dict):
            for pointer in ("result", "baseline_result", "regression_result"):
                case.pop(pointer, None)
    for gate in contract.get("gates", []):
        if isinstance(gate, dict):
            gate.pop("result_id", None)
    assurance = contract.get("assurance")
    if isinstance(assurance, dict):
        assurance.pop("result_ids", None)
    return sha256_bytes(canonical_json(contract).encode("utf-8"))


def verify_enhancement_scope(
    pack: Path,
    enhancement_id: str,
    *,
    timestamp: str | None = None,
) -> tuple[dict[str, Any], int]:
    root, manifest, plan_path, plan, index_path, index = _load_enhancement_pack(pack)
    recover_atomic_transactions(root)
    if enhancement_id != plan.get("enhancement_id") or enhancement_id != manifest["workstream"].get("enhancement_id"):
        raise ClonePackError("selected enhancement identity differs from the workstream", exit_code=2, diagnostic="ENHANCEMENT_ID_MISMATCH")
    if plan.get("status") != "IMPLEMENTED":
        raise ClonePackError(
            "scope verification requires enhancement state IMPLEMENTED",
            diagnostic="ENHANCEMENT_STATE_REQUIRED",
        )
    records = _record_map(index)
    changes = _scope_change_records(plan, records, enhancement_id)
    scope = plan.get("scope")
    if not isinstance(scope, dict):
        raise ClonePackError("enhancement scope must be an object", diagnostic="PLAN_INVALID")
    adopted_pointer, adopted_snapshot = retained_snapshot(root, "adopted")
    candidate_pointer, candidate_snapshot = retained_snapshot(root, "candidate")
    candidate_check, check_exit = check_repository_snapshot(root, "candidate")
    if check_exit:
        raise ClonePackError(
            f"live repository differs from candidate snapshot: {candidate_check['actual_sha256']}",
            exit_code=4,
            diagnostic="CANDIDATE_SNAPSHOT_STALE",
        )
    adopted = _entry_map(adopted_snapshot, "adopted")
    candidate = _entry_map(candidate_snapshot, "candidate")
    added = set(candidate) - set(adopted)
    removed = set(adopted) - set(candidate)
    modified = {
        path
        for path in set(adopted).intersection(candidate)
        if {key: value for key, value in adopted[path].items() if key != "path"}
        != {key: value for key, value in candidate[path].items() if key != "path"}
    }
    rename_pairs: list[tuple[str, str]] = []
    declared_renames = _declared_rename_pairs(scope)
    if scope.get("rename_policy") == "forbid" and declared_renames:
        raise ClonePackError("rename_policy forbid requires an empty declared_renames array", diagnostic="PLAN_INVALID")
    for source, target, change_id in declared_renames:
        declared_change = next((item for item in changes if item["id"] == change_id), None)
        if declared_change is None or declared_change["operation"] != "rename" or declared_change["paths"] != [source, target]:
            raise ClonePackError("declared rename does not exactly bind its CHANGE", diagnostic="PLAN_INDEX_DIVERGENCE")
        if source in removed and target in added:
            rename_pairs.append((source, target))
    changed = sorted(added | removed | modified)
    matches: list[dict[str, Any]] = []
    violations: list[dict[str, str]] = []
    match_counts = {path: 0 for path in changed}

    rename_change_pairs = {
        (str(change["paths"][0]), str(change["paths"][1])): change
        for change in changes
        if change["operation"] == "rename"
    }
    for source, target in rename_pairs:
        change = rename_change_pairs.get((source, target))
        if change is not None:
            match_counts[source] += 1
            match_counts[target] += 1
            matches.append({"operation": "rename", "paths": [source, target], "change_id": change["id"]})

    renamed_paths = {path for pair in rename_pairs for path in pair}
    for path in changed:
        if path in renamed_paths and match_counts[path]:
            continue
        actual_operation = _delta_operation(path, added, removed, modified)
        candidates = []
        for change in changes:
            operation = str(change["operation"])
            compatible = operation == actual_operation or (operation == "generate" and actual_operation == "create")
            if compatible and path in change["paths"]:
                candidates.append(change)
        match_counts[path] += len(candidates)
        for change in candidates:
            matches.append({"operation": actual_operation, "paths": [path], "change_id": change["id"]})

    for path in changed:
        if match_counts[path] != 1:
            violations.append(
                {
                    "code": "CHANGE_MATCH_COUNT",
                    "path": path,
                    "message": f"path matches {match_counts[path]} declared CHANGE records; exactly one is required",
                }
            )
        if not _path_in_fence(path, scope.get("allowed_paths", []), "allowed_paths"):
            violations.append({"code": "PATH_NOT_ALLOWED", "path": path, "message": "path is outside the allowed fence"})
        if _path_in_fence(path, scope.get("forbidden_paths", []), "forbidden_paths"):
            violations.append({"code": "PATH_FORBIDDEN", "path": path, "message": "path is inside the forbidden fence"})

    protected = scope.get("protected_dirty_paths", [])
    if not isinstance(protected, list) or any(not isinstance(item, str) for item in protected):
        raise ClonePackError("protected_dirty_paths must be a path array", diagnostic="PLAN_INVALID")
    declared_paths = {path for change in changes for path in change["paths"]}
    for path in sorted(set(protected).intersection(changed)):
        if path not in declared_paths:
            violations.append(
                {
                    "code": "PROTECTED_DIRTY_PATH_CHANGED",
                    "path": path,
                    "message": "adopted pre-existing dirty bytes changed without an explicit CHANGE",
                }
            )

    scope_id = _next_id(records, "SCOPE")
    verified_at, _ = utc_now(timestamp)
    unauthorized = sorted({item["path"] for item in violations if item["path"]})
    result = {
        "schema_version": "clone-scope-result/v2",
        "scope_id": scope_id,
        "pack_id": manifest["pack_id"],
        "pack_revision": manifest["pack_revision"],
        "enhancement_id": enhancement_id,
        "verified_at": verified_at,
        "enhancement_plan_sha256": _plan_contract_sha256(plan),
        "adopted_snapshot_id": adopted_pointer["snapshot_id"],
        "adopted_content_sha256": adopted_pointer["content_sha256"],
        "candidate_snapshot_id": candidate_pointer["snapshot_id"],
        "candidate_content_sha256": candidate_pointer["content_sha256"],
        "status": "FAIL" if violations else "PASS",
        "changed_paths": changed,
        "added_paths": sorted(added),
        "removed_paths": sorted(removed),
        "modified_paths": sorted(modified),
        "renames": [{"from": source, "to": target} for source, target in rename_pairs],
        "matches": sorted(matches, key=lambda item: (item["paths"], item["change_id"])),
        "unauthorized_paths": unauthorized,
        "violations": sorted(violations, key=lambda item: (item["path"], item["code"], item["message"])),
        "details": [item["message"] for item in sorted(violations, key=lambda item: (item["path"], item["code"]))],
        "runner_version": TOOL_VERSION,
    }
    _require_schema(result, "scope-result-v2.schema.json", "SCOPE_RESULT_INVALID")
    result_path = root / "evidence" / "scope" / f"{scope_id}.json"
    result_text = canonical_json(result)
    pointer = {
        "scope_id": scope_id,
        "status": result["status"],
        "path": result_path.relative_to(root).as_posix(),
        "sha256": sha256_bytes(result_text.encode("utf-8")),
        "candidate_snapshot_id": candidate_pointer["snapshot_id"],
    }
    plan["scope_result"] = pointer
    plan.setdefault("result_references", {}).setdefault("scope_ids", [])
    plan["result_references"]["scope_ids"] = sorted(
        set(plan["result_references"]["scope_ids"] + [scope_id])
    )
    anchor = f'"scope_id": "{scope_id}"'
    anchor_line = next(line for line in result_text.splitlines(keepends=True) if anchor in line)
    enhancement = records[enhancement_id]
    enhancement.setdefault("links", {}).setdefault("scopes", [])
    enhancement["links"]["scopes"] = sorted(set(enhancement["links"]["scopes"] + [scope_id]))
    index["records"].append(
        {
            "id": scope_id,
            "kind": "SCOPE",
            "locator": {
                "path": result_path.relative_to(root).as_posix(),
                "anchor": anchor,
                "sha256": sha256_bytes(anchor_line.encode("utf-8")),
            },
            "links": {"enhancements": [enhancement_id], "changes": sorted({item["change_id"] for item in matches})},
            "applicability": "REQUIRED",
            "state": "VERIFIED" if not violations else "BLOCKED",
            "attributes": {
                "status": result["status"],
                "candidate_snapshot_id": candidate_pointer["snapshot_id"],
                "result_sha256": pointer["sha256"],
            },
        }
    )
    atomic_write_many(
        {result_path: result_text, plan_path: canonical_json(plan), index_path: canonical_json(index)},
        transaction_root=root,
        operation=f"verify-scope:{enhancement_id}:{scope_id}",
    )
    command = {
        "schema_version": "clone-scope-command-result/v2",
        "scope_id": scope_id,
        "enhancement_id": enhancement_id,
        "status": result["status"],
        "changed_paths": changed,
        "added_paths": sorted(added),
        "removed_paths": sorted(removed),
        "modified_paths": sorted(modified),
        "renames": [{"from": source, "to": target} for source, target in rename_pairs],
        "unauthorized_paths": unauthorized,
        "result_path": result_path.relative_to(root).as_posix(),
        "adopted_snapshot_id": adopted_pointer["snapshot_id"],
        "candidate_snapshot_id": candidate_pointer["snapshot_id"],
    }
    return command, 5 if violations else 0


def _load_enhancement_history(path: Path, enhancement_id: str) -> list[dict[str, Any]]:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except FileNotFoundError as exc:
        raise ClonePackError("enhancement history file is missing", exit_code=4, diagnostic="ENHANCEMENT_HISTORY_MISSING") from exc
    except (OSError, UnicodeError) as exc:
        raise ClonePackError(f"enhancement history is unreadable: {exc}", exit_code=4, diagnostic="ENHANCEMENT_HISTORY_INVALID") from exc
    events: list[dict[str, Any]] = []
    previous_hash = ""
    previous_to = "DRAFT"
    blocked_prior: str | None = None
    previous_timestamp: datetime | None = None
    for sequence, line in enumerate(lines, 1):
        if not line.strip():
            raise ClonePackError("enhancement history contains a blank line", exit_code=4, diagnostic="ENHANCEMENT_HISTORY_INVALID")
        try:
            event = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ClonePackError(f"enhancement history line {sequence} is invalid JSON", exit_code=4, diagnostic="ENHANCEMENT_HISTORY_INVALID") from exc
        if not isinstance(event, dict):
            raise ClonePackError("enhancement history event must be an object", exit_code=4, diagnostic="ENHANCEMENT_HISTORY_INVALID")
        _require_schema(event, "clone-enhancement-event-v2.schema.json", "ENHANCEMENT_HISTORY_INVALID")
        supplied_hash = event.get("event_sha256")
        contract = {key: value for key, value in event.items() if key != "event_sha256"}
        expected_hash = sha256_bytes(canonical_json(contract).encode("utf-8"))
        if (
            event.get("enhancement_id") != enhancement_id
            or event.get("sequence") != sequence
            or event.get("previous_event_sha256") != previous_hash
            or event.get("from") != previous_to
            or supplied_hash != expected_hash
        ):
            raise ClonePackError("enhancement history chain is incomplete or tampered", exit_code=4, diagnostic="ENHANCEMENT_HISTORY_CHAIN_INVALID")
        if event["from"] == "BLOCKED":
            legal = event["to"] == blocked_prior and bool(event.get("evidence_ids"))
            blocked_prior = None if legal else blocked_prior
        else:
            legal = (str(event["from"]), str(event["to"])) in LEGAL_ENHANCEMENT_TRANSITIONS
            if event["to"] == "BLOCKED":
                blocked_prior = str(event["from"])
        if not legal:
            raise ClonePackError("enhancement history contains an illegal transition", exit_code=4, diagnostic="ENHANCEMENT_HISTORY_CHAIN_INVALID")
        try:
            event_timestamp = datetime.fromisoformat(str(event["timestamp"]).replace("Z", "+00:00"))
        except ValueError as exc:
            raise ClonePackError("enhancement history timestamp is invalid", exit_code=4, diagnostic="ENHANCEMENT_HISTORY_CHAIN_INVALID") from exc
        if previous_timestamp is not None and event_timestamp < previous_timestamp:
            raise ClonePackError("enhancement history timestamp regressed", exit_code=4, diagnostic="ENHANCEMENT_HISTORY_CHAIN_INVALID")
        previous_timestamp = event_timestamp
        previous_hash = str(supplied_hash)
        previous_to = str(event["to"])
        events.append(event)
    return events


def _validate_selected_ids(
    records: dict[str, dict[str, Any]],
    identifiers: list[str],
    *,
    role: str,
    permitted_kinds: frozenset[str] | set[str],
) -> list[str]:
    selected = list(dict.fromkeys(identifiers))
    if len(selected) != len(identifiers):
        raise ClonePackError(f"{role} IDs must be unique", exit_code=2, diagnostic="ARG_INVALID")
    for identifier in selected:
        record = records.get(identifier)
        if record is None:
            raise ClonePackError(f"{role} record is undefined: {identifier}", diagnostic="REF_UNDEFINED")
        if record.get("kind") not in permitted_kinds:
            raise ClonePackError(f"{role} record has the wrong kind: {identifier}", diagnostic="REF_WRONG_KIND")
    return selected


def _assert_profile_gate(root: Path, profile: str) -> None:
    from .pack import validate_v2

    validation = validate_v2(root, profile, require_seal=False)
    if validation.exit_code:
        first = validation.sorted_all()[0]
        raise ClonePackError(
            f"{profile} gate failed: {first.path}: {first.code}: {first.message}",
            exit_code=validation.exit_code,
            diagnostic="ENHANCEMENT_PROFILE_GATE",
        )


def _assert_verified_transition_preconditions(
    root: Path,
    manifest: dict[str, Any],
    plan: dict[str, Any],
    index: dict[str, Any],
) -> None:
    _assert_profile_gate(root, "implementation")
    problems = enhancement_profile_diagnostics(
        root,
        manifest,
        plan,
        index,
        "verified-enhancement",
        status_override="VERIFIED",
        require_seal=False,
    )
    if problems:
        first = problems[0]
        raise ClonePackError(
            f"verified-enhancement gate failed: {first['path']}: {first['code']}: {first['message']}",
            exit_code=5 if first.get("severity") == "HOLD" else 1,
            diagnostic="ENHANCEMENT_VERIFICATION_GATE",
        )


def transition_enhancement(
    pack: Path,
    enhancement_id: str,
    target: str,
    *,
    actor: str,
    reason: str,
    evidence_ids: list[str] | None = None,
    decision_ids: list[str] | None = None,
    timestamp: str | None = None,
) -> dict[str, Any]:
    root, manifest, plan_path, plan, index_path, index = _load_enhancement_pack(pack)
    recover_atomic_transactions(root)
    actor = clean_line("actor", actor)
    reason = clean_line("reason", reason)
    if target not in ENHANCEMENT_STATUSES:
        raise ClonePackError("enhancement target state is not controlled", exit_code=2, diagnostic="ARG_INVALID")
    if enhancement_id != plan.get("enhancement_id") or enhancement_id != manifest["workstream"].get("enhancement_id"):
        raise ClonePackError("selected enhancement identity differs from the workstream", exit_code=2, diagnostic="ENHANCEMENT_ID_MISMATCH")
    records = _record_map(index)
    enhancement = records.get(enhancement_id)
    if enhancement is None or enhancement.get("kind") != "ENH":
        raise ClonePackError(f"enhancement record is undefined: {enhancement_id}", diagnostic="REF_UNDEFINED")
    attributes = enhancement.get("attributes") if isinstance(enhancement.get("attributes"), dict) else {}
    current = plan.get("status")
    if current not in ENHANCEMENT_STATUSES or enhancement.get("state") != current or attributes.get("status") != current:
        raise ClonePackError("enhancement state differs between plan and index", exit_code=4, diagnostic="ENHANCEMENT_STATE_DIVERGENCE")
    history_path = root / "history" / "enhancement_events.jsonl"
    events = _load_enhancement_history(history_path, enhancement_id)
    historical_state = str(events[-1]["to"]) if events else "DRAFT"
    if historical_state != current:
        raise ClonePackError("enhancement state differs from its complete history", exit_code=4, diagnostic="ENHANCEMENT_STATE_DIVERGENCE")

    evidence = _validate_selected_ids(
        records,
        list(evidence_ids or []),
        role="evidence",
        permitted_kinds=EVIDENCE_KINDS,
    )
    decisions = _validate_selected_ids(
        records,
        list(decision_ids or []),
        role="decision",
        permitted_kinds=DECISION_KINDS,
    )
    legal = (str(current), target) in LEGAL_ENHANCEMENT_TRANSITIONS
    if current == "BLOCKED":
        prior = plan.get("blocked_prior_state")
        legal = target == prior and prior in {"DRAFT", "READY", "IN_PROGRESS"}
        if not evidence:
            raise ClonePackError("resolving BLOCKED requires resolution evidence", diagnostic="ENHANCEMENT_RESOLUTION_EVIDENCE_REQUIRED")
    if not legal:
        raise ClonePackError(f"illegal enhancement transition: {current} -> {target}", diagnostic="ENHANCEMENT_ILLEGAL_TRANSITION")
    if target == "DECLINED":
        preimplementation = current in {"DRAFT", "READY"} or (
            current == "BLOCKED" and plan.get("blocked_prior_state") in {"DRAFT", "READY"}
        )
        if not preimplementation or not decisions:
            raise ClonePackError("DECLINED is pre-implementation and requires authority", diagnostic="ENHANCEMENT_DECLINE_AUTHORITY_REQUIRED")
    if current == "IMPLEMENTED" and target == "IN_PROGRESS" and not evidence:
        raise ClonePackError("IMPLEMENTED -> IN_PROGRESS requires failed-verification or edit evidence", diagnostic="ENHANCEMENT_REOPEN_EVIDENCE_REQUIRED")
    if current == "IN_PROGRESS" and target == "IMPLEMENTED":
        try:
            candidate_pointer, _ = retained_snapshot(root, "candidate")
            candidate_check, candidate_exit = check_repository_snapshot(root, "candidate")
        except ClonePackError as exc:
            raise ClonePackError(
                f"IMPLEMENTED requires a current candidate snapshot: {exc}",
                exit_code=4,
                diagnostic="CANDIDATE_SNAPSHOT_STALE",
            ) from exc
        if candidate_exit:
            raise ClonePackError(
                f"IMPLEMENTED requires live repository equality with {candidate_pointer['snapshot_id']}",
                exit_code=4,
                diagnostic="CANDIDATE_SNAPSHOT_STALE",
            )
        if str(candidate_pointer["snapshot_id"]) not in evidence:
            raise ClonePackError(
                "IMPLEMENTED transition evidence must include the current candidate SNAP ID",
                diagnostic="ENHANCEMENT_EVIDENCE_REQUIRED",
            )
    if current == "VERIFIED" and target == "IN_PROGRESS":
        prior_revision = plan.get("verified_revision")
        supersedes = manifest.get("supersedes")
        if (
            not isinstance(prior_revision, int)
            or manifest.get("pack_revision", 0) <= prior_revision
            or not isinstance(supersedes, dict)
            or supersedes.get("pack_id") != manifest.get("pack_id")
            or supersedes.get("pack_revision") != prior_revision
            or not evidence
            or not decisions
        ):
            raise ClonePackError(
                "VERIFIED -> IN_PROGRESS requires a successor revision, exact predecessor lineage, contrary evidence, and authority",
                exit_code=4,
                diagnostic="ENHANCEMENT_SUCCESSOR_REQUIRED",
            )
    if current == "DRAFT" and target == "READY":
        _assert_profile_gate(root, "repository-adopted")
    if current == "READY" and target == "IN_PROGRESS":
        _assert_profile_gate(root, "enhancement-ready")
    if current == "IMPLEMENTED" and target == "VERIFIED":
        if not evidence:
            raise ClonePackError("VERIFIED transition requires explicit verification evidence", diagnostic="ENHANCEMENT_EVIDENCE_REQUIRED")
        _assert_verified_transition_preconditions(root, manifest, plan, index)

    occurred_at, _ = utc_now(timestamp)
    if events:
        prior_time = datetime.fromisoformat(str(events[-1]["timestamp"]).replace("Z", "+00:00"))
        current_time = datetime.fromisoformat(occurred_at.replace("Z", "+00:00"))
        if current_time < prior_time:
            raise ClonePackError("enhancement event timestamp precedes prior history", exit_code=4, diagnostic="ENHANCEMENT_HISTORY_CHAIN_INVALID")
    contract = {
        "schema_version": "clone-enhancement-event/v2",
        "event_id": f"ENHEVT-{len(events) + 1:03d}",
        "enhancement_id": enhancement_id,
        "sequence": len(events) + 1,
        "from": current,
        "to": target,
        "timestamp": occurred_at,
        "actor": actor,
        "evidence_ids": evidence,
        "decision_ids": decisions,
        "reason": reason,
        "previous_event_sha256": str(events[-1]["event_sha256"]) if events else "",
    }
    event = {**contract, "event_sha256": sha256_bytes(canonical_json(contract).encode("utf-8"))}
    _require_schema(event, "clone-enhancement-event-v2.schema.json", "ENHANCEMENT_EVENT_INVALID")
    plan["status"] = target
    if target == "BLOCKED":
        plan["blocked_prior_state"] = current
    elif current == "BLOCKED":
        plan["blocked_prior_state"] = None
    if target == "VERIFIED":
        plan["verified_revision"] = manifest["pack_revision"]
    if target == "IN_PROGRESS":
        manifest["workstream"]["mode"] = "enhancement-build"
    enhancement["state"] = target
    attributes["status"] = target
    enhancement["attributes"] = attributes
    history_text = history_path.read_text(encoding="utf-8")
    history_text += json.dumps(event, sort_keys=True, ensure_ascii=False, separators=(",", ":")) + "\n"
    atomic_write_many(
        {
            root / "clone_pack.json": canonical_json(manifest),
            plan_path: canonical_json(plan),
            index_path: canonical_json(index),
            history_path: history_text,
        },
        transaction_root=root,
        operation=f"enhancement-transition:{enhancement_id}:{event['sequence']}",
    )
    return event


def _anchor_digest(root: Path, locator: Any, identifier: str) -> str:
    if not isinstance(locator, dict) or set(locator) != {"path", "anchor", "sha256"}:
        raise ClonePackError(f"record locator is invalid: {identifier}", diagnostic="LOCATOR_INVALID")
    path = resolve_inside(root, str(locator["path"]), must_exist=True)
    if path.is_symlink() or not path.is_file():
        raise ClonePackError(f"record locator path is not a direct file: {identifier}", exit_code=4, diagnostic="LOCATOR_INVALID")
    try:
        lines = path.read_text(encoding="utf-8").splitlines(keepends=True)
    except (OSError, UnicodeError) as exc:
        raise ClonePackError(f"record locator is unreadable: {identifier}: {exc}", exit_code=4, diagnostic="LOCATOR_INVALID") from exc
    anchor = locator.get("anchor")
    if not isinstance(anchor, str) or not anchor:
        raise ClonePackError(f"record anchor is invalid: {identifier}", diagnostic="LOCATOR_INVALID")
    matches = [line for line in lines if anchor in line]
    if len(matches) != 1:
        raise ClonePackError(f"record anchor must occur exactly once: {identifier}", exit_code=4, diagnostic="LOCATOR_INVALID")
    if identifier not in matches[0]:
        raise ClonePackError(f"record anchor does not bind its identity: {identifier}", exit_code=4, diagnostic="LOCATOR_IDENTITY_MISMATCH")
    return sha256_bytes(matches[0].encode("utf-8"))


def _case_locations(manifest: dict[str, Any], plan: dict[str, Any]) -> dict[str, tuple[dict[str, Any], str]]:
    locations: dict[str, tuple[dict[str, Any], str]] = {}
    plan_files = manifest.get("plans") if isinstance(manifest.get("plans"), dict) else {}
    for plan_name in ("capture", "parity", "assurance"):
        path = plan_files.get(plan_name)
        if not isinstance(path, str):
            continue
        instance = load_json(resolve_inside(Path(str(manifest["__pack_root"])), path, must_exist=True))
        raw_cases = instance.get("cases")
        if not isinstance(raw_cases, list):
            continue
        for case in raw_cases:
            if isinstance(case, dict) and isinstance(case.get("id"), str):
                locations[str(case["id"])] = (case, plan_name)
    raw_preservation = plan.get("preservation_cases")
    if isinstance(raw_preservation, list):
        for case in raw_preservation:
            if isinstance(case, dict) and isinstance(case.get("id"), str):
                locations[str(case["id"])] = (case, "preservation")
    return locations


def rehash_targets(
    pack: Path,
    *,
    record_ids: list[str] | None = None,
    case_ids: list[str] | None = None,
) -> dict[str, Any]:
    root, manifest, _, plan, index_path, index = _load_enhancement_pack(pack)
    recover_atomic_transactions(root)
    selected_records = list(record_ids or [])
    selected_cases = list(case_ids or [])
    if not selected_records and not selected_cases:
        raise ClonePackError("rehash requires at least one explicit --record or --case", exit_code=2, diagnostic="ARG_INVALID")
    if len(selected_records) != len(set(selected_records)) or len(selected_cases) != len(set(selected_cases)):
        raise ClonePackError("rehash selectors must be unique", exit_code=2, diagnostic="ARG_INVALID")
    records = _record_map(index)
    updated_records: list[dict[str, str]] = []
    for identifier in selected_records:
        record = records.get(identifier)
        if record is None:
            raise ClonePackError(f"record is undefined: {identifier}", exit_code=2, diagnostic="REF_UNDEFINED")
        if record.get("kind") in FINAL_EVIDENCE_KINDS:
            raise ClonePackError(f"finalized evidence cannot be rehashed: {identifier}", exit_code=4, diagnostic="FINALIZED_EVIDENCE_IMMUTABLE")
        digest = _anchor_digest(root, record.get("locator"), identifier)
        record["locator"]["sha256"] = digest
        updated_records.append({"id": identifier, "sha256": digest})

    manifest_with_root = {**manifest, "__pack_root": root.as_posix()}
    locations = _case_locations(manifest_with_root, plan)
    updated_cases: list[dict[str, str]] = []
    for identifier in selected_cases:
        case_location = locations.get(identifier)
        record = records.get(identifier)
        if case_location is None or record is None or record.get("kind") not in {"CAP", "PAR", "ASSURE", "PRES"}:
            raise ClonePackError(f"case is undefined: {identifier}", exit_code=2, diagnostic="CASE_UNKNOWN")
        case, plan_name = case_location
        if plan_name == "preservation":
            if (
                case.get("baseline_result") is not None
                or case.get("regression_result") is not None
                or case.get("result") not in (None, {})
            ):
                raise ClonePackError(f"finalized preservation case cannot be rehashed: {identifier}", exit_code=4, diagnostic="FINALIZED_EVIDENCE_IMMUTABLE")
            digest = _case_sha256(case)
        else:
            if case.get("result") is not None:
                raise ClonePackError(f"finalized case cannot be rehashed: {identifier}", exit_code=4, diagnostic="FINALIZED_EVIDENCE_IMMUTABLE")
            digest = case_contract_sha256(case)
        attributes = record.get("attributes") if isinstance(record.get("attributes"), dict) else {}
        attributes["case_sha256"] = digest
        record["attributes"] = attributes
        locator_digest = _anchor_digest(root, record.get("locator"), identifier)
        record["locator"]["sha256"] = locator_digest
        updated_cases.append({"id": identifier, "case_sha256": digest, "locator_sha256": locator_digest})
    atomic_write_many(
        {index_path: canonical_json(index)},
        transaction_root=root,
        operation="rehash:" + ",".join(sorted([*selected_records, *selected_cases])),
    )
    return {
        "schema_version": "clone-rehash-result/v2",
        "status": "UPDATED",
        "records": sorted(updated_records, key=lambda item: item["id"]),
        "cases": sorted(updated_cases, key=lambda item: item["id"]),
    }


def _profile_problem(
    problems: list[dict[str, str]],
    path: str,
    code: str,
    message: str,
    *,
    record_id: str = "",
    severity: str = "ERROR",
) -> None:
    problems.append(
        {
            "path": path,
            "code": code,
            "message": message,
            "record_id": record_id,
            "severity": severity,
        }
    )


def _result_document(root: Path, pointer: Any, role: str) -> tuple[Path, dict[str, Any]]:
    if not isinstance(pointer, dict):
        raise ClonePackError(f"{role} result pointer is missing", diagnostic="RESULT_INVALID")
    path_value = pointer.get("path")
    digest = pointer.get("sha256")
    if not isinstance(path_value, str) or not isinstance(digest, str):
        raise ClonePackError(f"{role} result pointer is incomplete", diagnostic="RESULT_INVALID")
    path = resolve_inside(root, path_value, must_exist=True)
    if sha256_file(path) != digest:
        raise ClonePackError(f"{role} result pointer hash is stale", exit_code=4, diagnostic="ARTIFACT_HASH_MISMATCH")
    return path, load_json(path)


def _inventory_ids(items: Any) -> set[str]:
    if not isinstance(items, list):
        return set()
    return {
        str(item["id"])
        for item in items
        if isinstance(item, dict) and isinstance(item.get("id"), str)
    }


def _decision_is_valid(records: dict[str, dict[str, Any]], identifier: str) -> bool:
    return identifier in records and records[identifier].get("kind") in DECISION_KINDS


def _trace_chain_for_requirement(
    records: dict[str, dict[str, Any]], requirement_id: str
) -> list[tuple[str, str, str]]:
    requirement = records.get(requirement_id, {})
    requirement_links = requirement.get("links") if isinstance(requirement.get("links"), dict) else {}
    acceptance = set(requirement_links.get("acceptance", []))
    chains: list[tuple[str, str, str]] = []
    for test_id in requirement_links.get("tests", []):
        test = records.get(str(test_id), {})
        if test.get("kind") != "TEST":
            continue
        test_links = test.get("links") if isinstance(test.get("links"), dict) else {}
        if requirement_id not in test_links.get("requirements", []):
            continue
        shared = sorted(acceptance.intersection(test_links.get("acceptance", [])))
        if not shared:
            continue
        for gate_id in test_links.get("gates", []):
            gate = records.get(str(gate_id), {})
            gate_links = gate.get("links") if isinstance(gate.get("links"), dict) else {}
            if gate.get("kind") == "GATE" and test_id in gate_links.get("tests", []):
                chains.append((shared[0], str(test_id), str(gate_id)))
    return chains


def _load_indexed_results(
    root: Path,
    records: dict[str, dict[str, Any]],
    kind: str,
) -> dict[str, dict[str, Any]]:
    retained: dict[str, dict[str, Any]] = {}
    for identifier, record in records.items():
        if record.get("kind") != kind:
            continue
        locator = record.get("locator")
        path_value = locator.get("path") if isinstance(locator, dict) else None
        if not isinstance(path_value, str):
            continue
        try:
            retained[identifier] = load_json(resolve_inside(root, path_value, must_exist=True))
        except ClonePackError:
            continue
    return retained


def enhancement_profile_diagnostics(
    root: Path,
    manifest: dict[str, Any],
    plan: dict[str, Any],
    index: dict[str, Any],
    profile: str,
    *,
    status_override: str | None = None,
    require_seal: bool = True,
) -> list[dict[str, str]]:
    """Return deterministic semantic diagnostics for one brownfield profile branch."""

    root = root.expanduser().resolve()
    problems: list[dict[str, str]] = []
    records = _record_map(index)
    workstream = manifest.get("workstream") if isinstance(manifest.get("workstream"), dict) else {}
    enhancement_id = str(plan.get("enhancement_id", ""))
    enhancement = records.get(enhancement_id, {})
    inventory_path = root / "repository_inventory.json"
    try:
        inventory = load_json(inventory_path)
    except ClonePackError as exc:
        _profile_problem(problems, "repository_inventory.json", exc.diagnostic, str(exc))
        inventory = {}

    if (
        workstream.get("kind") != "brownfield-enhancement"
        or workstream.get("enhancement_id") != enhancement_id
        or workstream.get("scaffold_sentinel") != "clone-pack/v2-brownfield-enhancement"
    ):
        _profile_problem(
            problems,
            "clone_pack.json",
            "BROWNFIELD_SCAFFOLD_INVALID",
            "workstream identity and exact brownfield scaffold sentinel are required",
            record_id=enhancement_id,
        )
    if enhancement.get("kind") != "ENH":
        _profile_problem(problems, "clone_index.json", "REF_UNDEFINED", "workstream enhancement record is undefined", record_id=enhancement_id)
    actual_status = str(plan.get("status", ""))
    enhancement_attributes = (
        enhancement.get("attributes") if isinstance(enhancement.get("attributes"), dict) else {}
    )
    if (
        actual_status not in ENHANCEMENT_STATUSES
        or enhancement.get("state") != actual_status
        or enhancement_attributes.get("status") != actual_status
    ):
        _profile_problem(
            problems,
            "clone_index.json",
            "ENHANCEMENT_STATE_DIVERGENCE",
            "enhancement state differs between plan and index",
            record_id=enhancement_id,
        )
    try:
        history = _load_enhancement_history(
            root / "history" / "enhancement_events.jsonl",
            enhancement_id,
        )
    except ClonePackError as exc:
        _profile_problem(
            problems,
            "history/enhancement_events.jsonl",
            exc.diagnostic,
            str(exc),
            record_id=enhancement_id,
        )
    else:
        history_state = str(history[-1]["to"]) if history else "DRAFT"
        if history_state != actual_status:
            _profile_problem(
                problems,
                "history/enhancement_events.jsonl",
                "ENHANCEMENT_HISTORY_INCOMPLETE",
                f"history ends in {history_state}; plan/index state is {actual_status}",
                record_id=enhancement_id,
            )
    authority = plan.get("authority")
    request = plan.get("request") if isinstance(plan.get("request"), dict) else {}
    if (
        not isinstance(authority, dict)
        or authority.get("kind") != "user-supplied-request"
        or authority.get("evidence_path") != request.get("evidence_path")
        or authority.get("sha256") != request.get("sha256")
    ):
        _profile_problem(problems, "enhancement_plan.json", "AUTHORITY_INVALID", "workstream authority must bind the immutable supplied request", record_id=enhancement_id)
    try:
        request_path = resolve_inside(root, str(request.get("evidence_path")), must_exist=True)
        if request_path.is_symlink() or not request_path.is_file() or sha256_file(request_path) != request.get("sha256"):
            raise ClonePackError("request evidence bytes differ from the plan", exit_code=4, diagnostic="REQUEST_EVIDENCE_STALE")
    except ClonePackError as exc:
        _profile_problem(problems, "enhancement_plan.json", exc.diagnostic, str(exc), record_id=enhancement_id)
    for authority_id in plan.get("authority_ids", []):
        if not _decision_is_valid(records, str(authority_id)):
            _profile_problem(problems, "enhancement_plan.json", "REF_UNDEFINED", f"authority decision is undefined: {authority_id}", record_id=enhancement_id)

    blockers = inventory.get("adoption_blockers")
    if not isinstance(blockers, list):
        _profile_problem(problems, "repository_inventory.json", "INVENTORY_INVALID", "adoption_blockers must be an array")
    elif blockers:
        _profile_problem(problems, "repository_inventory.json", "ADOPTION_BLOCKED", "repository inventory contains unresolved adoption blockers", severity="HOLD")
    for required_inventory_field in ("instructions", "verification_commands"):
        if not isinstance(inventory.get(required_inventory_field), list):
            _profile_problem(problems, "repository_inventory.json", "INVENTORY_INCOMPLETE", f"{required_inventory_field} must be explicitly inventoried")
    if (
        inventory.get("pack_id") != manifest.get("pack_id")
        or inventory.get("pack_revision") != manifest.get("pack_revision")
        or inventory.get("enhancement_id") != enhancement_id
    ):
        _profile_problem(problems, "repository_inventory.json", "PACK_ID_MISMATCH", "repository inventory identity/revision differs from the workstream")

    adopted_pointer: dict[str, Any] | None = None
    adopted_snapshot: dict[str, Any] | None = None
    try:
        adopted_pointer, adopted_snapshot = retained_snapshot(root, "adopted")
    except ClonePackError as exc:
        _profile_problem(problems, "enhancement_plan.json", exc.diagnostic, str(exc), record_id=enhancement_id)
    else:
        if profile in {"repository-adopted", "enhancement-ready"}:
            try:
                check, exit_code = check_repository_snapshot(root, "adopted")
            except ClonePackError as exc:
                _profile_problem(problems, "repository_inventory.json", exc.diagnostic, str(exc), record_id=enhancement_id)
            else:
                if exit_code:
                    _profile_problem(
                        problems,
                        "repository_inventory.json",
                        "ADOPTED_SNAPSHOT_STALE",
                        f"live repository differs from adopted snapshot: {check['actual_sha256']}",
                        record_id=enhancement_id,
                    )
    if profile == "repository-adopted":
        return sorted(problems, key=lambda item: (item["path"], item["code"], item["record_id"], item["message"]))

    status = status_override or str(plan.get("status", ""))
    if profile == "implementation" and status not in {"IN_PROGRESS", "IMPLEMENTED", "VERIFIED"}:
        _profile_problem(problems, "enhancement_plan.json", "ENHANCEMENT_STATE_REQUIRED", "implementation profile requires IN_PROGRESS, IMPLEMENTED, or VERIFIED", record_id=enhancement_id)
    if profile == "verified-enhancement" and status != "VERIFIED":
        _profile_problem(problems, "enhancement_plan.json", "ENHANCEMENT_NOT_VERIFIED", "verified-enhancement requires lifecycle state VERIFIED", record_id=enhancement_id, severity="HOLD")

    target_requirements = plan.get("target_requirements")
    if not isinstance(target_requirements, list) or not target_requirements:
        _profile_problem(problems, "enhancement_plan.json", "REQUIREMENTS_MISSING", "enhancement-ready requires at least one exact target requirement")
        target_requirements = []
    enhancement_links = enhancement.get("links") if isinstance(enhancement.get("links"), dict) else {}
    if set(enhancement_links.get("requirements", [])) != set(str(item) for item in target_requirements):
        _profile_problem(problems, "clone_index.json", "PLAN_INDEX_DIVERGENCE", "ENH requirement links must exactly match target_requirements", record_id=enhancement_id)
    for requirement_id in target_requirements:
        requirement = records.get(str(requirement_id), {})
        if requirement.get("kind") != "REQ" or enhancement_id not in requirement.get("links", {}).get("enhancements", []):
            _profile_problem(problems, "clone_index.json", "TRACE_NOT_BIDIRECTIONAL", "target requirement lacks an ENH backlink", record_id=str(requirement_id))
            continue
        chains = _trace_chain_for_requirement(records, str(requirement_id))
        if not chains:
            _profile_problem(problems, "clone_index.json", "ACCEPTANCE_CHAIN_MISSING", "requirement lacks a reciprocal REQ -> AC -> TEST -> GATE chain", record_id=str(requirement_id))
        elif not any(records.get(test_id, {}).get("attributes", {}).get("discriminating") is True for _, test_id, _ in chains):
            _profile_problem(problems, "clone_index.json", "DISCRIMINATING_TEST_MISSING", "requirement chain lacks attributes.discriminating=true on a TEST", record_id=str(requirement_id))

    invariants = plan.get("invariants")
    invariant_ids = {
        str(item.get("id")) for item in invariants if isinstance(item, dict) and isinstance(item.get("id"), str)
    } if isinstance(invariants, list) else set()
    if not invariant_ids:
        _profile_problem(problems, "enhancement_plan.json", "INVARIANTS_MISSING", "affected scope requires at least one explicit invariant")
    if set(enhancement_links.get("invariants", [])) != invariant_ids:
        _profile_problem(problems, "clone_index.json", "PLAN_INDEX_DIVERGENCE", "ENH invariant links must exactly match the plan", record_id=enhancement_id)
    for invariant_id in invariant_ids:
        record = records.get(invariant_id, {})
        if record.get("kind") != "INV" or enhancement_id not in record.get("links", {}).get("enhancements", []):
            _profile_problem(problems, "clone_index.json", "TRACE_NOT_BIDIRECTIONAL", "invariant lacks an ENH backlink", record_id=invariant_id)

    impact_edges = plan.get("impact_edges")
    if not isinstance(impact_edges, list) or not impact_edges:
        _profile_problem(problems, "enhancement_plan.json", "IMPACT_MAP_MISSING", "enhancement-ready requires evidence-backed impact edges")
    else:
        for edge in impact_edges:
            if not isinstance(edge, dict):
                continue
            for evidence_id in edge.get("evidence_ids", []):
                if str(evidence_id) not in records:
                    _profile_problem(problems, "enhancement_plan.json", "REF_UNDEFINED", f"impact evidence is undefined: {evidence_id}", record_id=str(edge.get("id", "")))

    affected = set(str(item) for item in plan.get("affected_surfaces", []) if isinstance(item, str))
    public_interfaces = _inventory_ids(inventory.get("public_interfaces"))
    required_compatibility = affected | public_interfaces
    compatibility = plan.get("compatibility") if isinstance(plan.get("compatibility"), list) else []
    compatibility_ids = [str(item.get("surface_id")) for item in compatibility if isinstance(item, dict)]
    if set(compatibility_ids) != required_compatibility or len(compatibility_ids) != len(set(compatibility_ids)):
        _profile_problem(problems, "enhancement_plan.json", "COMPATIBILITY_INCOMPLETE", "every affected or public interface requires exactly one compatibility disposition")
    for item in compatibility:
        if not isinstance(item, dict):
            continue
        identifier = str(item.get("surface_id", ""))
        disposition = item.get("disposition")
        if disposition == "BREAK_APPROVED":
            required_break_fields = {
                "affected_consumers",
                "migration_procedure",
                "deprecation_procedure",
                "version_policy_outcome",
                "compatibility_window",
                "exit_condition",
            }
            if any(item.get(field) in (None, "", []) for field in required_break_fields) or not item.get("decision_ids"):
                _profile_problem(problems, "enhancement_plan.json", "BREAK_APPROVAL_INCOMPLETE", "BREAK_APPROVED lacks its complete authority and consumer migration contract", record_id=identifier)
        for decision_id in item.get("decision_ids", []):
            if not _decision_is_valid(records, str(decision_id)):
                _profile_problem(problems, "enhancement_plan.json", "REF_UNDEFINED", f"compatibility decision is undefined: {decision_id}", record_id=identifier)

    if not affected:
        _profile_problem(problems, "enhancement_plan.json", "AFFECTED_SCOPE_MISSING", "enhancement-ready requires at least one exact affected surface or component")
    inventory_categories = (
        "components",
        "entrypoints",
        "public_interfaces",
        "data_stores",
        "configuration",
        "background_jobs",
        "manifests",
        "lockfiles",
        "ci_surfaces",
        "deployment_surfaces",
        "telemetry",
    )
    for category in inventory_categories:
        if not isinstance(inventory.get(category), list):
            _profile_problem(problems, "repository_inventory.json", "INVENTORY_INCOMPLETE", f"affected-scope inventory category is absent: {category}")
    known_inventory_ids = set().union(*(_inventory_ids(inventory.get(category)) for category in inventory_categories))
    for affected_id in affected:
        if affected_id not in records and affected_id not in known_inventory_ids:
            _profile_problem(problems, "enhancement_plan.json", "REF_UNDEFINED", f"affected surface is not inventoried or indexed: {affected_id}", record_id=affected_id)

    scope = plan.get("scope") if isinstance(plan.get("scope"), dict) else {}
    if not scope.get("allowed_paths"):
        _profile_problem(problems, "enhancement_plan.json", "SCOPE_FENCE_MISSING", "enhancement-ready requires at least one exact allowed path fence")
    try:
        changes = _scope_change_records(plan, records, enhancement_id)
    except ClonePackError as exc:
        _profile_problem(problems, "enhancement_plan.json", exc.diagnostic, str(exc), record_id=enhancement_id)
        changes = []
    if not changes:
        _profile_problem(problems, "enhancement_plan.json", "CHANGE_MAP_MISSING", "enhancement-ready requires at least one exact CHANGE")

    slices = plan.get("slices") if isinstance(plan.get("slices"), list) else []
    if not slices:
        _profile_problem(problems, "enhancement_plan.json", "SLICES_MISSING", "enhancement-ready requires dependency-ordered implementation slices")
    else:
        ordered = sorted(
            [item for item in slices if isinstance(item, dict)],
            key=lambda item: item.get("order", 10**9),
        )
        if [item.get("order") for item in ordered] != list(range(1, len(ordered) + 1)):
            _profile_problem(problems, "enhancement_plan.json", "SLICE_ORDER_INVALID", "slice order values must be contiguous from 1")
        seen_slices: set[str] = set()
        assigned_changes: list[str] = []
        for item in ordered:
            slice_id = str(item.get("id", ""))
            dependencies = set(str(value) for value in item.get("depends_on", []))
            if not dependencies.issubset(seen_slices):
                _profile_problem(problems, "enhancement_plan.json", "SLICE_ORDER_INVALID", "slice depends on a later or undefined slice", record_id=slice_id)
            seen_slices.add(slice_id)
            assigned_changes.extend(str(value) for value in item.get("change_ids", []))
            for test_id in item.get("test_ids", []):
                test = records.get(str(test_id), {})
                if test.get("kind") != "TEST" or test.get("attributes", {}).get("discriminating") is not True:
                    _profile_problem(problems, "clone_index.json", "DISCRIMINATING_TEST_MISSING", "slice test is absent or not explicitly discriminating", record_id=str(test_id))
            for gate_id in item.get("gate_ids", []):
                if records.get(str(gate_id), {}).get("kind") != "GATE":
                    _profile_problem(problems, "clone_index.json", "REF_UNDEFINED", "slice gate is undefined", record_id=str(gate_id))
        change_ids = [str(item.get("id")) for item in changes]
        if sorted(assigned_changes) != sorted(change_ids) or len(assigned_changes) != len(set(assigned_changes)):
            _profile_problem(problems, "enhancement_plan.json", "SLICE_CHANGE_COVERAGE_INVALID", "every CHANGE must be assigned to exactly one slice")

    plan_gates = plan.get("gates") if isinstance(plan.get("gates"), list) else []
    required_gate_ids = {str(item.get("id")) for item in plan_gates if isinstance(item, dict) and item.get("required") is True}
    if not required_gate_ids:
        _profile_problem(problems, "enhancement_plan.json", "GATES_MISSING", "enhancement-ready requires at least one required gate")
    if set(enhancement_links.get("gates", [])) != required_gate_ids:
        _profile_problem(problems, "clone_index.json", "PLAN_INDEX_DIVERGENCE", "ENH gate links must exactly match required plan gates", record_id=enhancement_id)

    strategy = plan.get("delivery_strategy")
    if strategy == "feature-flag":
        flag = plan.get("feature_flag") if isinstance(plan.get("feature_flag"), dict) else {}
        required_flag_fields = {
            "existing_mechanism_evidence_ids",
            "key",
            "owner",
            "default_value",
            "targeting_inputs",
            "off_behavior",
            "on_behavior",
            "error_behavior",
            "telemetry",
            "rollback_action",
            "removal_condition",
        }
        if any(flag.get(field) in (None, "", []) for field in required_flag_fields):
            _profile_problem(problems, "enhancement_plan.json", "FEATURE_FLAG_INCOMPLETE", "feature-flag strategy lacks its complete existing-mechanism behavior contract")
        for evidence_id in flag.get("existing_mechanism_evidence_ids", []):
            if str(evidence_id) not in records:
                _profile_problem(problems, "enhancement_plan.json", "FEATURE_FLAG_MECHANISM_UNEVIDENCED", f"existing flag mechanism evidence is undefined: {evidence_id}")
    if strategy == "expand-contract":
        expansion = plan.get("expand_contract") if isinstance(plan.get("expand_contract"), dict) else {}
        for phase_name in ("expand", "backfill", "switch", "contract"):
            if not isinstance(expansion.get(phase_name), list) or not expansion.get(phase_name):
                _profile_problem(problems, "enhancement_plan.json", "EXPAND_CONTRACT_INCOMPLETE", f"expand-contract phase is absent: {phase_name}")
        if not expansion.get("application_rollback") or not expansion.get("data_rollback"):
            _profile_problem(problems, "enhancement_plan.json", "ROLLBACK_CONTRACT_INCOMPLETE", "expand-contract requires separate application and data rollback")

    required_cases = [
        case
        for case in plan.get("preservation_cases", [])
        if isinstance(case, dict) and case.get("required") is True
    ]
    if not required_cases:
        _profile_problem(problems, "enhancement_plan.json", "PRESERVATION_MISSING", "enhancement-ready requires at least one required preservation case")
    for case in required_cases:
        case_id = str(case.get("id", ""))
        try:
            _, baseline = _result_document(root, case.get("baseline_result"), f"{case_id} baseline")
        except ClonePackError as exc:
            _profile_problem(problems, "enhancement_plan.json", exc.diagnostic, str(exc), record_id=case_id, severity="HOLD")
            continue
        if (
            baseline.get("status") != "PASS"
            or baseline.get("case_sha256") != _case_sha256(case)
            or adopted_pointer is None
            or baseline.get("adopted_snapshot_id") != adopted_pointer.get("snapshot_id")
        ):
            _profile_problem(problems, "enhancement_plan.json", "BASELINE_STALE", "required preservation baseline is not a current accepted PASS", record_id=case_id, severity="HOLD")

    migration = plan.get("migration") if isinstance(plan.get("migration"), dict) else {}
    if adopted_snapshot is not None:
        adopted_entries = _entry_map(adopted_snapshot, "adopted")
        for applied in migration.get("applied_history", []):
            if not isinstance(applied, dict):
                continue
            migration_path = str(applied.get("path", ""))
            entry = adopted_entries.get(migration_path)
            if entry is None or entry.get("type") != "file" or entry.get("sha256") != applied.get("checksum"):
                _profile_problem(problems, "enhancement_plan.json", "APPLIED_MIGRATION_STALE", "applied migration checksum differs from the adopted snapshot", record_id=str(applied.get("id", "")))
    if "data-migration" in plan.get("change_types", []) and (
        not plan.get("rollback", {}).get("application") or not plan.get("rollback", {}).get("data")
    ):
        _profile_problem(problems, "enhancement_plan.json", "ROLLBACK_CONTRACT_INCOMPLETE", "data migration requires separate application and data rollback contracts")
    if plan.get("rollout", {}).get("deployment_permitted") is not False:
        _profile_problem(problems, "enhancement_plan.json", "DEPLOYMENT_FORBIDDEN", "brownfield workflow cannot permit deployment")

    if profile in {"enhancement-ready", "implementation"}:
        return sorted(problems, key=lambda item: (item["path"], item["code"], item["record_id"], item["message"]))

    candidate_pointer: dict[str, Any] | None = None
    candidate_snapshot: dict[str, Any] | None = None
    try:
        candidate_pointer, candidate_snapshot = retained_snapshot(root, "candidate")
        candidate_check, candidate_exit = check_repository_snapshot(root, "candidate")
        if candidate_exit:
            _profile_problem(
                problems,
                "enhancement_plan.json",
                "CANDIDATE_SNAPSHOT_STALE",
                f"live repository differs from candidate snapshot: {candidate_check['actual_sha256']}",
                record_id=enhancement_id,
                severity="HOLD",
            )
    except ClonePackError as exc:
        _profile_problem(problems, "enhancement_plan.json", exc.diagnostic, str(exc), record_id=enhancement_id, severity="HOLD")

    if candidate_snapshot is not None:
        candidate_entries = _entry_map(candidate_snapshot, "candidate")
        for applied in migration.get("applied_history", []):
            if not isinstance(applied, dict):
                continue
            migration_path = str(applied.get("path", ""))
            entry = candidate_entries.get(migration_path)
            if entry is None or entry.get("type") != "file" or entry.get("sha256") != applied.get("checksum"):
                _profile_problem(problems, "enhancement_plan.json", "APPLIED_MIGRATION_MUTATED", "candidate changed an applied migration", record_id=str(applied.get("id", "")), severity="HOLD")

    scope_pointer = plan.get("scope_result")
    try:
        _, scope_result = _result_document(root, scope_pointer, "scope")
    except ClonePackError as exc:
        _profile_problem(problems, "enhancement_plan.json", exc.diagnostic, str(exc), record_id=enhancement_id, severity="HOLD")
        scope_result = {}
    if candidate_pointer is not None and (
        scope_result.get("status") != "PASS"
        or scope_result.get("candidate_snapshot_id") != candidate_pointer.get("snapshot_id")
        or scope_result.get("candidate_content_sha256") != candidate_pointer.get("content_sha256")
        or scope_result.get("enhancement_plan_sha256") != _plan_contract_sha256(plan)
    ):
        _profile_problem(problems, "enhancement_plan.json", "SCOPE_RESULT_STALE", "current candidate lacks a current passing scope result", record_id=enhancement_id, severity="HOLD")

    for case in required_cases:
        case_id = str(case.get("id", ""))
        try:
            _, regression = _result_document(root, case.get("regression_result"), f"{case_id} regression")
        except ClonePackError as exc:
            _profile_problem(problems, "enhancement_plan.json", exc.diagnostic, str(exc), record_id=case_id, severity="HOLD")
            continue
        if candidate_pointer is None or (
            regression.get("status") != "PASS"
            or regression.get("case_sha256") != _case_sha256(case)
            or regression.get("candidate_snapshot_id") != candidate_pointer.get("snapshot_id")
            or regression.get("adopted_snapshot_id") != (adopted_pointer or {}).get("snapshot_id")
        ):
            _profile_problem(problems, "enhancement_plan.json", "PRESERVATION_STALE", "required preservation regression is not a current PASS", record_id=case_id, severity="HOLD")

    result_references = plan.get("result_references") if isinstance(plan.get("result_references"), dict) else {}
    required_preservation_ids = {str(case.get("id")) for case in required_cases}
    if not required_preservation_ids.issubset(
        set(str(item) for item in result_references.get("preservation_ids", []))
    ):
        _profile_problem(problems, "enhancement_plan.json", "PRESERVATION_REFERENCE_MISSING", "result_references omits a required preservation result", severity="HOLD")
    if isinstance(scope_pointer, dict) and scope_pointer.get("scope_id") not in result_references.get("scope_ids", []):
        _profile_problem(problems, "enhancement_plan.json", "SCOPE_REFERENCE_MISSING", "result_references omits the current scope result", severity="HOLD")

    assurance_contract = plan.get("assurance") if isinstance(plan.get("assurance"), dict) else {}
    required_assurance = set(str(item) for item in assurance_contract.get("required_ids", []))
    result_assurance = set(str(item) for item in assurance_contract.get("result_ids", []))
    if not required_assurance.issubset(result_assurance):
        _profile_problem(problems, "enhancement_plan.json", "ASSURANCE_BLOCKED", "required assurance IDs are absent from result_ids", severity="HOLD")
    if not required_assurance.issubset(
        set(str(item) for item in result_references.get("assurance_ids", []))
    ):
        _profile_problem(problems, "enhancement_plan.json", "ASSURANCE_REFERENCE_MISSING", "result_references omits required assurance results", severity="HOLD")
    assurance_plan_path = manifest.get("plans", {}).get("assurance")
    try:
        assurance_plan = load_json(resolve_inside(root, str(assurance_plan_path), must_exist=True))
    except ClonePackError as exc:
        _profile_problem(problems, str(assurance_plan_path), exc.diagnostic, str(exc))
        assurance_plan = {}
    assurance_cases = {
        str(case.get("id")): case
        for case in assurance_plan.get("cases", [])
        if isinstance(case, dict) and isinstance(case.get("id"), str)
    }
    if set(enhancement_links.get("assurance", [])) != required_assurance:
        _profile_problem(problems, "clone_index.json", "PLAN_INDEX_DIVERGENCE", "ENH assurance links must exactly match required assurance IDs", record_id=enhancement_id)
    for assurance_id in sorted(required_assurance):
        case = assurance_cases.get(assurance_id)
        if case is None or records.get(assurance_id, {}).get("kind") != "ASSURE":
            _profile_problem(problems, str(assurance_plan_path), "REF_UNDEFINED", "required assurance case is undefined", record_id=assurance_id)
            continue
        try:
            _, assurance_result = _result_document(root, case.get("result"), f"{assurance_id} assurance")
        except ClonePackError as exc:
            _profile_problem(problems, str(assurance_plan_path), exc.diagnostic, str(exc), record_id=assurance_id, severity="HOLD")
            continue
        if candidate_pointer is None or (
            assurance_result.get("status") != "PASS"
            or assurance_result.get("assurance_id") != assurance_id
            or assurance_result.get("case_sha256") != case_contract_sha256(case)
            or assurance_result.get("clone_revision") != candidate_pointer.get("snapshot_id")
            or assurance_result.get("clone_diff_sha256") != candidate_pointer.get("content_sha256")
        ):
            _profile_problem(problems, str(assurance_plan_path), "ASSURANCE_STALE", "required assurance result is not a current candidate PASS", record_id=assurance_id, severity="HOLD")

    run_results = _load_indexed_results(root, records, "RUN")
    referenced_run_ids = set(str(item) for item in plan.get("result_references", {}).get("run_ids", []))
    for requirement_id in target_requirements:
        passing = False
        for acceptance_id, test_id, gate_id in _trace_chain_for_requirement(records, str(requirement_id)):
            for run_id, run in run_results.items():
                covered = set(str(item) for item in run.get("covered_ids", []))
                if (
                    run.get("result") == "PASS"
                    and run.get("gate_id") == gate_id
                    and {str(requirement_id), acceptance_id, test_id}.issubset(covered)
                    and run.get("oracle_ids")
                    and candidate_pointer is not None
                    and run.get("clone_revision") == candidate_pointer.get("snapshot_id")
                    and run.get("clone_diff_sha256") == candidate_pointer.get("content_sha256")
                    and run_id in referenced_run_ids
                ):
                    passing = True
                    break
            if passing:
                break
        if not passing:
            _profile_problem(problems, "clone_index.json", "VERIFICATION_CHAIN_MISSING", "requirement lacks a current passing REQ -> AC -> TEST -> GATE -> RUN chain", record_id=str(requirement_id), severity="HOLD")

    for gate in plan_gates:
        if not isinstance(gate, dict) or gate.get("required") is not True:
            continue
        run_id = gate.get("result_id")
        run = run_results.get(str(run_id), {})
        if candidate_pointer is None or (
            run.get("result") != "PASS"
            or run.get("gate_id") != gate.get("id")
            or run.get("clone_revision") != candidate_pointer.get("snapshot_id")
            or run.get("clone_diff_sha256") != candidate_pointer.get("content_sha256")
        ):
            _profile_problem(problems, "enhancement_plan.json", "GATE_RESULT_STALE", "required gate lacks a current candidate PASS run", record_id=str(gate.get("id", "")), severity="HOLD")

    for category in ("security", "dependency"):
        findings = plan.get(category) if isinstance(plan.get(category), dict) else {}
        baseline_ids = {
            str(item.get("id"))
            for item in findings.get("baseline_findings", [])
            if isinstance(item, dict)
        }
        for finding in findings.get("candidate_findings", []):
            if not isinstance(finding, dict):
                continue
            identifier = str(finding.get("id", ""))
            if identifier in baseline_ids:
                continue
            severity = finding.get("severity")
            disposition = finding.get("status")
            decisions = [str(item) for item in finding.get("decision_ids", [])]
            if severity in {"critical", "high"} and disposition not in {"resolved", "not-applicable"}:
                _profile_problem(problems, "enhancement_plan.json", "NEW_HIGH_FINDING", f"new {severity} {category} finding blocks verification", record_id=identifier, severity="HOLD")
            elif severity in {"medium", "low", "informational"} and disposition == "open":
                _profile_problem(problems, "enhancement_plan.json", "FINDING_UNDISPOSITIONED", f"new {category} finding lacks an explicit disposition", record_id=identifier, severity="HOLD")
            if disposition in {"accepted", "not-applicable"} and (
                not decisions or any(not _decision_is_valid(records, decision_id) for decision_id in decisions)
            ):
                _profile_problem(problems, "enhancement_plan.json", "FINDING_DISPOSITION_UNAUTHORIZED", f"{category} finding disposition lacks authority", record_id=identifier, severity="HOLD")
        if findings.get("unavailable_data"):
            _profile_problem(problems, "enhancement_plan.json", "NOT_VERIFIED", f"{category} vulnerability data is unavailable", severity="HOLD")

    observability = plan.get("observability") if isinstance(plan.get("observability"), dict) else {}
    if observability.get("telemetry_changes") and not observability.get("existing_stack"):
        _profile_problem(problems, "enhancement_plan.json", "OBSERVABILITY_STACK_MISSING", "telemetry changes require an evidenced existing observability stack", severity="HOLD")

    if require_seal:
        seal_path = str(manifest.get("seal_path", "seal.json"))
        try:
            seal = load_json(resolve_inside(root, seal_path, must_exist=True))
        except ClonePackError as exc:
            _profile_problem(problems, seal_path, exc.diagnostic, str(exc), record_id=enhancement_id)
        else:
            expected_bindings = build_enhancement_seal_bindings(root, manifest, plan, index)
            if seal.get("profile") != "verified-enhancement" or seal.get("enhancement_bindings") != expected_bindings:
                _profile_problem(problems, seal_path, "SEAL_ENHANCEMENT_BINDING", "verified-enhancement seal bindings are absent or stale", record_id=enhancement_id)

    return sorted(problems, key=lambda item: (item["path"], item["code"], item["record_id"], item["message"]))


def _binding_from_pointer(root: Path, identifier: str, pointer: Any, role: str) -> dict[str, str]:
    path, _ = _result_document(root, pointer, role)
    return {"id": identifier, "sha256": sha256_file(path)}


def build_enhancement_seal_bindings(
    root: Path,
    manifest: dict[str, Any] | None = None,
    plan: dict[str, Any] | None = None,
    index: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Resolve the exact retained evidence set bound by a verified-enhancement seal."""

    root = root.expanduser().resolve()
    if manifest is None or plan is None or index is None:
        _, loaded_manifest, _, loaded_plan, _, loaded_index = _load_enhancement_pack(root)
        manifest = loaded_manifest
        plan = loaded_plan
        index = loaded_index
    records = _record_map(index)
    enhancement_id = str(plan["enhancement_id"])
    adopted_pointer, _ = retained_snapshot(root, "adopted")
    candidate_pointer, _ = retained_snapshot(root, "candidate")
    scope_pointer = plan.get("scope_result")
    if not isinstance(scope_pointer, dict) or not isinstance(scope_pointer.get("scope_id"), str):
        raise ClonePackError("current scope result pointer is missing", diagnostic="SCOPE_RESULT_STALE")
    preservation_bindings = []
    for case in sorted(
        [item for item in plan.get("preservation_cases", []) if isinstance(item, dict) and item.get("required") is True],
        key=lambda item: str(item.get("id")),
    ):
        case_id = str(case["id"])
        preservation_bindings.extend(
            [
                _binding_from_pointer(
                    root,
                    f"{case_id}:baseline",
                    case.get("baseline_result"),
                    f"{case_id} baseline",
                ),
                _binding_from_pointer(
                    root,
                    f"{case_id}:regression",
                    case.get("regression_result"),
                    f"{case_id} regression",
                ),
            ]
        )

    assurance_plan_path = manifest.get("plans", {}).get("assurance")
    assurance_plan = load_json(resolve_inside(root, str(assurance_plan_path), must_exist=True))
    assurance_cases = {
        str(case.get("id")): case
        for case in assurance_plan.get("cases", [])
        if isinstance(case, dict) and isinstance(case.get("id"), str)
    }
    assurance_bindings = []
    for assurance_id in sorted(set(str(item) for item in plan.get("assurance", {}).get("required_ids", []))):
        case = assurance_cases.get(assurance_id)
        if case is None:
            raise ClonePackError(f"required assurance case is undefined: {assurance_id}", diagnostic="REF_UNDEFINED")
        assurance_bindings.append(_binding_from_pointer(root, assurance_id, case.get("result"), f"{assurance_id} assurance"))

    run_bindings = []
    for run_id in sorted(set(str(item) for item in plan.get("result_references", {}).get("run_ids", []))):
        record = records.get(run_id)
        locator = record.get("locator") if isinstance(record, dict) else None
        path_value = locator.get("path") if isinstance(locator, dict) else None
        if record is None or record.get("kind") != "RUN" or not isinstance(path_value, str):
            raise ClonePackError(f"referenced run is undefined: {run_id}", diagnostic="REF_UNDEFINED")
        run_path = resolve_inside(root, path_value, must_exist=True)
        run_bindings.append({"id": run_id, "sha256": sha256_file(run_path)})

    return {
        "enhancement_id": enhancement_id,
        "adopted_snapshot": {"id": str(adopted_pointer["snapshot_id"]), "sha256": str(adopted_pointer["sha256"])},
        "candidate_snapshot": {"id": str(candidate_pointer["snapshot_id"]), "sha256": str(candidate_pointer["sha256"])},
        "enhancement_plan_sha256": sha256_file(root / "enhancement_plan.json"),
        "scope_result": _binding_from_pointer(root, str(scope_pointer["scope_id"]), scope_pointer, "scope"),
        "preservation_results": preservation_bindings,
        "assurance_results": assurance_bindings,
        "run_results": run_bindings,
    }
