from __future__ import annotations

import json
import os
import re
import shutil
import tempfile
from pathlib import Path
from typing import Any

from . import TOOL_VERSION
from .common import ClonePackError, atomic_write_json, atomic_write_text, load_json, resolve_inside, safe_relative_path, sha256_bytes, sha256_file
from .constants import V2_DOCUMENTS
from .legacy_v1 import DOCUMENT_SCHEMAS
from .pack import _record_kind_for_id, initialize_v2, utc_now
from .schema import SchemaDefinitionError, validate_schema_file


Definition = tuple[str, int, str]
MIGRATION_REPORT_SCHEMA = Path(__file__).resolve().parents[2] / "assets" / "schemas" / "migration-report-v2.schema.json"
MIGRATION_OPERATIONS = (
    "initialize-v2-scaffold",
    "archive-v1-source",
    "preserve-pack-lineage",
    "map-v1-definitions",
    "downgrade-unverified-status",
    "bind-v2-identity",
)


def _source_file_hashes(source: Path, manifest: dict[str, Any]) -> list[dict[str, str]]:
    return [
        {"path": str(name), "sha256": sha256_file(source / str(name))}
        for name in ["clone_pack.json", *manifest.get("documents", [])]
    ]


def _validate_migration_report(report: dict[str, Any]) -> None:
    try:
        violations = validate_schema_file(report, MIGRATION_REPORT_SCHEMA)
    except SchemaDefinitionError as exc:
        raise ClonePackError(
            f"packaged migration report schema is invalid: {exc}",
            exit_code=6,
            diagnostic="MIGRATION_REPORT_INVALID",
        ) from exc
    if violations:
        rendered = "; ".join(
            f"{violation.pointer or '/'}: {violation.message}" for violation in violations[:10]
        )
        raise ClonePackError(rendered, exit_code=6, diagnostic="MIGRATION_REPORT_INVALID")
    transformations = report["transformations"]
    if [item["sequence"] for item in transformations] != list(range(1, len(transformations) + 1)) or [
        item["operation"] for item in transformations
    ] != list(MIGRATION_OPERATIONS):
        raise ClonePackError(
            "migration transformations must use the complete canonical operation order",
            exit_code=6,
            diagnostic="MIGRATION_REPORT_INVALID",
        )
    losses = report["unresolved_losses"]
    if [item["sequence"] for item in losses] != list(range(1, len(losses) + 1)) or len(
        {item["loss_id"] for item in losses}
    ) != len(losses):
        raise ClonePackError(
            "unresolved losses require contiguous sequence values and unique loss IDs",
            exit_code=6,
            diagnostic="MIGRATION_REPORT_INVALID",
        )
    if report["tool_version"] != TOOL_VERSION:
        raise ClonePackError(
            f"migration report tool version must equal the executing tool version {TOOL_VERSION}",
            exit_code=6,
            diagnostic="MIGRATION_REPORT_INVALID",
        )
    check_files = report["source"]["source_files"]
    retained_files = [
        {"path": item["source_path"], "sha256": item["sha256"]}
        for item in report["source_files"]
    ]
    if check_files != retained_files or report["source"]["tool_version"] != report["tool_version"]:
        raise ClonePackError(
            "migration report source hashes or tool version diverge from preflight",
            exit_code=6,
            diagnostic="MIGRATION_REPORT_INVALID",
        )
    resolved = set(report["resolved_record_ids"])
    source_paths = [item["source_path"] for item in report["source_files"]]
    archived_paths = [item["archived_path"] for item in report["source_files"]]
    try:
        for path_value in [*source_paths, *archived_paths]:
            safe_relative_path(path_value)
    except ClonePackError as exc:
        raise ClonePackError(
            f"migration report contains an unsafe source/archive path: {exc}",
            exit_code=6,
            diagnostic="MIGRATION_REPORT_INVALID",
        ) from exc
    expected_archived_paths = [
        f"history/migrations/{report['migration_id']}/source/{path}"
        for path in source_paths
    ]
    if (
        len(set(source_paths)) != len(source_paths)
        or len(set(archived_paths)) != len(archived_paths)
        or archived_paths != expected_archived_paths
    ):
        raise ClonePackError(
            "migration report source paths must be unique canonical archive mappings",
            exit_code=6,
            diagnostic="MIGRATION_REPORT_INVALID",
        )
    downgrades = report["status_downgrades"]
    downgrade_ids = [item["record_id"] for item in downgrades]
    if (
        len(set(downgrade_ids)) != len(downgrade_ids)
        or any(identifier not in resolved for identifier in downgrade_ids)
        or any(
            (item["kind"], item["migrated_status"])
            not in {("REQ", "IMPLEMENTED_UNVERIFIED"), ("GAP", "IMPLEMENTED")}
            for item in downgrades
        )
    ):
        raise ClonePackError(
            "status downgrades require unique resolved IDs and the canonical status for each kind",
            exit_code=6,
            diagnostic="MIGRATION_REPORT_INVALID",
        )
    expected_loss_contract = [
        ("LOSS-001", "v2-document-semantic-reconciliation"),
        ("LOSS-002", "trace-link-reconstruction"),
    ]
    if downgrades:
        expected_loss_contract.append(
            ("LOSS-003", "verification-evidence-reconciliation")
        )
    if [(item["loss_id"], item["category"]) for item in losses] != expected_loss_contract:
        raise ClonePackError(
            "unresolved losses must use the complete canonical loss contract",
            exit_code=6,
            diagnostic="MIGRATION_REPORT_INVALID",
        )
    source_path_set = set(source_paths)
    if any(
        not set(item["affected_record_ids"]).issubset(resolved)
        or not set(item["source_paths"]).issubset(source_path_set)
        for item in losses
    ):
        raise ClonePackError(
            "unresolved losses must reference only retained source paths and resolved record IDs",
            exit_code=6,
            diagnostic="MIGRATION_REPORT_INVALID",
        )
    if downgrades and losses[2]["affected_record_ids"] != downgrade_ids:
        raise ClonePackError(
            "verification-evidence loss must cover exactly the status downgrade records",
            exit_code=6,
            diagnostic="MIGRATION_REPORT_INVALID",
        )


def _canonical_definition_files(identifier: str, kind: str) -> set[str]:
    if identifier.startswith("REQ-GAP-"):
        return {"gaps_analysis.md"}
    if identifier.startswith("AC-GAP-"):
        return {"gaps_analysis.md"}
    if identifier.startswith("TEST-GAP-"):
        return {"gaps_analysis.md"}
    if identifier.startswith("STEP-GAP-"):
        return {"gaps_analysis.md"}
    return {
        "ENV": {"evidence_ledger.md"},
        "ART": {"evidence_ledger.md"},
        "E": {"evidence_ledger.md"},
        "CONFLICT": {"evidence_ledger.md"},
        "DEC": {"clone_brief.md"},
        "ACT": {"clone_specification.md"},
        "WF": {"clone_specification.md"},
        "SURF": {"clone_specification.md"},
        "REQ": {"clone_specification.md"},
        "IF": {"clone_specification.md"},
        "DATA": {"clone_specification.md"},
        "SEC": {"clone_specification.md"},
        "NFR": {"clone_specification.md"},
        "EXC": {"clone_brief.md"},
        "AC": {"acceptance_matrix.md"},
        "RUN": {"acceptance_matrix.md"},
        "TEST": {"mvp_build_plan.md"},
        "GATE": {"mvp_build_plan.md", "gap_implementation_plan.md"},
        "STEP": {"mvp_build_plan.md", "gap_implementation_plan.md"},
        "SLICE": {"mvp_build_plan.md"},
        "GAP": {"gaps_analysis.md"},
        "GAPDEC": {"gaps_analysis.md"},
        "INV": {"gap_implementation_plan.md"},
        "DEP": {"gap_implementation_plan.md"},
        "CHANGE": {"gap_implementation_plan.md"},
        "HALT": {"gap_implementation_plan.md"},
    }.get(kind, set())


def _v1_inventory(source: Path) -> tuple[dict[str, Any], dict[str, list[Definition]], list[str]]:
    manifest = load_json(source / "clone_pack.json")
    if manifest.get("schema_version") != "clone-pack/v1":
        raise ClonePackError("migration source must be clone-pack/v1", exit_code=3, diagnostic="SCHEMA_UNSUPPORTED")
    documents = manifest.get("documents")
    if not isinstance(documents, list) or len(documents) != len(set(map(str, documents))) or set(map(str, documents)) != set(DOCUMENT_SCHEMAS):
        raise ClonePackError(
            "v1 manifest documents must exactly name the canonical v1 document set",
            exit_code=6,
            diagnostic="MIGRATION_SOURCE_INVALID",
        )
    definitions: dict[str, list[Definition]] = {}
    for name in documents:
        path = source / str(name)
        if not path.is_file():
            raise ClonePackError(f"v1 source document is missing: {name}", exit_code=6, diagnostic="MIGRATION_SOURCE_INVALID")
        for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            for identifier in re.findall(r"\b[A-Z]+(?:-[A-Z]+)*-\d{3,}(?:-\d{2,})?\b", line):
                kind = _record_kind_for_id(identifier)
                heading_definition = re.match(rf"^\s*#+\s+{re.escape(identifier)}\b", line)
                table_definition = re.match(rf"^\s*\|\s*{re.escape(identifier)}\s*\|", line)
                heading_kind = identifier.startswith("REQ-") and not identifier.startswith("REQ-GAP-") or kind == "GAP"
                if kind and str(name) in _canonical_definition_files(identifier, kind) and (
                    heading_definition if heading_kind else table_definition
                ):
                    definitions.setdefault(identifier, []).append((str(name), line_number, line))
    duplicates = sorted(identifier for identifier, locations in definitions.items() if len(locations) > 1)
    return manifest, definitions, duplicates


def _candidate_key(identifier: str, definition: Definition) -> str:
    path, line_number, _ = definition
    return f"{identifier}@{path}:{line_number}"


def _load_mapping(mapping_path: Path | None, definitions: dict[str, list[Definition]]) -> dict[str, str]:
    if mapping_path is None:
        return {}
    loaded = load_json(mapping_path.expanduser().resolve())
    if any(not isinstance(key, str) or not isinstance(value, str) for key, value in loaded.items()):
        raise ClonePackError(
            "migration mapping must be a source-occurrence-to-target-ID string object",
            exit_code=6,
            diagnostic="MIGRATION_MAPPING_INVALID",
        )
    ambiguous = {identifier: locations for identifier, locations in definitions.items() if len(locations) > 1}
    allowed = {
        _candidate_key(identifier, definition)
        for identifier, locations in ambiguous.items()
        for definition in locations
    }
    unexpected = sorted(set(loaded) - allowed)
    if unexpected:
        raise ClonePackError(
            "migration mapping has unknown source occurrence(s): " + ", ".join(unexpected),
            exit_code=6,
            diagnostic="MIGRATION_MAPPING_INVALID",
        )
    reserved = {identifier for identifier, locations in definitions.items() if len(locations) == 1}
    targets: set[str] = set()
    for source_key, target_id in loaded.items():
        source_id = source_key.split("@", 1)[0]
        source_kind = _record_kind_for_id(source_id)
        if _record_kind_for_id(target_id) != source_kind:
            raise ClonePackError(
                f"migration target ID must preserve kind for {source_key}: {target_id}",
                exit_code=6,
                diagnostic="MIGRATION_MAPPING_INVALID",
            )
        if target_id in reserved or target_id in targets:
            raise ClonePackError(
                f"migration target ID is not unique: {target_id}",
                exit_code=6,
                diagnostic="MIGRATION_MAPPING_INVALID",
            )
        targets.add(target_id)
    return {str(key): str(value) for key, value in loaded.items()}


def migration_check(source: Path, mapping_path: Path | None = None) -> dict[str, Any]:
    source = source.expanduser().resolve()
    manifest, definitions, duplicates = _v1_inventory(source)
    mapping = _load_mapping(mapping_path, definitions)
    candidates = {
        identifier: sorted(_candidate_key(identifier, definition) for definition in locations)
        for identifier, locations in definitions.items()
        if len(locations) > 1
    }
    unresolved = [
        identifier
        for identifier, source_keys in candidates.items()
        if any(source_key not in mapping for source_key in source_keys)
    ]
    return {
        "schema_version": "clone-migration-check/v2",
        "tool_version": TOOL_VERSION,
        "source_pack_id": manifest.get("pack_id"),
        "source_schema_version": manifest.get("schema_version"),
        "source_manifest_sha256": sha256_file(source / "clone_pack.json"),
        "source_files": _source_file_hashes(source, manifest),
        "record_count": sum(len(locations) for locations in definitions.values()),
        "ambiguous_ids": duplicates,
        "ambiguous_candidates": candidates,
        "resolved_by_mapping": sorted(set(duplicates) - set(unresolved)),
        "unresolved_ids": unresolved,
        "mapping_format": "{\"SOURCE-ID@document.md:line\": \"UNIQUE-TARGET-ID\"}",
        "migratable": not unresolved,
    }


def migrate_v1(
    *,
    skill_root: Path,
    source: Path,
    output: Path,
    mapping_path: Path | None = None,
    timestamp: str | None = None,
) -> Path:
    source = source.expanduser().resolve()
    output = output.expanduser().resolve()
    if output.exists():
        raise ClonePackError(f"migration destination already exists: {output}", exit_code=6, diagnostic="MIGRATION_DESTINATION_EXISTS")
    if output == source or source in output.parents:
        raise ClonePackError("migration destination must not be the source or its child", exit_code=6, diagnostic="MIGRATION_DESTINATION_INVALID")
    if not output.parent.is_dir():
        raise ClonePackError("migration destination parent must exist", exit_code=6, diagnostic="MIGRATION_DESTINATION_INVALID")
    check = migration_check(source, mapping_path)
    if not check["migratable"]:
        raise ClonePackError(
            "migration requires an explicit mapping for: " + ", ".join(check["unresolved_ids"]),
            exit_code=6,
            diagnostic="MIGRATION_MAPPING_REQUIRED",
        )
    source_manifest, definitions, _ = _v1_inventory(source)
    mapping = _load_mapping(mapping_path, definitions)
    created_at = str(source_manifest.get("created_at") or utc_now(timestamp)[0])
    temporary = Path(tempfile.mkdtemp(prefix=f".{output.name}.migration-", dir=output.parent))
    generated = temporary / "pack"
    try:
        initialize_v2(
            skill_root=skill_root,
            product_name=str(source_manifest["product_name"]),
            product_type=str(source_manifest["product_type"]),
            playbooks=[],
            source_description=str(source_manifest["reference_source"]),
            repo_root=output.parent,
            output_dir=generated,
            timestamp=created_at,
        )
        history_root = generated / "history" / "migrations" / "MIG-001" / "source"
        history_root.mkdir(parents=True)
        source_files: list[dict[str, str]] = []
        for name in ["clone_pack.json", *source_manifest.get("documents", [])]:
            source_path = source / str(name)
            destination = history_root / str(name)
            shutil.copy2(source_path, destination)
            source_files.append(
                {
                    "source_path": str(name),
                    "archived_path": destination.relative_to(generated).as_posix(),
                    "sha256": sha256_file(destination),
                }
            )
        copied_hashes = [
            {"path": item["source_path"], "sha256": item["sha256"]}
            for item in source_files
        ]
        if copied_hashes != check["source_files"]:
            raise ClonePackError(
                "archived source hashes differ from migration preflight",
                exit_code=6,
                diagnostic="MIGRATION_SOURCE_CHANGED",
            )

        manifest_path = generated / "clone_pack.json"
        manifest = load_json(manifest_path)
        generated_pack_id = manifest["pack_id"]
        preserved_pack_id = str(source_manifest["pack_id"])
        manifest["pack_id"] = preserved_pack_id
        manifest["pack_revision"] = 2
        manifest["supersedes"] = {
            "schema_version": "clone-pack/v1",
            "pack_id": preserved_pack_id,
            "pack_revision": 1,
            "manifest_sha256": check["source_manifest_sha256"],
        }
        index_path = generated / "clone_index.json"
        index = load_json(index_path)
        index["pack_id"] = preserved_pack_id
        index["pack_revision"] = 2
        resolved_definitions: list[tuple[str, str, Definition]] = []
        for source_id, locations in sorted(definitions.items()):
            if len(locations) == 1:
                resolved_definitions.append((source_id, source_id, locations[0]))
            else:
                for definition in locations:
                    resolved_definitions.append((mapping[_candidate_key(source_id, definition)], source_id, definition))
        record_map_path = generated / "history" / "migrations" / "MIG-001" / "record_map.md"
        map_lines = ["# Migration record map", ""]
        for identifier, source_id, (path_name, line_number, line) in sorted(resolved_definitions):
            source_line_sha256 = sha256_bytes((line + "\n").encode("utf-8"))
            map_lines.append(
                f"- {identifier} <- {source_id}@{path_name}:{line_number} source-line-sha256={source_line_sha256}"
            )
        atomic_write_text(record_map_path, "\n".join(map_lines) + "\n")

        records: list[dict[str, Any]] = []
        status_downgrades: list[dict[str, str]] = []
        for identifier, source_id, (path_name, line_number, line) in sorted(resolved_definitions):
            kind = _record_kind_for_id(identifier)
            if not kind:
                continue
            source_line_sha256 = sha256_bytes((line + "\n").encode("utf-8"))
            map_line = (
                f"- {identifier} <- {source_id}@{path_name}:{line_number} "
                f"source-line-sha256={source_line_sha256}"
            )
            attributes: dict[str, Any] = {
                "migrated_from_v1": True,
                "reconciliation_required": True,
                "source_id": source_id,
                "source_path": f"history/migrations/MIG-001/source/{path_name}",
                "source_line": line_number,
                "source_line_sha256": source_line_sha256,
            }
            if kind == "REQ":
                attributes.update({"mvp": True, "verification_status": "IMPLEMENTED_UNVERIFIED", "implementation_locator": "MIGRATION_REQUIRED"})
                if re.search(r"\bVERIFIED\b", line):
                    status_downgrades.append(
                        {
                            "record_id": identifier,
                            "kind": kind,
                            "source_claim": "VERIFIED",
                            "migrated_status": "IMPLEMENTED_UNVERIFIED",
                            "reason": "v1 claim lacks v2 run, oracle, and artifact evidence",
                        }
                    )
            if kind == "GAP":
                status_match = re.search(r"\b(OPEN|BLOCKED|IN_PROGRESS|IMPLEMENTED|VERIFIED|DECLINED)\b", line)
                status = status_match.group(1) if status_match else "OPEN"
                attributes.update({"status": "IMPLEMENTED" if status == "VERIFIED" else status, "readiness": "BLOCKED"})
                if status == "VERIFIED":
                    status_downgrades.append(
                        {
                            "record_id": identifier,
                            "kind": kind,
                            "source_claim": "VERIFIED",
                            "migrated_status": "IMPLEMENTED",
                            "reason": "v1 gap claim lacks v2 closure-run and lifecycle evidence",
                        }
                    )
            records.append(
                {
                    "id": identifier,
                    "kind": kind,
                    "locator": {
                        "path": "history/migrations/MIG-001/record_map.md",
                        "anchor": map_line,
                        "sha256": sha256_bytes((map_line + "\n").encode("utf-8")),
                    },
                    "links": {},
                    "applicability": "MIGRATION_RECONCILIATION",
                    "state": "BLOCKED",
                    "attributes": attributes,
                }
            )
        index["records"] = records
        atomic_write_json(index_path, index)
        for path in (generated / name for name in V2_DOCUMENTS):
            text = path.read_text(encoding="utf-8")
            text = text.replace(generated_pack_id, preserved_pack_id)
            text = re.sub(r"^pack_revision:\s*1\s*$", "pack_revision: 2", text, count=1, flags=re.MULTILINE)
            atomic_write_text(path, text)
        for path in (generated / name for name in manifest["plans"].values()):
            plan = load_json(path)
            plan["pack_id"] = preserved_pack_id
            plan["pack_revision"] = 2
            atomic_write_json(path, plan)
        resolved_record_ids = [identifier for identifier, _, _ in sorted(resolved_definitions)]
        source_document_paths = [str(name) for name in source_manifest.get("documents", [])]
        transformations = [
            {
                "sequence": 1,
                "operation": "initialize-v2-scaffold",
                "inputs": ["clone_pack.json"],
                "outputs": ["clone_pack.json", "clone_index.json", *sorted(V2_DOCUMENTS)],
                "effect": "created draft v2 structures without implementation or verification claims",
            },
            {
                "sequence": 2,
                "operation": "archive-v1-source",
                "inputs": [item["source_path"] for item in source_files],
                "outputs": [item["archived_path"] for item in source_files],
                "effect": "copied every canonical v1 source file byte-for-byte and bound its SHA-256",
            },
            {
                "sequence": 3,
                "operation": "preserve-pack-lineage",
                "inputs": ["clone_pack.json"],
                "outputs": ["clone_pack.json"],
                "effect": "preserved pack_id, advanced pack_revision to 2, and recorded v1 supersession",
            },
            {
                "sequence": 4,
                "operation": "map-v1-definitions",
                "inputs": source_document_paths,
                "outputs": ["history/migrations/MIG-001/record_map.md", "clone_index.json"],
                "effect": f"mapped {len(resolved_record_ids)} source definition occurrence(s) to v2 index records",
            },
            {
                "sequence": 5,
                "operation": "downgrade-unverified-status",
                "inputs": [item["record_id"] for item in status_downgrades],
                "outputs": ["clone_index.json"],
                "effect": (
                    f"downgraded {len(status_downgrades)} explicit VERIFIED claim(s) lacking v2 evidence"
                    if status_downgrades
                    else "found no explicit VERIFIED source claim requiring a status downgrade"
                ),
            },
            {
                "sequence": 6,
                "operation": "bind-v2-identity",
                "inputs": ["clone_pack.json"],
                "outputs": [*sorted(V2_DOCUMENTS), *sorted(manifest["plans"].values())],
                "effect": "bound generated documents and plans to the preserved pack_id and pack_revision 2",
            },
        ]
        unresolved_losses = [
            {
                "sequence": 1,
                "loss_id": "LOSS-001",
                "category": "v2-document-semantic-reconciliation",
                "affected_record_ids": resolved_record_ids,
                "source_paths": source_document_paths,
                "reason": "v1 bytes are archived but are not reinterpreted as completed v2 document contracts",
                "required_action": "complete each v2 document from authorized archived evidence and remove every migration marker only after validation",
            },
            {
                "sequence": 2,
                "loss_id": "LOSS-002",
                "category": "trace-link-reconstruction",
                "affected_record_ids": resolved_record_ids,
                "source_paths": source_document_paths,
                "reason": "migration preserves definitions but does not infer v2 trace links from prose proximity",
                "required_action": "author and validate every required v2 link against explicit source evidence or a recorded decision",
            },
        ]
        if status_downgrades:
            unresolved_losses.append(
                {
                    "sequence": 3,
                    "loss_id": "LOSS-003",
                    "category": "verification-evidence-reconciliation",
                    "affected_record_ids": [item["record_id"] for item in status_downgrades],
                    "source_paths": sorted(
                        {
                            definition[0]
                            for identifier, _, definition in resolved_definitions
                            if identifier in {item["record_id"] for item in status_downgrades}
                        }
                    ),
                    "reason": "v1 VERIFIED text has no v2 current run, independent oracle, and retained artifact chain",
                    "required_action": "execute current v2 gates and record passing run, parity, assurance, and lifecycle evidence before claiming VERIFIED",
                }
            )
        report = {
            "schema_version": "clone-migration/v2",
            "migration_id": "MIG-001",
            "tool_version": TOOL_VERSION,
            "source": check,
            "source_files": source_files,
            "preserved_record_ids": sorted(definitions),
            "resolved_record_ids": resolved_record_ids,
            "occurrence_mapping": mapping,
            "transformations": transformations,
            "status_downgrades": status_downgrades,
            "unresolved_losses": unresolved_losses,
            "required_reconciliation": True,
        }
        _validate_migration_report(report)
        report_path = generated / "history" / "migrations" / "MIG-001" / "migration_report.json"
        atomic_write_json(report_path, report)
        retained_report = load_json(report_path)
        _validate_migration_report(retained_report)
        manifest["migration"] = {
            "migration_id": "MIG-001",
            "from": "clone-pack/v1",
            "source_path": "history/migrations/MIG-001/source/clone_pack.json",
            "source_manifest_sha256": check["source_manifest_sha256"],
            "report_path": report_path.relative_to(generated).as_posix(),
            "report_sha256": sha256_file(report_path),
            "tool_version": TOOL_VERSION,
            "source_files": source_files,
            "transformations": transformations,
            "unresolved_losses": unresolved_losses,
            "status_downgrade_policy": "v1 VERIFIED claims require fresh v2 evidence and remain unverified until reconciled",
        }
        atomic_write_json(manifest_path, manifest)
        os.replace(generated, output)
    except BaseException:
        shutil.rmtree(temporary, ignore_errors=True)
        raise
    shutil.rmtree(temporary, ignore_errors=True)
    return output


def diff_packs(left: Path, right: Path) -> dict[str, Any]:
    left = left.expanduser().resolve()
    right = right.expanduser().resolve()
    left_manifest = load_json(left / "clone_pack.json")
    right_manifest = load_json(right / "clone_pack.json")
    if left_manifest.get("schema_version") != "clone-pack/v2" or right_manifest.get("schema_version") != "clone-pack/v2":
        raise ClonePackError(
            "diff requires two clone-pack/v2 packs",
            exit_code=3,
            diagnostic="SCHEMA_UNSUPPORTED",
        )
    left_index_path = left_manifest.get("index_path")
    right_index_path = right_manifest.get("index_path")
    if not isinstance(left_index_path, str) or not isinstance(right_index_path, str):
        raise ClonePackError("diff pack is missing index_path", diagnostic="INDEX_INVALID")
    left_records = load_json(resolve_inside(left, left_index_path, must_exist=True)).get("records", [])
    right_records = load_json(resolve_inside(right, right_index_path, must_exist=True)).get("records", [])
    if not isinstance(left_records, list) or not isinstance(right_records, list):
        raise ClonePackError("diff index records must be arrays", diagnostic="INDEX_INVALID")
    indexed: list[dict[str, dict[str, Any]]] = []
    for label, records in (("left", left_records), ("right", right_records)):
        by_id: dict[str, dict[str, Any]] = {}
        for position, record in enumerate(records):
            identifier = record.get("id") if isinstance(record, dict) else None
            if not isinstance(identifier, str):
                raise ClonePackError(
                    f"{label} index record {position} has no string id",
                    diagnostic="INDEX_INVALID",
                )
            if identifier in by_id:
                raise ClonePackError(
                    f"{label} index contains duplicate ID: {identifier}",
                    diagnostic="ID_DUPLICATE",
                )
            by_id[identifier] = record
        indexed.append(by_id)
    left_by_id, right_by_id = indexed
    return {
        "schema_version": "clone-pack-diff/v2",
        "left": {"pack_id": left_manifest.get("pack_id"), "revision": left_manifest.get("pack_revision")},
        "right": {"pack_id": right_manifest.get("pack_id"), "revision": right_manifest.get("pack_revision")},
        "added_ids": sorted(set(right_by_id) - set(left_by_id)),
        "removed_ids": sorted(set(left_by_id) - set(right_by_id)),
        "changed_ids": sorted(
            identifier
            for identifier in set(left_by_id) & set(right_by_id)
            if left_by_id[identifier] != right_by_id[identifier]
        ),
    }
