from __future__ import annotations

import base64
import binascii
import json
import math
import mimetypes
import os
import re
import shutil
import signal
import stat
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from . import TOOL_VERSION
from .common import (
    ClonePackError,
    atomic_write_many,
    atomic_write_json,
    case_contract_sha256,
    canonical_json,
    contract_hashes_for_records,
    gate_execution_contract,
    load_json,
    recover_atomic_transactions,
    resolve_inside,
    safe_relative_path,
    sha256_bytes,
    sha256_file,
)
from .constants import EXIT_HOLD, EXIT_INFRASTRUCTURE
from .pack import utc_now
from .schema import SchemaDefinitionError, load_schema, validate_instance, validate_schema_file


SCHEMA_ROOT = Path(__file__).resolve().parents[2] / "assets" / "schemas"
SENSITIVE_HTTP_HEADERS = {
    "authorization",
    "proxy-authorization",
    "cookie",
    "set-cookie",
    "x-api-key",
}
SENSITIVE_QUERY_NAMES = {
    "token",
    "access_token",
    "api_key",
    "key",
    "secret",
    "password",
    "auth",
    "authorization",
}
SECRET_ENV_TERMS = ("TOKEN", "KEY", "SECRET", "PASSWORD", "AUTH", "COOKIE", "CREDENTIAL")
ENV_REFERENCE = re.compile(r"env:([A-Za-z_][A-Za-z0-9_]*)")
CAPTURE_STAGING_MARKER = ".clone-capture-staging.json"
CAPTURE_RESULT_FIELDS = frozenset(
    {
        "schema_version",
        "capture_id",
        "pack_id",
        "pack_revision",
        "reference_baseline_id",
        "adapter",
        "side",
        "environment_id",
        "case_sha256",
        "clone_revision",
        "clone_diff_sha256",
        "started_at",
        "completed_at",
        "status",
        "acquisition_exit_code",
        "summary",
        "artifacts",
        "redactions",
        "runner_version",
    }
)
CANONICAL_PLAN_PATHS = {
    "capture": "capture_plan.json",
    "parity": "parity_plan.json",
    "scaffold": "scaffold_plan.json",
    "assurance": "assurance_plan.json",
}


class _NoRedirectHandler(urllib.request.HTTPRedirectHandler):
    def redirect_request(
        self,
        request: urllib.request.Request,
        file_pointer: Any,
        code: int,
        message: str,
        headers: Any,
        new_url: str,
    ) -> None:
        return None


def _require_schema(instance: dict[str, Any], schema_name: str, diagnostic: str) -> None:
    try:
        violations = validate_schema_file(instance, SCHEMA_ROOT / schema_name)
    except SchemaDefinitionError as exc:
        raise ClonePackError(f"packaged schema is invalid: {exc}", diagnostic="SCHEMA_INVALID") from exc
    if violations:
        rendered = "; ".join(
            f"{violation.pointer or '/'}: {violation.message}" for violation in violations[:10]
        )
        if len(violations) > 10:
            rendered += f"; {len(violations) - 10} additional violation(s)"
        raise ClonePackError(rendered, diagnostic=diagnostic)


def _require_run_execution_contract(instance: dict[str, Any]) -> None:
    """Validate the retained automatic-run contract before executing its GATE."""

    try:
        run_schema = load_schema((SCHEMA_ROOT / "clone-run-v2.schema.json").resolve())
        definitions = run_schema.get("$defs")
        if not isinstance(definitions, dict) or "executionContract" not in definitions:
            raise SchemaDefinitionError(
                "clone-run-v2 schema does not define $defs.executionContract"
            )
        violations = validate_instance(
            instance,
            {
                "$ref": "#/$defs/executionContract",
                "$defs": definitions,
            },
        )
    except SchemaDefinitionError as exc:
        raise ClonePackError(
            f"packaged execution-contract schema is invalid: {exc}",
            diagnostic="SCHEMA_INVALID",
        ) from exc
    if violations:
        rendered = "; ".join(
            f"{violation.pointer or '/'}: {violation.message}"
            for violation in violations[:10]
        )
        if len(violations) > 10:
            rendered += f"; {len(violations) - 10} additional violation(s)"
        raise ClonePackError(rendered, diagnostic="RUN_CONTRACT_INVALID")


def _load_v2_manifest(pack: Path) -> dict[str, Any]:
    manifest = load_json(pack / "clone_pack.json")
    _require_schema(manifest, "clone-pack-v2.schema.json", "MANIFEST_INVALID")
    return manifest


def _manifest_plan_path(
    pack: Path,
    manifest: dict[str, Any],
    name: str,
    *,
    must_exist: bool = True,
) -> Path:
    plans = manifest.get("plans")
    value = plans.get(name) if isinstance(plans, dict) else None
    if not isinstance(value, str):
        raise ClonePackError(f"manifest plans.{name} must be a relative path", diagnostic="MANIFEST_INVALID")
    expected = CANONICAL_PLAN_PATHS.get(name)
    if expected is None or value != expected:
        raise ClonePackError(
            f"manifest plans.{name} must equal {expected or '<unsupported>'}",
            diagnostic="MANIFEST_PATH_INVALID",
        )
    if must_exist:
        return _require_direct_regular_file(pack, value, role=f"manifest plans.{name}")
    return resolve_inside(pack, value, must_exist=False)


def _manifest_index_path(pack: Path, manifest: dict[str, Any], *, must_exist: bool = True) -> Path:
    value = manifest.get("index_path")
    if not isinstance(value, str):
        raise ClonePackError("manifest index_path must be a relative path", diagnostic="MANIFEST_INVALID")
    if value != "clone_index.json":
        raise ClonePackError("manifest index_path must equal clone_index.json", diagnostic="MANIFEST_PATH_INVALID")
    if must_exist:
        return _require_direct_regular_file(pack, value, role="manifest index_path")
    return resolve_inside(pack, value, must_exist=False)


def _require_real_pack_directory(pack: Path, relative_value: str) -> Path:
    """Return an existing pack directory only when no component is a symlink."""

    relative = safe_relative_path(relative_value)
    current = pack.resolve()
    for part in relative.parts:
        current = current / part
        try:
            metadata = current.lstat()
        except FileNotFoundError as exc:
            raise ClonePackError(
                f"required directory does not exist: {relative_value}",
                diagnostic="FILE_MISSING",
            ) from exc
        if stat.S_ISLNK(metadata.st_mode):
            raise ClonePackError(
                f"pack output directory may not contain symlinks: {relative_value}",
                exit_code=4,
                diagnostic="PATH_UNSAFE",
            )
        if not stat.S_ISDIR(metadata.st_mode):
            raise ClonePackError(
                f"pack output path is not a directory: {relative_value}",
                diagnostic="PATH_UNSAFE",
            )
    try:
        current.resolve(strict=True).relative_to(pack.resolve())
    except (OSError, RuntimeError, ValueError) as exc:
        raise ClonePackError(
            f"pack output directory escapes the pack: {relative_value}",
            exit_code=4,
            diagnostic="PATH_ESCAPE",
        ) from exc
    return current


def _require_direct_regular_file(root: Path, relative_value: str, *, role: str) -> Path:
    """Resolve an existing regular file while rejecting every symlink component."""

    relative = safe_relative_path(relative_value)
    root = root.resolve()
    current = root
    for position, part in enumerate(relative.parts):
        current = current / part
        try:
            metadata = current.lstat()
        except OSError as exc:
            raise ClonePackError(f"{role} is missing: {relative_value}", diagnostic="FILE_MISSING") from exc
        if stat.S_ISLNK(metadata.st_mode):
            raise ClonePackError(
                f"{role} may not use a symlink: {relative_value}",
                diagnostic="PATH_UNSAFE",
            )
        final = position == len(relative.parts) - 1
        if final and not stat.S_ISREG(metadata.st_mode):
            raise ClonePackError(f"{role} must name a regular file", diagnostic="CAPTURE_INPUT_INVALID")
        if not final and not stat.S_ISDIR(metadata.st_mode):
            raise ClonePackError(f"{role} has a non-directory ancestor", diagnostic="PATH_UNSAFE")
    try:
        current.resolve(strict=True).relative_to(root)
    except (OSError, RuntimeError, ValueError) as exc:
        raise ClonePackError(f"{role} escapes its root", diagnostic="PATH_ESCAPE") from exc
    return current


def _validate_selected_plan_cases(
    plan: dict[str, Any],
    cases: list[dict[str, Any]],
    *,
    schema_name: str,
    diagnostic: str,
    pack_id: str,
    pack_revision: int,
) -> None:
    if plan.get("pack_id") != pack_id or plan.get("pack_revision") != pack_revision:
        raise ClonePackError(
            "plan pack_id or pack_revision does not match the manifest",
            diagnostic="PLAN_IDENTITY_STALE",
        )
    candidate = dict(plan)
    candidate["cases"] = cases
    try:
        violations = validate_schema_file(candidate, SCHEMA_ROOT / schema_name)
    except SchemaDefinitionError as exc:
        raise ClonePackError(f"packaged plan schema is invalid: {exc}", diagnostic="SCHEMA_INVALID") from exc
    if violations:
        rendered = "; ".join(
            f"{violation.pointer or '/'}: {violation.message}" for violation in violations[:10]
        )
        if len(violations) > 10:
            rendered += f"; {len(violations) - 10} additional violation(s)"
        raise ClonePackError(rendered, diagnostic=diagnostic)


def _decode_base64_field(value: Any, field: str) -> bytes | None:
    if value is None:
        return None
    try:
        return base64.b64decode(value, validate=True)
    except (binascii.Error, TypeError, ValueError) as exc:
        raise ClonePackError(f"{field} is not valid RFC 4648 base64", diagnostic="CAPTURE_INPUT_INVALID") from exc


def _validate_http_secret_input(url: str) -> None:
    try:
        parsed = urllib.parse.urlsplit(url)
        hostname = parsed.hostname
        parsed.port
        query = urllib.parse.parse_qsl(parsed.query, keep_blank_values=True)
    except (TypeError, ValueError) as exc:
        raise ClonePackError("HTTP URL is invalid", diagnostic="CAPTURE_INPUT_INVALID") from exc
    if parsed.scheme.lower() not in {"http", "https"} or not parsed.netloc or not hostname:
        raise ClonePackError("HTTP URL must be absolute http or https", diagnostic="CAPTURE_INPUT_INVALID")
    if parsed.username is not None or parsed.password is not None:
        raise ClonePackError("HTTP URL userinfo is forbidden", diagnostic="SECRET_INPUT_FORBIDDEN")
    secret_names = sorted({name for name, _ in query if name.lower() in SENSITIVE_QUERY_NAMES})
    if secret_names:
        raise ClonePackError(
            "secret-bearing HTTP query parameter name(s) are forbidden: " + ", ".join(secret_names),
            diagnostic="SECRET_INPUT_FORBIDDEN",
        )


def _resolve_environment_reference(value: str, *, context: str, required: bool) -> str:
    match = ENV_REFERENCE.fullmatch(value)
    if match is None:
        if required:
            raise ClonePackError(
                f"{context} must use env:NAME indirection",
                diagnostic="SECRET_INPUT_FORBIDDEN",
            )
        if value.startswith("env:"):
            raise ClonePackError(f"{context} has an invalid env:NAME reference", diagnostic="SECRET_INPUT_FORBIDDEN")
        return value
    name = match.group(1)
    resolved = os.environ.get(name)
    if resolved is None or resolved == "":
        raise ClonePackError(f"{context} references missing or empty environment variable {name}", diagnostic="SECRET_ENV_MISSING")
    if any(ord(character) < 32 or ord(character) == 127 for character in resolved):
        raise ClonePackError(f"{context} resolved environment value contains a control character", diagnostic="SECRET_ENV_INVALID")
    return resolved


def _resolve_http_request_headers(headers: dict[str, str]) -> list[tuple[str, str]]:
    return [
        (
            name,
            _resolve_environment_reference(
                value,
                context=f"HTTP header {name}",
                required=name.lower() in SENSITIVE_HTTP_HEADERS,
            ),
        )
        for name, value in headers.items()
    ]


def _resolve_capture_environment(environment: dict[str, str]) -> dict[str, str]:
    resolved: dict[str, str] = {}
    for name, value in environment.items():
        secret_like = any(term in name.upper() for term in SECRET_ENV_TERMS)
        resolved[name] = _resolve_environment_reference(
            value,
            context=f"environment variable {name}",
            required=secret_like,
        )
    return resolved


def _redact_http_headers(
    headers: list[tuple[str, str]],
    rules: list[dict[str, Any]],
    *,
    location: str,
) -> tuple[list[tuple[str, str]], list[dict[str, Any]]]:
    retained: list[tuple[str, str]] = []
    events: list[dict[str, Any]] = []
    for raw_name, raw_value in headers:
        name = str(raw_name).lower()
        value = str(raw_value)
        if name in SENSITIVE_HTTP_HEADERS:
            retained.append((name, "[REDACTED]"))
            events.append(
                {
                    "kind": "sensitive-header",
                    "location": location,
                    "name": name,
                    "replacement": "[REDACTED]",
                    "count": 1,
                }
            )
            continue
        redacted, applied = _apply_redactions(value.encode("utf-8"), rules)
        retained.append((name, redacted.decode("utf-8")))
        events.extend(
            {**event, "kind": "regex-header", "location": location, "name": name}
            for event in applied
            if event["count"] > 0
        )
    return sorted(retained), events


def _next_id(existing: list[str], prefix: str) -> str:
    numbers = [int(value.rsplit("-", 1)[1]) for value in existing if re.fullmatch(rf"{re.escape(prefix)}-\d+", value)]
    return f"{prefix}-{max(numbers, default=0) + 1:03d}"


def _artifact(path: Path, pack: Path, identifier: str) -> dict[str, Any]:
    return {
        "id": identifier,
        "path": path.relative_to(pack).as_posix(),
        "size": path.stat().st_size,
        "media_type": mimetypes.guess_type(path.name)[0] or "application/octet-stream",
        "sha256": sha256_file(path),
    }


RUN_COVERED_KINDS = {"REQ", "AC", "TEST"}
RUN_ORACLE_KINDS = {"E", "ART", "CAP"}


def _index_record_map(index: dict[str, Any]) -> dict[str, dict[str, Any]]:
    raw = index.get("records")
    if not isinstance(raw, list):
        raise ClonePackError("clone index records must be an array", diagnostic="INDEX_INVALID")
    records: dict[str, dict[str, Any]] = {}
    for record in raw:
        if not isinstance(record, dict) or not isinstance(record.get("id"), str):
            raise ClonePackError("clone index contains a record without an ID", diagnostic="INDEX_INVALID")
        identifier = record["id"]
        if identifier in records:
            raise ClonePackError(f"duplicate index record ID: {identifier}", diagnostic="ID_DUPLICATE")
        records[identifier] = record
    return records


def _required_record(
    records: dict[str, dict[str, Any]],
    identifier: Any,
    allowed_kinds: set[str],
    role: str,
) -> dict[str, Any]:
    if not isinstance(identifier, str) or not identifier:
        raise ClonePackError(f"{role} must be a non-empty record ID", diagnostic="RUN_CONTRACT_INVALID")
    record = records.get(identifier)
    if record is None:
        raise ClonePackError(f"{role} references missing record: {identifier}", diagnostic="REF_UNDEFINED")
    if record.get("kind") not in allowed_kinds:
        expected = ", ".join(sorted(allowed_kinds))
        raise ClonePackError(
            f"{role} {identifier} must have kind {expected}, not {record.get('kind')}",
            diagnostic="REF_WRONG_KIND",
        )
    return record


def _case_counterpart(
    records: dict[str, dict[str, Any]],
    case: dict[str, Any],
    expected_kind: str,
    role: str,
) -> dict[str, Any]:
    case_id = case.get("id")
    counterpart = _required_record(records, case_id, {expected_kind}, role)
    attributes = counterpart.get("attributes") if isinstance(counterpart.get("attributes"), dict) else {}
    if attributes.get("case_sha256") != case_contract_sha256(case):
        raise ClonePackError(
            f"{role} counterpart case_sha256 differs from the current plan case",
            diagnostic="PLAN_CASE_INDEX_STALE",
        )
    return counterpart


def _rule_authority_ids(rules: Any, role: str) -> list[str]:
    if not isinstance(rules, list):
        raise ClonePackError(f"{role} must be an array", diagnostic="RUN_CONTRACT_INVALID")
    collected: list[str] = []
    for position, rule in enumerate(rules, 1):
        if not isinstance(rule, dict):
            raise ClonePackError(f"{role} item {position} must be an object", diagnostic="RUN_CONTRACT_INVALID")
        collected.extend(_record_id_array(rule.get("authority_ids"), f"{role} item {position} authority_ids"))
    return sorted(set(collected))


def _capture_case_counterpart(records: dict[str, dict[str, Any]], case: dict[str, Any]) -> dict[str, Any]:
    counterpart = _case_counterpart(records, case, "CAP", "capture case")
    environment_id = case.get("environment_id")
    _required_record(records, environment_id, {"ENV"}, "capture environment")
    authority_ids = sorted(
        set(_record_id_array(case.get("authorization_decision_ids", []), "capture authorization_decision_ids"))
        | set(_rule_authority_ids(case.get("redactions", []), "capture redactions"))
    )
    for authority_id in authority_ids:
        _required_record(records, authority_id, {"DEC", "ADR", "GAPDEC"}, "capture authority")
    links = counterpart.get("links") if isinstance(counterpart.get("links"), dict) else {}
    linked_environments = _record_id_array(links.get("environments", []), "CAP environments")
    if linked_environments != [environment_id]:
        raise ClonePackError(
            "CAP counterpart environments must exactly match the capture case",
            diagnostic="PLAN_CASE_INDEX_TRACE_INVALID",
        )
    linked_decisions = _record_id_array(links.get("decisions", []), "CAP decisions")
    if linked_decisions != authority_ids:
        raise ClonePackError(
            "CAP counterpart decisions must exactly match the union of authorization_decision_ids and redaction authority_ids",
            diagnostic="PLAN_CASE_INDEX_TRACE_INVALID",
        )
    return counterpart


def _parity_case_counterpart(
    records: dict[str, dict[str, Any]],
    case: dict[str, Any],
    reference_case: dict[str, Any],
    clone_case: dict[str, Any],
) -> dict[str, Any]:
    counterpart = _case_counterpart(records, case, "PAR", "parity case")
    _capture_case_counterpart(records, reference_case)
    _capture_case_counterpart(records, clone_case)
    capture_ids = sorted([str(reference_case["id"]), str(clone_case["id"])])
    links = counterpart.get("links") if isinstance(counterpart.get("links"), dict) else {}
    linked_captures = _record_id_array(links.get("captures", []), "PAR captures")
    if linked_captures != capture_ids:
        raise ClonePackError(
            "PAR counterpart captures must exactly match the parity case",
            diagnostic="PLAN_CASE_INDEX_TRACE_INVALID",
        )
    authority_ids = _rule_authority_ids(case.get("normalizations", []), "parity normalizations")
    for authority_id in authority_ids:
        _required_record(records, authority_id, {"DEC", "ADR", "GAPDEC"}, "parity normalization authority")
    linked_decisions = _record_id_array(links.get("decisions", []), "PAR decisions")
    if linked_decisions != authority_ids:
        raise ClonePackError(
            "PAR counterpart decisions must exactly match normalization authority_ids",
            diagnostic="PLAN_CASE_INDEX_TRACE_INVALID",
        )
    return counterpart


def _record_id_array(value: Any, role: str) -> list[str]:
    if (
        not isinstance(value, list)
        or any(not isinstance(item, str) or not item for item in value)
        or len(value) != len(set(value))
    ):
        raise ClonePackError(f"{role} must be a unique record-ID array", diagnostic="RUN_CONTRACT_INVALID")
    return sorted(value)


def _governing_contract_hashes(
    records: dict[str, dict[str, Any]],
    identifiers: list[str],
) -> dict[str, str]:
    return contract_hashes_for_records(records, identifiers)


def _next_run_paths(
    pack: Path,
    manifest: dict[str, Any],
    records: dict[str, dict[str, Any]],
) -> tuple[str, Path, Path]:
    run_directory = resolve_inside(pack, str(manifest.get("runs_path", "runs")), must_exist=True)
    if not run_directory.is_dir():
        raise ClonePackError("runs_path must name a directory", diagnostic="RUNS_PATH_INVALID")
    existing = {path.stem for path in run_directory.glob("RUN-*.json")}
    existing.update(
        identifier
        for identifier, record in records.items()
        if record.get("kind") == "RUN" and re.fullmatch(r"RUN-\d{3,}", identifier)
    )
    artifact_root = run_directory / "artifacts"
    if artifact_root.is_dir():
        existing.update(path.name for path in artifact_root.glob("RUN-*") if path.is_dir())
    run_id = _next_id(sorted(existing), "RUN")
    run_path = run_directory / f"{run_id}.json"
    artifact_dir = artifact_root / run_id
    if run_path.exists() or artifact_dir.exists() or run_id in records:
        raise ClonePackError(f"run output already exists: {run_id}", diagnostic="OUTPUT_EXISTS")
    return run_id, run_path, artifact_dir


def _run_index_links(
    records: dict[str, dict[str, Any]],
    covered_ids: list[str],
    oracle_ids: list[str],
    gate_id: str | None,
) -> dict[str, list[str]]:
    links = {
        "tests": sorted(identifier for identifier in covered_ids if records[identifier].get("kind") == "TEST"),
        "acceptance": sorted(identifier for identifier in covered_ids if records[identifier].get("kind") == "AC"),
        "oracles": sorted(oracle_ids),
        "requirements": sorted(identifier for identifier in covered_ids if records[identifier].get("kind") == "REQ"),
    }
    if gate_id is not None:
        links["gates"] = [gate_id]
    return links


def _add_run_backlinks(
    records: dict[str, dict[str, Any]],
    run_id: str,
    covered_ids: list[str],
    oracle_ids: list[str],
    gate_id: str | None,
) -> None:
    """Add every reciprocal RUN edge in the same index mutation as the RUN record."""

    target_ids = [*covered_ids, *oracle_ids]
    if gate_id is not None:
        target_ids.append(gate_id)
    for target_id in sorted(set(target_ids)):
        target = records[target_id]
        links = target.get("links")
        if not isinstance(links, dict):
            raise ClonePackError(
                f"run backlink target has invalid links: {target_id}",
                diagnostic="RUN_CONTRACT_INVALID",
            )
        runs = links.setdefault("runs", [])
        if not isinstance(runs, list) or any(not isinstance(item, str) for item in runs):
            raise ClonePackError(
                f"run backlink target has an invalid runs relation: {target_id}",
                diagnostic="RUN_CONTRACT_INVALID",
            )
        if run_id not in runs:
            runs.append(run_id)
            runs.sort()


def _apply_redactions(value: bytes, rules: list[dict[str, Any]]) -> tuple[bytes, list[dict[str, Any]]]:
    if not rules:
        return value, []
    try:
        text = value.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ClonePackError(
            "redaction rules require UTF-8 input; binary content must be excluded or pre-redacted",
            diagnostic="REDACTION_UNSUPPORTED",
        ) from exc
    applied: list[dict[str, Any]] = []
    for rule in rules:
        if not isinstance(rule, dict) or set(rule) != {"pattern", "replacement", "authority_ids"}:
            raise ClonePackError("redaction rule requires pattern, replacement, authority_ids", diagnostic="REDACTION_INVALID")
        if not isinstance(rule["pattern"], str) or not rule["pattern"] or not isinstance(rule["replacement"], str):
            raise ClonePackError("redaction pattern must be non-empty and replacement must be a string", diagnostic="REDACTION_INVALID")
        authorities = rule["authority_ids"]
        if (
            not isinstance(authorities, list)
            or not authorities
            or any(not isinstance(item, str) or not item for item in authorities)
            or len(authorities) != len(set(authorities))
        ):
            raise ClonePackError("redaction authority_ids must be a non-empty unique string array", diagnostic="REDACTION_INVALID")
        try:
            text, count = re.subn(rule["pattern"], rule["replacement"], text)
        except re.error as exc:
            raise ClonePackError(f"invalid redaction pattern: {exc}", diagnostic="REDACTION_INVALID") from exc
        applied.append({"pattern": rule["pattern"], "replacement": rule["replacement"], "count": count, "authority_ids": rule["authority_ids"]})
    return text.encode("utf-8"), applied


def _redact_json_strings(
    value: Any,
    rules: list[dict[str, Any]],
    *,
    location: str,
) -> tuple[Any, list[dict[str, Any]]]:
    """Apply declared regex rules to every string value without changing JSON keys."""

    if isinstance(value, str):
        redacted, events = _apply_redactions(value.encode("utf-8"), rules)
        return redacted.decode("utf-8"), [
            {**event, "kind": "regex-structured", "location": location}
            for event in events
            if event["count"] > 0
        ]
    if isinstance(value, list):
        retained: list[Any] = []
        events: list[dict[str, Any]] = []
        for position, item in enumerate(value):
            redacted, applied = _redact_json_strings(
                item,
                rules,
                location=f"{location}/{position}",
            )
            retained.append(redacted)
            events.extend(applied)
        return retained, events
    if isinstance(value, dict):
        retained_object: dict[str, Any] = {}
        events = []
        for key, item in value.items():
            redacted, applied = _redact_json_strings(
                item,
                rules,
                location=f"{location}/{key}",
            )
            retained_object[key] = redacted
            events.extend(applied)
        return retained_object, events
    return value, []


def _redact_file_in_place(
    path: Path,
    rules: list[dict[str, Any]],
    *,
    location: str,
) -> list[dict[str, Any]]:
    try:
        metadata = path.lstat()
    except OSError as exc:
        raise ClonePackError(f"cannot inspect capture artifact: {path}", diagnostic="CAPTURE_OUTPUT_UNSAFE") from exc
    if not stat.S_ISREG(metadata.st_mode) or metadata.st_nlink != 1:
        raise ClonePackError(
            f"capture artifact is not a private regular file: {path}",
            diagnostic="CAPTURE_OUTPUT_UNSAFE",
        )
    if not rules:
        return []
    try:
        value = path.read_bytes()
        redacted, events = _apply_redactions(value, rules)
    except ClonePackError:
        # Never promote an unredacted binary or otherwise unsafe artifact.
        try:
            if path.lstat().st_ino == metadata.st_ino and stat.S_ISREG(path.lstat().st_mode):
                path.unlink()
        except OSError:
            pass
        raise
    path.write_bytes(redacted)
    return [
        {**event, "kind": "regex-artifact", "location": location}
        for event in events
        if event["count"] > 0
    ]


def _write_capture_artifact(directory: Path, name: str, value: bytes, rules: list[dict[str, Any]]) -> tuple[Path, list[dict[str, Any]]]:
    redacted, applied = _apply_redactions(value, rules)
    path = directory / name
    path.write_bytes(redacted)
    return path, applied


def _snapshot_tree(root: Path) -> list[dict[str, Any]]:
    if not root.exists():
        raise ClonePackError(f"snapshot path does not exist: {root}", diagnostic="CAPTURE_INPUT_MISSING")
    entries: list[dict[str, Any]] = []
    candidates = [root] if root.is_file() or root.is_symlink() else sorted(root.rglob("*"))
    base = root.parent if root.is_file() or root.is_symlink() else root
    for path in candidates:
        relative = path.relative_to(base).as_posix()
        info = path.lstat()
        entry: dict[str, Any] = {"path": relative, "mode": stat.S_IMODE(info.st_mode)}
        if path.is_symlink():
            entry.update({"type": "symlink", "target": os.readlink(path)})
        elif path.is_dir():
            entry["type"] = "directory"
        elif path.is_file():
            entry.update({"type": "file", "size": info.st_size, "sha256": sha256_file(path)})
        else:
            entry["type"] = "other"
        entries.append(entry)
    return entries


def _resolve_executable(argv0: str, cwd: Path, environment: dict[str, str]) -> str:
    candidate = Path(argv0)
    if candidate.is_absolute():
        resolved = candidate
    elif "/" in argv0 or "\\" in argv0:
        resolved = (cwd / candidate).resolve()
    else:
        found = shutil.which(argv0, path=environment.get("PATH"))
        if found is None:
            raise ClonePackError(
                f"required executable is unavailable: {argv0}",
                exit_code=EXIT_INFRASTRUCTURE,
                diagnostic="CAPABILITY_MISSING",
            )
        resolved = Path(found)
    if not resolved.is_file() or not os.access(resolved, os.X_OK):
        raise ClonePackError(
            f"required executable is unavailable: {argv0}",
            exit_code=EXIT_INFRASTRUCTURE,
            diagnostic="CAPABILITY_MISSING",
        )
    return str(resolved)


def _run_process(argv: list[str], cwd: Path, environment: dict[str, str], timeout: float, stdin: bytes | None = None) -> subprocess.CompletedProcess[bytes]:
    if not argv or any(not isinstance(item, str) or not item for item in argv):
        raise ClonePackError("process argv must be a non-empty string array", diagnostic="CAPTURE_INPUT_INVALID")
    _resolve_executable(argv[0], cwd, environment)
    try:
        return subprocess.run(
            argv,
            cwd=cwd,
            env=environment,
            input=stdin,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout,
            shell=False,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise ClonePackError(f"process exceeded timeout of {timeout} seconds", exit_code=EXIT_INFRASTRUCTURE, diagnostic="CAPTURE_TIMEOUT") from exc
    except OSError as exc:
        raise ClonePackError(f"process could not start: {exc}", exit_code=EXIT_INFRASTRUCTURE, diagnostic="CAPTURE_INFRASTRUCTURE") from exc


def _capture_http(case: dict[str, Any], directory: Path) -> dict[str, Any]:
    data = case["input"]
    method = data["method"].upper()
    if case.get("side") == "reference" and method not in {"GET", "HEAD", "OPTIONS"} and (
        not case.get("safe_test_environment") or not case.get("authorization_decision_ids")
    ):
        raise ClonePackError(
            "mutating reference HTTP capture requires safe_test_environment and authorization_decision_ids",
            diagnostic="AUTHORIZATION_REQUIRED",
        )
    url = data["url"]
    _validate_http_secret_input(url)
    body = _decode_base64_field(data.get("body_base64"), "body_base64")
    request_headers = _resolve_http_request_headers(data["headers"])
    try:
        request = urllib.request.Request(url, data=body, headers=dict(request_headers), method=method)
    except (TypeError, ValueError) as exc:
        raise ClonePackError(f"HTTP request input is invalid: {exc}", diagnostic="CAPTURE_INPUT_INVALID") from exc
    started = time.monotonic()
    try:
        opener = urllib.request.build_opener(_NoRedirectHandler())
        response = opener.open(request, timeout=float(case.get("timeout_seconds", 30)))
        response_body = response.read()
        status = response.status
        headers = list(response.headers.items())
    except urllib.error.HTTPError as exc:
        response_body = exc.read()
        status = exc.code
        headers = list(exc.headers.items())
    except (TypeError, ValueError) as exc:
        raise ClonePackError(f"HTTP request input is invalid: {exc}", diagnostic="CAPTURE_INPUT_INVALID") from exc
    except (urllib.error.URLError, TimeoutError) as exc:
        raise ClonePackError(f"HTTP capture failed: {exc}", exit_code=EXIT_INFRASTRUCTURE, diagnostic="CAPTURE_INFRASTRUCTURE") from exc
    elapsed_ms = round((time.monotonic() - started) * 1000, 3)
    rules = case["redactions"]
    body_path, applied = _write_capture_artifact(directory, "response.body", response_body, rules)
    request_body_path = None
    if body is not None:
        request_body_path, request_applied = _write_capture_artifact(directory, "request.body", body, rules)
        applied.extend(request_applied)
    retained_request_headers, request_header_redactions = _redact_http_headers(
        request_headers, rules, location="request_headers"
    )
    retained_response_headers, response_header_redactions = _redact_http_headers(
        [(str(key), str(value)) for key, value in headers], rules, location="response_headers"
    )
    applied.extend(request_header_redactions)
    applied.extend(response_header_redactions)
    metadata = {
        "method": method,
        "url": url,
        "redirect_policy": "disabled",
        "request_headers": retained_request_headers,
        "status": status,
        "response_headers": retained_response_headers,
        "elapsed_ms_context": elapsed_ms,
    }
    metadata, metadata_redactions = _redact_json_strings(metadata, rules, location="http")
    applied.extend(metadata_redactions)
    metadata_path = directory / "http.json"
    atomic_write_json(metadata_path, metadata)
    artifacts = [metadata_path, body_path]
    if request_body_path:
        artifacts.append(request_body_path)
    return {"summary": metadata, "paths": artifacts, "redactions": applied}


def _capture_process(pack: Path, manifest: dict[str, Any], case: dict[str, Any], directory: Path) -> dict[str, Any]:
    if case.get("side") == "reference" and (
        not case.get("safe_test_environment") or not case.get("authorization_decision_ids")
    ):
        raise ClonePackError(
            "reference process capture requires safe_test_environment and authorization_decision_ids",
            diagnostic="AUTHORIZATION_REQUIRED",
        )
    data = case["input"]
    repository = Path(str(manifest["repository_root"])).resolve()
    cwd_value = data["cwd"]
    cwd = repository if cwd_value == "." else resolve_inside(repository, cwd_value, must_exist=True)
    environment = _resolve_capture_environment(data["environment"])
    for key in ("PATH", "SYSTEMROOT", "WINDIR", "COMSPEC", "PATHEXT", "TMP", "TEMP"):
        if key in os.environ and key not in environment:
            environment[key] = os.environ[key]
    stdin = _decode_base64_field(data.get("stdin_base64"), "stdin_base64")
    completed = _run_process(
        data["argv"], cwd, environment, float(case["timeout_seconds"]), stdin
    )
    rules = case["redactions"]
    stdout_path, stdout_redactions = _write_capture_artifact(directory, "stdout.bin", completed.stdout, rules)
    stderr_path, stderr_redactions = _write_capture_artifact(directory, "stderr.bin", completed.stderr, rules)
    metadata = {"argv": data["argv"], "cwd": cwd_value, "exit_code": completed.returncode}
    metadata, metadata_redactions = _redact_json_strings(metadata, rules, location="process")
    metadata_path = directory / "process.json"
    atomic_write_json(metadata_path, metadata)
    return {
        "summary": metadata,
        "paths": [metadata_path, stdout_path, stderr_path],
        "redactions": [*stdout_redactions, *stderr_redactions, *metadata_redactions],
    }


def _capture_filesystem(manifest: dict[str, Any], case: dict[str, Any], directory: Path) -> dict[str, Any]:
    data = case["input"]
    repository = Path(str(manifest["repository_root"])).resolve()
    target_value = data["path"]
    target = repository if target_value == "." else resolve_inside(repository, target_value, must_exist=True)
    snapshot = {"root": target_value, "entries": _snapshot_tree(target)}
    snapshot, applied = _redact_json_strings(snapshot, case["redactions"], location="filesystem")
    path = directory / "filesystem.json"
    atomic_write_json(path, snapshot)
    return {"summary": {"entry_count": len(snapshot["entries"])}, "paths": [path], "redactions": applied}


def _capture_manual(pack: Path, case: dict[str, Any], directory: Path) -> dict[str, Any]:
    data = case["input"]
    source = _require_direct_regular_file(pack, data["source_path"], role="manual source_path")
    manual_directory = directory / "manual"
    try:
        manual_directory.mkdir()
    except FileExistsError as exc:
        raise ClonePackError("manual capture output namespace already exists", diagnostic="CAPTURE_OUTPUT_COLLISION") from exc
    rules = case["redactions"]
    destination, applied = _write_capture_artifact(manual_directory, source.name, source.read_bytes(), rules)
    summary, summary_redactions = _redact_json_strings(
        {"source_path": data.get("source_path")},
        rules,
        location="manual",
    )
    return {
        "summary": summary,
        "paths": [destination],
        "redactions": [*applied, *summary_redactions],
    }


def _capture_web(pack: Path, manifest: dict[str, Any], case: dict[str, Any], directory: Path) -> dict[str, Any]:
    data = case["input"]
    driver = data["driver_argv"]
    driver_directory = directory / "web"
    try:
        driver_directory.mkdir()
    except FileExistsError as exc:
        raise ClonePackError("web capture output namespace already exists", diagnostic="CAPTURE_OUTPUT_COLLISION") from exc
    custom_case = dict(case)
    driver_environment = dict(data["environment"])
    driver_environment["CLONE_CAPTURE_OUTPUT"] = str(driver_directory)
    custom_case["input"] = {"argv": driver, "cwd": data["cwd"], "environment": driver_environment}
    result = _capture_process(pack, manifest, custom_case, directory)
    try:
        driver_metadata = driver_directory.lstat()
    except OSError as exc:
        raise ClonePackError("web driver output namespace disappeared", diagnostic="CAPTURE_OUTPUT_UNSAFE") from exc
    if not stat.S_ISDIR(driver_metadata.st_mode):
        raise ClonePackError("web driver output namespace is not a real directory", diagnostic="CAPTURE_OUTPUT_UNSAFE")
    manifest_path = driver_directory / "web-driver-result.json"
    if not manifest_path.exists():
        raise ClonePackError("web driver did not emit web-driver-result.json", exit_code=EXIT_INFRASTRUCTURE, diagnostic="CAPTURE_DRIVER_INVALID")
    try:
        manifest_metadata = manifest_path.lstat()
        if not stat.S_ISREG(manifest_metadata.st_mode) or manifest_metadata.st_nlink != 1:
            raise ClonePackError("web driver result is not a regular file", diagnostic="CAPTURE_DRIVER_INVALID")
    except OSError as exc:
        raise ClonePackError("cannot inspect web driver result", diagnostic="CAPTURE_DRIVER_INVALID") from exc
    driver_result = load_json(manifest_path)
    if set(driver_result) != {"schema_version", "artifacts", "summary"} or driver_result.get("schema_version") != "clone-web-capture-result/v1":
        raise ClonePackError(
            "web driver result requires exactly schema_version, artifacts, and summary",
            diagnostic="CAPTURE_DRIVER_INVALID",
        )
    emitted = driver_result["artifacts"]
    if (
        not isinstance(emitted, list)
        or not emitted
        or any(not isinstance(relative, str) or not relative for relative in emitted)
        or len(emitted) != len(set(emitted))
        or not isinstance(driver_result["summary"], dict)
    ):
        raise ClonePackError(
            "web driver artifacts must be a non-empty unique relative-path array and summary must be an object",
            diagnostic="CAPTURE_DRIVER_INVALID",
        )
    rules = case["redactions"]
    summary, summary_redactions = _redact_json_strings(
        driver_result["summary"],
        rules,
        location="web/summary",
    )
    driver_result["summary"] = summary
    atomic_write_json(manifest_path, driver_result)
    paths = [*result["paths"], manifest_path]
    reserved = {"web-driver-result.json"}
    artifact_redactions: list[dict[str, Any]] = []
    for relative in emitted:
        safe_relative_path(relative)
        if relative in reserved or relative.split("/", 1)[0] in reserved:
            raise ClonePackError(f"web driver artifact uses a reserved path: {relative}", diagnostic="CAPTURE_DRIVER_INVALID")
        redacted_relative, path_events = _redact_json_strings(
            relative,
            rules,
            location="web/artifact-path",
        )
        if redacted_relative != relative or path_events:
            raise ClonePackError(
                f"web driver artifact path requires pre-redaction: {relative}",
                diagnostic="REDACTION_UNSUPPORTED",
            )
        emitted_path = _require_direct_regular_file(
            driver_directory,
            relative,
            role="web driver artifact",
        )
        try:
            emitted_metadata = emitted_path.lstat()
        except OSError as exc:
            raise ClonePackError(f"cannot inspect web driver artifact: {relative}", diagnostic="CAPTURE_DRIVER_INVALID") from exc
        if not stat.S_ISREG(emitted_metadata.st_mode) or emitted_metadata.st_nlink != 1:
            raise ClonePackError(f"web driver artifact is not a file: {relative}", diagnostic="CAPTURE_DRIVER_INVALID")
        artifact_redactions.extend(
            _redact_file_in_place(emitted_path, rules, location=f"web/artifact/{relative}")
        )
        paths.append(emitted_path)
    result["paths"] = paths
    result["summary"]["web"] = summary
    result["redactions"].extend([*summary_redactions, *artifact_redactions])
    return result


def _capture_time(timestamp: str | None) -> str:
    return utc_now(timestamp)[0]


def _capture_cwd(manifest: dict[str, Any], cwd_value: str) -> Path:
    repository = Path(str(manifest["repository_root"])).resolve()
    return repository if cwd_value == "." else resolve_inside(repository, cwd_value, must_exist=True)


def _capture_launch_environment(declared: dict[str, str]) -> dict[str, str]:
    environment = _resolve_capture_environment(declared)
    for key in ("PATH", "SYSTEMROOT", "WINDIR", "COMSPEC", "PATHEXT", "TMP", "TEMP"):
        if key in os.environ and key not in environment:
            environment[key] = os.environ[key]
    return environment


def _validate_lifecycle_authorization(case: dict[str, Any]) -> None:
    lifecycle = case.get("lifecycle")
    if not isinstance(lifecycle, dict):
        return
    has_command = any(lifecycle.get(phase) is not None for phase in ("setup", "teardown"))
    if case.get("side") == "reference" and has_command and (
        not case.get("safe_test_environment") or not case.get("authorization_decision_ids")
    ):
        raise ClonePackError(
            "reference lifecycle commands require safe_test_environment and authorization_decision_ids",
            diagnostic="AUTHORIZATION_REQUIRED",
        )


def _validate_reference_adapter_authorization(case: dict[str, Any]) -> None:
    if case.get("side") != "reference":
        return
    adapter = case.get("adapter")
    data = case.get("input", {})
    mutating_http = adapter == "http" and str(data.get("method", "GET")).upper() not in {"GET", "HEAD", "OPTIONS"}
    process_like = adapter in {"process", "cli", "custom", "web"}
    credentialed_http = adapter == "http" and any(
        str(name).lower() in SENSITIVE_HTTP_HEADERS
        for name in (data.get("headers") if isinstance(data.get("headers"), dict) else {})
    )
    authority_ids = case.get("authorization_decision_ids")
    if credentialed_http and not authority_ids:
        raise ClonePackError(
            "credentialed reference HTTP capture requires authorization_decision_ids",
            diagnostic="AUTHORIZATION_REQUIRED",
        )
    if (mutating_http or process_like) and (not case.get("safe_test_environment") or not authority_ids):
        raise ClonePackError(
            "reference process, web, or mutating HTTP capture requires safe_test_environment and authorization_decision_ids",
            diagnostic="AUTHORIZATION_REQUIRED",
        )


def _validate_redaction_patterns(case: dict[str, Any]) -> None:
    for rule in case.get("redactions", []):
        try:
            re.compile(rule["pattern"])
        except (KeyError, TypeError, re.error) as exc:
            raise ClonePackError(f"invalid redaction pattern: {exc}", diagnostic="REDACTION_INVALID") from exc


def _preflight_adapter(pack: Path, manifest: dict[str, Any], case: dict[str, Any]) -> None:
    _validate_reference_adapter_authorization(case)
    _validate_redaction_patterns(case)
    adapter = case["adapter"]
    data = case["input"]
    if adapter == "http":
        _validate_http_secret_input(data["url"])
        _resolve_http_request_headers(data["headers"])
        _decode_base64_field(data.get("body_base64"), "body_base64")
        return
    if adapter in {"process", "cli", "custom"}:
        cwd = _capture_cwd(manifest, data["cwd"])
        environment = _capture_launch_environment(data["environment"])
        _decode_base64_field(data.get("stdin_base64"), "stdin_base64")
        _resolve_executable(data["argv"][0], cwd, environment)
        return
    if adapter == "web":
        cwd = _capture_cwd(manifest, data["cwd"])
        environment = _capture_launch_environment(data["environment"])
        _resolve_executable(data["driver_argv"][0], cwd, environment)
        return
    if adapter == "filesystem":
        repository = Path(str(manifest["repository_root"])).resolve()
        target = repository if data["path"] == "." else resolve_inside(repository, data["path"], must_exist=True)
        if not target.exists() and not target.is_symlink():
            raise ClonePackError(f"snapshot path does not exist: {target}", diagnostic="CAPTURE_INPUT_MISSING")
        return
    if adapter == "manual":
        _require_direct_regular_file(pack, data["source_path"], role="manual source_path")
        return
    raise ClonePackError(
        f"unsupported capture adapter: {adapter}",
        exit_code=EXIT_INFRASTRUCTURE,
        diagnostic="CAPABILITY_MISSING",
    )


def _preflight_lifecycle(pack: Path, manifest: dict[str, Any], case: dict[str, Any]) -> None:
    del pack
    _validate_lifecycle_authorization(case)
    lifecycle = case.get("lifecycle")
    if not isinstance(lifecycle, dict):
        return
    for phase in ("setup", "teardown"):
        command = lifecycle.get(phase)
        if command is None:
            continue
        cwd = _capture_cwd(manifest, command["cwd"])
        environment = _capture_launch_environment(command["environment"])
        _decode_base64_field(command.get("stdin_base64"), f"lifecycle.{phase}.stdin_base64")
        _resolve_executable(command["argv"][0], cwd, environment)


def _run_lifecycle_phase(
    manifest: dict[str, Any],
    phase: str,
    command: dict[str, Any],
    directory: Path,
    rules: list[dict[str, Any]],
) -> tuple[dict[str, Any], list[Path], ClonePackError | None, list[dict[str, Any]]]:
    phase_directory = directory / "lifecycle" / phase
    phase_directory.mkdir(parents=True)
    invocation_path = phase_directory / "invocation.json"
    stdout_path = phase_directory / "stdout.bin"
    stderr_path = phase_directory / "stderr.bin"
    stdout = b""
    stderr = b""
    observed_exit: int | None = None
    failure: ClonePackError | None = None
    diagnostic: str | None = None
    message: str | None = None
    redaction_events: list[dict[str, Any]] = []
    try:
        cwd = _capture_cwd(manifest, command["cwd"])
        environment = _capture_launch_environment(command["environment"])
        stdin = _decode_base64_field(command.get("stdin_base64"), f"lifecycle.{phase}.stdin_base64")
        completed = _run_process(
            command["argv"],
            cwd,
            environment,
            float(command["timeout_seconds"]),
            stdin,
        )
        stdout = completed.stdout
        stderr = completed.stderr
        observed_exit = completed.returncode
        if completed.returncode != command["expected_exit"]:
            failure = ClonePackError(
                f"lifecycle {phase} exited {completed.returncode}; expected {command['expected_exit']}",
                diagnostic="LIFECYCLE_EXIT_MISMATCH",
            )
    except ClonePackError as exc:
        failure = exc
    if failure is not None:
        diagnostic = failure.diagnostic
        message = str(failure)
    for stream_name, stream_path, stream_value in (
        ("stdout", stdout_path, stdout),
        ("stderr", stderr_path, stderr),
    ):
        try:
            retained_path, applied = _write_capture_artifact(
                phase_directory,
                f"{stream_name}.bin",
                stream_value,
                rules,
            )
            if retained_path != stream_path:  # pragma: no cover - fixed runner names
                raise ClonePackError("lifecycle artifact path changed unexpectedly", diagnostic="CAPTURE_OUTPUT_UNSAFE")
            redaction_events.extend(
                {**event, "kind": "regex-artifact", "location": f"lifecycle/{phase}/{stream_name}"}
                for event in applied
                if event["count"] > 0
            )
        except ClonePackError as exc:
            # The raw bytes are never retained when declared redaction cannot be applied.
            stream_path.write_bytes(b"")
            failure = exc
            diagnostic = exc.diagnostic
            message = str(exc)
    invocation = {
        "argv": command["argv"],
        "cwd": command["cwd"],
        "environment_names": sorted(command["environment"]),
        "stdin_present": command.get("stdin_base64") is not None,
        "expected_exit": command["expected_exit"],
        "observed_exit": observed_exit,
        "timeout_seconds": command["timeout_seconds"],
        "status": "PASS" if failure is None else ("BLOCKED" if failure.exit_code == EXIT_INFRASTRUCTURE else "FAIL"),
        "diagnostic": diagnostic,
        "message": message,
    }
    invocation, invocation_redactions = _redact_json_strings(
        invocation,
        rules,
        location=f"lifecycle/{phase}/invocation",
    )
    redaction_events.extend(invocation_redactions)
    atomic_write_json(invocation_path, invocation)
    return invocation, [invocation_path, stdout_path, stderr_path], failure, redaction_events


def _capture_stage_paths(pack: Path, case_id: str) -> tuple[Path, Path]:
    root = _require_real_pack_directory(pack, "evidence/captures")
    return root / f".{case_id}.staging", root / case_id


def _staging_marker(manifest: dict[str, Any], case: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": "clone-capture-staging/v1",
        "runner": "clone-software",
        "pack_id": manifest["pack_id"],
        "pack_revision": manifest["pack_revision"],
        "capture_id": case["id"],
        "case_sha256": case_contract_sha256(case),
    }


def _owned_staging(directory: Path, expected: dict[str, Any]) -> bool:
    try:
        directory_metadata = directory.lstat()
    except OSError:
        return False
    if not stat.S_ISDIR(directory_metadata.st_mode):
        return False
    marker_path = directory / CAPTURE_STAGING_MARKER
    try:
        marker_metadata = marker_path.lstat()
        if not stat.S_ISREG(marker_metadata.st_mode) or marker_metadata.st_nlink != 1:
            return False
    except OSError:
        return False
    try:
        marker = load_json(marker_path)
    except ClonePackError:
        return False
    return marker == expected


def _remove_owned_capture_staging(
    pack: Path,
    manifest: dict[str, Any],
    case: dict[str, Any],
    directory: Path,
) -> None:
    expected_stage, _ = _capture_stage_paths(pack, str(case["id"]))
    if directory != expected_stage or not _owned_staging(directory, _staging_marker(manifest, case)):
        raise ClonePackError(
            f"refusing to remove unowned or stale capture staging: {directory}",
            diagnostic="CAPTURE_STAGING_UNOWNED",
        )
    if not getattr(shutil.rmtree, "avoids_symlink_attacks", False):
        raise ClonePackError(
            "safe recursive staging cleanup is unavailable on this platform",
            exit_code=EXIT_INFRASTRUCTURE,
            diagnostic="CAPABILITY_MISSING",
        )
    try:
        shutil.rmtree(directory)
    except OSError as exc:
        raise ClonePackError(
            f"cannot remove owned capture staging: {directory}",
            diagnostic="CAPTURE_STAGING_CLEANUP_FAILED",
        ) from exc


def _validate_capture_output_tree(
    stage: Path,
    expected_paths: list[Path],
) -> list[Path]:
    expected: set[Path] = set()
    for path in expected_paths:
        try:
            relative = path.relative_to(stage)
        except ValueError as exc:
            raise ClonePackError(
                f"capture artifact escapes staging: {path}",
                diagnostic="CAPTURE_OUTPUT_UNSAFE",
            ) from exc
        if not relative.parts or relative.as_posix() in {CAPTURE_STAGING_MARKER, "manifest.json"}:
            raise ClonePackError(
                f"capture artifact uses a runner-owned path: {relative.as_posix()}",
                diagnostic="CAPTURE_OUTPUT_COLLISION",
            )
        try:
            metadata = path.lstat()
        except OSError as exc:
            raise ClonePackError(
                f"declared capture artifact is missing: {relative.as_posix()}",
                diagnostic="CAPTURE_OUTPUT_MISSING",
            ) from exc
        if not stat.S_ISREG(metadata.st_mode) or metadata.st_nlink != 1:
            raise ClonePackError(
                f"declared capture artifact is not a private regular file: {relative.as_posix()}",
                diagnostic="CAPTURE_OUTPUT_UNSAFE",
            )
        try:
            path.resolve(strict=True).relative_to(stage.resolve(strict=True))
        except (OSError, RuntimeError, ValueError) as exc:
            raise ClonePackError(
                f"declared capture artifact escapes staging: {relative.as_posix()}",
                diagnostic="CAPTURE_OUTPUT_UNSAFE",
            ) from exc
        if path in expected:
            raise ClonePackError(
                f"capture artifact is declared more than once: {relative.as_posix()}",
                diagnostic="CAPTURE_OUTPUT_COLLISION",
            )
        expected.add(path)

    observed: set[Path] = set()
    allowed_directories = {stage}
    for path in expected:
        parent = path.parent
        while parent != stage:
            allowed_directories.add(parent)
            parent = parent.parent
    for root_value, directory_names, file_names in os.walk(stage, topdown=True, followlinks=False):
        root = Path(root_value)
        for name in [*directory_names, *file_names]:
            candidate = root / name
            try:
                metadata = candidate.lstat()
            except OSError as exc:
                raise ClonePackError(
                    f"capture output changed during validation: {candidate.relative_to(stage)}",
                    diagnostic="CAPTURE_OUTPUT_UNSAFE",
                ) from exc
            if stat.S_ISLNK(metadata.st_mode):
                raise ClonePackError(
                    f"capture output contains a symlink: {candidate.relative_to(stage)}",
                    diagnostic="CAPTURE_OUTPUT_UNSAFE",
                )
            if name in directory_names:
                if not stat.S_ISDIR(metadata.st_mode) or candidate not in allowed_directories:
                    raise ClonePackError(
                        f"capture output contains an undeclared or unsafe directory: {candidate.relative_to(stage)}",
                        diagnostic="CAPTURE_OUTPUT_UNSAFE",
                    )
                continue
            if not stat.S_ISREG(metadata.st_mode) or metadata.st_nlink != 1:
                raise ClonePackError(
                    f"capture output contains a non-private or non-regular file: {candidate.relative_to(stage)}",
                    diagnostic="CAPTURE_OUTPUT_UNSAFE",
                )
            if candidate.name == CAPTURE_STAGING_MARKER and candidate.parent == stage:
                continue
            observed.add(candidate)
    if observed != expected:
        undeclared = sorted(path.relative_to(stage).as_posix() for path in observed - expected)
        missing = sorted(path.relative_to(stage).as_posix() for path in expected - observed)
        details = []
        if undeclared:
            details.append("undeclared: " + ", ".join(undeclared))
        if missing:
            details.append("missing: " + ", ".join(missing))
        raise ClonePackError(
            "capture output inventory differs from declared artifacts (" + "; ".join(details) + ")",
            diagnostic="CAPTURE_OUTPUT_UNSAFE",
        )
    return sorted(expected, key=lambda path: path.relative_to(stage).as_posix())


def _discard_isolated_web_output(stage: Path) -> None:
    directory = stage / "web"
    try:
        metadata = directory.lstat()
    except FileNotFoundError:
        return
    except OSError as exc:
        raise ClonePackError("cannot inspect isolated web output", diagnostic="CAPTURE_OUTPUT_UNSAFE") from exc
    try:
        if stat.S_ISLNK(metadata.st_mode):
            directory.unlink()
        elif stat.S_ISDIR(metadata.st_mode):
            if not getattr(shutil.rmtree, "avoids_symlink_attacks", False):
                raise ClonePackError(
                    "safe recursive web-output cleanup is unavailable on this platform",
                    exit_code=EXIT_INFRASTRUCTURE,
                    diagnostic="CAPABILITY_MISSING",
                )
            shutil.rmtree(directory)
        else:
            directory.unlink()
    except OSError as exc:
        raise ClonePackError("cannot discard unsafe web output", diagnostic="CAPTURE_OUTPUT_UNSAFE") from exc


def _validate_final_capture_inventory(directory: Path, expected_files: list[Path]) -> None:
    expected = set(expected_files)
    expected.add(directory / CAPTURE_STAGING_MARKER)
    expected.add(directory / "manifest.json")
    allowed_directories = {directory}
    for path in expected:
        parent = path.parent
        while parent != directory:
            allowed_directories.add(parent)
            parent = parent.parent
    observed: set[Path] = set()
    for root_value, directory_names, file_names in os.walk(directory, topdown=True, followlinks=False):
        root = Path(root_value)
        for name in directory_names:
            candidate = root / name
            try:
                metadata = candidate.lstat()
            except OSError as exc:
                raise ClonePackError("final capture inventory changed during validation", diagnostic="CAPTURE_RESULT_STALE") from exc
            if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISDIR(metadata.st_mode) or candidate not in allowed_directories:
                raise ClonePackError(
                    f"final capture has an undeclared or unsafe directory: {candidate.relative_to(directory)}",
                    diagnostic="CAPTURE_RESULT_STALE",
                )
        for name in file_names:
            candidate = root / name
            try:
                metadata = candidate.lstat()
            except OSError as exc:
                raise ClonePackError("final capture inventory changed during validation", diagnostic="CAPTURE_RESULT_STALE") from exc
            if not stat.S_ISREG(metadata.st_mode) or metadata.st_nlink != 1:
                raise ClonePackError(
                    f"final capture has a non-private or unsafe file: {candidate.relative_to(directory)}",
                    diagnostic="CAPTURE_RESULT_STALE",
                )
            observed.add(candidate)
    if observed != expected:
        raise ClonePackError(
            "final capture file inventory differs from its manifest",
            diagnostic="CAPTURE_RESULT_STALE",
        )


def _capture_result_exit(result: dict[str, Any]) -> int:
    value = result.get("acquisition_exit_code")
    if isinstance(value, int):
        return value
    return 0 if result.get("status") == "PASS" else (EXIT_INFRASTRUCTURE if result.get("status") == "BLOCKED" else 1)


def _load_current_capture_result(
    pack: Path,
    manifest: dict[str, Any],
    case: dict[str, Any],
    directory: Path,
) -> dict[str, Any]:
    try:
        directory_metadata = directory.lstat()
    except OSError as exc:
        raise ClonePackError(f"capture destination is unreadable: {directory}", diagnostic="OUTPUT_EXISTS") from exc
    if not stat.S_ISDIR(directory_metadata.st_mode):
        raise ClonePackError(f"capture destination is not a directory: {directory}", diagnostic="OUTPUT_EXISTS")
    result_path = directory / "manifest.json"
    try:
        result_metadata = result_path.lstat()
        if not stat.S_ISREG(result_metadata.st_mode) or result_metadata.st_nlink != 1:
            raise ClonePackError(
                f"capture manifest is not a regular file: {case['id']}",
                diagnostic="CAPTURE_RESULT_INVALID",
            )
    except OSError as exc:
        raise ClonePackError(
            f"capture manifest is missing: {case['id']}",
            diagnostic="CAPTURE_RESULT_INVALID",
        ) from exc
    result = load_json(result_path)
    if not _owned_staging(directory, _staging_marker(manifest, case)):
        raise ClonePackError(
            f"existing capture result lacks valid runner ownership metadata: {case['id']}",
            diagnostic="CAPTURE_RESULT_INVALID",
        )
    if set(result) != CAPTURE_RESULT_FIELDS:
        raise ClonePackError(
            f"existing capture result has unexpected or missing fields: {case['id']}",
            diagnostic="CAPTURE_RESULT_INVALID",
        )
    repository_state = manifest.get("repository_state", {})
    expected_clone_revision = repository_state.get("revision") if case.get("side") == "clone" else None
    expected_clone_diff = repository_state.get("diff_sha256") if case.get("side") == "clone" else None
    checks = {
        "schema_version": "clone-capture-result/v2",
        "capture_id": case["id"],
        "pack_id": manifest["pack_id"],
        "pack_revision": manifest["pack_revision"],
        "reference_baseline_id": manifest["reference_baseline_id"],
        "case_sha256": case_contract_sha256(case),
        "clone_revision": expected_clone_revision,
        "clone_diff_sha256": expected_clone_diff,
        "adapter": case.get("adapter"),
        "side": case.get("side"),
        "environment_id": case.get("environment_id"),
        "runner_version": TOOL_VERSION,
    }
    for field, expected in checks.items():
        if result.get(field) != expected:
            raise ClonePackError(
                f"existing capture result is stale at {field}: {case['id']}",
                diagnostic="CAPTURE_RESULT_STALE",
            )
    status = result.get("status")
    if status not in {"PASS", "FAIL", "BLOCKED"}:
        raise ClonePackError(f"existing capture result has invalid status: {case['id']}", diagnostic="CAPTURE_RESULT_INVALID")
    acquisition_exit = result.get("acquisition_exit_code")
    if (
        not isinstance(acquisition_exit, int)
        or isinstance(acquisition_exit, bool)
        or (status == "PASS" and acquisition_exit != 0)
        or (status == "FAIL" and (acquisition_exit == 0 or acquisition_exit == EXIT_INFRASTRUCTURE))
        or (status == "BLOCKED" and acquisition_exit != EXIT_INFRASTRUCTURE)
    ):
        raise ClonePackError(
            f"existing capture result status and acquisition exit differ: {case['id']}",
            diagnostic="CAPTURE_RESULT_INVALID",
        )
    if not isinstance(result.get("summary"), dict) or not isinstance(result.get("redactions"), list):
        raise ClonePackError(
            f"existing capture result summary or redactions are invalid: {case['id']}",
            diagnostic="CAPTURE_RESULT_INVALID",
        )
    if not isinstance(result.get("started_at"), str) or not isinstance(result.get("completed_at"), str):
        raise ClonePackError(f"existing capture result lacks timestamps: {case['id']}", diagnostic="CAPTURE_RESULT_INVALID")
    try:
        started = datetime.fromisoformat(result["started_at"].replace("Z", "+00:00"))
        completed = datetime.fromisoformat(result["completed_at"].replace("Z", "+00:00"))
    except ValueError as exc:
        raise ClonePackError(
            f"existing capture result has invalid timestamps: {case['id']}",
            diagnostic="CAPTURE_RESULT_INVALID",
        ) from exc
    if started.tzinfo is None or completed.tzinfo is None or completed < started:
        raise ClonePackError(
            f"existing capture result has an invalid time interval: {case['id']}",
            diagnostic="CAPTURE_RESULT_INVALID",
        )
    result_digest = sha256_file(result_path)
    pointer = case.get("result")
    if pointer is not None:
        expected_pointer = {
            "status": status,
            "path": result_path.relative_to(pack).as_posix(),
            "sha256": result_digest,
        }
        if pointer != expected_pointer:
            raise ClonePackError(
                f"existing capture result differs from the current plan pointer: {case['id']}",
                diagnostic="CAPTURE_RESULT_STALE",
            )
    artifacts = result.get("artifacts")
    if not isinstance(artifacts, list):
        raise ClonePackError(f"existing capture result lacks artifacts: {case['id']}", diagnostic="CAPTURE_RESULT_INVALID")
    artifact_ids: set[str] = set()
    artifact_paths: set[str] = set()
    retained_artifact_paths: list[Path] = []
    for artifact in artifacts:
        if not isinstance(artifact, dict) or set(artifact) != {"id", "path", "size", "media_type", "sha256"}:
            raise ClonePackError(f"existing capture result has an invalid artifact: {case['id']}", diagnostic="CAPTURE_RESULT_INVALID")
        identifier = artifact.get("id")
        path_value = artifact.get("path")
        if (
            not isinstance(identifier, str)
            or re.fullmatch(rf"ART-{re.escape(str(case['id']))}-\d{{2,}}", identifier) is None
            or identifier in artifact_ids
            or not isinstance(path_value, str)
            or path_value in artifact_paths
            or not isinstance(artifact.get("sha256"), str)
            or re.fullmatch(r"[0-9a-f]{64}", artifact["sha256"]) is None
            or not isinstance(artifact.get("size"), int)
            or isinstance(artifact.get("size"), bool)
            or artifact["size"] < 0
            or not isinstance(artifact.get("media_type"), str)
            or not artifact["media_type"]
        ):
            raise ClonePackError(f"existing capture result has an invalid artifact: {case['id']}", diagnostic="CAPTURE_RESULT_INVALID")
        artifact_ids.add(identifier)
        artifact_paths.add(path_value)
        relative_artifact = safe_relative_path(path_value)
        raw_artifact_path = pack.joinpath(*relative_artifact.parts)
        try:
            raw_metadata = raw_artifact_path.lstat()
        except OSError as exc:
            raise ClonePackError(
                f"existing capture artifact is missing: {path_value}",
                diagnostic="CAPTURE_RESULT_STALE",
            ) from exc
        if not stat.S_ISREG(raw_metadata.st_mode) or raw_metadata.st_nlink != 1:
            raise ClonePackError(
                f"existing capture artifact is not a private regular file: {path_value}",
                diagnostic="CAPTURE_RESULT_INVALID",
            )
        artifact_path = resolve_inside(pack, path_value, must_exist=True)
        if artifact_path != raw_artifact_path.absolute():
            raise ClonePackError(
                f"existing capture artifact uses a symlinked path: {path_value}",
                diagnostic="CAPTURE_RESULT_INVALID",
            )
        try:
            raw_artifact_path.relative_to(directory)
        except ValueError as exc:
            raise ClonePackError(
                f"existing capture artifact is outside its result directory: {path_value}",
                diagnostic="CAPTURE_RESULT_INVALID",
            ) from exc
        expected_media_type = mimetypes.guess_type(artifact_path.name)[0] or "application/octet-stream"
        if (
            raw_metadata.st_size != artifact["size"]
            or expected_media_type != artifact["media_type"]
            or sha256_file(artifact_path) != artifact["sha256"]
        ):
            raise ClonePackError(f"existing capture artifact integrity failed: {path_value}", diagnostic="CAPTURE_RESULT_STALE")
        retained_artifact_paths.append(raw_artifact_path)
    _validate_final_capture_inventory(directory, retained_artifact_paths)
    return result


def _capture_artifact(path: Path, stage: Path, final: Path, pack: Path, identifier: str) -> dict[str, Any]:
    relative = path.relative_to(stage)
    try:
        metadata = path.lstat()
    except OSError as exc:
        raise ClonePackError(f"capture artifact disappeared: {relative}", diagnostic="CAPTURE_OUTPUT_UNSAFE") from exc
    if not stat.S_ISREG(metadata.st_mode) or metadata.st_nlink != 1:
        raise ClonePackError(f"capture artifact is not regular: {relative}", diagnostic="CAPTURE_OUTPUT_UNSAFE")
    return {
        "id": identifier,
        "path": (final / relative).relative_to(pack).as_posix(),
        "size": metadata.st_size,
        "media_type": mimetypes.guess_type(path.name)[0] or "application/octet-stream",
        "sha256": sha256_file(path),
    }


def _execute_capture_case(
    pack: Path,
    manifest: dict[str, Any],
    case: dict[str, Any],
    timestamp: str | None,
) -> tuple[dict[str, Any], int]:
    repository_state = manifest["repository_state"]
    stage, final = _capture_stage_paths(pack, case["id"])
    try:
        stage.mkdir()
    except FileExistsError as exc:
        raise ClonePackError(f"capture staging destination already exists: {stage}", diagnostic="OUTPUT_EXISTS") from exc
    atomic_write_json(stage / CAPTURE_STAGING_MARKER, _staging_marker(manifest, case))
    started_at = _capture_time(timestamp)
    lifecycle_summaries: dict[str, Any] = {"setup": None, "teardown": None}
    failures: list[tuple[str, ClonePackError]] = []
    captured: dict[str, Any] = {"summary": {}, "paths": [], "redactions": []}
    lifecycle_paths: list[Path] = []
    lifecycle_redactions: list[dict[str, Any]] = []
    adapter_completed = False
    lifecycle = case["lifecycle"]
    interrupted: BaseException | None = None
    try:
        setup = lifecycle.get("setup")
        if setup is not None:
            setup_summary, setup_paths, setup_failure, setup_redactions = _run_lifecycle_phase(
                manifest,
                "setup",
                setup,
                stage,
                case["redactions"],
            )
            lifecycle_summaries["setup"] = setup_summary
            lifecycle_paths.extend(setup_paths)
            lifecycle_redactions.extend(setup_redactions)
            if setup_failure is not None:
                failures.append(("setup", setup_failure))
        if not failures:
            try:
                adapter = case.get("adapter")
                if adapter == "http":
                    captured = _capture_http(case, stage)
                elif adapter in {"process", "cli", "custom"}:
                    captured = _capture_process(pack, manifest, case, stage)
                elif adapter == "filesystem":
                    captured = _capture_filesystem(manifest, case, stage)
                elif adapter == "manual":
                    captured = _capture_manual(pack, case, stage)
                elif adapter == "web":
                    captured = _capture_web(pack, manifest, case, stage)
                else:
                    raise ClonePackError(
                        f"unsupported capture adapter: {adapter}",
                        exit_code=EXIT_INFRASTRUCTURE,
                        diagnostic="CAPABILITY_MISSING",
                    )
                paths = captured.get("paths")
                if not isinstance(paths, list) or not paths:
                    raise ClonePackError(
                        "successful capture adapter retained no observation artifacts",
                        diagnostic="CAPTURE_OUTPUT_MISSING",
                    )
                adapter_completed = True
            except ClonePackError as exc:
                failures.append(("adapter", exc))
                if case.get("adapter") == "web":
                    _discard_isolated_web_output(stage)
                safe_partial_paths = []
                for name in ("process.json", "stdout.bin", "stderr.bin", "http.json", "response.body", "request.body", "filesystem.json"):
                    candidate = stage / name
                    try:
                        if stat.S_ISREG(candidate.lstat().st_mode):
                            safe_partial_paths.append(candidate)
                    except OSError:
                        continue
                captured = {
                    "summary": {"diagnostic": exc.diagnostic, "message": str(exc)},
                    "paths": safe_partial_paths,
                    "redactions": [],
                }
    except BaseException as exc:  # teardown is mandatory even on interruption
        interrupted = exc
    finally:
        teardown = lifecycle.get("teardown")
        if teardown is not None:
            try:
                teardown_summary, teardown_paths, teardown_failure, teardown_redactions = _run_lifecycle_phase(
                    manifest,
                    "teardown",
                    teardown,
                    stage,
                    case["redactions"],
                )
                lifecycle_summaries["teardown"] = teardown_summary
                lifecycle_paths.extend(teardown_paths)
                lifecycle_redactions.extend(teardown_redactions)
                if teardown_failure is not None:
                    failures.append(("teardown", teardown_failure))
            except BaseException as exc:
                if interrupted is None:
                    interrupted = exc
    if interrupted is not None:
        raise interrupted

    status = "PASS"
    exit_code = 0
    if failures:
        blocked = any(failure.exit_code == EXIT_INFRASTRUCTURE for _, failure in failures)
        status = "BLOCKED" if blocked else "FAIL"
        exit_code = EXIT_INFRASTRUCTURE if blocked else next(
            (failure.exit_code for _, failure in failures if failure.exit_code),
            1,
        )
    summary = dict(captured.get("summary", {}))
    summary["lifecycle"] = lifecycle_summaries
    if failures:
        phases = [phase for phase, _ in failures]
        summary["failure_phase"] = phases[0] if len(phases) == 1 else "+".join(phases)
        summary["failures"] = [
            {"phase": phase, "diagnostic": failure.diagnostic, "message": str(failure)}
            for phase, failure in failures
        ]
    summary, summary_redactions = _redact_json_strings(
        summary,
        case["redactions"],
        location="capture-result/summary",
    )
    retained_redactions = [
        *captured.get("redactions", []),
        *lifecycle_redactions,
        *summary_redactions,
    ]
    expected_paths = [*lifecycle_paths, *captured.get("paths", [])]
    try:
        if status == "PASS" and (not adapter_completed or not captured.get("paths")):
            raise ClonePackError(
                "capture PASS requires at least one retained adapter observation",
                diagnostic="CAPTURE_OUTPUT_MISSING",
            )
        if not _owned_staging(stage, _staging_marker(manifest, case)):
            raise ClonePackError("capture ownership marker changed during execution", diagnostic="CAPTURE_OUTPUT_UNSAFE")
        artifact_paths = _validate_capture_output_tree(stage, expected_paths)
    except ClonePackError:
        _remove_owned_capture_staging(pack, manifest, case, stage)
        raise
    artifacts = [
        _capture_artifact(path, stage, final, pack, f"ART-{case['id']}-{position:02d}")
        for position, path in enumerate(artifact_paths, 1)
    ]
    completed_at = _capture_time(timestamp)
    result_manifest = {
        "schema_version": "clone-capture-result/v2",
        "capture_id": case["id"],
        "pack_id": manifest["pack_id"],
        "pack_revision": manifest["pack_revision"],
        "reference_baseline_id": manifest["reference_baseline_id"],
        "adapter": case.get("adapter"),
        "side": case.get("side"),
        "environment_id": case.get("environment_id"),
        "case_sha256": case_contract_sha256(case),
        "clone_revision": repository_state.get("revision") if case.get("side") == "clone" else None,
        "clone_diff_sha256": repository_state.get("diff_sha256") if case.get("side") == "clone" else None,
        "started_at": started_at,
        "completed_at": completed_at,
        "status": status,
        "acquisition_exit_code": exit_code,
        "summary": summary,
        "artifacts": artifacts,
        "redactions": retained_redactions,
        "runner_version": TOOL_VERSION,
    }
    atomic_write_json(stage / "manifest.json", result_manifest)
    expected_stage, expected_final = _capture_stage_paths(pack, str(case["id"]))
    if stage != expected_stage or final != expected_final or not _owned_staging(stage, _staging_marker(manifest, case)):
        raise ClonePackError("capture output paths changed before promotion", diagnostic="CAPTURE_OUTPUT_UNSAFE")
    if final.exists() or final.is_symlink():
        raise ClonePackError(f"capture destination already exists: {final}", diagnostic="OUTPUT_EXISTS")
    try:
        os.replace(stage, final)
    except OSError as exc:
        raise ClonePackError(f"capture promotion failed: {exc}", diagnostic="CAPTURE_PROMOTION_FAILED") from exc
    return result_manifest, exit_code


def _capture_context(
    pack: Path,
    case_ids: list[str] | None,
    *,
    resume: bool,
) -> tuple[
    Path,
    dict[str, Any],
    Path,
    dict[str, Any],
    list[dict[str, Any]],
    dict[str, dict[str, Any]],
    list[tuple[dict[str, Any], Path]],
]:
    pack = pack.expanduser().resolve()
    manifest = _load_v2_manifest(pack)
    repository_state = manifest.get("repository_state")
    if not isinstance(repository_state, dict):
        raise ClonePackError("manifest repository_state must be an object", diagnostic="MANIFEST_INVALID")
    plan_path = _manifest_plan_path(pack, manifest, "capture")
    plan = load_json(plan_path)
    cases = plan.get("cases")
    if not isinstance(cases, list):
        raise ClonePackError("capture plan cases must be an array", diagnostic="PLAN_INVALID")
    if any(not isinstance(item, dict) or not isinstance(item.get("id"), str) for item in cases):
        raise ClonePackError("capture plan contains a case without an ID", diagnostic="PLAN_INVALID")
    plan_ids = [str(item["id"]) for item in cases]
    if len(plan_ids) != len(set(plan_ids)):
        raise ClonePackError("capture plan contains duplicate case IDs", diagnostic="ID_DUPLICATE")
    requested = sorted(plan_ids if case_ids is None else case_ids)
    if not requested:
        raise ClonePackError("capture selection is empty", diagnostic="PLAN_INVALID")
    unknown = sorted(set(requested) - set(plan_ids))
    if unknown:
        raise ClonePackError(f"unknown capture case: {unknown[0]}", exit_code=2, diagnostic="CASE_UNKNOWN")
    selected = [next(item for item in cases if item["id"] == case_id) for case_id in requested]
    _validate_selected_plan_cases(
        plan,
        selected,
        schema_name="capture-plan-v2.schema.json",
        diagnostic="CAPTURE_PLAN_INVALID",
        pack_id=manifest["pack_id"],
        pack_revision=manifest["pack_revision"],
    )
    index = load_json(_manifest_index_path(pack, manifest))
    records = _index_record_map(index)
    skipped: dict[str, dict[str, Any]] = {}
    stale_staging: list[tuple[dict[str, Any], Path]] = []
    for case in selected:
        _capture_case_counterpart(records, case)
        _preflight_adapter(pack, manifest, case)
        _preflight_lifecycle(pack, manifest, case)
        stage, final = _capture_stage_paths(pack, case["id"])
        if final.exists() or final.is_symlink():
            if not resume:
                raise ClonePackError(f"capture destination already exists: {final}", diagnostic="OUTPUT_EXISTS")
            skipped[case["id"]] = _load_current_capture_result(pack, manifest, case, final)
        if stage.exists() or stage.is_symlink():
            if not resume:
                raise ClonePackError(f"capture staging destination already exists: {stage}", diagnostic="OUTPUT_EXISTS")
            expected_marker = _staging_marker(manifest, case)
            if not _owned_staging(stage, expected_marker):
                raise ClonePackError(
                    f"refusing to remove unowned or stale capture staging: {stage}",
                    diagnostic="CAPTURE_STAGING_UNOWNED",
                )
            stale_staging.append((case, stage))
    return pack, manifest, plan_path, plan, selected, skipped, stale_staging


def _capture_result_pointer(pack: Path, case_id: str, result: dict[str, Any]) -> dict[str, Any]:
    result_path = pack / "evidence" / "captures" / case_id / "manifest.json"
    return {
        "status": result["status"],
        "path": result_path.relative_to(pack).as_posix(),
        "sha256": sha256_file(result_path),
    }


def execute_capture(
    pack: Path,
    case_id: str,
    timestamp: str | None = None,
    *,
    resume: bool = False,
) -> tuple[dict[str, Any], int]:
    pack, manifest, plan_path, plan, selected, skipped, stale_staging = _capture_context(
        pack,
        [case_id],
        resume=resume,
    )
    for staged_case, stage in stale_staging:
        _remove_owned_capture_staging(pack, manifest, staged_case, stage)
    case = selected[0]
    if case_id in skipped:
        result = skipped[case_id]
        case["result"] = _capture_result_pointer(pack, case_id, result)
        atomic_write_json(plan_path, plan)
        return result, _capture_result_exit(result)
    result, exit_code = _execute_capture_case(pack, manifest, case, timestamp)
    case["result"] = _capture_result_pointer(pack, case_id, result)
    atomic_write_json(plan_path, plan)
    return result, exit_code


def execute_capture_batch(
    pack: Path,
    timestamp: str | None = None,
    *,
    resume: bool = False,
) -> tuple[dict[str, Any], int]:
    pack, manifest, plan_path, plan, selected, skipped, stale_staging = _capture_context(
        pack,
        None,
        resume=resume,
    )
    batch_started = _capture_time(timestamp)
    for staged_case, stage in stale_staging:
        _remove_owned_capture_staging(pack, manifest, staged_case, stage)
    entries: list[dict[str, Any]] = []
    for case in selected:
        case_id = case["id"]
        was_skipped = case_id in skipped
        if was_skipped:
            result = skipped[case_id]
            exit_code = _capture_result_exit(result)
        else:
            result, exit_code = _execute_capture_case(pack, manifest, case, timestamp)
        case["result"] = _capture_result_pointer(pack, case_id, result)
        atomic_write_json(plan_path, plan)
        entries.append(
            {
                "capture_id": case_id,
                "status": result["status"],
                "skipped": was_skipped,
                "exit_code": exit_code,
                "result_path": case["result"]["path"],
                "result_sha256": case["result"]["sha256"],
            }
        )
    statuses = {entry["status"] for entry in entries}
    aggregate_status = "BLOCKED" if "BLOCKED" in statuses else ("FAIL" if "FAIL" in statuses else "PASS")
    aggregate_exit = EXIT_INFRASTRUCTURE if aggregate_status == "BLOCKED" else (1 if aggregate_status == "FAIL" else 0)
    batch = {
        "schema_version": "clone-capture-batch-result/v2",
        "pack_id": manifest["pack_id"],
        "pack_revision": manifest["pack_revision"],
        "reference_baseline_id": manifest["reference_baseline_id"],
        "started_at": batch_started,
        "completed_at": _capture_time(timestamp),
        "status": aggregate_status,
        "results": entries,
    }
    return batch, aggregate_exit


def _delete_json_pointer(value: Any, pointer: str) -> None:
    if pointer == "":
        raise ClonePackError("normalization cannot delete the JSON document root", diagnostic="NORMALIZATION_INVALID")
    if not pointer.startswith("/"):
        raise ClonePackError(f"JSON pointer must start with '/': {pointer}", diagnostic="NORMALIZATION_INVALID")
    parts = [part.replace("~1", "/").replace("~0", "~") for part in pointer[1:].split("/")]
    try:
        current = value
        for part in parts[:-1]:
            current = current[int(part)] if isinstance(current, list) else current[part]
        final = parts[-1]
        if isinstance(current, list):
            del current[int(final)]
        elif isinstance(current, dict):
            if final not in current:
                raise KeyError(final)
            del current[final]
        else:
            raise TypeError("pointer parent is not a container")
    except (KeyError, IndexError, ValueError, TypeError) as exc:
        raise ClonePackError(
            f"JSON normalization path does not exist: {pointer}",
            diagnostic="NORMALIZATION_PATH_MISSING",
        ) from exc


def _validated_normalizations(value: Any, comparator: str) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        raise ClonePackError("normalizations must be an array", diagnostic="NORMALIZATION_INVALID")
    allowed_kinds = {
        "text": {"regex-replace"},
        "json": {"json-pointer-remove"},
        "http": {"json-pointer-remove"},
        "filesystem": {"json-pointer-remove"},
        "dom": {"json-pointer-remove"},
        "accessibility": {"json-pointer-remove"},
        "performance": {"json-pointer-remove"},
    }.get(comparator, set())
    validated: list[dict[str, Any]] = []
    for index, rule in enumerate(value, 1):
        if not isinstance(rule, dict):
            raise ClonePackError(f"normalization {index} must be an object", diagnostic="NORMALIZATION_INVALID")
        kind = rule.get("kind")
        expected_keys = (
            {"kind", "artifact_names", "path", "reason", "authority_ids"}
            if kind == "json-pointer-remove"
            else {"kind", "artifact_names", "pattern", "replacement", "reason", "authority_ids"}
            if kind == "regex-replace"
            else set()
        )
        if not expected_keys or set(rule) != expected_keys or kind not in allowed_kinds:
            raise ClonePackError(
                f"normalization {index} is not supported by comparator {comparator}",
                diagnostic="NORMALIZATION_INVALID",
            )
        artifact_names = rule.get("artifact_names")
        authorities = rule.get("authority_ids")
        if (
            not isinstance(artifact_names, list)
            or not artifact_names
            or any(not isinstance(item, str) or not item for item in artifact_names)
            or len(artifact_names) != len(set(artifact_names))
        ):
            raise ClonePackError(f"normalization {index} requires unique artifact_names", diagnostic="NORMALIZATION_INVALID")
        if (
            not isinstance(authorities, list)
            or not authorities
            or any(not isinstance(item, str) or not item for item in authorities)
            or len(authorities) != len(set(authorities))
        ):
            raise ClonePackError(f"normalization {index} requires unique authority_ids", diagnostic="NORMALIZATION_INVALID")
        if not isinstance(rule.get("reason"), str) or not rule["reason"]:
            raise ClonePackError(f"normalization {index} requires a reason", diagnostic="NORMALIZATION_INVALID")
        if kind == "json-pointer-remove" and (not isinstance(rule.get("path"), str) or not rule["path"].startswith("/")):
            raise ClonePackError(f"normalization {index} requires a JSON pointer path", diagnostic="NORMALIZATION_INVALID")
        if kind == "regex-replace":
            if not isinstance(rule.get("pattern"), str) or not rule["pattern"] or not isinstance(rule.get("replacement"), str):
                raise ClonePackError(f"normalization {index} requires string pattern and replacement", diagnostic="NORMALIZATION_INVALID")
            try:
                re.compile(rule["pattern"])
            except re.error as exc:
                raise ClonePackError(f"invalid normalization pattern: {exc}", diagnostic="NORMALIZATION_INVALID") from exc
        validated.append(rule)
    return validated


def _rules_for_artifact(rules: list[dict[str, Any]], artifact_name: str) -> list[dict[str, Any]]:
    return [rule for rule in rules if artifact_name in rule["artifact_names"]]


def _normalized_json(value: bytes, rules: list[dict[str, Any]]) -> Any:
    try:
        parsed = json.loads(value.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ClonePackError("comparator input is not valid UTF-8 JSON", diagnostic="COMPARATOR_INPUT_INVALID") from exc
    for rule in rules:
        _delete_json_pointer(parsed, rule["path"])
    return parsed


def _normalized_bytes(value: bytes, comparator: str, rules: list[dict[str, Any]]) -> bytes:
    if comparator in {"json", "http", "filesystem", "dom", "accessibility", "performance"}:
        parsed = _normalized_json(value, rules)
        return canonical_json(parsed).encode("utf-8")
    if comparator == "text":
        try:
            text = value.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise ClonePackError("text comparator input is not UTF-8", diagnostic="COMPARATOR_INPUT_INVALID") from exc
        for rule in rules:
            text = re.sub(rule["pattern"], rule["replacement"], text)
        return text.encode("utf-8")
    if rules:
        raise ClonePackError("normalization is unsupported for exact binary comparison", diagnostic="NORMALIZATION_INVALID")
    return value


def _nonnegative_number(value: Any, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value)) or value < 0:
        raise ClonePackError(f"{field} must be a finite non-negative number", diagnostic="COMPARATOR_OPTIONS_INVALID")
    return float(value)


def _validate_driver_options(options: dict[str, Any], *, perceptual: bool) -> dict[str, Any]:
    allowed = {"driver_argv", "artifact_pairs", "cwd", "environment", "timeout_seconds"}
    required = set(allowed)
    if perceptual:
        allowed.add("threshold")
        required.add("threshold")
    if set(options) != allowed or not required.issubset(options):
        raise ClonePackError(
            "driver options require exactly driver_argv, artifact_pairs, cwd, environment, timeout_seconds"
            + (", threshold" if perceptual else ""),
            diagnostic="COMPARATOR_OPTIONS_INVALID",
        )
    argv = options.get("driver_argv")
    if not isinstance(argv, list) or not argv or any(not isinstance(item, str) or not item for item in argv):
        raise ClonePackError("driver_argv must be a non-empty string array", diagnostic="COMPARATOR_OPTIONS_INVALID")
    pairs = options.get("artifact_pairs")
    if not isinstance(pairs, list) or not pairs:
        raise ClonePackError("artifact_pairs must be a non-empty array", diagnostic="COMPARATOR_OPTIONS_INVALID")
    identities: set[tuple[str, str]] = set()
    for pair in pairs:
        if (
            not isinstance(pair, dict)
            or set(pair) != {"reference_name", "clone_name"}
            or any(not isinstance(pair.get(key), str) or not pair[key] for key in ("reference_name", "clone_name"))
        ):
            raise ClonePackError(
                "each artifact pair requires only reference_name and clone_name",
                diagnostic="COMPARATOR_OPTIONS_INVALID",
            )
        identity = (pair["reference_name"], pair["clone_name"])
        if identity in identities:
            raise ClonePackError("artifact_pairs must be unique", diagnostic="COMPARATOR_OPTIONS_INVALID")
        identities.add(identity)
    if not isinstance(options.get("cwd"), str) or not options["cwd"]:
        raise ClonePackError("driver cwd must be a non-empty relative path", diagnostic="COMPARATOR_OPTIONS_INVALID")
    environment = options.get("environment")
    if not isinstance(environment, dict) or any(not isinstance(key, str) or not isinstance(value, str) for key, value in environment.items()):
        raise ClonePackError("driver environment must map strings to strings", diagnostic="COMPARATOR_OPTIONS_INVALID")
    _resolve_capture_environment(environment)
    timeout = options.get("timeout_seconds")
    if isinstance(timeout, bool) or not isinstance(timeout, int) or not 1 <= timeout <= 86400:
        raise ClonePackError("driver timeout_seconds must be an integer from 1 through 86400", diagnostic="COMPARATOR_OPTIONS_INVALID")
    if perceptual:
        _nonnegative_number(options.get("threshold"), "threshold")
    return options


def _validated_comparator_options(comparator: str, value: Any) -> dict[str, Any]:
    supported = {
        "exact",
        "text",
        "json",
        "http",
        "filesystem",
        "dom",
        "accessibility",
        "performance",
        "perceptual-image",
        "custom",
    }
    if comparator not in supported:
        raise ClonePackError(f"unsupported comparator: {comparator}", diagnostic="COMPARATOR_UNSUPPORTED")
    options = {} if value is None else value
    if not isinstance(options, dict):
        raise ClonePackError("comparator options must be an object", diagnostic="COMPARATOR_OPTIONS_INVALID")
    if comparator in {"exact", "text", "json", "filesystem", "dom", "accessibility"}:
        if options:
            raise ClonePackError(f"comparator {comparator} accepts only empty options", diagnostic="COMPARATOR_OPTIONS_INVALID")
        return options
    if comparator == "http":
        if set(options) != {"json_artifact_names"}:
            raise ClonePackError("HTTP options require exactly json_artifact_names", diagnostic="COMPARATOR_OPTIONS_INVALID")
        names = options.get("json_artifact_names")
        if (
            not isinstance(names, list)
            or any(not isinstance(item, str) or not item for item in names)
            or len(names) != len(set(names))
        ):
            raise ClonePackError("json_artifact_names must be a unique string array", diagnostic="COMPARATOR_OPTIONS_INVALID")
        return options
    if comparator == "performance":
        if set(options) != {"absolute_tolerance", "relative_tolerance"}:
            raise ClonePackError(
                "performance options require exactly absolute_tolerance and relative_tolerance",
                diagnostic="COMPARATOR_OPTIONS_INVALID",
            )
        _nonnegative_number(options.get("absolute_tolerance"), "absolute_tolerance")
        _nonnegative_number(options.get("relative_tolerance"), "relative_tolerance")
        return options
    return _validate_driver_options(options, perceptual=comparator == "perceptual-image")


def _performance_equal(expected: Any, actual: Any, absolute: float, relative: float) -> bool:
    if isinstance(expected, bool) or isinstance(actual, bool):
        return type(expected) is type(actual) and expected == actual
    if isinstance(expected, (int, float)) and isinstance(actual, (int, float)):
        if not math.isfinite(float(expected)) or not math.isfinite(float(actual)):
            raise ClonePackError("performance inputs contain a non-finite number", diagnostic="COMPARATOR_INPUT_INVALID")
        difference = abs(float(expected) - float(actual))
        return difference <= max(absolute, relative * max(abs(float(expected)), abs(float(actual))))
    if isinstance(expected, dict) and isinstance(actual, dict):
        return set(expected) == set(actual) and all(
            _performance_equal(expected[key], actual[key], absolute, relative) for key in expected
        )
    if isinstance(expected, list) and isinstance(actual, list):
        return len(expected) == len(actual) and all(
            _performance_equal(left, right, absolute, relative) for left, right in zip(expected, actual, strict=True)
        )
    return type(expected) is type(actual) and expected == actual


def _artifact_by_name(artifacts: list[Any], side: str) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for artifact in artifacts:
        if not isinstance(artifact, dict) or not isinstance(artifact.get("path"), str):
            raise ClonePackError(f"{side} capture contains an invalid artifact record", diagnostic="CAPTURE_RESULT_INVALID")
        name = Path(artifact["path"]).name
        if name in result:
            raise ClonePackError(f"{side} capture has duplicate artifact name: {name}", diagnostic="CAPTURE_RESULT_INVALID")
        result[name] = artifact
    return result


def _driver_artifact(path: Path, pack: Path, identifier: str) -> dict[str, Any]:
    if not path.is_file():
        raise ClonePackError(f"comparator artifact is not a file: {path.name}", diagnostic="COMPARATOR_DRIVER_INVALID")
    return _artifact(path, pack, identifier)


def _execute_comparator_driver(
    *,
    pack: Path,
    manifest: dict[str, Any],
    comparator: str,
    options: dict[str, Any],
    expected_path: Path,
    actual_path: Path,
    output_dir: Path,
    pair_number: int,
) -> tuple[bool, list[str], list[dict[str, Any]]]:
    pair_dir = output_dir / f"driver-{pair_number:02d}"
    pair_dir.mkdir()
    repository = Path(str(manifest["repository_root"])).resolve()
    cwd_value = options["cwd"]
    cwd = repository if cwd_value == "." else resolve_inside(repository, cwd_value, must_exist=True)
    environment = _resolve_capture_environment(options["environment"])
    for key in ("PATH", "SYSTEMROOT", "WINDIR", "COMSPEC", "PATHEXT", "TMP", "TEMP"):
        if key in os.environ and key not in environment:
            environment[key] = os.environ[key]
    result_path = pair_dir / "result.json"
    environment.update(
        {
            "CLONE_PARITY_COMPARATOR": comparator,
            "CLONE_PARITY_EXPECTED_PATH": str(expected_path),
            "CLONE_PARITY_ACTUAL_PATH": str(actual_path),
            "CLONE_PARITY_RESULT_PATH": str(result_path),
            "CLONE_PARITY_OPTIONS_JSON": canonical_json(options),
        }
    )
    completed = _run_process(options["driver_argv"], cwd, environment, float(options["timeout_seconds"]))
    stdout_path = pair_dir / "stdout.bin"
    stderr_path = pair_dir / "stderr.bin"
    stdout_path.write_bytes(completed.stdout)
    stderr_path.write_bytes(completed.stderr)
    invocation_path = pair_dir / "invocation.json"
    atomic_write_json(
        invocation_path,
        {
            "argv": options["driver_argv"],
            "cwd": cwd_value,
            "exit_code": completed.returncode,
            "expected_path": expected_path.relative_to(pack).as_posix(),
            "actual_path": actual_path.relative_to(pack).as_posix(),
        },
    )
    if completed.returncode != 0:
        raise ClonePackError(
            f"comparator driver exited {completed.returncode}; retained evidence at {pair_dir.relative_to(pack)}",
            exit_code=EXIT_INFRASTRUCTURE,
            diagnostic="COMPARATOR_DRIVER_FAILED",
        )
    if not result_path.is_file():
        raise ClonePackError(
            f"comparator driver did not write {result_path.name}; retained evidence at {pair_dir.relative_to(pack)}",
            exit_code=EXIT_INFRASTRUCTURE,
            diagnostic="COMPARATOR_DRIVER_INVALID",
        )
    driver_result = load_json(result_path)
    allowed_result_keys = {"schema_version", "equal", "distance", "details", "artifacts"}
    if set(driver_result) - allowed_result_keys or driver_result.get("schema_version") != "clone-comparator-result/v1":
        raise ClonePackError("comparator result has an unsupported shape or schema_version", diagnostic="COMPARATOR_DRIVER_INVALID")
    details = driver_result.get("details")
    declared = driver_result.get("artifacts")
    if not isinstance(details, list) or any(not isinstance(item, str) for item in details):
        raise ClonePackError("comparator result details must be a string array", diagnostic="COMPARATOR_DRIVER_INVALID")
    if not isinstance(declared, list) or any(not isinstance(item, str) or not item for item in declared):
        raise ClonePackError("comparator result artifacts must be a relative-path array", diagnostic="COMPARATOR_DRIVER_INVALID")
    if comparator == "perceptual-image":
        distance = _nonnegative_number(driver_result.get("distance"), "driver distance")
        equal = distance <= float(options["threshold"])
        details = [*details, f"distance {distance} <= threshold {float(options['threshold'])}: {str(equal).lower()}"]
    else:
        if not isinstance(driver_result.get("equal"), bool):
            raise ClonePackError("custom comparator result requires boolean equal", diagnostic="COMPARATOR_DRIVER_INVALID")
        equal = driver_result["equal"]
    paths = [invocation_path, stdout_path, stderr_path, result_path]
    reserved = {path.name for path in paths}
    for relative in declared:
        safe_relative_path(relative)
        if Path(relative).name in reserved:
            raise ClonePackError(f"comparator artifact uses reserved name: {relative}", diagnostic="COMPARATOR_DRIVER_INVALID")
        paths.append(resolve_inside(pair_dir, relative, must_exist=True))
    artifacts = [
        _driver_artifact(path, pack, f"ART-PAR-DRIVER-{pair_number:02d}-{index:02d}")
        for index, path in enumerate(paths, 1)
    ]
    return equal, details, artifacts


def execute_parity(pack: Path, case_id: str) -> tuple[dict[str, Any], int]:
    pack = pack.expanduser().resolve()
    manifest = _load_v2_manifest(pack)
    repository_state = manifest.get("repository_state")
    if not isinstance(repository_state, dict):
        raise ClonePackError("manifest repository_state must be an object", diagnostic="MANIFEST_INVALID")
    parity_path = _manifest_plan_path(pack, manifest, "parity")
    parity_plan = load_json(parity_path)
    capture_plan = load_json(_manifest_plan_path(pack, manifest, "capture"))
    cases = parity_plan.get("cases")
    if not isinstance(cases, list):
        raise ClonePackError("parity cases must be an array", diagnostic="PLAN_INVALID")
    case = next((item for item in cases if isinstance(item, dict) and item.get("id") == case_id), None)
    if case is None:
        raise ClonePackError(f"unknown parity case: {case_id}", exit_code=2, diagnostic="CASE_UNKNOWN")
    _validate_selected_plan_cases(
        parity_plan,
        [case],
        schema_name="parity-plan-v2.schema.json",
        diagnostic="PARITY_PLAN_INVALID",
        pack_id=manifest["pack_id"],
        pack_revision=manifest["pack_revision"],
    )
    captures = {
        item.get("id"): item
        for item in capture_plan.get("cases", [])
        if isinstance(item, dict) and isinstance(item.get("id"), str)
    }
    reference_case = captures.get(case.get("reference_capture_id"))
    clone_case = captures.get(case.get("clone_capture_id"))
    if not reference_case or not clone_case:
        raise ClonePackError("parity case references an unknown capture", diagnostic="REF_UNDEFINED")
    _validate_selected_plan_cases(
        capture_plan,
        [reference_case, clone_case],
        schema_name="capture-plan-v2.schema.json",
        diagnostic="CAPTURE_PLAN_INVALID",
        pack_id=manifest["pack_id"],
        pack_revision=manifest["pack_revision"],
    )
    if reference_case.get("side") != "reference" or clone_case.get("side") != "clone":
        raise ClonePackError(
            "parity requires a reference-side oracle and a clone-side observation",
            diagnostic="RUN_ORACLE_INVALID",
        )
    index = load_json(_manifest_index_path(pack, manifest))
    records = _index_record_map(index)
    _parity_case_counterpart(records, case, reference_case, clone_case)
    if reference_case.get("environment_id") != clone_case.get("environment_id"):
        raise ClonePackError("parity preconditions differ by environment_id", diagnostic="PARITY_PRECONDITION_MISMATCH")
    for capture in (reference_case, clone_case):
        result_ref = capture.get("result")
        if not isinstance(result_ref, dict) or result_ref.get("status") != "PASS":
            raise ClonePackError("parity requires two successful captures", exit_code=EXIT_HOLD, diagnostic="PARITY_BLOCKED")
        result_path = resolve_inside(pack, str(result_ref.get("path")), must_exist=True)
        if sha256_file(result_path) != result_ref.get("sha256"):
            raise ClonePackError("capture result hash mismatch", exit_code=4, diagnostic="ARTIFACT_HASH_MISMATCH")
    reference = load_json(resolve_inside(pack, reference_case["result"]["path"], must_exist=True))
    clone = load_json(resolve_inside(pack, clone_case["result"]["path"], must_exist=True))
    for capture_case, retained in ((reference_case, reference), (clone_case, clone)):
        expected_case_sha256 = case_contract_sha256(capture_case)
        if retained.get("case_sha256") != expected_case_sha256:
            raise ClonePackError(
                f"capture contract changed after evidence was recorded: {capture_case.get('id')}",
                exit_code=EXIT_HOLD,
                diagnostic="CAPTURE_CONTRACT_STALE",
            )
        if retained.get("reference_baseline_id") != manifest.get("reference_baseline_id"):
            raise ClonePackError(
                f"capture reference baseline is stale: {capture_case.get('id')}",
                exit_code=EXIT_HOLD,
                diagnostic="CAPTURE_REFERENCE_STALE",
            )
        if capture_case.get("side") == "reference" and (
            "clone_revision" not in retained
            or "clone_diff_sha256" not in retained
            or retained.get("clone_revision") is not None
            or retained.get("clone_diff_sha256") is not None
        ):
            raise ClonePackError(
                f"reference capture has invalid clone repository identity fields: {capture_case.get('id')}",
                diagnostic="CAPTURE_RESULT_INVALID",
            )
        if capture_case.get("side") == "clone" and (
            "clone_revision" not in retained
            or "clone_diff_sha256" not in retained
            or retained.get("clone_revision") != repository_state.get("revision")
            or retained.get("clone_diff_sha256") != repository_state.get("diff_sha256")
        ):
            raise ClonePackError(
                f"clone repository changed after capture: {capture_case.get('id')}",
                exit_code=EXIT_HOLD,
                diagnostic="CAPTURE_CLONE_STALE",
            )
    comparator = str(case.get("comparator", "exact"))
    parity_case_sha256 = case_contract_sha256(case)
    options = _validated_comparator_options(comparator, case.get("options"))
    rules = _validated_normalizations(case.get("normalizations"), comparator)
    reference_artifacts = reference.get("artifacts", [])
    clone_artifacts = clone.get("artifacts", [])
    if not isinstance(reference_artifacts, list) or not isinstance(clone_artifacts, list):
        raise ClonePackError("capture result artifacts must be arrays", diagnostic="CAPTURE_RESULT_INVALID")
    output_dir = pack / "evidence" / "parity" / case_id
    if output_dir.exists():
        raise ClonePackError(f"parity destination already exists: {output_dir}", diagnostic="OUTPUT_EXISTS")
    driver_artifacts: list[dict[str, Any]] = []
    if comparator in {"custom", "perceptual-image"}:
        output_dir.mkdir(parents=True)
        reference_by_name = _artifact_by_name(reference_artifacts, "reference")
        clone_by_name = _artifact_by_name(clone_artifacts, "clone")
        pairs_equal = True
        details: list[str] = []
        for pair_number, pair in enumerate(options["artifact_pairs"], 1):
            expected_artifact = reference_by_name.get(pair["reference_name"])
            actual_artifact = clone_by_name.get(pair["clone_name"])
            if expected_artifact is None or actual_artifact is None:
                raise ClonePackError(
                    f"configured driver artifact pair is missing: {pair['reference_name']} -> {pair['clone_name']}",
                    diagnostic="COMPARATOR_INPUT_MISSING",
                )
            expected_path = resolve_inside(pack, expected_artifact["path"], must_exist=True)
            actual_path = resolve_inside(pack, actual_artifact["path"], must_exist=True)
            if sha256_file(expected_path) != expected_artifact.get("sha256") or sha256_file(actual_path) != actual_artifact.get("sha256"):
                raise ClonePackError("capture artifact hash mismatch", exit_code=4, diagnostic="ARTIFACT_HASH_MISMATCH")
            pair_equal, pair_details, retained = _execute_comparator_driver(
                pack=pack,
                manifest=manifest,
                comparator=comparator,
                options=options,
                expected_path=expected_path,
                actual_path=actual_path,
                output_dir=output_dir,
                pair_number=pair_number,
            )
            if not pair_equal:
                pairs_equal = False
                details.append(f"configured artifact pair {pair_number} differs")
            details.extend(f"pair {pair_number}: {item}" for item in pair_details)
            driver_artifacts.extend(retained)
    elif len(reference_artifacts) != len(clone_artifacts):
        pairs_equal = False
        details = [f"artifact count {len(reference_artifacts)} != {len(clone_artifacts)}"]
    else:
        pairs_equal = True
        details = []
        if rules:
            reference_names_for_rules = set(_artifact_by_name(reference_artifacts, "reference"))
            clone_names_for_rules = set(_artifact_by_name(clone_artifacts, "clone"))
            common_names = reference_names_for_rules & clone_names_for_rules
            missing_rule_targets = sorted(
                {
                    name
                    for rule in rules
                    for name in rule["artifact_names"]
                    if name not in common_names
                }
            )
            if missing_rule_targets:
                raise ClonePackError(
                    "normalization artifact_names are missing from one or both captures: "
                    + ", ".join(missing_rule_targets),
                    diagnostic="COMPARATOR_INPUT_MISSING",
                )
        http_json_names = set(options.get("json_artifact_names", []))
        if comparator == "http":
            if reference_case.get("adapter") != "http" or clone_case.get("adapter") != "http":
                raise ClonePackError("HTTP comparator requires two HTTP captures", diagnostic="COMPARATOR_INPUT_INVALID")
            reference_names = set(_artifact_by_name(reference_artifacts, "reference"))
            clone_names = set(_artifact_by_name(clone_artifacts, "clone"))
            missing_names = sorted(name for name in http_json_names if name not in reference_names or name not in clone_names)
            if missing_names:
                raise ClonePackError(
                    "HTTP json_artifact_names are missing from one or both captures: " + ", ".join(missing_names),
                    diagnostic="COMPARATOR_INPUT_MISSING",
                )
        for index, (expected_artifact, actual_artifact) in enumerate(zip(reference_artifacts, clone_artifacts, strict=True), 1):
            if (
                not isinstance(expected_artifact, dict)
                or not isinstance(actual_artifact, dict)
                or not isinstance(expected_artifact.get("path"), str)
                or not isinstance(actual_artifact.get("path"), str)
                or not isinstance(expected_artifact.get("sha256"), str)
                or not isinstance(actual_artifact.get("sha256"), str)
            ):
                raise ClonePackError("capture contains an invalid artifact record", diagnostic="CAPTURE_RESULT_INVALID")
            expected_path = resolve_inside(pack, expected_artifact["path"], must_exist=True)
            actual_path = resolve_inside(pack, actual_artifact["path"], must_exist=True)
            if sha256_file(expected_path) != expected_artifact.get("sha256") or sha256_file(actual_path) != actual_artifact.get("sha256"):
                raise ClonePackError("capture artifact hash mismatch", exit_code=4, diagnostic="ARTIFACT_HASH_MISMATCH")
            effective_comparator = comparator
            expected_name = expected_path.name
            actual_name = actual_path.name
            expected_rules = _rules_for_artifact(rules, expected_name)
            actual_rules = _rules_for_artifact(rules, actual_name)
            if comparator == "http":
                if expected_name == "http.json" and actual_name == "http.json":
                    effective_comparator = "json"
                elif expected_name in http_json_names and actual_name in http_json_names:
                    effective_comparator = "json"
                else:
                    effective_comparator = "exact"
            if comparator == "performance":
                expected_value = _normalized_json(expected_path.read_bytes(), expected_rules)
                actual_value = _normalized_json(actual_path.read_bytes(), actual_rules)
                equal = _performance_equal(
                    expected_value,
                    actual_value,
                    float(options["absolute_tolerance"]),
                    float(options["relative_tolerance"]),
                )
            else:
                expected_value = _normalized_bytes(expected_path.read_bytes(), effective_comparator, expected_rules)
                actual_value = _normalized_bytes(actual_path.read_bytes(), effective_comparator, actual_rules)
                equal = expected_value == actual_value
            if not equal:
                pairs_equal = False
                details.append(f"artifact pair {index} differs")
    status = "PASS" if pairs_equal else "FAIL"
    if not output_dir.exists():
        output_dir.mkdir(parents=True)
    parity_result = {
        "schema_version": "clone-parity-result/v2",
        "parity_id": case_id,
        "pack_id": manifest["pack_id"],
        "pack_revision": manifest["pack_revision"],
        "reference_baseline_id": manifest["reference_baseline_id"],
        "reference_capture_id": case.get("reference_capture_id"),
        "clone_capture_id": case.get("clone_capture_id"),
        "case_sha256": parity_case_sha256,
        "clone_revision": repository_state.get("revision"),
        "clone_diff_sha256": repository_state.get("diff_sha256"),
        "comparator": comparator,
        "normalizations": rules,
        "options": options,
        "status": status,
        "details": details,
        "artifacts": driver_artifacts,
        "runner_version": TOOL_VERSION,
    }
    result_path = output_dir / "result.json"
    atomic_write_json(result_path, parity_result)
    case["result"] = {"status": status, "path": result_path.relative_to(pack).as_posix(), "sha256": sha256_file(result_path)}
    atomic_write_json(parity_path, parity_plan)
    return parity_result, 0 if status == "PASS" else EXIT_HOLD


def _retained_artifact(
    source: Path,
    destination: Path,
    pack: Path,
    identifier: str,
) -> dict[str, Any]:
    """Describe staged bytes using the path they will have after promotion."""

    return {
        "id": identifier,
        "path": destination.relative_to(pack).as_posix(),
        "size": source.stat().st_size,
        "media_type": mimetypes.guess_type(destination.name)[0] or "application/octet-stream",
        "sha256": sha256_file(source),
    }


def _retained_bytes_artifact(
    value: bytes,
    destination: Path,
    pack: Path,
    identifier: str,
    *,
    source_path: str | None = None,
) -> dict[str, Any]:
    """Describe bytes that will be committed by the enclosing transaction."""

    artifact = {
        "id": identifier,
        "path": destination.relative_to(pack).as_posix(),
        "size": len(value),
        "media_type": mimetypes.guess_type(destination.name)[0] or "application/octet-stream",
        "sha256": sha256_bytes(value),
    }
    if source_path is not None:
        artifact["source_path"] = source_path
    return artifact


def _validate_timeout(value: Any, role: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ClonePackError(f"{role} must be a positive number", diagnostic="RUN_CONTRACT_INVALID")
    timeout = float(value)
    if not math.isfinite(timeout) or timeout <= 0:
        raise ClonePackError(f"{role} must be a positive finite number", diagnostic="RUN_CONTRACT_INVALID")
    return timeout


def _validate_declared_artifact_paths(value: Any, role: str) -> list[str]:
    if (
        not isinstance(value, list)
        or any(not isinstance(item, str) or not item for item in value)
        or len(value) != len(set(value))
    ):
        raise ClonePackError(f"{role} must be a unique relative-path array", diagnostic="RUN_CONTRACT_INVALID")
    for item in value:
        safe_relative_path(item)
    return list(value)


def _prepare_retained_bytes(value: bytes, rules: list[dict[str, Any]]) -> bytes:
    retained, _ = _apply_redactions(value, rules)
    return retained


def _run_artifact_state(repository: Path, relative: str) -> tuple[int, int, int, int, int, str] | None:
    try:
        path = _require_direct_regular_file(repository, relative, role="gate artifact")
    except ClonePackError as exc:
        if exc.diagnostic == "FILE_MISSING":
            return None
        raise
    try:
        metadata = path.lstat()
        value = path.read_bytes()
    except OSError as exc:
        raise ClonePackError(
            f"cannot inspect gate artifact: {relative}: {exc}",
            diagnostic="RUN_ARTIFACT_INVALID",
        ) from exc
    if metadata.st_nlink != 1:
        raise ClonePackError(
            f"gate artifact must not be hard-linked: {relative}",
            diagnostic="RUN_ARTIFACT_INVALID",
        )
    return (
        metadata.st_dev,
        metadata.st_ino,
        metadata.st_size,
        metadata.st_mtime_ns,
        metadata.st_ctime_ns,
        sha256_bytes(value),
    )


def record_run(pack: Path, gate_id: str, environment_id: str, timestamp: str | None = None) -> tuple[dict[str, Any], int]:
    pack = pack.expanduser().resolve()
    recover_atomic_transactions(pack)
    manifest = _load_v2_manifest(pack)
    index_path = _manifest_index_path(pack, manifest)
    index = load_json(index_path)
    records = _index_record_map(index)
    gate = _required_record(records, gate_id, {"GATE"}, "gate")
    _required_record(records, environment_id, {"ENV"}, "environment")
    attributes = gate.get("attributes") if isinstance(gate.get("attributes"), dict) else {}
    enhancement_plan_path: Path | None = None
    enhancement_plan: dict[str, Any] | None = None
    enhancement_gate: dict[str, Any] | None = None
    workstream = manifest.get("workstream")
    if isinstance(workstream, dict) and workstream.get("kind") == "brownfield-enhancement":
        enhancement_plan_path = resolve_inside(pack, "enhancement_plan.json", must_exist=True)
        enhancement_plan = load_json(enhancement_plan_path)
        plan_gates = enhancement_plan.get("gates")
        if not isinstance(plan_gates, list):
            raise ClonePackError("enhancement gates must be an array", diagnostic="PLAN_INVALID")
        counterparts = [item for item in plan_gates if isinstance(item, dict) and item.get("id") == gate_id]
        if len(counterparts) != 1:
            raise ClonePackError("recorded gate must have exactly one enhancement plan counterpart", diagnostic="PLAN_INDEX_DIVERGENCE")
        enhancement_gate = counterparts[0]
        references = enhancement_plan.get("result_references")
        if not isinstance(references, dict) or not isinstance(references.get("run_ids"), list):
            raise ClonePackError("enhancement result_references.run_ids must be an array", diagnostic="PLAN_INVALID")

    argv = attributes.get("argv")
    if not isinstance(argv, list) or not argv or any(not isinstance(item, str) or not item for item in argv):
        raise ClonePackError("gate argv must be a non-empty string array", diagnostic="RUN_CONTRACT_INVALID")
    cwd_value = attributes.get("cwd", ".")
    if not isinstance(cwd_value, str) or not cwd_value:
        raise ClonePackError("gate cwd must be a non-empty relative path", diagnostic="RUN_CONTRACT_INVALID")
    timeout = _validate_timeout(attributes.get("timeout_seconds", 300), "gate timeout_seconds")
    expected_exit = attributes.get("expected_exit", 0)
    if isinstance(expected_exit, bool) or not isinstance(expected_exit, int):
        raise ClonePackError("gate expected_exit must be an integer", diagnostic="RUN_CONTRACT_INVALID")
    blocked_exit_codes = attributes.get("blocked_exit_codes", [])
    if (
        not isinstance(blocked_exit_codes, list)
        or any(isinstance(item, bool) or not isinstance(item, int) for item in blocked_exit_codes)
        or len(blocked_exit_codes) != len(set(blocked_exit_codes))
        or expected_exit in blocked_exit_codes
    ):
        raise ClonePackError(
            "gate blocked_exit_codes must be unique integers excluding expected_exit",
            diagnostic="RUN_CONTRACT_INVALID",
        )
    normalizations = attributes.get("normalizations", [])
    if not isinstance(normalizations, list) or any(not isinstance(item, str) for item in normalizations):
        raise ClonePackError("gate normalizations must be a string array", diagnostic="RUN_CONTRACT_INVALID")
    artifact_paths = _validate_declared_artifact_paths(
        attributes.get("artifact_paths", []),
        "gate artifact_paths",
    )
    fresh_artifact_paths = _validate_declared_artifact_paths(
        attributes.get("fresh_artifact_paths", []),
        "gate fresh_artifact_paths",
    )
    if not set(fresh_artifact_paths).issubset(artifact_paths):
        raise ClonePackError(
            "gate fresh_artifact_paths must be a subset of artifact_paths",
            diagnostic="RUN_CONTRACT_INVALID",
        )
    rules = attributes.get("redactions", [])
    authority_ids = _rule_authority_ids(rules, "gate redactions")
    for authority_id in authority_ids:
        _required_record(records, authority_id, {"DEC", "ADR", "GAPDEC"}, "gate redaction authority")
    # This applies every rule to harmless input so malformed patterns fail before execution.
    _apply_redactions(b"", rules)
    for relative in artifact_paths:
        redacted_path, path_events = _redact_json_strings(relative, rules, location="run/artifact-path")
        if redacted_path != relative or path_events:
            raise ClonePackError(
                f"gate artifact path requires pre-redaction: {relative}",
                diagnostic="REDACTION_UNSUPPORTED",
            )

    declared_environment = attributes.get("environment", {})
    if not isinstance(declared_environment, dict) or any(
        not isinstance(key, str) or not isinstance(value, str)
        for key, value in declared_environment.items()
    ):
        raise ClonePackError("gate environment must map strings to strings", diagnostic="RUN_CONTRACT_INVALID")
    resolved_environment = _resolve_capture_environment(declared_environment)
    covered_ids = _record_id_array(attributes.get("covered_ids", []), "gate covered_ids")
    oracle_ids = _record_id_array(attributes.get("oracle_ids", []), "gate oracle_ids")
    for identifier in covered_ids:
        _required_record(records, identifier, RUN_COVERED_KINDS, "covered ID")
    for identifier in oracle_ids:
        _required_record(records, identifier, RUN_ORACLE_KINDS, "oracle ID")
    contract_hashes = _governing_contract_hashes(
        records,
        [gate_id, environment_id, *covered_ids, *oracle_ids],
    )
    execution_contract = gate_execution_contract(attributes)
    _require_run_execution_contract(execution_contract)

    run_id, run_path, artifact_dir = _next_run_paths(pack, manifest, records)
    artifact_root = artifact_dir.parent
    artifact_root.mkdir(parents=True, exist_ok=True)
    try:
        artifact_root_metadata = artifact_root.lstat()
    except OSError as exc:
        raise ClonePackError("run artifact root is unavailable", exit_code=4, diagnostic="PATH_UNSAFE") from exc
    if stat.S_ISLNK(artifact_root_metadata.st_mode) or not stat.S_ISDIR(artifact_root_metadata.st_mode):
        raise ClonePackError("run artifact root must be a real directory", exit_code=4, diagnostic="PATH_UNSAFE")
    repository = Path(str(manifest["repository_root"])).resolve()
    cwd = repository if cwd_value == "." else resolve_inside(repository, cwd_value, must_exist=True)
    if not cwd.is_dir():
        raise ClonePackError("gate cwd must name a directory", diagnostic="RUN_CONTRACT_INVALID")
    environment = {
        key: os.environ[key]
        for key in ("PATH", "SYSTEMROOT", "WINDIR", "COMSPEC", "PATHEXT", "TMP", "TEMP")
        if key in os.environ
    }
    environment.update(resolved_environment)
    artifact_before = {
        relative: _run_artifact_state(repository, relative)
        for relative in fresh_artifact_paths
    }
    started_at, _ = utc_now(timestamp)
    started = time.monotonic()
    observed_exit: int | None = None
    diagnostic: dict[str, Any] | None = None
    stdout = b""
    stderr = b""
    try:
        completed = _run_process(list(argv), cwd, environment, timeout)
    except ClonePackError as exc:
        if exc.exit_code != EXIT_INFRASTRUCTURE:
            raise
        status = "BLOCKED"
        diagnostic = {"code": exc.diagnostic, "message": str(exc)}
    else:
        observed_exit = completed.returncode
        stdout = completed.stdout
        stderr = completed.stderr
        if observed_exit == expected_exit:
            status = "PASS"
        elif observed_exit in blocked_exit_codes:
            status = "BLOCKED"
            diagnostic = {
                "code": "RUN_DECLARED_BLOCK",
                "message": (
                    f"gate reported infrastructure block with exit {observed_exit}; "
                    f"declared blocked exits are {blocked_exit_codes}"
                ),
            }
        else:
            status = "FAIL"
    ended_at = datetime.now(timezone.utc).isoformat(timespec="seconds")

    retained_payloads: list[tuple[str, bytes, str | None]] = [
        ("stdout.bin", _prepare_retained_bytes(stdout, rules), None),
        ("stderr.bin", _prepare_retained_bytes(stderr, rules), None),
    ]
    if status != "BLOCKED":
        for position, relative in enumerate(artifact_paths, 3):
            emitted = _require_direct_regular_file(repository, relative, role="gate artifact")
            try:
                metadata = emitted.lstat()
                if metadata.st_nlink != 1:
                    raise ClonePackError(
                        f"gate artifact must not be hard-linked: {relative}",
                        diagnostic="RUN_ARTIFACT_INVALID",
                    )
                value = emitted.read_bytes()
            except ClonePackError:
                raise
            except OSError as exc:
                raise ClonePackError(
                    f"cannot read gate artifact: {relative}: {exc}",
                    diagnostic="RUN_ARTIFACT_INVALID",
                ) from exc
            if relative in artifact_before:
                current_state = (
                    metadata.st_dev,
                    metadata.st_ino,
                    metadata.st_size,
                    metadata.st_mtime_ns,
                    metadata.st_ctime_ns,
                    sha256_bytes(value),
                )
                if current_state == artifact_before[relative]:
                    raise ClonePackError(
                        f"gate artifact was not created or rewritten by the current run: {relative}",
                        exit_code=4,
                        diagnostic="RUN_ARTIFACT_STALE",
                    )
            retained_payloads.append(
                (
                    f"emitted-{position:02d}-{emitted.name}",
                    _prepare_retained_bytes(value, rules),
                    relative,
                )
            )

    if diagnostic is not None:
        retained_message, _ = _apply_redactions(diagnostic["message"].encode("utf-8"), rules)
        diagnostic["message"] = retained_message.decode("utf-8")
    artifacts = [
        _retained_bytes_artifact(
            value,
            artifact_dir / name,
            pack,
            f"ART-{run_id}-{position:02d}",
            source_path=source_path,
        )
        for position, (name, value, source_path) in enumerate(retained_payloads, 1)
    ]
    run = {
        "schema_version": "clone-run/v2",
        "run_id": run_id,
        "pack_id": manifest["pack_id"],
        "pack_revision": manifest["pack_revision"],
        "reference_baseline_id": manifest["reference_baseline_id"],
        "clone_revision": manifest["repository_state"]["revision"],
        "clone_diff_sha256": manifest["repository_state"].get("diff_sha256"),
        "environment_id": environment_id,
        "gate_id": gate_id,
        "contract_hashes": contract_hashes,
        "execution_contract": execution_contract,
        "argv": argv,
        "started_at": started_at,
        "ended_at": ended_at,
        "elapsed_ms_context": round((time.monotonic() - started) * 1000, 3),
        "expected_exit": expected_exit,
        "observed_exit": observed_exit,
        "result": status,
        "covered_ids": covered_ids,
        "oracle_ids": oracle_ids,
        "artifacts": artifacts,
        "normalizations": normalizations,
        "redactions": rules,
        "runner_version": TOOL_VERSION,
        "diagnostic": diagnostic,
    }
    _require_schema(run, "clone-run-v2.schema.json", "RUN_INVALID")

    run_content = canonical_json(run)
    anchor = f'"run_id": "{run_id}"'
    anchor_line = next(line for line in run_content.splitlines(keepends=True) if anchor in line)
    index["records"].append(
        {
            "id": run_id,
            "kind": "RUN",
            "locator": {
                "path": run_path.relative_to(pack).as_posix(),
                "anchor": anchor,
                "sha256": sha256_bytes(anchor_line.encode("utf-8")),
            },
            "links": _run_index_links(records, covered_ids, oracle_ids, gate_id),
            "applicability": "MVP",
            "state": status,
            "attributes": {"result": status, "gate_id": gate_id, "environment_id": environment_id},
        }
    )
    _add_run_backlinks(records, run_id, covered_ids, oracle_ids, gate_id)
    transaction_files: dict[Path, str | bytes] = {
        run_path: run_content,
        index_path: canonical_json(index),
        **{artifact_dir / name: value for name, value, _ in retained_payloads},
    }
    if enhancement_plan_path is not None and enhancement_plan is not None and enhancement_gate is not None:
        enhancement_gate["result_id"] = run_id
        references = enhancement_plan["result_references"]
        references["run_ids"] = sorted(set(str(item) for item in references["run_ids"] + [run_id]))
        transaction_files[enhancement_plan_path] = canonical_json(enhancement_plan)
    atomic_write_many(
        transaction_files,
        transaction_root=pack,
        operation=f"record-run:{run_id}",
    )
    return run, 0 if status == "PASS" else (EXIT_INFRASTRUCTURE if status == "BLOCKED" else EXIT_HOLD)


def record_manual(pack: Path, test_id: str, procedure: Path, observer: str, authority: str, artifact_paths: list[str], timestamp: str | None = None) -> dict[str, Any]:
    if not observer.strip() or not authority.strip():
        raise ClonePackError("manual verification requires observer and authority", exit_code=2, diagnostic="ARG_INVALID")
    pack = pack.expanduser().resolve()
    manifest = _load_v2_manifest(pack)
    index_path = _manifest_index_path(pack, manifest)
    index = load_json(index_path)
    records = _index_record_map(index)
    test = _required_record(records, test_id, {"TEST"}, "manual test")
    attributes = test.get("attributes") if isinstance(test.get("attributes"), dict) else {}
    environment_id = attributes.get("environment_id")
    _required_record(records, environment_id, {"ENV"}, "manual environment")
    links = test.get("links") if isinstance(test.get("links"), dict) else {}
    acceptance_ids = _record_id_array(links.get("acceptance", []), "manual test acceptance links")
    requirement_ids = _record_id_array(links.get("requirements", []), "manual test requirement links")
    oracle_ids = _record_id_array(links.get("oracles", []), "manual test oracle links")
    for identifier in acceptance_ids:
        _required_record(records, identifier, {"AC"}, "manual acceptance ID")
    for identifier in requirement_ids:
        _required_record(records, identifier, {"REQ"}, "manual requirement ID")
    for identifier in oracle_ids:
        _required_record(records, identifier, RUN_ORACLE_KINDS, "manual oracle ID")
    covered_ids = sorted([test_id, *acceptance_ids, *requirement_ids])
    contract_hashes = _governing_contract_hashes(
        records,
        [environment_id, *covered_ids, *oracle_ids],
    )
    procedure = procedure.expanduser().resolve()
    if not procedure.is_file():
        raise ClonePackError("manual procedure file is missing", exit_code=2, diagnostic="ARG_INVALID")
    procedure_sha256 = sha256_file(procedure)
    expected_procedure_sha256 = attributes.get("manual_procedure_sha256")
    if not isinstance(expected_procedure_sha256, str) or not re.fullmatch(r"[0-9a-f]{64}", expected_procedure_sha256):
        raise ClonePackError(
            "manual TEST must pin attributes.manual_procedure_sha256",
            diagnostic="MANUAL_PROCEDURE_UNPINNED",
        )
    if procedure_sha256 != expected_procedure_sha256:
        raise ClonePackError(
            "supplied manual procedure differs from TEST.attributes.manual_procedure_sha256",
            diagnostic="MANUAL_PROCEDURE_MISMATCH",
        )
    resolved_artifacts: list[Path] = []
    for relative in artifact_paths:
        path = resolve_inside(pack, relative, must_exist=True)
        if not path.is_file():
            raise ClonePackError(f"manual artifact is not a file: {relative}", diagnostic="RUN_ARTIFACT_INVALID")
        resolved_artifacts.append(path)
    if len({path.resolve() for path in resolved_artifacts}) != len(resolved_artifacts):
        raise ClonePackError("manual artifact paths must be unique", diagnostic="RUN_ARTIFACT_INVALID")
    run_id, run_path, artifact_dir = _next_run_paths(pack, manifest, records)
    recorded_at, _ = utc_now(timestamp)
    artifact_dir.mkdir(parents=True)
    procedure_copy = artifact_dir / "procedure.md"
    procedure_copy.write_bytes(procedure.read_bytes())
    artifacts = []
    artifacts.append(_artifact(procedure_copy, pack, f"ART-{run_id}-01"))
    for index_number, path in enumerate(resolved_artifacts, 2):
        artifacts.append(_artifact(path, pack, f"ART-{run_id}-{index_number:02d}"))
    run = {
        "schema_version": "clone-manual-run/v2",
        "run_id": run_id,
        "pack_id": manifest["pack_id"],
        "pack_revision": manifest["pack_revision"],
        "reference_baseline_id": manifest["reference_baseline_id"],
        "clone_revision": manifest["repository_state"]["revision"],
        "clone_diff_sha256": manifest["repository_state"].get("diff_sha256"),
        "environment_id": environment_id,
        "gate_id": "MANUAL",
        "contract_hashes": contract_hashes,
        "argv": [],
        "started_at": recorded_at,
        "ended_at": recorded_at,
        "expected_exit": 0,
        "observed_exit": 0,
        "result": "PASS",
        "covered_ids": covered_ids,
        "oracle_ids": oracle_ids,
        "artifacts": artifacts,
        "normalizations": [],
        "redactions": [],
        "runner_version": TOOL_VERSION,
        "manual_attestation": {"procedure_sha256": procedure_sha256, "observer": observer, "authority": authority},
    }
    atomic_write_json(run_path, run)
    anchor = f'"run_id": "{run_id}"'
    anchor_line = next(line for line in run_path.read_text(encoding="utf-8").splitlines(keepends=True) if anchor in line)
    index["records"].append(
        {
            "id": run_id,
            "kind": "RUN",
            "locator": {"path": run_path.relative_to(pack).as_posix(), "anchor": anchor, "sha256": sha256_bytes(anchor_line.encode("utf-8"))},
            "links": _run_index_links(records, covered_ids, oracle_ids, None),
            "applicability": "MVP",
            "state": "PASS",
            "attributes": {
                "result": "PASS",
                "gate_id": "MANUAL",
                "environment_id": environment_id,
                "observer": observer,
            },
        }
    )
    _add_run_backlinks(records, run_id, covered_ids, oracle_ids, None)
    atomic_write_json(index_path, index)
    return run


def execute_assurance(
    pack: Path,
    case_ids: list[str],
    *,
    all_cases: bool = False,
) -> tuple[dict[str, Any], int]:
    """Execute an exact assurance selection and return its deterministic aggregate."""

    pack = pack.expanduser().resolve()
    recover_atomic_transactions(pack)
    manifest = _load_v2_manifest(pack)
    plan_path = _manifest_plan_path(pack, manifest, "assurance")
    plan = load_json(plan_path)
    _require_schema(plan, "assurance-plan-v2.schema.json", "PLAN_INVALID")
    enhancement_plan_path: Path | None = None
    enhancement_plan: dict[str, Any] | None = None
    workstream = manifest.get("workstream")
    if isinstance(workstream, dict) and workstream.get("kind") == "brownfield-enhancement":
        raw_enhancement_path = manifest.get("plans", {}).get("enhancement")
        if not isinstance(raw_enhancement_path, str) or not raw_enhancement_path:
            raise ClonePackError("brownfield manifest lacks an enhancement plan", diagnostic="PLAN_INVALID")
        enhancement_plan_path = resolve_inside(pack, raw_enhancement_path, must_exist=True)
        enhancement_plan = load_json(enhancement_plan_path)
        assurance_contract = enhancement_plan.get("assurance")
        result_references = enhancement_plan.get("result_references")
        if (
            not isinstance(assurance_contract, dict)
            or not isinstance(assurance_contract.get("required_ids"), list)
            or not isinstance(assurance_contract.get("result_ids"), list)
            or not isinstance(result_references, dict)
            or not isinstance(result_references.get("assurance_ids"), list)
        ):
            raise ClonePackError(
                "brownfield assurance result references are incomplete",
                diagnostic="PLAN_INVALID",
            )
    cases = plan.get("cases")
    if not isinstance(cases, list) or any(not isinstance(case, dict) for case in cases):
        raise ClonePackError("assurance cases must be an object array", diagnostic="PLAN_INVALID")
    if len(case_ids) != len(set(case_ids)):
        raise ClonePackError("assurance --case values must be unique", exit_code=2, diagnostic="ARG_INVALID")
    if all_cases and case_ids:
        raise ClonePackError("--all and --case are mutually exclusive", exit_code=2, diagnostic="ARG_CONFLICT")

    if case_ids:
        requested = set(case_ids)
        selected = [case for case in cases if case.get("id") in requested]
        if {str(case.get("id")) for case in selected} != requested:
            raise ClonePackError("unknown assurance case requested", exit_code=2, diagnostic="CASE_UNKNOWN")
    elif all_cases:
        selected = list(cases)
    else:
        selected = [case for case in cases if case.get("required") is True]
    selected.sort(key=lambda case: str(case.get("id")))
    if not selected:
        raise ClonePackError("assurance selection is empty", diagnostic="CASE_SELECTION_EMPTY")
    selected_ids = [str(case.get("id")) for case in selected]
    if any(not re.fullmatch(r"ASSURE-[0-9]{3,}", case_id) for case_id in selected_ids):
        raise ClonePackError("assurance case ID is invalid", diagnostic="PLAN_INVALID")
    if len(selected_ids) != len(set(selected_ids)):
        raise ClonePackError("assurance case IDs must be unique", diagnostic="ID_DUPLICATE")

    index = load_json(_manifest_index_path(pack, manifest))
    records = _index_record_map(index)
    repository = Path(str(manifest["repository_root"])).resolve()
    assurance_root = _require_real_pack_directory(pack, "evidence/assurance")
    contexts: list[dict[str, Any]] = []
    for case in selected:
        _case_counterpart(records, case, "ASSURE", "assurance case")
        argv = case.get("argv")
        if not isinstance(argv, list) or not argv or any(not isinstance(item, str) or not item for item in argv):
            raise ClonePackError("assurance argv must be a non-empty string array", diagnostic="PLAN_INVALID")
        cwd_value = case.get("cwd", ".")
        if not isinstance(cwd_value, str) or not cwd_value:
            raise ClonePackError("assurance cwd must be a non-empty relative path", diagnostic="PLAN_INVALID")
        cwd = repository if cwd_value == "." else resolve_inside(repository, cwd_value, must_exist=True)
        if not cwd.is_dir():
            raise ClonePackError("assurance cwd must name a directory", diagnostic="PLAN_INVALID")
        timeout = _validate_timeout(case.get("timeout_seconds", 300), "assurance timeout_seconds")
        expected_exit = case.get("expected_exit", 0)
        if isinstance(expected_exit, bool) or not isinstance(expected_exit, int):
            raise ClonePackError("assurance expected_exit must be an integer", diagnostic="PLAN_INVALID")
        artifact_paths = _validate_declared_artifact_paths(
            case.get("artifact_paths", []),
            "assurance artifact_paths",
        )
        case_id = str(case["id"])
        output_dir = assurance_root / case_id
        contexts.append(
            {
                "case": case,
                "case_id": case_id,
                "argv": list(argv),
                "cwd": cwd,
                "timeout": timeout,
                "expected_exit": expected_exit,
                "artifact_paths": artifact_paths,
                "output_dir": output_dir,
            }
        )
    collisions = sorted(
        context["case_id"]
        for context in contexts
        if context["output_dir"].exists()
        or context["output_dir"].is_symlink()
        or context["case"].get("result") is not None
    )
    if collisions:
        raise ClonePackError(
            "assurance output already exists: " + ", ".join(collisions),
            diagnostic="OUTPUT_EXISTS",
        )

    result_pointers: list[dict[str, Any]] = []
    result_statuses: list[str] = []
    transaction_files: dict[Path, str | bytes] = {}
    launch_environment = {
        key: os.environ[key]
        for key in ("PATH", "SYSTEMROOT", "WINDIR", "COMSPEC", "PATHEXT", "TMP", "TEMP")
        if key in os.environ
    }
    for context in contexts:
        case = context["case"]
        case_id = context["case_id"]
        case_sha256 = case_contract_sha256(case)
        output_dir = context["output_dir"]
        started_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
        started = time.monotonic()
        stdout = b""
        stderr = b""
        observed_exit: int | None = None
        diagnostic: dict[str, str] | None = None
        status = "PASS"
        try:
            completed = _run_process(
                context["argv"],
                context["cwd"],
                launch_environment,
                context["timeout"],
            )
        except ClonePackError as exc:
            status = "BLOCKED"
            diagnostic = {"code": exc.diagnostic, "message": str(exc)}
        else:
            stdout = completed.stdout
            stderr = completed.stderr
            observed_exit = completed.returncode
            if observed_exit != context["expected_exit"]:
                status = "FAIL"
                diagnostic = {
                    "code": "ASSURANCE_EXIT_MISMATCH",
                    "message": f"assurance case exited {observed_exit}; expected {context['expected_exit']}",
                }
        ended_at = datetime.now(timezone.utc).isoformat(timespec="seconds")

        retained_payloads: list[tuple[str, bytes]] = [
            ("stdout.bin", stdout),
            ("stderr.bin", stderr),
        ]
        if status != "BLOCKED":
            try:
                for artifact_index, relative in enumerate(context["artifact_paths"], 3):
                    emitted = _require_direct_regular_file(
                        repository,
                        relative,
                        role="assurance artifact",
                    )
                    metadata = emitted.lstat()
                    if metadata.st_nlink != 1:
                        raise ClonePackError(
                            f"assurance artifact must not be hard-linked: {relative}",
                            diagnostic="ASSURANCE_ARTIFACT_INVALID",
                        )
                    retained_payloads.append(
                        (f"emitted-{artifact_index:02d}-{emitted.name}", emitted.read_bytes())
                    )
            except (ClonePackError, OSError) as exc:
                status = "BLOCKED"
                if isinstance(exc, ClonePackError):
                    diagnostic = {"code": exc.diagnostic, "message": str(exc)}
                else:
                    diagnostic = {
                        "code": "ASSURANCE_ARTIFACT_UNAVAILABLE",
                        "message": f"cannot retain assurance artifact: {exc}",
                    }
        artifacts = [
            _retained_bytes_artifact(
                value,
                output_dir / name,
                pack,
                f"ART-{case_id}-{position:02d}",
            )
            for position, (name, value) in enumerate(retained_payloads, 1)
        ]
        result = {
            "schema_version": "clone-assurance-result/v2",
            "assurance_id": case_id,
            "pack_id": manifest["pack_id"],
            "pack_revision": manifest["pack_revision"],
            "reference_baseline_id": manifest["reference_baseline_id"],
            "clone_revision": manifest["repository_state"]["revision"],
            "clone_diff_sha256": manifest["repository_state"].get("diff_sha256"),
            "case_sha256": case_sha256,
            "kind": case.get("kind"),
            "started_at": started_at,
            "ended_at": ended_at,
            "elapsed_ms_context": round((time.monotonic() - started) * 1000, 3),
            "expected_exit": context["expected_exit"],
            "observed_exit": observed_exit,
            "status": status,
            "diagnostic": diagnostic,
            "artifacts": artifacts,
            "runner_version": TOOL_VERSION,
        }

        result_path = output_dir / "result.json"
        result_text = canonical_json(result)
        transaction_files[result_path] = result_text
        transaction_files.update({output_dir / name: value for name, value in retained_payloads})
        pointer = {
            "status": status,
            "path": result_path.relative_to(pack).as_posix(),
            "sha256": sha256_bytes(result_text.encode("utf-8")),
        }
        case["result"] = pointer
        result_pointers.append({"assurance_id": case_id, **pointer})
        result_statuses.append(status)

    transaction_files[plan_path] = canonical_json(plan)
    if enhancement_plan_path is not None and enhancement_plan is not None:
        assurance_contract = enhancement_plan["assurance"]
        assurance_contract["result_ids"] = sorted(
            set(str(item) for item in assurance_contract["result_ids"] + selected_ids)
        )
        result_references = enhancement_plan["result_references"]
        result_references["assurance_ids"] = sorted(
            set(str(item) for item in result_references["assurance_ids"] + selected_ids)
        )
        transaction_files[enhancement_plan_path] = canonical_json(enhancement_plan)
    atomic_write_many(
        transaction_files,
        transaction_root=pack,
        operation="assure:" + ",".join(selected_ids),
    )

    if "BLOCKED" in result_statuses:
        aggregate_status = "BLOCKED"
        final_exit = EXIT_INFRASTRUCTURE
    elif "FAIL" in result_statuses:
        aggregate_status = "FAIL"
        final_exit = EXIT_HOLD
    else:
        aggregate_status = "PASS"
        final_exit = 0
    aggregate = {
        "schema_version": "clone-assurance-batch-result/v2",
        "pack_id": manifest["pack_id"],
        "pack_revision": manifest["pack_revision"],
        "selected_case_ids": selected_ids,
        "status": aggregate_status,
        "exit_code": final_exit,
        "results": result_pointers,
    }
    return aggregate, final_exit


def run_assurance(pack: Path, case_ids: list[str], *, all_cases: bool = False) -> int:
    """Compatibility wrapper for callers that consume only the process exit status."""

    _, exit_code = execute_assurance(pack, case_ids, all_cases=all_cases)
    return exit_code
