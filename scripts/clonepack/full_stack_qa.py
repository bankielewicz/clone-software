from __future__ import annotations

import ipaddress
import re
import stat
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import unquote_to_bytes, urlsplit

from .common import (
    ClonePackError,
    canonical_json,
    load_json,
    safe_relative_path,
    sha256_bytes,
    sha256_file,
)
from .schema import SchemaDefinitionError, validate_schema_file


QA_PLAN_PATH = "full_stack_qa_plan.json"
QA_RESULT_SCHEMA = Path(__file__).resolve().parents[2] / "assets" / "schemas" / "full-stack-qa-result-v1.schema.json"
SECRET_KEY = re.compile(r"(?:TOKEN|KEY|SECRET|PASSWORD|AUTH|COOKIE|CREDENTIAL)", re.IGNORECASE)
UNRESOLVED_MARKER = re.compile(r"\[\[(?:REQUIRED|MIGRATION_REQUIRED):[^\]]*\]\]")
DECISION_KINDS = {"DEC", "ADR", "GAPDEC"}
ORACLE_KINDS = {"E", "ART", "CAP"}


@dataclass(order=True, frozen=True)
class FullStackQaIssue:
    path: str
    code: str
    message: str
    record_id: str = ""
    hold: bool = False


def full_stack_qa_contract_sha256(plan: dict[str, Any]) -> str:
    contract = {key: value for key, value in plan.items() if key != "contract_sha256"}
    return sha256_bytes(canonical_json(contract).encode("utf-8"))


def _issue(
    issues: list[FullStackQaIssue],
    path: str,
    code: str,
    message: str,
    record_id: str = "",
    *,
    hold: bool = False,
) -> None:
    issues.append(FullStackQaIssue(path, code, message, record_id, hold))


def _record(
    issues: list[FullStackQaIssue],
    records: dict[str, dict[str, Any]],
    identifier: Any,
    kinds: set[str],
    role: str,
    path: str,
) -> dict[str, Any] | None:
    if not isinstance(identifier, str) or not identifier:
        _issue(issues, path, "QA_TRACE_INVALID", f"{role} ID is missing")
        return None
    record = records.get(identifier)
    if record is None:
        _issue(issues, path, "QA_TRACE_INVALID", f"{role} references undefined ID {identifier}", identifier)
        return None
    if record.get("kind") not in kinds:
        _issue(
            issues,
            path,
            "QA_TRACE_INVALID",
            f"{role} {identifier} has kind {record.get('kind')}; expected {', '.join(sorted(kinds))}",
            identifier,
        )
        return None
    return record


def _links(record: dict[str, Any] | None, relation: str) -> set[str]:
    if record is None:
        return set()
    links = record.get("links") if isinstance(record.get("links"), dict) else {}
    values = links.get(relation, [])
    if not isinstance(values, list) or any(not isinstance(item, str) for item in values):
        return set()
    return set(values)


def _attributes(record: dict[str, Any] | None) -> dict[str, Any]:
    if record is None or not isinstance(record.get("attributes"), dict):
        return {}
    return record["attributes"]


def _list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _string_set(value: Any) -> set[str]:
    return {item for item in _list(value) if isinstance(item, str)}


def _unresolved_marker_paths(value: Any, path: str = "") -> list[str]:
    matches: list[str] = []
    if isinstance(value, dict):
        for key, item in sorted(value.items()):
            matches.extend(_unresolved_marker_paths(item, f"{path}/{key}"))
    elif isinstance(value, list):
        for position, item in enumerate(value):
            matches.extend(_unresolved_marker_paths(item, f"{path}/{position}"))
    elif isinstance(value, str) and UNRESOLVED_MARKER.search(value):
        matches.append(path or "/")
    return matches


def _json_pointer_value(document: Any, pointer: Any) -> tuple[bool, Any]:
    if not isinstance(pointer, str) or not pointer.startswith("/"):
        return False, None
    current = document
    for encoded in pointer[1:].split("/"):
        token = encoded.replace("~1", "/").replace("~0", "~")
        if isinstance(current, dict) and token in current:
            current = current[token]
        elif (
            isinstance(current, list)
            and re.fullmatch(r"0|[1-9][0-9]*", token) is not None
            and int(token) < len(current)
        ):
            current = current[int(token)]
        else:
            return False, None
    return True, current


def _identity_consumer_pointer_allowed(kind: Any, pointer: Any, journey_position: int) -> bool:
    if not isinstance(kind, str) or not isinstance(pointer, str):
        return False
    prefix = f"/journeys/{journey_position}"
    patterns = {
        "WIRE_PATH": rf"^{re.escape(prefix)}/wire/(?:path|additional_exchanges/(?:0|[1-9][0-9]*)/path)$",
        "SERVICE": rf"^{re.escape(prefix)}/service/(?:probe|postcondition)$",
        "PERSISTENCE": rf"^{re.escape(prefix)}/persistence/postcondition$",
        "SUPPORTING_SERVICE": r"^/owned_stack/supporting_services/(?:0|[1-9][0-9]*)/assertion$",
        "EXTERNAL_DEPENDENCY": r"^/external_dependencies/(?:0|[1-9][0-9]*)/assertion$",
        "JOB": rf"^{re.escape(prefix)}/jobs/assertion$",
        "UI": rf"^{re.escape(prefix)}/ui/assertion$",
    }
    pattern = patterns.get(kind)
    return pattern is not None and re.fullmatch(pattern, pointer) is not None


def _wire_exchange_position(pointer: str, journey_position: int) -> int | None:
    primary = f"/journeys/{journey_position}/wire/path"
    if pointer == primary:
        return 0
    match = re.fullmatch(
        rf"/journeys/{journey_position}/wire/additional_exchanges/((?:0|[1-9][0-9]*))/path",
        pointer,
    )
    return int(match.group(1)) + 1 if match is not None else None


def _decoded_path_segment(value: str, value_type: Any) -> str | None:
    if re.search(r"%(?![0-9A-Fa-f]{2})", value):
        return None
    try:
        decoded = unquote_to_bytes(value).decode("utf-8")
    except UnicodeDecodeError:
        return None
    if value_type == "integer" and re.fullmatch(r"0|-?[1-9][0-9]*", decoded) is None:
        return None
    return decoded


def _wire_path_matches_binding(
    expected_path: Any,
    observed_path: Any,
    bindings_by_name: dict[str, tuple[str, str]],
) -> bool:
    if not isinstance(expected_path, str) or not isinstance(observed_path, str):
        return False
    expected_segments = expected_path.split("/")
    observed_segments = observed_path.split("/")
    if len(expected_segments) != len(observed_segments):
        return False
    for expected_segment, observed_segment in zip(expected_segments, observed_segments, strict=True):
        marker = re.fullmatch(r"\{([a-z][a-z0-9_]*)\}", expected_segment)
        if marker is None:
            if expected_segment != observed_segment:
                return False
            continue
        binding = bindings_by_name.get(marker.group(1))
        if binding is None:
            return False
        expected_sha256, value_type = binding
        decoded = _decoded_path_segment(observed_segment, value_type)
        if decoded is None or sha256_bytes(decoded.encode("utf-8")) != expected_sha256:
            return False
    return True


def _direct_repository_file(repository: Path, value: Any) -> Path:
    relative = safe_relative_path(value)
    root = repository.resolve()
    current = root
    for part in relative.parts:
        current = current / part
        try:
            metadata = current.lstat()
        except OSError as exc:
            raise ClonePackError(
                f"required repository file does not exist: {value}",
                diagnostic="FILE_MISSING",
            ) from exc
        if stat.S_ISLNK(metadata.st_mode):
            raise ClonePackError(
                f"repository QA path must not contain a symlink: {value}",
                exit_code=4,
                diagnostic="PATH_UNSAFE",
            )
    if not stat.S_ISREG(current.lstat().st_mode):
        raise ClonePackError(
            f"repository QA path must name a regular file: {value}",
            exit_code=4,
            diagnostic="PATH_UNSAFE",
        )
    try:
        current.resolve().relative_to(root)
    except ValueError as exc:
        raise ClonePackError(
            f"repository QA path escapes the repository: {value}",
            exit_code=4,
            diagnostic="PATH_ESCAPE",
        ) from exc
    return current


def _check_repository_hash(
    issues: list[FullStackQaIssue],
    repository: Path,
    path_value: Any,
    expected: Any,
    owner: str,
) -> None:
    try:
        path = _direct_repository_file(repository, path_value)
        actual = sha256_file(path)
    except ClonePackError as exc:
        _issue(issues, owner, exc.diagnostic, str(exc))
        return
    if not isinstance(expected, str) or actual != expected:
        _issue(
            issues,
            owner,
            "QA_ARTIFACT_HASH_MISMATCH",
            f"pinned SHA-256 does not match repository file {path_value}",
        )


def _check_decisions(
    issues: list[FullStackQaIssue],
    records: dict[str, dict[str, Any]],
    values: Any,
    owner: str,
    *,
    required: bool,
) -> None:
    identifiers = values if isinstance(values, list) else []
    if required and not identifiers:
        _issue(issues, owner, "QA_AUTHORITY_MISSING", "an authority decision is required")
    for identifier in identifiers:
        _record(issues, records, identifier, DECISION_KINDS, "authority decision", owner)


def _check_command_environment(
    issues: list[FullStackQaIssue],
    command: Any,
    owner: str,
) -> None:
    if not isinstance(command, dict):
        return
    environment = command.get("environment")
    if not isinstance(environment, dict):
        return
    for key, value in sorted(environment.items()):
        if SECRET_KEY.search(str(key)) and (
            not isinstance(value, str) or re.fullmatch(r"env:[A-Za-z_][A-Za-z0-9_]*", value) is None
        ):
            _issue(
                issues,
                owner,
                "QA_SECRET_INVALID",
                f"secret-like environment key {key} requires env:NAME indirection",
            )


def _http_origin(value: Any, *, origin_only: bool = False) -> tuple[str, str, int] | None:
    if not isinstance(value, str):
        return None
    try:
        parsed = urlsplit(value)
        port = parsed.port
    except ValueError:
        return None
    if (
        parsed.scheme not in {"http", "https"}
        or not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
        or (origin_only and (parsed.path not in {"", "/"} or parsed.query or parsed.fragment))
    ):
        return None
    return (
        parsed.scheme.lower(),
        parsed.hostname.lower(),
        port if port is not None else (443 if parsed.scheme.lower() == "https" else 80),
    )


def _is_loopback_host(host: str) -> bool:
    if host == "localhost":
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def _external_endpoint(
    protocol_value: Any,
    endpoint_value: Any,
) -> tuple[str, tuple[str, str, int] | None] | None:
    if not isinstance(protocol_value, str) or not isinstance(endpoint_value, str):
        return None
    protocol = protocol_value.lower()
    has_scheme = "://" in endpoint_value
    if protocol in {"http", "https"} and not has_scheme:
        return None
    candidate = endpoint_value if has_scheme else f"{protocol}://{endpoint_value}"
    try:
        parsed = urlsplit(candidate)
        _ = parsed.port
    except ValueError:
        return None
    if (
        parsed.scheme.lower() != protocol
        or not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
    ):
        return None
    if parsed.query:
        if re.search(r"%(?![0-9A-Fa-f]{2})", parsed.query):
            return None
        try:
            decoded_query = unquote_to_bytes(parsed.query).decode("utf-8")
        except UnicodeDecodeError:
            return None
        if SECRET_KEY.search(decoded_query):
            return None
    origin = _http_origin(endpoint_value) if protocol in {"http", "https"} else None
    if protocol in {"http", "https"} and origin is None:
        return None
    return parsed.hostname.lower(), origin


def _check_readiness(
    issues: list[FullStackQaIssue],
    readiness: Any,
    owner: str,
    allowed_origins: set[tuple[str, str, int]],
    *,
    role: str,
) -> None:
    if not isinstance(readiness, dict):
        return
    if readiness.get("kind") == "HTTP":
        readiness_origin = _http_origin(readiness.get("target"))
        if readiness_origin is None or readiness_origin not in allowed_origins:
            _issue(
                issues,
                f"{owner}/target",
                "QA_ORIGIN_UNAUTHORIZED",
                f"{role} HTTP readiness target origin is absent from environment.allowed_origins",
            )
    elif readiness.get("kind") == "COMMAND":
        _check_command_environment(issues, readiness.get("command"), f"{owner}/command")


def _run_field(run: dict[str, Any], name: str) -> Any:
    if name in run:
        return run.get(name)
    attributes = run.get("attributes") if isinstance(run.get("attributes"), dict) else {}
    return attributes.get(name)


def _run_sequence(identifier: str) -> tuple[int, str]:
    match = re.fullmatch(r"RUN-([0-9]+)", identifier)
    return (int(match.group(1)) if match else -1, identifier)


def _direct_pack_file(pack: Path, value: Any) -> Path:
    relative = safe_relative_path(value)
    root = pack.resolve()
    current = root
    for part in relative.parts:
        current = current / part
        try:
            metadata = current.lstat()
        except OSError as exc:
            raise ClonePackError(
                f"retained QA result does not exist: {value}",
                diagnostic="FILE_MISSING",
            ) from exc
        if stat.S_ISLNK(metadata.st_mode):
            raise ClonePackError(
                f"retained QA result path must not contain a symlink: {value}",
                exit_code=4,
                diagnostic="PATH_UNSAFE",
            )
    if not stat.S_ISREG(current.lstat().st_mode):
        raise ClonePackError(
            f"retained QA result must be a regular file: {value}",
            exit_code=4,
            diagnostic="PATH_UNSAFE",
        )
    return current


def _validate_full_stack_result(
    issues: list[FullStackQaIssue],
    *,
    pack: Path,
    plan: dict[str, Any],
    run: dict[str, Any],
    run_id: str,
) -> None:
    owner = f"runs/{run_id}.json"
    ci = plan.get("ci") if isinstance(plan.get("ci"), dict) else {}
    result_source = ci.get("result_path")
    artifacts = run.get("artifacts") if isinstance(run.get("artifacts"), list) else []
    matches = [
        artifact
        for artifact in artifacts
        if isinstance(artifact, dict) and artifact.get("source_path") == result_source
    ]
    if len(matches) != 1:
        _issue(
            issues,
            owner,
            "QA_RESULT_MISSING",
            "latest PASS RUN must retain exactly one artifact from ci.result_path",
            run_id,
            hold=True,
        )
        return
    artifact = matches[0]
    if artifact.get("media_type") != "application/json":
        _issue(
            issues,
            owner,
            "QA_RESULT_INVALID",
            "canonical full-stack result artifact media_type must be application/json",
            run_id,
        )
        return
    try:
        retained = _direct_pack_file(pack, artifact.get("path"))
        if sha256_file(retained) != artifact.get("sha256"):
            raise ClonePackError(
                "retained full-stack result SHA-256 differs from RUN metadata",
                exit_code=4,
                diagnostic="ARTIFACT_HASH_MISMATCH",
            )
        result = load_json(retained)
        violations = validate_schema_file(result, QA_RESULT_SCHEMA)
    except (ClonePackError, SchemaDefinitionError) as exc:
        code = exc.diagnostic if isinstance(exc, ClonePackError) else "SCHEMA_INVALID"
        _issue(issues, owner, "QA_RESULT_INVALID", f"{code}: {exc}", run_id)
        return
    if violations:
        rendered = "; ".join(
            f"{violation.pointer or '/'}: {violation.message}" for violation in violations[:5]
        )
        _issue(
            issues,
            owner,
            "QA_RESULT_INVALID",
            "canonical full-stack result violates its schema: " + rendered,
            run_id,
        )
        return

    plan_environment = plan.get("environment") if isinstance(plan.get("environment"), dict) else {}
    playwright = plan.get("playwright") if isinstance(plan.get("playwright"), dict) else {}
    identity_mismatches = [
        name
        for name, expected in (
            ("plan_contract_sha256", plan.get("contract_sha256")),
            ("gate_id", ci.get("gate_id")),
            ("environment_id", plan_environment.get("environment_id")),
            ("playwright_project", playwright.get("project")),
        )
        if result.get(name) != expected
    ]
    expected_journeys = {
        str(journey.get("id")): journey
        for journey in _list(plan.get("journeys"))
        if isinstance(journey, dict) and isinstance(journey.get("id"), str)
    }
    result_entries = result.get("journeys", [])
    result_ids = [
        entry.get("id")
        for entry in result_entries
        if isinstance(entry, dict) and isinstance(entry.get("id"), str)
    ]
    if len(result_ids) != len(set(result_ids)) or set(result_ids) != set(expected_journeys):
        identity_mismatches.append("journeys")
    expected_external = {
        str(dependency.get("id")): dependency
        for dependency in _list(plan.get("external_dependencies"))
        if isinstance(dependency, dict) and isinstance(dependency.get("id"), str)
    }
    external_entries = result.get("external_dependencies", [])
    external_ids = [
        entry.get("id")
        for entry in external_entries
        if isinstance(entry, dict) and isinstance(entry.get("id"), str)
    ]
    if len(external_ids) != len(set(external_ids)) or set(external_ids) != set(expected_external):
        identity_mismatches.append("external_dependencies")
    owned_stack = plan.get("owned_stack") if isinstance(plan.get("owned_stack"), dict) else {}
    expected_supporting = {
        str(service.get("service_id")): service
        for service in _list(owned_stack.get("supporting_services"))
        if isinstance(service, dict) and isinstance(service.get("service_id"), str)
    }
    supporting_entries = result.get("supporting_services", [])
    supporting_ids = [
        entry.get("service_id")
        for entry in supporting_entries
        if isinstance(entry, dict) and isinstance(entry.get("service_id"), str)
    ]
    if len(supporting_ids) != len(set(supporting_ids)) or set(supporting_ids) != set(expected_supporting):
        identity_mismatches.append("supporting_services")
    if identity_mismatches:
        _issue(
            issues,
            owner,
            "QA_RESULT_CONTRACT_MISMATCH",
            "canonical result differs from the current plan contract: "
            + ", ".join(sorted(identity_mismatches)),
            run_id,
        )
        return
    if result.get("status") != "PASS":
        _issue(
            issues,
            owner,
            "QA_RESULT_NOT_PASS",
            "canonical full-stack result status is not PASS",
            run_id,
            hold=True,
        )

    actual_external = {str(entry["id"]): entry for entry in external_entries}
    for dependency_id, expected_dependency in sorted(expected_external.items()):
        actual_dependency = actual_external[dependency_id]
        expected_status = (
            "NOT_APPLICABLE"
            if expected_dependency.get("disposition") == "EXCLUDED"
            else "PASS"
        )
        if actual_dependency.get("status") != expected_status:
            _issue(
                issues,
                owner,
                "QA_RESULT_NOT_PASS",
                f"external dependency result has the wrong status: {dependency_id}",
                dependency_id,
                hold=True,
            )
        if (
            actual_dependency.get("disposition") != expected_dependency.get("disposition")
            or actual_dependency.get("assertion") != expected_dependency.get("assertion")
            or actual_dependency.get("interface") != expected_dependency.get("interface")
        ):
            _issue(
                issues,
                owner,
                "QA_RESULT_CONTRACT_MISMATCH",
                f"external dependency result differs from the plan: {dependency_id}",
                dependency_id,
            )

    actual_supporting = {str(entry["service_id"]): entry for entry in supporting_entries}
    for service_id, expected_service in sorted(expected_supporting.items()):
        actual_service = actual_supporting[service_id]
        if actual_service.get("status") != "PASS":
            _issue(
                issues,
                owner,
                "QA_RESULT_NOT_PASS",
                f"supporting service result is not PASS: {service_id}",
                service_id,
                hold=True,
            )
        if (
            actual_service.get("role") != expected_service.get("role")
            or actual_service.get("assertion") != expected_service.get("assertion")
        ):
            _issue(
                issues,
                owner,
                "QA_RESULT_CONTRACT_MISMATCH",
                f"supporting service result differs from the plan: {service_id}",
                service_id,
            )

    actual_journeys = {str(entry["id"]): entry for entry in result_entries}
    for journey_id, expected in sorted(expected_journeys.items()):
        actual = actual_journeys[journey_id]
        if any(
            not isinstance(expected.get(dimension), dict)
            for dimension in (
                "ui",
                "wire",
                "service",
                "persistence",
                "authorization",
                "jobs",
                "accessibility",
                "visual",
            )
        ):
            _issue(
                issues,
                owner,
                "QA_RESULT_CONTRACT_MISMATCH",
                f"current plan journey is not structurally comparable: {journey_id}",
                journey_id,
            )
            continue
        mismatches: list[str] = []
        expected_bindings = _list(expected.get("identity_bindings"))
        actual_bindings = _list(actual.get("identity_bindings"))
        expected_binding_ids = [
            binding.get("id")
            for binding in expected_bindings
            if isinstance(binding, dict) and isinstance(binding.get("id"), str)
        ]
        actual_binding_ids = [
            binding.get("id")
            for binding in actual_bindings
            if isinstance(binding, dict) and isinstance(binding.get("id"), str)
        ]
        bindings_by_name: dict[str, tuple[str, str]] = {}
        if (
            len(expected_binding_ids) != len(expected_bindings)
            or len(actual_binding_ids) != len(actual_bindings)
            or len(actual_binding_ids) != len(set(actual_binding_ids))
            or set(actual_binding_ids) != set(expected_binding_ids)
        ):
            mismatches.append("identity_bindings")
        else:
            actual_bindings_by_id = {
                str(binding["id"]): binding
                for binding in actual_bindings
                if isinstance(binding, dict)
            }
            for expected_binding in expected_bindings:
                if not isinstance(expected_binding, dict):
                    mismatches.append("identity_bindings")
                    continue
                binding_id = str(expected_binding["id"])
                actual_binding = actual_bindings_by_id[binding_id]
                if actual_binding.get("status") != "PASS":
                    _issue(
                        issues,
                        owner,
                        "QA_RESULT_NOT_PASS",
                        f"identity binding result is not PASS: {journey_id}.{binding_id}",
                        journey_id,
                        hold=True,
                    )
                if actual_binding.get("source") != expected_binding.get("source"):
                    mismatches.append(f"identity_bindings.{binding_id}.source")
                expected_consumers = [
                    {
                        "kind": consumer.get("kind"),
                        "contract_pointer": consumer.get("contract_pointer"),
                    }
                    for consumer in _list(expected_binding.get("consumers"))
                    if isinstance(consumer, dict)
                ]
                actual_consumers = _list(actual_binding.get("consumers"))
                actual_descriptors = [
                    {
                        "kind": consumer.get("kind"),
                        "contract_pointer": consumer.get("contract_pointer"),
                    }
                    for consumer in actual_consumers
                    if isinstance(consumer, dict)
                ]
                if actual_descriptors != expected_consumers:
                    mismatches.append(f"identity_bindings.{binding_id}.consumers")
                captured_sha256 = actual_binding.get("captured_value_sha256")
                for consumer_position, consumer in enumerate(actual_consumers):
                    if not isinstance(consumer, dict):
                        mismatches.append(
                            f"identity_bindings.{binding_id}.consumers[{consumer_position}]"
                        )
                        continue
                    if consumer.get("status") != "PASS":
                        _issue(
                            issues,
                            owner,
                            "QA_RESULT_NOT_PASS",
                            "identity-binding consumer is not PASS: "
                            f"{journey_id}.{binding_id}[{consumer_position}]",
                            journey_id,
                            hold=True,
                        )
                    if consumer.get("observed_value_sha256") != captured_sha256:
                        mismatches.append(
                            "identity_bindings."
                            f"{binding_id}.consumers[{consumer_position}].observed_value_sha256"
                        )
                name = expected_binding.get("name")
                source = expected_binding.get("source")
                if (
                    isinstance(name, str)
                    and isinstance(captured_sha256, str)
                    and isinstance(source, dict)
                    and isinstance(source.get("value_type"), str)
                ):
                    bindings_by_name[name] = (
                        captured_sha256,
                        str(source["value_type"]),
                    )
        if actual.get("status") != "PASS":
            _issue(
                issues,
                owner,
                "QA_RESULT_NOT_PASS",
                f"canonical result journey is not PASS: {journey_id}",
                journey_id,
                hold=True,
            )
        contract_pairs = (
            ("ui.assertion", actual["ui"].get("assertion"), expected["ui"].get("assertion")),
            ("wire.trigger", actual["wire"].get("trigger"), expected["wire"].get("trigger")),
            ("wire.method", actual["wire"].get("observed_method"), expected["wire"].get("method")),
            ("wire.status", actual["wire"].get("observed_status"), expected["wire"].get("expected_status")),
            (
                "wire.schema_assertion",
                actual["wire"].get("schema_assertion"),
                expected["wire"].get("schema_assertion"),
            ),
            ("service.probe", actual["service"].get("probe"), expected["service"].get("probe")),
            (
                "service.postcondition",
                actual["service"].get("postcondition"),
                expected["service"].get("postcondition"),
            ),
            (
                "persistence.verification_event",
                actual["persistence"].get("verification_event"),
                expected["persistence"].get("verification_event"),
            ),
            (
                "persistence.postcondition",
                actual["persistence"].get("postcondition"),
                expected["persistence"].get("postcondition"),
            ),
        )
        mismatches.extend(name for name, observed, declared in contract_pairs if observed != declared)
        if not _wire_path_matches_binding(
            expected["wire"].get("path"),
            actual["wire"].get("observed_path"),
            bindings_by_name,
        ):
            mismatches.append("wire.path")
        expected_exchanges = _list(expected["wire"].get("additional_exchanges"))
        actual_exchanges = _list(actual["wire"].get("additional_exchanges"))
        if len(actual_exchanges) != len(expected_exchanges):
            mismatches.append("wire.additional_exchanges")
        else:
            for exchange_position, (actual_exchange, expected_exchange) in enumerate(
                zip(actual_exchanges, expected_exchanges, strict=True)
            ):
                if not isinstance(actual_exchange, dict) or not isinstance(expected_exchange, dict):
                    mismatches.append(f"wire.additional_exchanges[{exchange_position}]")
                    continue
                exchange_pairs = (
                    ("trigger", "trigger"),
                    ("observed_method", "method"),
                    ("observed_status", "expected_status"),
                    ("schema_assertion", "schema_assertion"),
                )
                for actual_field, expected_field in exchange_pairs:
                    if actual_exchange.get(actual_field) != expected_exchange.get(expected_field):
                        mismatches.append(
                            f"wire.additional_exchanges[{exchange_position}].{actual_field}"
                        )
                if not _wire_path_matches_binding(
                    expected_exchange.get("path"),
                    actual_exchange.get("observed_path"),
                    bindings_by_name,
                ):
                    mismatches.append(
                        f"wire.additional_exchanges[{exchange_position}].observed_path"
                    )
                if actual_exchange.get("status") != "PASS":
                    _issue(
                        issues,
                        owner,
                        "QA_RESULT_NOT_PASS",
                        "canonical additional wire exchange is not PASS: "
                        f"{journey_id}[{exchange_position}]",
                        journey_id,
                        hold=True,
                    )
        for dimension in ("ui", "wire", "service", "persistence"):
            if actual[dimension].get("status") != "PASS":
                _issue(
                    issues,
                    owner,
                    "QA_RESULT_NOT_PASS",
                    f"canonical result dimension is not PASS: {journey_id}.{dimension}",
                    journey_id,
                    hold=True,
                )
        for dimension in ("authorization", "jobs", "accessibility", "visual"):
            expected_dimension = expected[dimension]
            actual_dimension = actual[dimension]
            expected_status = (
                "NOT_APPLICABLE"
                if expected_dimension.get("disposition") == "NOT_APPLICABLE"
                else "PASS"
            )
            if actual_dimension.get("status") != expected_status:
                _issue(
                    issues,
                    owner,
                    "QA_RESULT_NOT_PASS",
                    f"canonical optional dimension has the wrong status: {journey_id}.{dimension}",
                    journey_id,
                    hold=True,
                )
            if actual_dimension.get("assertion") != expected_dimension.get("assertion"):
                mismatches.append(f"{dimension}.assertion")
        if mismatches:
            _issue(
                issues,
                owner,
                "QA_RESULT_CONTRACT_MISMATCH",
                f"canonical journey result differs from the plan: {journey_id}: "
                + ", ".join(sorted(mismatches)),
                journey_id,
            )


def validate_full_stack_qa_plan(
    *,
    pack: Path,
    repository: Path,
    plan: dict[str, Any],
    records: dict[str, dict[str, Any]],
    runs: dict[str, dict[str, Any]],
    require_ready: bool,
    require_verified: bool,
) -> list[FullStackQaIssue]:
    """Validate the optional vertical QA contract against repository and index evidence."""

    if not require_ready:
        return []
    issues: list[FullStackQaIssue] = []
    owner = QA_PLAN_PATH

    for pointer in _unresolved_marker_paths(plan):
        _issue(
            issues,
            f"{owner}#{pointer}",
            "QA_MARKER_UNRESOLVED",
            "full-stack QA plan contains an unresolved required marker",
        )

    expected_contract = full_stack_qa_contract_sha256(plan)
    contract_digest = plan.get("contract_sha256")
    if contract_digest != expected_contract:
        _issue(
            issues,
            owner,
            "QA_CONTRACT_HASH_MISMATCH",
            "contract_sha256 does not match the canonical plan with contract_sha256 excluded",
        )

    contract_artifact_id = plan.get("contract_artifact_id")
    contract_artifact = _record(
        issues,
        records,
        contract_artifact_id,
        {"ART"},
        "contract artifact",
        owner,
    )
    if contract_artifact is not None:
        locator = contract_artifact.get("locator") if isinstance(contract_artifact.get("locator"), dict) else {}
        if locator.get("path") != QA_PLAN_PATH or locator.get("anchor") != contract_digest:
            _issue(
                issues,
                owner,
                "QA_CONTRACT_ARTIFACT_INVALID",
                "contract ART locator must bind full_stack_qa_plan.json at the current contract_sha256",
                str(contract_artifact_id),
            )

    environment = plan.get("environment") if isinstance(plan.get("environment"), dict) else {}
    environment_id = environment.get("environment_id")
    _record(issues, records, environment_id, {"ENV"}, "QA environment", owner)
    for field in ("fixture_reset", "fixture_seed", "fixture_cleanup"):
        _check_command_environment(issues, environment.get(field), f"{owner}#/environment/{field}")
    allowed_origins: set[tuple[str, str, int]] = set()
    for position, origin in enumerate(_list(environment.get("allowed_origins"))):
        if not isinstance(origin, dict):
            continue
        normalized_origin = _http_origin(origin.get("url"), origin_only=True)
        if normalized_origin is None:
            _issue(
                issues,
                f"{owner}#/environment/allowed_origins/{position}/url",
                "QA_ORIGIN_INVALID",
                "allowed origin must be HTTP(S) without credentials, a non-root path, query, or fragment",
            )
        else:
            allowed_origins.add(normalized_origin)
        if (
            origin.get("classification") == "LOOPBACK"
            and normalized_origin is not None
            and not _is_loopback_host(normalized_origin[1])
        ):
            _issue(
                issues,
                f"{owner}#/environment/allowed_origins/{position}",
                "QA_ORIGIN_CLASSIFICATION_INVALID",
                "LOOPBACK origin must use localhost or a loopback IP address",
            )
        _check_decisions(
            issues,
            records,
            origin.get("decision_ids"),
            f"{owner}#/environment/allowed_origins/{position}",
            required=origin.get("classification") == "AUTHORIZED_SANDBOX",
        )

    primary_service_declarations: dict[str, str] = {}
    owned_stack = plan.get("owned_stack") if isinstance(plan.get("owned_stack"), dict) else {}
    for role in ("frontend", "mid_tier", "backend", "persistence"):
        service = owned_stack.get(role)
        if not isinstance(service, dict):
            continue
        service_id = service.get("service_id")
        service_path = f"{owner}#/owned_stack/{role}"
        if isinstance(service_id, str):
            declaration = canonical_json(service)
            prior = primary_service_declarations.get(service_id)
            if prior is not None and prior != declaration:
                _issue(
                    issues,
                    service_path,
                    "QA_SERVICE_CONFLICT",
                    f"reused application service ID has conflicting declarations: {service_id}",
                    service_id,
                )
            primary_service_declarations[service_id] = declaration
        _check_readiness(
            issues,
            service.get("readiness"),
            f"{service_path}/readiness",
            allowed_origins,
            role="application service",
        )

    supporting_ids: set[str] = set()
    supporting_services = _list(owned_stack.get("supporting_services"))
    for position, service in enumerate(supporting_services):
        if not isinstance(service, dict):
            continue
        service_id = service.get("service_id")
        service_path = f"{owner}#/owned_stack/supporting_services/{position}"
        if isinstance(service_id, str):
            if service_id in supporting_ids or service_id in primary_service_declarations:
                _issue(
                    issues,
                    service_path,
                    "QA_SERVICE_CONFLICT",
                    f"supporting service ID must be unique and distinct from primary services: {service_id}",
                    service_id,
                )
            supporting_ids.add(service_id)
        _check_readiness(
            issues,
            service.get("readiness"),
            f"{service_path}/readiness",
            allowed_origins,
            role="supporting service",
        )

    external_ids: set[str] = set()
    external_artifacts: list[Any] = []
    for position, dependency in enumerate(_list(plan.get("external_dependencies"))):
        if not isinstance(dependency, dict):
            continue
        dependency_id = dependency.get("id")
        if isinstance(dependency_id, str):
            if dependency_id in external_ids:
                _issue(
                    issues,
                    f"{owner}#/external_dependencies/{position}",
                    "QA_EXTERNAL_DEPENDENCY_DUPLICATE",
                    f"external dependency ID occurs more than once: {dependency_id}",
                    dependency_id,
                )
            external_ids.add(dependency_id)
        _check_decisions(
            issues,
            records,
            dependency.get("decision_ids"),
            f"{owner}#/external_dependencies/{position}",
            required=True,
        )
        if dependency.get("disposition") != "EXCLUDED":
            interface = dependency.get("interface") if isinstance(dependency.get("interface"), dict) else {}
            endpoint = _external_endpoint(interface.get("protocol"), interface.get("endpoint"))
            interface_path = f"{owner}#/external_dependencies/{position}/interface"
            if endpoint is None:
                _issue(
                    issues,
                    interface_path,
                    "QA_EXTERNAL_INTERFACE_INVALID",
                    "external interface must name a credential-free endpoint matching its protocol",
                    str(dependency_id or ""),
                )
            else:
                endpoint_host, endpoint_origin = endpoint
                if (
                    interface.get("classification") == "LOOPBACK"
                    and not _is_loopback_host(endpoint_host)
                ):
                    _issue(
                        issues,
                        interface_path,
                        "QA_EXTERNAL_INTERFACE_INVALID",
                        "LOOPBACK external interface must use localhost or a loopback IP address",
                        str(dependency_id or ""),
                    )
                if endpoint_origin is not None and endpoint_origin not in allowed_origins:
                    _issue(
                        issues,
                        interface_path,
                        "QA_ORIGIN_UNAUTHORIZED",
                        "HTTP(S) external interface origin is absent from environment.allowed_origins",
                        str(dependency_id or ""),
                    )
            _check_readiness(
                issues,
                dependency.get("readiness"),
                f"{owner}#/external_dependencies/{position}/readiness",
                allowed_origins,
                role="external dependency",
            )
            external_artifacts.append(dependency.get("artifact_path"))

    playwright = plan.get("playwright") if isinstance(plan.get("playwright"), dict) else {}
    _check_repository_hash(
        issues,
        repository,
        playwright.get("lockfile_path"),
        playwright.get("lockfile_sha256"),
        f"{owner}#/playwright/lockfile_path",
    )
    _check_repository_hash(
        issues,
        repository,
        playwright.get("config_path"),
        playwright.get("config_sha256"),
        f"{owner}#/playwright/config_path",
    )
    driver_argv = playwright.get("driver_argv")
    if isinstance(driver_argv, list) and driver_argv and all(isinstance(item, str) for item in driver_argv):
        executable = driver_argv[0].lower()
        subcommand = driver_argv[1].lower() if len(driver_argv) > 1 else ""
        forbidden = (
            executable in {"npx", "bunx"}
            or (executable == "npm" and subcommand in {"exec", "x"})
            or (executable in {"pnpm", "yarn"} and subcommand in {"dlx", "exec"})
            or (executable == "bun" and subcommand == "x")
        )
        if forbidden:
            _issue(
                issues,
                f"{owner}#/playwright/driver_argv",
                "QA_INSTALLER_SHIM_FORBIDDEN",
                "Playwright driver_argv must invoke repository-owned or preinstalled tooling without a downloader shim",
            )

    ci = plan.get("ci") if isinstance(plan.get("ci"), dict) else {}
    if "pull_request" not in _list(ci.get("triggers")):
        _issue(
            issues,
            f"{owner}#/ci/triggers",
            "QA_CI_TRIGGER_INVALID",
            "full-stack QA required check must run on pull_request",
        )
    _check_repository_hash(
        issues,
        repository,
        ci.get("workflow_path"),
        ci.get("workflow_sha256"),
        f"{owner}#/ci/workflow_path",
    )
    restore_argv = ci.get("restore_argv")
    _check_decisions(
        issues,
        records,
        ci.get("restore_authority_decision_ids"),
        f"{owner}#/ci/restore_argv",
        required=restore_argv is not None,
    )

    ci_gate_id = ci.get("gate_id")
    ci_gate = _record(issues, records, ci_gate_id, {"GATE"}, "CI gate", f"{owner}#/ci/gate_id")
    gate_attributes = _attributes(ci_gate)
    gate_comparisons = {
        "argv": ci.get("gate_argv"),
        "cwd": ci.get("gate_cwd"),
        "expected_exit": ci.get("expected_exit"),
        "blocked_exit_codes": ci.get("blocked_exit_codes"),
        "artifact_paths": ci.get("artifact_paths"),
        "fresh_artifact_paths": ci.get("fresh_artifact_paths"),
    }
    mismatches = [
        field
        for field, expected in gate_comparisons.items()
        if gate_attributes.get(field, 0 if field == "expected_exit" else None) != expected
    ]
    if mismatches:
        _issue(
            issues,
            f"{owner}#/ci",
            "QA_GATE_CONTRACT_MISMATCH",
            "QA CI contract differs from indexed GATE attributes: " + ", ".join(sorted(mismatches)),
            str(ci_gate_id or ""),
        )
    if contract_artifact_id not in _string_set(gate_attributes.get("oracle_ids")):
        _issue(
            issues,
            f"{owner}#/ci",
            "QA_GATE_CONTRACT_MISMATCH",
            "QA GATE oracle_ids must include the full-stack plan contract artifact",
            str(ci_gate_id or ""),
        )

    declared_artifacts = _string_set(ci.get("artifact_paths"))
    if ci.get("result_path") not in declared_artifacts:
        _issue(
            issues,
            f"{owner}#/ci/result_path",
            "QA_RESULT_UNDECLARED",
            "ci.result_path must occur in ci.artifact_paths and the indexed GATE artifact paths",
        )
    if ci.get("result_path") not in _string_set(ci.get("fresh_artifact_paths")):
        _issue(
            issues,
            f"{owner}#/ci/fresh_artifact_paths",
            "QA_RESULT_FRESHNESS_MISSING",
            "ci.result_path must occur in fresh_artifact_paths and the indexed GATE contract",
        )
    supporting_artifacts = [
        service.get("artifact_path")
        for service in supporting_services
        if isinstance(service, dict)
    ]
    unbound_global_artifacts = sorted(
        str(value)
        for value in [*external_artifacts, *supporting_artifacts]
        if not isinstance(value, str) or value not in declared_artifacts
    )
    if unbound_global_artifacts:
        _issue(
            issues,
            f"{owner}#/ci/artifact_paths",
            "QA_ARTIFACT_UNDECLARED",
            "supporting-service or external-dependency proof artifacts are absent from "
            "GATE artifact_paths: " + ", ".join(unbound_global_artifacts),
        )
    plan_journeys = _list(plan.get("journeys"))
    expected_gate_covered: set[str] = set()
    expected_gate_oracles: set[str] = set()
    for planned_journey in plan_journeys:
        if not isinstance(planned_journey, dict):
            continue
        expected_gate_covered.update(_string_set(planned_journey.get("requirement_ids")))
        expected_gate_covered.update(_string_set(planned_journey.get("acceptance_ids")))
        test_identifier = planned_journey.get("test_id")
        if isinstance(test_identifier, str):
            expected_gate_covered.add(test_identifier)
        expected_gate_oracles.update(_string_set(planned_journey.get("oracle_ids")))
    if (
        _string_set(gate_attributes.get("covered_ids")) != expected_gate_covered
        or _string_set(gate_attributes.get("oracle_ids")) != expected_gate_oracles
        or _links(ci_gate, "oracles") != expected_gate_oracles
    ):
        _issue(
            issues,
            f"{owner}#/ci",
            "QA_GATE_CONTRACT_MISMATCH",
            "GATE covered_ids and oracle links/attributes must exactly equal the union of declared journeys",
            str(ci_gate_id or ""),
        )
    seen_journey_ids: set[str] = set()
    bound_supporting_ids: set[str] = set()
    bound_external_ids: set[str] = set()
    for position, journey in enumerate(plan_journeys):
        if not isinstance(journey, dict):
            continue
        journey_id = str(journey.get("id", f"position-{position}"))
        journey_path = f"{owner}#/journeys/{position}"
        if journey_id in seen_journey_ids:
            _issue(
                issues,
                journey_path,
                "QA_JOURNEY_DUPLICATE",
                f"journey ID occurs more than once: {journey_id}",
                journey_id,
            )
        seen_journey_ids.add(journey_id)
        workflow = _record(issues, records, journey.get("workflow_id"), {"WF"}, "workflow", journey_path)
        _record(issues, records, journey.get("actor_id"), {"ACT"}, "actor", journey_path)
        requirements = {
            identifier
            for identifier in _list(journey.get("requirement_ids"))
            if isinstance(identifier, str)
        }
        acceptance = {
            identifier
            for identifier in _list(journey.get("acceptance_ids"))
            if isinstance(identifier, str)
        }
        for identifier in sorted(requirements):
            _record(issues, records, identifier, {"REQ"}, "requirement", journey_path)
        for identifier in sorted(acceptance):
            _record(issues, records, identifier, {"AC"}, "acceptance criterion", journey_path)
        test_id = journey.get("test_id")
        test = _record(issues, records, test_id, {"TEST"}, "test", journey_path)
        gate_id = journey.get("gate_id")
        gate = _record(issues, records, gate_id, {"GATE"}, "gate", journey_path)
        _record(issues, records, journey.get("environment_id"), {"ENV"}, "environment", journey_path)
        journey_oracles = _string_set(journey.get("oracle_ids"))
        oracle_records: dict[str, dict[str, Any] | None] = {}
        for identifier in sorted(journey_oracles):
            oracle_records[identifier] = _record(
                issues,
                records,
                identifier,
                ORACLE_KINDS,
                "oracle",
                journey_path,
            )
        if contract_artifact_id not in journey_oracles:
            _issue(
                issues,
                journey_path,
                "QA_TRACE_INVALID",
                "journey oracle_ids must include the full-stack plan contract ART",
                journey_id,
            )
        if not (journey_oracles - {str(contract_artifact_id)}):
            _issue(
                issues,
                journey_path,
                "QA_ORACLE_INDEPENDENT_MISSING",
                "journey requires at least one E, ART, or CAP oracle in addition to the plan contract ART",
                journey_id,
            )
        for identifier in sorted(journey_oracles - {str(contract_artifact_id)}):
            if not requirements.issubset(_links(oracle_records.get(identifier), "requirements")):
                _issue(
                    issues,
                    journey_path,
                    "QA_TRACE_INVALID",
                    f"independent oracle {identifier} lacks every journey requirement link",
                    identifier,
                )

        if journey.get("environment_id") != environment_id or gate_id != ci_gate_id:
            _issue(
                issues,
                journey_path,
                "QA_TRACE_INVALID",
                "journey environment and gate must equal the plan environment and CI gate",
                journey_id,
            )
        if not requirements.issubset(_links(workflow, "requirements")):
            _issue(issues, journey_path, "QA_TRACE_INVALID", "workflow lacks every journey requirement link", journey_id)
        if not requirements.issubset(_links(test, "requirements")) or not acceptance.issubset(_links(test, "acceptance")):
            _issue(issues, journey_path, "QA_TRACE_INVALID", "TEST lacks journey requirement or acceptance links", journey_id)
        if str(gate_id) not in _links(test, "gates") or str(test_id) not in _links(gate, "tests"):
            _issue(issues, journey_path, "QA_TRACE_INVALID", "TEST and GATE links are not reciprocal", journey_id)
        if not journey_oracles.issubset(_links(test, "oracles")):
            _issue(issues, journey_path, "QA_TRACE_INVALID", "TEST lacks every declared journey oracle", journey_id)

        expected_covered = {*requirements, *acceptance, str(test_id)}
        if not expected_covered.issubset(_string_set(gate_attributes.get("covered_ids"))):
            _issue(
                issues,
                journey_path,
                "QA_GATE_CONTRACT_MISMATCH",
                "GATE covered_ids omit journey requirements, acceptance, or test",
                journey_id,
            )
        _check_repository_hash(
            issues,
            repository,
            journey.get("test_path"),
            journey.get("test_sha256"),
            f"{journey_path}/test_path",
        )

        wire = journey.get("wire") if isinstance(journey.get("wire"), dict) else {}
        wire_triggers = [wire.get("trigger")]
        wire_triggers.extend(
            exchange.get("trigger")
            for exchange in _list(wire.get("additional_exchanges"))
            if isinstance(exchange, dict)
        )
        string_triggers = [trigger for trigger in wire_triggers if isinstance(trigger, str)]
        if len(string_triggers) != len(set(string_triggers)):
            _issue(
                issues,
                f"{journey_path}/wire",
                "QA_WIRE_TRIGGER_DUPLICATE",
                "each wire exchange trigger must be unique within its journey",
                journey_id,
            )

        trigger_positions = {
            trigger: trigger_position
            for trigger_position, trigger in enumerate(wire_triggers)
            if isinstance(trigger, str)
        }
        journey_supporting_ids = _string_set(journey.get("supporting_service_ids"))
        journey_external_ids = _string_set(journey.get("external_dependency_ids"))
        seen_binding_ids: set[str] = set()
        seen_binding_names: set[str] = set()
        identity_bindings = _list(journey.get("identity_bindings"))
        for binding_position, binding in enumerate(identity_bindings):
            if not isinstance(binding, dict):
                continue
            binding_path = f"{journey_path}/identity_bindings/{binding_position}"
            binding_id = binding.get("id")
            binding_name = binding.get("name")
            if (
                not isinstance(binding_id, str)
                or binding_id in seen_binding_ids
                or not isinstance(binding_name, str)
                or binding_name in seen_binding_names
            ):
                _issue(
                    issues,
                    binding_path,
                    "QA_IDENTITY_BINDING_INVALID",
                    "identity binding IDs and names must each be unique within a journey",
                    journey_id,
                )
            if isinstance(binding_id, str):
                seen_binding_ids.add(binding_id)
            if isinstance(binding_name, str):
                seen_binding_names.add(binding_name)
            source = binding.get("source") if isinstance(binding.get("source"), dict) else {}
            source_trigger = source.get("exchange_trigger")
            source_position = (
                trigger_positions.get(source_trigger)
                if isinstance(source_trigger, str)
                else None
            )
            if source_position is None:
                _issue(
                    issues,
                    binding_path,
                    "QA_IDENTITY_BINDING_INVALID",
                    "identity source exchange_trigger must name an exchange in the same journey",
                    journey_id,
                )
            consumers = _list(binding.get("consumers"))
            consumer_kinds = {
                consumer.get("kind")
                for consumer in consumers
                if isinstance(consumer, dict) and isinstance(consumer.get("kind"), str)
            }
            missing_kinds = {"WIRE_PATH", "SERVICE", "PERSISTENCE"} - consumer_kinds
            if missing_kinds:
                _issue(
                    issues,
                    binding_path,
                    "QA_IDENTITY_BINDING_INCOMPLETE",
                    "identity binding must include WIRE_PATH, SERVICE, and PERSISTENCE consumers; missing: "
                    + ", ".join(sorted(missing_kinds)),
                    journey_id,
                )
            seen_pointers: set[str] = set()
            marker = f"{{{binding_name}}}" if isinstance(binding_name, str) else ""
            for consumer_position, consumer in enumerate(consumers):
                if not isinstance(consumer, dict):
                    continue
                consumer_path = f"{binding_path}/consumers/{consumer_position}"
                kind = consumer.get("kind")
                pointer = consumer.get("contract_pointer")
                if (
                    not _identity_consumer_pointer_allowed(kind, pointer, position)
                    or not isinstance(pointer, str)
                    or pointer in seen_pointers
                ):
                    _issue(
                        issues,
                        consumer_path,
                        "QA_IDENTITY_BINDING_INVALID",
                        "identity consumer pointer is duplicate or outside the controlled surface for its kind",
                        journey_id,
                    )
                    continue
                seen_pointers.add(pointer)
                resolved, target = _json_pointer_value(plan, pointer)
                marker_count = target.count(marker) if isinstance(target, str) and marker else 0
                if not resolved or not isinstance(target, str) or marker_count != 1:
                    _issue(
                        issues,
                        consumer_path,
                        "QA_IDENTITY_BINDING_INVALID",
                        "identity consumer pointer must resolve to a string containing its exact placeholder once",
                        journey_id,
                    )
                    continue
                if kind == "WIRE_PATH":
                    if marker not in target.split("/"):
                        _issue(
                            issues,
                            consumer_path,
                            "QA_IDENTITY_BINDING_INVALID",
                            "WIRE_PATH placeholder must occupy one complete path segment",
                            journey_id,
                        )
                    wire_position = _wire_exchange_position(pointer, position)
                    if (
                        source_position is None
                        or wire_position is None
                        or wire_position <= source_position
                    ):
                        _issue(
                            issues,
                            consumer_path,
                            "QA_IDENTITY_BINDING_INVALID",
                            "WIRE_PATH consumer must occur after the source response exchange",
                            journey_id,
                        )
                elif kind == "SUPPORTING_SERVICE":
                    match = re.fullmatch(
                        r"/owned_stack/supporting_services/((?:0|[1-9][0-9]*))/assertion",
                        pointer,
                    )
                    target_service = (
                        supporting_services[int(match.group(1))]
                        if match is not None and int(match.group(1)) < len(supporting_services)
                        else None
                    )
                    target_service_id = (
                        target_service.get("service_id")
                        if isinstance(target_service, dict)
                        else None
                    )
                    if target_service_id not in journey_supporting_ids:
                        _issue(
                            issues,
                            consumer_path,
                            "QA_IDENTITY_BINDING_INVALID",
                            "SUPPORTING_SERVICE consumer must target a service referenced by this journey",
                            journey_id,
                        )
                elif kind == "EXTERNAL_DEPENDENCY":
                    match = re.fullmatch(
                        r"/external_dependencies/((?:0|[1-9][0-9]*))/assertion",
                        pointer,
                    )
                    dependencies = _list(plan.get("external_dependencies"))
                    target_dependency = (
                        dependencies[int(match.group(1))]
                        if match is not None and int(match.group(1)) < len(dependencies)
                        else None
                    )
                    target_dependency_id = (
                        target_dependency.get("id")
                        if isinstance(target_dependency, dict)
                        else None
                    )
                    if target_dependency_id not in journey_external_ids:
                        _issue(
                            issues,
                            consumer_path,
                            "QA_IDENTITY_BINDING_INVALID",
                            "EXTERNAL_DEPENDENCY consumer must target a dependency referenced by this journey",
                            journey_id,
                        )
            if binding.get("artifact_path") != ci.get("result_path"):
                _issue(
                    issues,
                    binding_path,
                    "QA_IDENTITY_BINDING_INVALID",
                    "identity binding artifact_path must equal ci.result_path",
                    journey_id,
                )

        artifact_values: list[Any] = []
        for dimension in ("ui", "wire", "service", "persistence"):
            value = journey.get(dimension)
            if isinstance(value, dict):
                artifact_values.append(value.get("artifact_path"))
        for dimension in ("authorization", "jobs", "accessibility", "visual"):
            value = journey.get(dimension)
            if not isinstance(value, dict):
                continue
            if value.get("disposition") == "NOT_APPLICABLE":
                _check_decisions(
                    issues,
                    records,
                    value.get("decision_ids"),
                    f"{journey_path}/{dimension}",
                    required=True,
                )
            else:
                artifact_values.append(value.get("artifact_path"))
        artifact_values.extend(
            binding.get("artifact_path")
            for binding in identity_bindings
            if isinstance(binding, dict)
        )
        missing_artifacts = sorted(
            str(value) for value in artifact_values if not isinstance(value, str) or value not in declared_artifacts
        )
        if missing_artifacts:
            _issue(
                issues,
                journey_path,
                "QA_ARTIFACT_UNDECLARED",
                "journey proof artifacts are absent from GATE artifact_paths: " + ", ".join(missing_artifacts),
                journey_id,
            )
        unknown_external = sorted(journey_external_ids - external_ids)
        if unknown_external:
            _issue(
                issues,
                journey_path,
                "QA_EXTERNAL_DEPENDENCY_UNDEFINED",
                "journey references undefined external dependencies: " + ", ".join(unknown_external),
                journey_id,
            )
        bound_external_ids.update(journey_external_ids & external_ids)
        unknown_supporting = sorted(journey_supporting_ids - supporting_ids)
        if unknown_supporting:
            _issue(
                issues,
                journey_path,
                "QA_SUPPORTING_SERVICE_UNDEFINED",
                "journey references undefined supporting services: " + ", ".join(unknown_supporting),
                journey_id,
            )
        bound_supporting_ids.update(journey_supporting_ids & supporting_ids)

        if require_verified:
            gate_run_ids = _links(gate, "runs")
            candidates = [
                (run_id, run)
                for run_id, run in runs.items()
                if run_id in gate_run_ids
                and _run_field(run, "gate_id") == gate_id
                and _run_field(run, "environment_id") == environment_id
            ]
            if not candidates:
                _issue(
                    issues,
                    journey_path,
                    "QA_RUN_MISSING",
                    "verified profile requires a current PASS RUN for this full-stack journey gate",
                    journey_id,
                    hold=True,
                )
                continue
            latest_run_id, latest_run = max(candidates, key=lambda item: _run_sequence(item[0]))
            latest_links = latest_run.get("links") if isinstance(latest_run.get("links"), dict) else {}
            covered_ids = (
                set(latest_run.get("covered_ids", []))
                if isinstance(latest_run.get("covered_ids"), list)
                else set()
            )
            if not covered_ids:
                covered_ids = (
                    set(latest_links.get("requirements", []))
                    | set(latest_links.get("acceptance", []))
                    | set(latest_links.get("tests", []))
                )
            oracle_ids = (
                set(latest_run.get("oracle_ids", []))
                if isinstance(latest_run.get("oracle_ids"), list)
                else set(latest_links.get("oracles", []))
            )
            if _run_field(latest_run, "result") != "PASS":
                _issue(
                    issues,
                    journey_path,
                    "QA_RUN_NOT_PASS",
                    "latest linked run for this full-stack journey gate and environment is not PASS",
                    journey_id,
                    hold=True,
                )
            elif not expected_covered.issubset(covered_ids) or not journey_oracles.issubset(oracle_ids):
                _issue(
                    issues,
                    journey_path,
                    "QA_RUN_MISSING",
                    "latest PASS RUN does not cover this journey and its full-stack contract artifact",
                    journey_id,
                    hold=True,
                )
            else:
                _validate_full_stack_result(
                    issues,
                    pack=pack,
                    plan=plan,
                    run=latest_run,
                    run_id=latest_run_id,
                )

    unbound_external = sorted(external_ids - bound_external_ids)
    if unbound_external:
        _issue(
            issues,
            f"{owner}#/external_dependencies",
            "QA_EXTERNAL_DEPENDENCY_UNBOUND",
            "external dependencies are not referenced by a journey: " + ", ".join(unbound_external),
        )
    unbound_supporting = sorted(supporting_ids - bound_supporting_ids)
    if unbound_supporting:
        _issue(
            issues,
            f"{owner}#/owned_stack/supporting_services",
            "QA_SUPPORTING_SERVICE_UNBOUND",
            "supporting services are not referenced by a journey: " + ", ".join(unbound_supporting),
        )

    return sorted(set(issues))
