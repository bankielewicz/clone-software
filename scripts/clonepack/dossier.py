from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any, Iterable

from .common import ClonePackError, resolve_inside
from .schema import SchemaDefinitionError, validate_schema_file


SCHEMA_PATH = Path(__file__).resolve().parents[2] / "assets" / "schemas" / "gap-dossier-v2.schema.json"
ACTIONABLE_GAP_CLASSES = {"MVP_BLOCKER", "PARITY_GAP", "QUALITY_GAP", "ENHANCEMENT_GAP"}
SOURCE_KINDS = {"E", "ART", "CAP", "PAR", "RUN", "REQ", "DEC", "ADR", "GAPDEC"}
PROOF_KINDS = {"E", "ART", "CAP", "PAR", "RUN"}
DECISION_KINDS = {"DEC", "ADR", "GAPDEC"}
SECRET_ENV_TERMS = ("TOKEN", "KEY", "SECRET", "PASSWORD", "AUTH", "COOKIE", "CREDENTIAL")
ENV_REFERENCE = re.compile(r"env:[A-Za-z_][A-Za-z0-9_]*")
UNRESOLVED = re.compile(
    r"\[\[(?:REQUIRED|MIGRATION_REQUIRED):|\b(?:TBD|TODO|TBC|FIXME|TK)\b|\?\?\?",
    re.IGNORECASE,
)
AMBIGUOUS_MODAL = re.compile(r"\b(?:should|could|may|might|maybe|ideally|eventually)\b|\bas needed\b")
NON_PROSE_KEYS = {
    "schema_version",
    "gap_id",
    "id",
    "source_ids",
    "actor_ids",
    "workflow_ids",
    "requirement_ids",
    "change_ids",
    "fixture_ids",
    "test_ids",
    "covered_ids",
    "acceptance_ids",
    "evidence_ids",
    "decision_id",
    "run_ids",
    "parity_ids",
    "assurance_ids",
    "residual_gap_ids",
    "path",
    "destination_path",
    "paths",
    "forbidden_paths",
    "cwd",
    "argv",
    "symbol",
    "status",
    "state",
    "scope",
    "existence",
    "operation",
    "priority",
    "categories",
    "order",
    "expected_exit",
    "timeout_seconds",
    "implemented_revision",
}


@dataclass(order=True, frozen=True)
class DossierProblem:
    code: str
    message: str


def _problem(problems: list[DossierProblem], code: str, message: str) -> None:
    problems.append(DossierProblem(code, message))


def _record(
    records: dict[str, dict[str, Any]],
    identifier: Any,
    kinds: set[str],
    role: str,
    problems: list[DossierProblem],
) -> dict[str, Any] | None:
    if not isinstance(identifier, str) or not identifier:
        _problem(problems, "GAP_DOSSIER_REF_INVALID", f"{role} must be a non-empty record ID")
        return None
    record = records.get(identifier)
    if record is None:
        _problem(problems, "GAP_DOSSIER_REF_UNDEFINED", f"{role} is undefined: {identifier}")
        return None
    if record.get("kind") not in kinds:
        _problem(
            problems,
            "GAP_DOSSIER_REF_WRONG_KIND",
            f"{role} {identifier} has kind {record.get('kind')}; expected {', '.join(sorted(kinds))}",
        )
        return None
    return record


def _ids(items: Iterable[dict[str, Any]], key: str = "id") -> list[str]:
    return [str(item.get(key)) for item in items if isinstance(item, dict) and isinstance(item.get(key), str)]


def _unique_identifiers(items: list[dict[str, Any]], role: str, problems: list[DossierProblem]) -> list[str]:
    identifiers = _ids(items)
    if len(identifiers) != len(items) or len(identifiers) != len(set(identifiers)):
        _problem(problems, "GAP_DOSSIER_ID_DUPLICATE", f"{role} IDs must be present and unique")
    return identifiers


def _orders(items: list[dict[str, Any]], role: str, problems: list[DossierProblem]) -> None:
    observed = [item.get("order") for item in items]
    if observed != list(range(1, len(items) + 1)):
        _problem(problems, "GAP_DOSSIER_ORDER_INVALID", f"{role} order must be contiguous and array-ordered from 1")


def _inside_fence(path_value: str, fences: list[str]) -> bool:
    candidate = PurePosixPath(path_value)
    return any(
        fence == "."
        or candidate == PurePosixPath(fence)
        or PurePosixPath(fence) in candidate.parents
        for fence in fences
    )


def _check_path(
    base: Path,
    path_value: str,
    existence: str,
    role: str,
    problems: list[DossierProblem],
    *,
    symbol: str | None = None,
) -> None:
    try:
        path = resolve_inside(base, path_value, must_exist=existence == "existing")
    except ClonePackError as exc:
        _problem(problems, "GAP_DOSSIER_PATH_INVALID", f"{role}: {exc}")
        return
    if existence == "new" or existence == "missing":
        if path.exists():
            _problem(problems, "GAP_DOSSIER_PATH_STATE", f"{role} claims absent path but it exists: {path_value}")
        if symbol is not None:
            _problem(problems, "GAP_DOSSIER_SYMBOL_INVALID", f"{role} cannot name a symbol in an absent path: {path_value}")
        return
    if not path.is_file():
        if symbol is not None:
            _problem(problems, "GAP_DOSSIER_SYMBOL_INVALID", f"{role} symbol requires a regular file: {path_value}")
        return
    if symbol is not None:
        try:
            count = path.read_text(encoding="utf-8").count(symbol)
        except (OSError, UnicodeError) as exc:
            _problem(problems, "GAP_DOSSIER_SYMBOL_INVALID", f"{role} symbol file is unreadable: {exc}")
            return
        if count != 1:
            _problem(
                problems,
                "GAP_DOSSIER_SYMBOL_INVALID",
                f"{role} symbol must occur exactly once; found {count}: {symbol}",
            )


def _scan_prose(value: Any, problems: list[DossierProblem], path: str = "dossier", key: str = "") -> None:
    if key == "environment":
        return
    if isinstance(value, dict):
        for child_key, child in value.items():
            _scan_prose(child, problems, f"{path}.{child_key}", child_key)
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _scan_prose(child, problems, f"{path}[{index}]", key)
    elif isinstance(value, str) and key not in NON_PROSE_KEYS:
        match = UNRESOLVED.search(value) or AMBIGUOUS_MODAL.search(value)
        if match:
            _problem(
                problems,
                "GAP_DOSSIER_AMBIGUOUS",
                f"{path} contains forbidden unresolved or ambiguous language: {match.group(0)!r}",
            )


def _check_command(
    repository: Path,
    command: dict[str, Any],
    role: str,
    problems: list[DossierProblem],
) -> None:
    cwd_value = str(command["cwd"])
    try:
        cwd = repository if cwd_value == "." else resolve_inside(repository, cwd_value, must_exist=True)
    except ClonePackError as exc:
        _problem(problems, "GAP_DOSSIER_COMMAND_INVALID", f"{role} cwd is invalid: {exc}")
    else:
        if not cwd.is_dir():
            _problem(problems, "GAP_DOSSIER_COMMAND_INVALID", f"{role} cwd is not a directory: {cwd_value}")
    for name, value in command["environment"].items():
        if any(term in name.upper() for term in SECRET_ENV_TERMS) and ENV_REFERENCE.fullmatch(value) is None:
            _problem(
                problems,
                "GAP_DOSSIER_SECRET_INVALID",
                f"{role} secret-like environment key {name} must use env:NAME indirection",
            )


def _require_backlink(
    records: dict[str, dict[str, Any]],
    identifier: str,
    relation: str,
    target: str,
    role: str,
    problems: list[DossierProblem],
) -> None:
    record = records.get(identifier, {})
    links = record.get("links") if isinstance(record.get("links"), dict) else {}
    if target not in links.get(relation, []):
        _problem(
            problems,
            "GAP_DOSSIER_TRACE_INVALID",
            f"{role} {identifier}.{relation} omits {target}",
        )


def _validate_blocker(attributes: dict[str, Any], gap_id: str, problems: list[DossierProblem]) -> None:
    blocker = attributes.get("blocker")
    expected = {"missing_evidence", "investigations", "resolution_question", "authority"}
    if not isinstance(blocker, dict) or set(blocker) != expected:
        _problem(
            problems,
            "GAP_BLOCKER_INCOMPLETE",
            f"{gap_id} BLOCKED/EVIDENCE_GAP requires blocker with exactly {', '.join(sorted(expected))}",
        )
        return
    if any(not isinstance(blocker[name], str) or not blocker[name].strip() for name in ("missing_evidence", "resolution_question", "authority")):
        _problem(problems, "GAP_BLOCKER_INCOMPLETE", f"{gap_id} blocker text fields must be non-empty")
    investigations = blocker.get("investigations")
    if not isinstance(investigations, list) or not investigations or any(not isinstance(item, str) or not item.strip() for item in investigations):
        _problem(problems, "GAP_BLOCKER_INCOMPLETE", f"{gap_id} blocker investigations must be a non-empty string array")
    _scan_prose(blocker, problems, f"{gap_id}.blocker")


def validate_gap_plan_record(
    pack: Path,
    manifest: dict[str, Any],
    records: dict[str, dict[str, Any]],
    gap_id: str,
    gap: dict[str, Any],
) -> list[DossierProblem]:
    problems: list[DossierProblem] = []
    attributes = gap.get("attributes") if isinstance(gap.get("attributes"), dict) else {}
    gap_class = attributes.get("class")
    status = attributes.get("status")
    readiness = attributes.get("readiness")
    if gap_class not in ACTIONABLE_GAP_CLASSES | {"EVIDENCE_GAP"}:
        _problem(problems, "GAP_CLASS_INVALID", f"{gap_id} has no controlled gap class")
        return sorted(set(problems))
    if gap_class == "EVIDENCE_GAP":
        if status != "BLOCKED" or readiness != "BLOCKED":
            _problem(problems, "GAP_EVIDENCE_STATE_INVALID", f"{gap_id} EVIDENCE_GAP must be BLOCKED with readiness BLOCKED")
        _validate_blocker(attributes, gap_id, problems)
        return sorted(set(problems))
    if status == "BLOCKED" or readiness == "BLOCKED":
        _validate_blocker(attributes, gap_id, problems)
        return sorted(set(problems))
    if status not in {"OPEN", "IN_PROGRESS", "IMPLEMENTED", "VERIFIED", "DECLINED"} or readiness != "READY":
        _problem(
            problems,
            "GAP_PLAN_STATE_INVALID",
            f"{gap_id} actionable dossier requires controlled lifecycle state and readiness READY",
        )
        return sorted(set(problems))

    dossier = attributes.get("dossier")
    if not isinstance(dossier, dict):
        _problem(problems, "GAP_DOSSIER_MISSING", f"{gap_id} requires attributes.dossier")
        return problems
    try:
        violations = validate_schema_file(dossier, SCHEMA_PATH)
    except SchemaDefinitionError as exc:
        _problem(problems, "GAP_DOSSIER_SCHEMA", f"packaged gap dossier schema is invalid: {exc}")
        return problems
    for violation in violations:
        _problem(
            problems,
            "GAP_DOSSIER_SCHEMA",
            f"{violation.pointer or '/'}: {violation.message}",
        )
    if violations:
        return sorted(set(problems))
    _scan_prose(dossier, problems)
    if dossier["gap_id"] != gap_id:
        _problem(problems, "GAP_DOSSIER_IDENTITY", f"dossier gap_id differs from {gap_id}")

    source_records = [
        _record(records, identifier, SOURCE_KINDS, "dossier source", problems)
        for identifier in dossier["source_ids"]
    ]
    source_kinds = {record.get("kind") for record in source_records if record is not None}
    if "REQ" not in source_kinds or not (source_kinds & PROOF_KINDS):
        _problem(problems, "GAP_DOSSIER_SOURCE_INCOMPLETE", "dossier sources require at least one REQ and one independent proof record")
    source_relations = {
        "E": "evidence",
        "ART": "artifacts",
        "CAP": "captures",
        "PAR": "parity",
        "RUN": "runs",
        "REQ": "requirements",
        "DEC": "decisions",
        "ADR": "decisions",
        "GAPDEC": "decisions",
    }
    gap_links = gap.get("links") if isinstance(gap.get("links"), dict) else {}
    for identifier, source_record in zip(dossier["source_ids"], source_records):
        if source_record is None:
            continue
        relation = source_relations[str(source_record["kind"])]
        if identifier not in gap_links.get(relation, []):
            _problem(problems, "GAP_DOSSIER_TRACE_INVALID", f"GAP.{relation} omits dossier source {identifier}")
        _require_backlink(records, identifier, "gaps", gap_id, "dossier source", problems)

    for identifier in dossier["impact"]["actor_ids"]:
        _record(records, identifier, {"ACT"}, "impact actor", problems)
        if identifier not in gap_links.get("actors", []):
            _problem(problems, "GAP_DOSSIER_TRACE_INVALID", f"GAP.actors omits {identifier}")
        _require_backlink(records, identifier, "gaps", gap_id, "impact actor", problems)
    for identifier in dossier["impact"]["workflow_ids"]:
        _record(records, identifier, {"WF"}, "impact workflow", problems)
        if identifier not in gap_links.get("workflows", []):
            _problem(problems, "GAP_DOSSIER_TRACE_INVALID", f"GAP.workflows omits {identifier}")
        _require_backlink(records, identifier, "gaps", gap_id, "impact workflow", problems)

    repository = Path(str(manifest.get("repository_root", ""))).resolve()
    fences = dossier["allowed_fence"]["paths"]
    forbidden = dossier["allowed_fence"]["forbidden_paths"]
    for fence in [*fences, *forbidden]:
        try:
            resolve_inside(repository, fence)
        except ClonePackError as exc:
            _problem(problems, "GAP_DOSSIER_FENCE_INVALID", str(exc))
    for fence in fences:
        if _inside_fence(fence, forbidden):
            _problem(problems, "GAP_DOSSIER_FENCE_INVALID", f"allowed and forbidden fences overlap: {fence}")

    for side in ("reference", "clone"):
        for locator in dossier["current_behavior"][side]["locators"]:
            for identifier in locator["evidence_ids"]:
                proof = _record(records, identifier, PROOF_KINDS, f"{side} behavior evidence", problems)
                if proof is not None:
                    relation = source_relations[str(proof["kind"])]
                    if identifier not in gap_links.get(relation, []):
                        _problem(problems, "GAP_DOSSIER_TRACE_INVALID", f"GAP.{relation} omits {side} behavior evidence {identifier}")
                    _require_backlink(records, identifier, "gaps", gap_id, f"{side} behavior evidence", problems)
            base = pack if locator["scope"] == "pack" else repository
            _check_path(
                base,
                locator["path"],
                locator["existence"],
                f"{side} behavior locator",
                problems,
                symbol=locator["symbol"],
            )

    changes = dossier["change_map"]
    change_ids = _unique_identifiers(changes, "change", problems)
    _orders(changes, "change", problems)
    change_paths = {item["path"] for item in changes}
    requirement_ids: set[str] = set()
    for change in changes:
        _record(records, change["id"], {"CHANGE"}, "change", problems)
        _require_backlink(records, change["id"], "gaps", gap_id, "change", problems)
        for identifier in change["requirement_ids"]:
            requirement_ids.add(identifier)
            _record(records, identifier, {"REQ"}, "change requirement", problems)
            _require_backlink(records, change["id"], "requirements", identifier, "change", problems)
        if not _inside_fence(change["path"], fences):
            _problem(problems, "GAP_DOSSIER_FENCE_VIOLATION", f"change path is outside allowed fence: {change['path']}")
        if _inside_fence(change["path"], forbidden):
            _problem(problems, "GAP_DOSSIER_FENCE_VIOLATION", f"change path is forbidden: {change['path']}")
        if change["operation"] == "create" and change["existence"] != "new":
            _problem(problems, "GAP_DOSSIER_PATH_STATE", f"create change must declare new: {change['id']}")
        if change["operation"] in {"modify", "delete", "rename"} and change["existence"] != "existing":
            _problem(problems, "GAP_DOSSIER_PATH_STATE", f"{change['operation']} change must declare existing: {change['id']}")
        destination = change["destination_path"]
        if change["operation"] == "rename":
            if destination is None:
                _problem(problems, "GAP_DOSSIER_PATH_STATE", f"rename change requires destination_path: {change['id']}")
            else:
                if not _inside_fence(destination, fences) or _inside_fence(destination, forbidden):
                    _problem(problems, "GAP_DOSSIER_FENCE_VIOLATION", f"rename destination is outside the allowed fence: {destination}")
                _check_path(repository, destination, "new", f"rename destination {change['id']}", problems)
                change_paths.add(destination)
        elif destination is not None:
            _problem(problems, "GAP_DOSSIER_PATH_STATE", f"non-rename change must set destination_path null: {change['id']}")
        _check_path(repository, change["path"], change["existence"], f"change {change['id']}", problems, symbol=change["symbol"])

    for contract_name, disposition in dossier["contracts"].items():
        if disposition["status"] == "NOT_APPLICABLE":
            _record(records, disposition["decision_id"], DECISION_KINDS, f"{contract_name} disposition", problems)
    for rollout_name, disposition in dossier["rollout"].items():
        if disposition["status"] == "NOT_APPLICABLE":
            _record(records, disposition["decision_id"], DECISION_KINDS, f"{rollout_name} disposition", problems)

    steps = dossier["steps"]
    step_ids = _unique_identifiers(steps, "step", problems)
    _orders(steps, "step", problems)
    for step in steps:
        _record(records, step["id"], {"STEP"}, "implementation step", problems)
        _require_backlink(records, step["id"], "gaps", gap_id, "implementation step", problems)
        unknown_changes = sorted(set(step["change_ids"]) - set(change_ids))
        if unknown_changes:
            _problem(problems, "GAP_DOSSIER_TRACE_INVALID", f"step {step['id']} names unknown changes: {', '.join(unknown_changes)}")
        for identifier in step["change_ids"]:
            _require_backlink(records, step["id"], "changes", identifier, "implementation step", problems)
        unknown_paths = sorted(set(step["paths"]) - change_paths)
        if unknown_paths:
            _problem(problems, "GAP_DOSSIER_TRACE_INVALID", f"step {step['id']} names paths absent from change_map: {', '.join(unknown_paths)}")

    fixture_ids = _unique_identifiers(dossier["fixtures"], "fixture", problems)
    for fixture in dossier["fixtures"]:
        _record(records, fixture["id"], {"ART"}, "fixture", problems)
        _require_backlink(records, fixture["id"], "gaps", gap_id, "fixture", problems)
        for identifier in fixture["evidence_ids"]:
            _record(records, identifier, PROOF_KINDS, "fixture origin evidence", problems)
            _require_backlink(records, fixture["id"], "evidence", identifier, "fixture", problems)
        if fixture["path"] not in change_paths and fixture["existence"] == "new":
            _problem(problems, "GAP_DOSSIER_TRACE_INVALID", f"new fixture lacks a change_map entry: {fixture['path']}")
        if not _inside_fence(fixture["path"], fences):
            _problem(problems, "GAP_DOSSIER_FENCE_VIOLATION", f"fixture path is outside allowed fence: {fixture['path']}")
        if _inside_fence(fixture["path"], forbidden):
            _problem(problems, "GAP_DOSSIER_FENCE_VIOLATION", f"fixture path is forbidden: {fixture['path']}")
        _check_path(repository, fixture["path"], fixture["existence"], f"fixture {fixture['id']}", problems)

    tests = dossier["tests"]
    test_ids = _unique_identifiers(tests, "test", problems)
    for test in tests:
        _record(records, test["id"], {"TEST"}, "dossier test", problems)
        _require_backlink(records, test["id"], "gaps", gap_id, "dossier test", problems)
        for identifier in requirement_ids:
            _require_backlink(records, test["id"], "requirements", identifier, "dossier test", problems)
        for identifier in dossier["acceptance_ids"]:
            _require_backlink(records, test["id"], "acceptance", identifier, "dossier test", problems)
        unknown_fixtures = sorted(set(test["fixture_ids"]) - set(fixture_ids))
        if unknown_fixtures:
            _problem(problems, "GAP_DOSSIER_TRACE_INVALID", f"test {test['id']} names unknown fixtures: {', '.join(unknown_fixtures)}")
        for identifier in test["fixture_ids"]:
            _require_backlink(records, test["id"], "artifacts", identifier, "dossier test", problems)
        if test["path"] not in change_paths and test["existence"] == "new":
            _problem(problems, "GAP_DOSSIER_TRACE_INVALID", f"new test lacks a change_map entry: {test['path']}")
        if not _inside_fence(test["path"], fences):
            _problem(problems, "GAP_DOSSIER_FENCE_VIOLATION", f"test path is outside allowed fence: {test['path']}")
        if _inside_fence(test["path"], forbidden):
            _problem(problems, "GAP_DOSSIER_FENCE_VIOLATION", f"test path is forbidden: {test['path']}")
        _check_path(repository, test["path"], test["existence"], f"test {test['id']}", problems)
        _check_command(repository, test, f"test {test['id']}", problems)

    for dimension, disposition in dossier["test_dimensions"].items():
        if dimension in {"normal", "boundary", "negative"} and disposition["status"] != "REQUIRED":
            _problem(problems, "GAP_DOSSIER_TEST_INCOMPLETE", f"{dimension} testing cannot be NOT_APPLICABLE")
        if disposition["status"] == "NOT_APPLICABLE":
            _record(records, disposition["decision_id"], DECISION_KINDS, f"{dimension} test disposition", problems)
            continue
        unknown_tests = sorted(set(disposition["test_ids"]) - set(test_ids))
        if unknown_tests:
            _problem(problems, "GAP_DOSSIER_TRACE_INVALID", f"{dimension} dimension names unknown tests: {', '.join(unknown_tests)}")
        for test in tests:
            if test["id"] in disposition["test_ids"] and dimension not in test["categories"]:
                _problem(problems, "GAP_DOSSIER_TEST_INCOMPLETE", f"test {test['id']} lacks declared {dimension} category")

    gate_ids = _unique_identifiers(dossier["gates"], "gate", problems)
    for gate in dossier["gates"]:
        _record(records, gate["id"], {"GATE"}, "dossier gate", problems)
        _require_backlink(records, gate["id"], "gaps", gap_id, "dossier gate", problems)
        unknown_coverage = sorted(set(gate["covered_ids"]) - (set(test_ids) | set(dossier["acceptance_ids"]) | requirement_ids))
        if unknown_coverage:
            _problem(problems, "GAP_DOSSIER_TRACE_INVALID", f"gate {gate['id']} has ungoverned coverage: {', '.join(unknown_coverage)}")
        for identifier in gate["covered_ids"]:
            target = records.get(identifier, {})
            relation = {"REQ": "requirements", "AC": "acceptance", "TEST": "tests"}.get(str(target.get("kind")))
            if relation is not None:
                _require_backlink(records, gate["id"], relation, identifier, "dossier gate", problems)
        _check_command(repository, gate, f"gate {gate['id']}", problems)
    for identifier in dossier["acceptance_ids"]:
        _record(records, identifier, {"AC"}, "dossier acceptance", problems)
    for halt in dossier["halts"]:
        _record(records, halt["id"], {"HALT"}, "dossier HALT", problems)
        _require_backlink(records, halt["id"], "gaps", gap_id, "dossier HALT", problems)
    _unique_identifiers(dossier["halts"], "HALT", problems)

    links = gap.get("links") if isinstance(gap.get("links"), dict) else {}
    required_links: dict[str, set[str]] = {
        "requirements": requirement_ids,
        "acceptance": set(dossier["acceptance_ids"]),
        "tests": set(test_ids),
        "gates": set(gate_ids),
        "changes": set(change_ids),
        "steps": set(step_ids),
        "halts": set(_ids(dossier["halts"])),
    }
    for relation, expected in required_links.items():
        missing = sorted(expected - set(links.get(relation, [])))
        if missing:
            _problem(problems, "GAP_DOSSIER_TRACE_INVALID", f"GAP.{relation} omits dossier IDs: {', '.join(missing)}")

    closure = dossier["closure"]
    closure_state = closure["state"]
    revision = closure["implemented_revision"]
    run_ids = set(closure["run_ids"])
    parity_ids = set(closure["parity_ids"])
    assurance_ids = set(closure["assurance_ids"])
    if status == "OPEN":
        if closure_state != "NOT_STARTED" or revision is not None or any(
            closure[name] for name in ("run_ids", "parity_ids", "assurance_ids", "residual_gap_ids")
        ):
            _problem(problems, "GAP_DOSSIER_CLOSURE_PREMATURE", "OPEN dossier closure must be NOT_STARTED with no proof")
    elif status == "IN_PROGRESS":
        if closure_state != "IN_PROGRESS" or revision is not None or run_ids or parity_ids or assurance_ids:
            _problem(problems, "GAP_DOSSIER_CLOSURE_INVALID", "IN_PROGRESS dossier closure contains stale proof")
    elif status == "IMPLEMENTED":
        if closure_state != "IMPLEMENTED" or not isinstance(revision, str) or not revision or not run_ids:
            _problem(problems, "GAP_DOSSIER_CLOSURE_INVALID", "IMPLEMENTED dossier closure requires revision and run proof")
    elif status == "VERIFIED":
        expected_runs = set(gap_links.get("runs", []))
        expected_parity = set(gap_links.get("parity", []))
        expected_assurance = set(gap_links.get("assurance", []))
        if (
            closure_state != "VERIFIED"
            or not isinstance(revision, str)
            or not revision
            or not run_ids
            or run_ids != expected_runs
            or parity_ids != expected_parity
            or assurance_ids != expected_assurance
        ):
            _problem(
                problems,
                "GAP_DOSSIER_CLOSURE_INVALID",
                "VERIFIED dossier closure must exactly bind current run, parity, and assurance proof",
            )
    elif status == "DECLINED":
        if closure_state != "DECLINED" or revision is not None or run_ids or parity_ids or assurance_ids:
            _problem(problems, "GAP_DOSSIER_CLOSURE_INVALID", "DECLINED dossier closure cannot retain implementation proof")
    for residual_id in closure["residual_gap_ids"]:
        residual = records.get(residual_id)
        if residual_id == gap_id or residual is None or residual.get("kind") != "GAP":
            _problem(problems, "GAP_DOSSIER_RESIDUAL_INVALID", f"invalid residual gap: {residual_id}")
    return sorted(set(problems))
