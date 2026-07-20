from __future__ import annotations

import os
import re
import stat
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from .common import (
    ClonePackError,
    atomic_write_many,
    canonical_json,
    load_json,
    resolve_inside,
    safe_relative_path,
    sha256_bytes,
    sha256_file,
    recover_atomic_transactions,
)
from .pack import utc_now
from .schema import SchemaDefinitionError, validate_schema_file


SCHEMA_ROOT = Path(__file__).resolve().parents[2] / "assets" / "schemas"
SNAPSHOT_ROLES = frozenset({"adopted", "candidate"})
RUNTIME_EXCLUSION_FIELDS = frozenset(
    {
        "id",
        "path",
        "reason",
        "authority_ids",
        "kind",
        "evidence_ids",
        "pre_session_presence",
        "expected_identity",
    }
)
RUNTIME_IDENTITY_FIELDS = frozenset({"type", "device", "inode", "mode", "empty"})
RUNTIME_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]*$")
RUNTIME_DECISION_KINDS = frozenset({"DEC", "ADR", "GAPDEC"})
RUNTIME_EVIDENCE_KINDS = frozenset(
    {"E", "ART", "CAP", "RUN", "PAR", "ASSURE", "FIND", "SBOM", "BUILD", "PROV", "SNAP", "SCOPE", "PRES"}
)
RUNTIME_EXCLUSION_REASON = (
    "User-authorized empty tool-runtime directory excluded from product identity."
)
RUNTIME_DESCRIPTOR_CAPABLE = (
    all(hasattr(os, name) for name in ("O_DIRECTORY", "O_NOFOLLOW"))
    and os.open in os.supports_dir_fd
    and os.stat in os.supports_dir_fd
    and os.scandir in os.supports_fd
)


@dataclass(frozen=True)
class RuntimeExclusionBinding:
    """A user-authorized empty-directory exclusion bound against replacement.

    Device and inode values are used only to prove that the same filesystem
    object was inspected throughout one operation.  They are not ownership or
    provider-provenance evidence.
    """

    contract: dict[str, Any]
    path: Path
    observed_identity: tuple[tuple[int, int, int, int, int], ...]


def _require_schema(instance: dict[str, Any], filename: str, diagnostic: str) -> None:
    try:
        violations = validate_schema_file(instance, SCHEMA_ROOT / filename)
    except SchemaDefinitionError as exc:
        raise ClonePackError(f"packaged schema is invalid: {exc}", diagnostic="SCHEMA_INVALID") from exc
    if violations:
        rendered = "; ".join(
            f"{violation.pointer or '/'}: {violation.message}" for violation in violations[:10]
        )
        if len(violations) > 10:
            rendered += f"; {len(violations) - 10} additional violation(s)"
        raise ClonePackError(rendered, diagnostic=diagnostic)


def _record_map(index: dict[str, Any]) -> dict[str, dict[str, Any]]:
    raw = index.get("records")
    if not isinstance(raw, list):
        raise ClonePackError("clone index records must be an array", diagnostic="INDEX_INVALID")
    records: dict[str, dict[str, Any]] = {}
    for record in raw:
        if not isinstance(record, dict) or not isinstance(record.get("id"), str):
            raise ClonePackError("clone index contains a record without an ID", diagnostic="INDEX_INVALID")
        identifier = str(record["id"])
        if identifier in records:
            raise ClonePackError(f"duplicate index record ID: {identifier}", diagnostic="ID_DUPLICATE")
        records[identifier] = record
    return records


def _next_id(existing: Iterable[str], prefix: str) -> str:
    numbers = [
        int(identifier.rsplit("-", 1)[1])
        for identifier in existing
        if re.fullmatch(rf"{re.escape(prefix)}-[0-9]+", identifier)
    ]
    return f"{prefix}-{max(numbers, default=0) + 1:03d}"


def _require_enhancement_manifest(pack: Path) -> dict[str, Any]:
    manifest = load_json(pack / "clone_pack.json")
    if manifest.get("schema_version") != "clone-pack/v2":
        raise ClonePackError("brownfield operations require clone-pack/v2", exit_code=3, diagnostic="SCHEMA_UNSUPPORTED")
    workstream = manifest.get("workstream")
    if not isinstance(workstream, dict) or workstream.get("kind") != "brownfield-enhancement":
        raise ClonePackError(
            "pack is not a brownfield enhancement workstream",
            exit_code=3,
            diagnostic="WORKSTREAM_UNSUPPORTED",
        )
    return manifest


def _plan_path(pack: Path, manifest: dict[str, Any]) -> Path:
    plans = manifest.get("plans")
    value = plans.get("enhancement") if isinstance(plans, dict) else None
    if value != "enhancement_plan.json":
        raise ClonePackError(
            "manifest plans.enhancement must equal enhancement_plan.json",
            diagnostic="MANIFEST_PATH_INVALID",
        )
    return resolve_inside(pack, value, must_exist=True)


def _index_path(pack: Path, manifest: dict[str, Any]) -> Path:
    value = manifest.get("index_path")
    if value != "clone_index.json":
        raise ClonePackError(
            "manifest index_path must equal clone_index.json",
            diagnostic="MANIFEST_PATH_INVALID",
        )
    return resolve_inside(pack, value, must_exist=True)


def _inventory_path(pack: Path, manifest: dict[str, Any]) -> Path:
    plans = manifest.get("plans")
    value = plans.get("repository_inventory") if isinstance(plans, dict) else None
    if value != "repository_inventory.json":
        raise ClonePackError(
            "manifest plans.repository_inventory must equal repository_inventory.json",
            diagnostic="MANIFEST_PATH_INVALID",
        )
    return resolve_inside(pack, value, must_exist=True)


def _inventoried_entry_paths(pack: Path, manifest: dict[str, Any]) -> set[str]:
    inventory = load_json(_inventory_path(pack, manifest))
    entries = inventory.get("entries")
    if not isinstance(entries, list):
        raise ClonePackError("repository inventory entries must be an array", diagnostic="INVENTORY_INVALID")
    paths: set[str] = set()
    for position, entry in enumerate(entries):
        value = entry.get("path") if isinstance(entry, dict) else None
        if not isinstance(value, str):
            raise ClonePackError(
                f"repository inventory entry {position} has no path",
                diagnostic="INVENTORY_INVALID",
            )
        normalized = safe_relative_path(value).as_posix()
        if normalized in paths:
            raise ClonePackError(
                f"repository inventory repeats path: {normalized}",
                diagnostic="INVENTORY_INVALID",
            )
        paths.add(normalized)
    return paths


def _snapshot_runtime_context(
    pack: Path,
    manifest: dict[str, Any],
) -> tuple[list[dict[str, Any]], list[str], list[str], list[str]]:
    inventory = load_json(_inventory_path(pack, manifest))
    raw_exclusions = inventory.get("exclusions", [])
    if not isinstance(raw_exclusions, list):
        raise _runtime_error("repository exclusions must be an array", "RUNTIME_EXCLUSION_INVALID")
    runtime_present = any(
        isinstance(item, dict) and item.get("kind") == "tool-runtime"
        for item in raw_exclusions
    )
    if not runtime_present:
        return [], [], [], []

    instruction_paths: list[str] = []
    for field in ("instructions", "agents_files"):
        values = inventory.get(field)
        if not isinstance(values, list) or any(not isinstance(value, str) for value in values):
            raise _runtime_error(
                f"repository inventory {field} must be a path array",
                "RUNTIME_EXCLUSION_CONTEXT_INVALID",
            )
        instruction_paths.extend(values)
    for entry in inventory.get("entries", []):
        value = entry.get("path") if isinstance(entry, dict) else None
        if isinstance(value, str) and Path(value).name == "AGENTS.md":
            instruction_paths.append(value)

    scaffold_paths: list[str] = []
    plans = manifest.get("plans")
    scaffold_value = plans.get("scaffold") if isinstance(plans, dict) else None
    if isinstance(scaffold_value, str):
        scaffold_plan = load_json(resolve_inside(pack, scaffold_value, must_exist=True))
        output_root = scaffold_plan.get("output_root", ".")
        required_paths = scaffold_plan.get("required_paths", [])
        if not isinstance(output_root, str) or not isinstance(required_paths, list) or any(
            not isinstance(value, str) for value in required_paths
        ):
            raise _runtime_error(
                "scaffold plan paths are invalid",
                "RUNTIME_EXCLUSION_CONTEXT_INVALID",
            )
        for value in required_paths:
            normalized = safe_relative_path(value).as_posix()
            if output_root == ".":
                scaffold_paths.append(normalized)
            else:
                root = safe_relative_path(output_root).as_posix()
                scaffold_paths.append(f"{root}/{normalized}")

    change_paths: list[str] = []
    enhancement_value = plans.get("enhancement") if isinstance(plans, dict) else None
    if isinstance(enhancement_value, str):
        enhancement_plan = load_json(resolve_inside(pack, enhancement_value, must_exist=True))
        changes = enhancement_plan.get("change_map", [])
        if not isinstance(changes, list):
            raise _runtime_error(
                "enhancement change_map must be an array",
                "RUNTIME_EXCLUSION_CONTEXT_INVALID",
            )
        for change in changes:
            values = change.get("paths") if isinstance(change, dict) else None
            if not isinstance(values, list) or any(not isinstance(value, str) for value in values):
                raise _runtime_error(
                    "enhancement change paths are invalid",
                    "RUNTIME_EXCLUSION_CONTEXT_INVALID",
                )
            change_paths.extend(values)
        scope = enhancement_plan.get("scope")
        generated = scope.get("generated_paths", []) if isinstance(scope, dict) else []
        if not isinstance(generated, list) or any(not isinstance(value, str) for value in generated):
            raise _runtime_error(
                "enhancement generated paths are invalid",
                "RUNTIME_EXCLUSION_CONTEXT_INVALID",
            )
        change_paths.extend(generated)
    return raw_exclusions, sorted(set(instruction_paths)), sorted(set(scaffold_paths)), sorted(set(change_paths))


def _inside(candidate: Path, root: Path) -> bool:
    try:
        candidate.relative_to(root)
    except ValueError:
        return False
    return True


def _pack_relative_to_repository(repository: Path, pack: Path | None) -> str | None:
    if pack is None:
        return None
    try:
        return pack.resolve().relative_to(repository.resolve()).as_posix()
    except ValueError:
        return None


def _path_overlaps(left: str, right: str) -> bool:
    return (
        left == right
        or left.startswith(right.rstrip("/") + "/")
        or right.startswith(left.rstrip("/") + "/")
    )


def _runtime_error(message: str, diagnostic: str) -> ClonePackError:
    return ClonePackError(message, exit_code=4, diagnostic=diagnostic)


def _runtime_id_array(value: Any, role: str) -> list[str]:
    if (
        not isinstance(value, list)
        or not value
        or any(not isinstance(item, str) or RUNTIME_ID.fullmatch(item) is None for item in value)
        or len(value) != len(set(value))
    ):
        raise _runtime_error(
            f"runtime exclusion {role} must be a non-empty unique ID array",
            "RUNTIME_EXCLUSION_INVALID",
        )
    return sorted(value)


def _canonical_runtime_contract(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != RUNTIME_EXCLUSION_FIELDS:
        raise _runtime_error(
            "tool-runtime exclusion has unexpected or missing fields",
            "RUNTIME_EXCLUSION_INVALID",
        )
    if value.get("kind") != "tool-runtime" or value.get("pre_session_presence") is not False:
        raise _runtime_error(
            "tool-runtime exclusion must declare kind tool-runtime and pre_session_presence false",
            "RUNTIME_EXCLUSION_INVALID",
        )
    identifier = value.get("id")
    reason = value.get("reason")
    if not isinstance(identifier, str) or RUNTIME_ID.fullmatch(identifier) is None:
        raise _runtime_error("runtime exclusion ID is invalid", "RUNTIME_EXCLUSION_INVALID")
    if reason != RUNTIME_EXCLUSION_REASON:
        raise _runtime_error(
            f"runtime exclusion reason must equal {RUNTIME_EXCLUSION_REASON!r}",
            "RUNTIME_EXCLUSION_REASON_INVALID",
        )
    relative = safe_relative_path(value.get("path"))
    normalized_path = relative.as_posix()
    if normalized_path != value.get("path"):
        raise _runtime_error("runtime exclusion path is not canonical", "RUNTIME_EXCLUSION_INVALID")
    authority_ids = _runtime_id_array(value.get("authority_ids"), "authority_ids")
    evidence_ids = _runtime_id_array(value.get("evidence_ids"), "evidence_ids")
    expected = value.get("expected_identity")
    if not isinstance(expected, dict) or set(expected) != RUNTIME_IDENTITY_FIELDS:
        raise _runtime_error(
            "runtime exclusion expected_identity has unexpected or missing fields",
            "RUNTIME_EXCLUSION_INVALID",
        )
    device = expected.get("device")
    inode = expected.get("inode")
    mode = expected.get("mode")
    if (
        expected.get("type") != "directory"
        or expected.get("empty") is not True
        or isinstance(device, bool)
        or not isinstance(device, int)
        or device < 0
        or isinstance(inode, bool)
        or not isinstance(inode, int)
        or inode < 1
        or isinstance(mode, bool)
        or not isinstance(mode, int)
        or not 0 <= mode <= 0o7777
    ):
        raise _runtime_error(
            "runtime exclusion expected_identity is invalid",
            "RUNTIME_EXCLUSION_INVALID",
        )
    if mode & 0o222:
        raise _runtime_error(
            f"runtime exclusion directory is authorized only without write bits: {normalized_path}",
            "RUNTIME_EXCLUSION_WRITABLE",
        )
    return {
        "id": identifier,
        "path": normalized_path,
        "reason": reason,
        "authority_ids": authority_ids,
        "kind": "tool-runtime",
        "evidence_ids": evidence_ids,
        "pre_session_presence": False,
        "expected_identity": {
            "type": "directory",
            "device": device,
            "inode": inode,
            "mode": mode,
            "empty": True,
        },
    }


def require_runtime_exclusion_capability(exclusions: Any) -> None:
    """Fail before repository collection when a runtime exclusion is selected."""

    if not isinstance(exclusions, list):
        raise _runtime_error("repository exclusions must be an array", "RUNTIME_EXCLUSION_INVALID")
    runtime_contracts: list[dict[str, Any]] = []
    for position, raw in enumerate(exclusions):
        if not isinstance(raw, dict):
            raise _runtime_error(
                f"repository exclusion {position} is not an object",
                "RUNTIME_EXCLUSION_INVALID",
            )
        if raw.get("kind") is None:
            continue
        if raw.get("kind") != "tool-runtime":
            raise _runtime_error("repository exclusion kind is unsupported", "RUNTIME_EXCLUSION_INVALID")
        runtime_contracts.append(_canonical_runtime_contract(raw))
    if runtime_contracts and not RUNTIME_DESCRIPTOR_CAPABLE:
        raise ClonePackError(
            "runtime exclusions require descriptor-safe directory traversal capabilities",
            exit_code=3,
            diagnostic="RUNTIME_EXCLUSION_CAPABILITY_MISSING",
        )


def _directory_operation_identity(metadata: os.stat_result) -> tuple[int, int, int, int, int]:
    return (
        metadata.st_dev,
        metadata.st_ino,
        stat.S_IMODE(metadata.st_mode),
        metadata.st_mtime_ns,
        metadata.st_ctime_ns,
    )


def _inspect_runtime_directory(
    repository: Path,
    contract: dict[str, Any],
) -> tuple[Path, tuple[tuple[int, int, int, int, int], ...]]:
    relative = safe_relative_path(str(contract["path"]))
    if not RUNTIME_DESCRIPTOR_CAPABLE:
        raise ClonePackError(
            "runtime exclusions require descriptor-safe directory traversal capabilities",
            exit_code=3,
            diagnostic="RUNTIME_EXCLUSION_CAPABILITY_MISSING",
        )
    flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
    descriptors: list[int] = []
    identities: list[tuple[int, int, int, int, int]] = []
    try:
        root_before = os.stat(repository, follow_symlinks=False)
        if not stat.S_ISDIR(root_before.st_mode) or stat.S_ISLNK(root_before.st_mode):
            raise _runtime_error("repository root is not a real directory", "RUNTIME_EXCLUSION_UNSAFE")
        root_descriptor = os.open(repository, flags)
        descriptors.append(root_descriptor)
        root_opened = os.fstat(root_descriptor)
        root_identity = _directory_operation_identity(root_opened)
        if _directory_operation_identity(root_before) != root_identity:
            raise _runtime_error(
                "repository root changed during runtime-exclusion inspection",
                "RUNTIME_EXCLUSION_IDENTITY_DRIFT",
            )
        identities.append(root_identity)

        for part in relative.parts:
            parent_descriptor = descriptors[-1]
            before = os.stat(part, dir_fd=parent_descriptor, follow_symlinks=False)
            if stat.S_ISLNK(before.st_mode) or not stat.S_ISDIR(before.st_mode):
                raise _runtime_error(
                    f"runtime exclusion path or ancestor is not a real directory: {relative.as_posix()}",
                    "RUNTIME_EXCLUSION_UNSAFE",
                )
            child_descriptor = os.open(part, flags, dir_fd=parent_descriptor)
            opened = os.fstat(child_descriptor)
            if (
                not stat.S_ISDIR(opened.st_mode)
                or _directory_operation_identity(before) != _directory_operation_identity(opened)
            ):
                os.close(child_descriptor)
                raise _runtime_error(
                    f"runtime exclusion path changed while opening: {relative.as_posix()}",
                    "RUNTIME_EXCLUSION_IDENTITY_DRIFT",
                )
            descriptors.append(child_descriptor)
            identities.append(_directory_operation_identity(opened))

        final_metadata = os.fstat(descriptors[-1])
        expected = contract["expected_identity"]
        observed_basic = (
            final_metadata.st_dev,
            final_metadata.st_ino,
            stat.S_IMODE(final_metadata.st_mode),
        )
        expected_basic = (expected["device"], expected["inode"], expected["mode"])
        if observed_basic != expected_basic:
            raise _runtime_error(
                f"runtime exclusion identity changed: {relative.as_posix()}",
                "RUNTIME_EXCLUSION_IDENTITY_DRIFT",
            )
        if observed_basic[2] & 0o222:
            raise _runtime_error(
                f"runtime exclusion directory has write bits: {relative.as_posix()}",
                "RUNTIME_EXCLUSION_WRITABLE",
            )
        with os.scandir(descriptors[-1]) as children:
            if next(children, None) is not None:
                raise _runtime_error(
                    f"runtime exclusion directory is populated: {relative.as_posix()}",
                    "RUNTIME_EXCLUSION_NOT_EMPTY",
                )

        if _directory_operation_identity(os.stat(repository, follow_symlinks=False)) != identities[0]:
            raise _runtime_error(
                "repository root changed during runtime-exclusion inspection",
                "RUNTIME_EXCLUSION_IDENTITY_DRIFT",
            )
        for position, part in enumerate(relative.parts):
            linked = os.stat(part, dir_fd=descriptors[position], follow_symlinks=False)
            opened = os.fstat(descriptors[position + 1])
            if (
                stat.S_ISLNK(linked.st_mode)
                or not stat.S_ISDIR(linked.st_mode)
                or _directory_operation_identity(linked) != identities[position + 1]
                or _directory_operation_identity(opened) != identities[position + 1]
            ):
                raise _runtime_error(
                    f"runtime exclusion path changed during inspection: {relative.as_posix()}",
                    "RUNTIME_EXCLUSION_IDENTITY_DRIFT",
                )
        return repository.joinpath(*relative.parts), tuple(identities)
    except ClonePackError:
        raise
    except FileNotFoundError as exc:
        raise _runtime_error(
            f"runtime exclusion path is missing: {relative.as_posix()}",
            "RUNTIME_EXCLUSION_MISSING",
        ) from exc
    except OSError as exc:
        raise _runtime_error(
            f"runtime exclusion path cannot be inspected safely: {relative.as_posix()}: {exc}",
            "RUNTIME_EXCLUSION_UNSAFE",
        ) from exc
    finally:
        for descriptor in reversed(descriptors):
            os.close(descriptor)


def validate_runtime_exclusion_references(
    exclusions: Any,
    index: dict[str, Any],
) -> None:
    records = _record_map(index)
    for raw in exclusions if isinstance(exclusions, list) else []:
        if not isinstance(raw, dict) or raw.get("kind") != "tool-runtime":
            continue
        contract = _canonical_runtime_contract(raw)
        for identifier in contract["authority_ids"]:
            record = records.get(identifier)
            if record is None:
                raise _runtime_error(
                    f"runtime exclusion authority is undefined: {identifier}",
                    "REF_UNDEFINED",
                )
            if record.get("kind") not in RUNTIME_DECISION_KINDS:
                raise _runtime_error(
                    f"runtime exclusion authority has the wrong kind: {identifier}",
                    "REF_WRONG_KIND",
                )
        for identifier in contract["evidence_ids"]:
            record = records.get(identifier)
            if record is None:
                raise _runtime_error(
                    f"runtime exclusion evidence is undefined: {identifier}",
                    "REF_UNDEFINED",
                )
            if record.get("kind") not in RUNTIME_EVIDENCE_KINDS:
                raise _runtime_error(
                    f"runtime exclusion evidence has the wrong kind: {identifier}",
                    "REF_WRONG_KIND",
                )


def canonical_runtime_exclusions(
    bindings: Iterable[RuntimeExclusionBinding],
) -> list[dict[str, Any]]:
    return [
        binding.contract
        for binding in sorted(bindings, key=lambda item: (str(item.contract["path"]), str(item.contract["id"])))
    ]


def _binding_repository(binding: RuntimeExclusionBinding) -> Path:
    repository = binding.path
    for _ in safe_relative_path(str(binding.contract["path"])).parts:
        repository = repository.parent
    return repository


def _runtime_binding_identity_matches(
    expected: tuple[tuple[int, int, int, int, int], ...],
    observed: tuple[tuple[int, int, int, int, int], ...],
) -> bool:
    if len(expected) != len(observed) or not expected:
        return False
    if any(
        expected_identity[:3] != observed_identity[:3]
        for expected_identity, observed_identity in zip(
            expected[:-1],
            observed[:-1],
            strict=True,
        )
    ):
        return False
    return expected[-1] == observed[-1]


def recheck_runtime_exclusions(bindings: Iterable[RuntimeExclusionBinding]) -> None:
    for binding in bindings:
        path, observed_identity = _inspect_runtime_directory(_binding_repository(binding), binding.contract)
        if path != binding.path or not _runtime_binding_identity_matches(
            binding.observed_identity,
            observed_identity,
        ):
            raise _runtime_error(
                f"runtime exclusion directory changed during operation: {binding.contract['path']}",
                "RUNTIME_EXCLUSION_IDENTITY_DRIFT",
            )


def validate_runtime_exclusions(
    repository_root: Path,
    exclusions: Any,
    *,
    pack_root: Path | None = None,
    includes: Iterable[str] = (),
    instruction_paths: Iterable[str] = (),
    scaffold_paths: Iterable[str] = (),
    change_paths: Iterable[str] = (),
) -> tuple[RuntimeExclusionBinding, ...]:
    """Validate all tool-runtime claims and return one canonical live binding set.

    Exclusions with an omitted kind remain scope-only and are deliberately not
    returned or applied to traversal.
    """

    if not isinstance(exclusions, list):
        raise _runtime_error("repository exclusions must be an array", "RUNTIME_EXCLUSION_INVALID")
    require_runtime_exclusion_capability(exclusions)
    repository = repository_root.expanduser().resolve()
    runtime_contracts: list[dict[str, Any]] = []
    all_exclusion_paths: list[tuple[str, str | None]] = []
    for position, raw in enumerate(exclusions):
        if not isinstance(raw, dict):
            raise _runtime_error(
                f"repository exclusion {position} is not an object",
                "RUNTIME_EXCLUSION_INVALID",
            )
        raw_path = raw.get("path")
        if isinstance(raw_path, str):
            all_exclusion_paths.append((safe_relative_path(raw_path).as_posix(), raw.get("kind")))
        if raw.get("kind") is None:
            continue
        if raw.get("kind") != "tool-runtime":
            raise _runtime_error("repository exclusion kind is unsupported", "RUNTIME_EXCLUSION_INVALID")
        runtime_contracts.append(_canonical_runtime_contract(raw))
    if not runtime_contracts:
        return ()

    identifiers = [str(item["id"]) for item in runtime_contracts]
    paths = [str(item["path"]) for item in runtime_contracts]
    if len(identifiers) != len(set(identifiers)) or len(paths) != len(set(paths)):
        raise _runtime_error("runtime exclusions repeat an ID or path", "RUNTIME_EXCLUSION_COLLISION")
    for position, path in enumerate(paths):
        for other in paths[position + 1 :]:
            if _path_overlaps(path, other):
                raise _runtime_error(
                    f"runtime exclusions overlap: {path}, {other}",
                    "RUNTIME_EXCLUSION_COLLISION",
                )
        for other, other_kind in all_exclusion_paths:
            if other_kind != "tool-runtime" and _path_overlaps(path, other):
                raise _runtime_error(
                    f"tool-runtime and scope-only exclusions overlap: {path}, {other}",
                    "RUNTIME_EXCLUSION_COLLISION",
                )

    reserved = [".git"]
    pack_relative = _pack_relative_to_repository(repository, pack_root)
    if pack_relative is not None:
        reserved.append(pack_relative)
    governed_paths: list[tuple[str, str]] = []
    for role, values in (
        ("repository instruction", instruction_paths),
        ("scaffold path", scaffold_paths),
        ("change path", change_paths),
    ):
        for value in values:
            governed_paths.append((role, safe_relative_path(str(value)).as_posix()))
    for path in paths:
        if Path(path).name == "AGENTS.md":
            governed_paths.append(("repository instruction", path))
        for reserved_path in reserved:
            if _path_overlaps(path, reserved_path):
                raise _runtime_error(
                    f"runtime exclusion collides with reserved path: {path}",
                    "RUNTIME_EXCLUSION_COLLISION",
                )
        for role, governed in governed_paths:
            if _path_overlaps(path, governed):
                raise _runtime_error(
                    f"runtime exclusion collides with {role}: {path}, {governed}",
                    "RUNTIME_EXCLUSION_COLLISION",
                )
        for include in includes:
            normalized_include = safe_relative_path(str(include)).as_posix()
            if _path_overlaps(path, normalized_include):
                raise ClonePackError(
                    f"snapshot include names or overlaps a runtime exclusion: {include}",
                    exit_code=4,
                    diagnostic="SNAPSHOT_INCLUDE_EXCLUDED",
                )

    if _git_root(repository) is not None:
        tracked_raw = _run_git(repository, ["ls-files", "-z"]).stdout
        tracked_paths = [
            value for value in _decode_git(tracked_raw, "tracked path list").split("\0") if value
        ]
        for path in paths:
            collision = next((tracked for tracked in tracked_paths if _path_overlaps(path, tracked)), None)
            if collision is not None:
                raise _runtime_error(
                    f"runtime exclusion collides with tracked path: {path}, {collision}",
                    "RUNTIME_EXCLUSION_COLLISION",
                )

    bindings: list[RuntimeExclusionBinding] = []
    for contract in runtime_contracts:
        path, observed_identity = _inspect_runtime_directory(repository, contract)
        bindings.append(RuntimeExclusionBinding(contract, path, observed_identity))
    return tuple(sorted(bindings, key=lambda item: (str(item.contract["path"]), str(item.contract["id"]))))


def runtime_path_is_excluded(path: Path, bindings: Iterable[RuntimeExclusionBinding]) -> bool:
    absolute = path.absolute()
    return any(absolute == binding.path or _inside(absolute, binding.path) for binding in bindings)


def _is_excluded(path: Path, repository: Path, pack: Path | None) -> bool:
    try:
        relative = path.relative_to(repository)
    except ValueError:
        return True
    if relative.parts and relative.parts[0] == ".git":
        return True
    if pack is None:
        return False
    lexical_pack = pack.parent.resolve(strict=False) / pack.name
    return _inside(path, lexical_pack)


def _safe_include(
    repository: Path,
    value: str,
    pack: Path | None,
    runtime_bindings: Iterable[RuntimeExclusionBinding] = (),
) -> Path:
    relative = safe_relative_path(value)
    candidate = repository.joinpath(*relative.parts)
    if any(
        _path_overlaps(relative.as_posix(), str(binding.contract["path"]))
        for binding in runtime_bindings
    ):
        raise ClonePackError(
            f"snapshot include names or overlaps a runtime exclusion: {value}",
            exit_code=4,
            diagnostic="SNAPSHOT_INCLUDE_EXCLUDED",
        )
    current = repository
    for position, part in enumerate(relative.parts):
        current = current / part
        try:
            metadata = current.lstat()
        except OSError as exc:
            raise ClonePackError(
                f"snapshot include does not exist: {value}",
                exit_code=2,
                diagnostic="SNAPSHOT_INCLUDE_MISSING",
            ) from exc
        if position < len(relative.parts) - 1 and stat.S_ISLNK(metadata.st_mode):
            raise ClonePackError(
                f"snapshot include has a symlink ancestor: {value}",
                exit_code=4,
                diagnostic="PATH_UNSAFE",
            )
        if position < len(relative.parts) - 1 and not stat.S_ISDIR(metadata.st_mode):
            raise ClonePackError(
                f"snapshot include has a non-directory ancestor: {value}",
                exit_code=2,
                diagnostic="SNAPSHOT_INCLUDE_MISSING",
            )
    if _is_excluded(candidate, repository, pack):
        raise ClonePackError(
            f"snapshot include names an excluded path: {value}",
            exit_code=2,
            diagnostic="SNAPSHOT_INCLUDE_EXCLUDED",
        )
    return candidate


def _metadata_identity(metadata: os.stat_result) -> tuple[int, int, int, int, int, int]:
    return (
        metadata.st_dev,
        metadata.st_ino,
        metadata.st_mode,
        metadata.st_size,
        metadata.st_mtime_ns,
        metadata.st_ctime_ns,
    )


def _regular_entry(path: Path, relative: str, metadata: os.stat_result) -> dict[str, Any]:
    digest = sha256_bytes(b"")
    try:
        import hashlib

        hasher = hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                hasher.update(chunk)
        digest = hasher.hexdigest()
        after = path.lstat()
    except (OSError, RuntimeError) as exc:
        raise ClonePackError(
            f"cannot read repository file during snapshot: {relative}: {exc}",
            exit_code=4,
            diagnostic="SNAPSHOT_UNREADABLE",
        ) from exc
    if _metadata_identity(metadata) != _metadata_identity(after) or not stat.S_ISREG(after.st_mode):
        raise ClonePackError(
            f"repository file changed while it was being snapshotted: {relative}",
            exit_code=4,
            diagnostic="SNAPSHOT_CONCURRENT_MUTATION",
        )
    return {
        "path": relative,
        "type": "file",
        "mode": stat.S_IMODE(metadata.st_mode),
        "size": metadata.st_size,
        "sha256": digest,
    }


def _symlink_entry(path: Path, relative: str, metadata: os.stat_result) -> dict[str, Any]:
    try:
        target = os.readlink(path)
        target.encode("utf-8")
        after = path.lstat()
    except (OSError, RuntimeError, UnicodeError) as exc:
        raise ClonePackError(
            f"cannot read repository symlink during snapshot: {relative}: {exc}",
            exit_code=4,
            diagnostic="SNAPSHOT_UNREADABLE",
        ) from exc
    if _metadata_identity(metadata) != _metadata_identity(after) or not stat.S_ISLNK(after.st_mode):
        raise ClonePackError(
            f"repository symlink changed while it was being snapshotted: {relative}",
            exit_code=4,
            diagnostic="SNAPSHOT_CONCURRENT_MUTATION",
        )
    return {
        "path": relative,
        "type": "symlink",
        "mode": stat.S_IMODE(metadata.st_mode),
        "target": target,
        "sha256": sha256_bytes(target.encode("utf-8")),
    }


def _entry_for_path(path: Path, repository: Path) -> dict[str, Any] | None:
    relative = path.relative_to(repository).as_posix()
    try:
        metadata = path.lstat()
    except OSError as exc:
        raise ClonePackError(
            f"cannot inspect repository path during snapshot: {relative}: {exc}",
            exit_code=4,
            diagnostic="SNAPSHOT_UNREADABLE",
        ) from exc
    if stat.S_ISREG(metadata.st_mode):
        return _regular_entry(path, relative, metadata)
    if stat.S_ISLNK(metadata.st_mode):
        return _symlink_entry(path, relative, metadata)
    if stat.S_ISDIR(metadata.st_mode):
        return None
    raise ClonePackError(
        f"repository contains unsupported special file: {relative}",
        exit_code=4,
        diagnostic="SNAPSHOT_SPECIAL_FILE",
    )


def _walk_non_git(
    repository: Path,
    pack: Path | None,
    includes: list[str],
    runtime_bindings: Iterable[RuntimeExclusionBinding] = (),
) -> list[dict[str, Any]]:
    runtime_bindings = tuple(runtime_bindings)
    for value in includes:
        _safe_include(repository, value, pack, runtime_bindings)
    entries: dict[str, dict[str, Any]] = {}

    def visit(path: Path) -> None:
        if path != repository and runtime_path_is_excluded(path, runtime_bindings):
            return
        if path != repository and _is_excluded(path, repository, pack):
            return
        try:
            metadata = path.lstat()
        except OSError as exc:
            relative = path.relative_to(repository).as_posix()
            raise ClonePackError(
                f"cannot inspect repository path during snapshot: {relative}: {exc}",
                exit_code=4,
                diagnostic="SNAPSHOT_UNREADABLE",
            ) from exc
        if stat.S_ISDIR(metadata.st_mode):
            try:
                children = sorted(path.iterdir(), key=lambda child: child.name)
            except OSError as exc:
                relative = path.relative_to(repository).as_posix() or "."
                raise ClonePackError(
                    f"cannot enumerate repository directory: {relative}: {exc}",
                    exit_code=4,
                    diagnostic="SNAPSHOT_UNREADABLE",
                ) from exc
            for child in children:
                visit(child)
            return
        entry = _entry_for_path(path, repository)
        if entry is not None:
            entries[entry["path"]] = entry

    visit(repository)
    return [entries[path] for path in sorted(entries)]


def _run_git(repository: Path, arguments: list[str], *, allow: set[int] | None = None) -> subprocess.CompletedProcess[bytes]:
    allowed = allow or {0}
    environment = os.environ.copy()
    environment["LC_ALL"] = "C"
    environment["GIT_OPTIONAL_LOCKS"] = "0"
    try:
        completed = subprocess.run(
            ["git", "-C", str(repository), *arguments],
            env=environment,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
            shell=False,
        )
    except OSError as exc:
        raise ClonePackError(
            f"Git is unavailable: {exc}",
            exit_code=7,
            diagnostic="CAPABILITY_MISSING",
        ) from exc
    if completed.returncode not in allowed:
        message = completed.stderr.decode("utf-8", errors="replace").strip()
        raise ClonePackError(
            f"Git command failed ({' '.join(arguments)}): {message}",
            exit_code=7,
            diagnostic="GIT_COMMAND_FAILED",
        )
    return completed


def _decode_git(value: bytes, role: str) -> str:
    try:
        return value.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ClonePackError(
            f"Git returned a non-UTF-8 {role}",
            exit_code=4,
            diagnostic="GIT_PATH_ENCODING_UNSUPPORTED",
        ) from exc


def _git_root(repository: Path) -> Path | None:
    # A repository-local marker is the capability boundary.  A directory that
    # has no marker remains usable as a deterministic filesystem repository
    # even when Git is not installed.  Once a marker exists, silently falling
    # back would discard index, HEAD, ignore, and submodule semantics.
    marker = repository / ".git"
    if not marker.exists() and not marker.is_symlink():
        return None
    completed = _run_git(repository, ["rev-parse", "--show-toplevel"], allow={0, 128})
    if completed.returncode != 0:
        message = completed.stderr.decode("utf-8", errors="replace").strip()
        raise ClonePackError(
            f"repository has a .git marker but is not a usable Git worktree: {message}",
            exit_code=4,
            diagnostic="GIT_REPOSITORY_INVALID",
        )
    value = _decode_git(completed.stdout, "repository root").strip()
    if not value:
        return None
    return Path(value).resolve()


def _path_selected(path: str, includes: list[str]) -> bool:
    if not includes:
        return True
    return any(path == include or path.startswith(include.rstrip("/") + "/") for include in includes)


def _path_excluded_by_pack(path: str, repository: Path, pack: Path | None) -> bool:
    pack_relative = _pack_relative_to_repository(repository, pack)
    return pack_relative is not None and (
        path == pack_relative or path.startswith(pack_relative.rstrip("/") + "/")
    )


def _parse_porcelain_v2(raw: bytes, repository: Path, pack: Path | None) -> list[dict[str, Any]]:
    text = _decode_git(raw, "status output")
    tokens = text.split("\0")
    records: list[dict[str, Any]] = []
    position = 0
    while position < len(tokens):
        token = tokens[position]
        position += 1
        if not token:
            continue
        kind = token[0]
        if kind in {"?", "!"}:
            path = token[2:]
            record = {"kind": "untracked" if kind == "?" else "ignored", "path": path, "xy": "??" if kind == "?" else "!!"}
        elif kind == "1":
            fields = token.split(" ", 8)
            if len(fields) != 9:
                raise ClonePackError("Git status record is malformed", exit_code=4, diagnostic="GIT_STATUS_INVALID")
            record = {"kind": "ordinary", "xy": fields[1], "path": fields[8]}
        elif kind == "2":
            fields = token.split(" ", 9)
            if len(fields) != 10 or position >= len(tokens):
                raise ClonePackError("Git rename record is malformed", exit_code=4, diagnostic="GIT_STATUS_INVALID")
            original = tokens[position]
            position += 1
            record = {"kind": "rename", "xy": fields[1], "path": fields[9], "original_path": original}
        elif kind == "u":
            fields = token.split(" ", 10)
            if len(fields) != 11:
                raise ClonePackError("Git unmerged record is malformed", exit_code=4, diagnostic="GIT_STATUS_INVALID")
            record = {"kind": "unmerged", "xy": fields[1], "path": fields[10]}
        else:
            raise ClonePackError(
                f"unsupported Git porcelain-v2 record: {kind}",
                exit_code=4,
                diagnostic="GIT_STATUS_INVALID",
            )
        paths = [str(record["path"])]
        if "original_path" in record:
            paths.append(str(record["original_path"]))
        if any(_path_excluded_by_pack(path, repository, pack) for path in paths):
            continue
        records.append(record)
    return sorted(records, key=lambda record: (str(record["path"]), str(record.get("original_path", ""))))


def _git_metadata(repository: Path, pack: Path | None) -> dict[str, Any]:
    root = _git_root(repository)
    if root is None:
        raise ClonePackError("repository is not a Git worktree", diagnostic="GIT_REPOSITORY_INVALID")
    if root != repository.resolve():
        raise ClonePackError(
            f"--repo-root must equal the Git worktree root: {root}",
            exit_code=2,
            diagnostic="REPOSITORY_ROOT_MISMATCH",
        )
    head_process = _run_git(repository, ["rev-parse", "--verify", "HEAD"], allow={0, 128})
    head = _decode_git(head_process.stdout, "HEAD").strip() if head_process.returncode == 0 else None
    branch_process = _run_git(repository, ["symbolic-ref", "--quiet", "--short", "HEAD"], allow={0, 1})
    branch = _decode_git(branch_process.stdout, "branch").strip() if branch_process.returncode == 0 else None
    status_raw = _run_git(
        repository,
        ["status", "--porcelain=v2", "-z", "--untracked-files=all", "--ignore-submodules=none"],
    ).stdout
    status = _parse_porcelain_v2(status_raw, repository, pack)
    index_raw = _run_git(repository, ["ls-files", "--stage", "-z"]).stdout
    submodule_process = _run_git(repository, ["submodule", "status", "--recursive"], allow={0, 1})
    submodule_text = _decode_git(submodule_process.stdout, "submodule output")
    submodules = [line for line in submodule_text.splitlines() if line]
    uninitialized = [line for line in submodules if line.startswith("-")]
    if uninitialized:
        paths: list[str] = []
        for line in uninitialized:
            fields = line[1:].split(maxsplit=1)
            paths.append(fields[1].split(" (", 1)[0] if len(fields) == 2 else "<unknown>")
        raise ClonePackError(
            "repository contains uninitialized submodules: " + ", ".join(paths),
            exit_code=4,
            diagnostic="SUBMODULE_UNINITIALIZED",
        )
    return {
        "head": head,
        "branch": branch,
        "detached": head is not None and branch is None,
        "index_sha256": sha256_bytes(index_raw),
        "status": status,
        "status_sha256": sha256_bytes(canonical_json(status).encode("utf-8")),
        "submodules": submodules,
    }


def _git_path_is_ignored(repository: Path, value: str) -> bool:
    completed = _run_git(repository, ["check-ignore", "-q", "--", value], allow={0, 1})
    return completed.returncode == 0


def _git_entries(
    repository: Path,
    pack: Path | None,
    includes: list[str],
    inventoried_paths: set[str],
    runtime_bindings: Iterable[RuntimeExclusionBinding] = (),
) -> list[dict[str, Any]]:
    runtime_bindings = tuple(runtime_bindings)
    for include in includes:
        _safe_include(repository, include, pack, runtime_bindings)
    raw = _run_git(repository, ["ls-files", "-c", "-o", "--exclude-standard", "-z"]).stdout
    paths = {value for value in _decode_git(raw, "path list").split("\0") if value}

    # Git intentionally omits ignored paths.  An ignored path may enter the
    # ordinary snapshot only when the governed repository inventory already
    # names that exact file.  This prevents --include from turning an ignored
    # secret/build-output tree into newly discovered evidence.
    for include in includes:
        if not _git_path_is_ignored(repository, include):
            continue
        declared = {
            path
            for path in inventoried_paths
            if path == include or path.startswith(include.rstrip("/") + "/")
        }
        if not declared:
            raise ClonePackError(
                f"ignored snapshot include is absent from repository inventory: {include}",
                exit_code=2,
                diagnostic="SNAPSHOT_INCLUDE_NOT_INVENTORIED",
            )
    if includes:
        for value in inventoried_paths:
            if _path_selected(value, includes) and _git_path_is_ignored(repository, value):
                paths.add(value)

    entries: list[dict[str, Any]] = []
    for value in sorted(paths):
        if _path_excluded_by_pack(value, repository, pack):
            continue
        relative = safe_relative_path(value)
        path = repository.joinpath(*relative.parts)
        if runtime_path_is_excluded(path, runtime_bindings):
            continue
        try:
            path.lstat()
        except FileNotFoundError:
            continue
        entry = _entry_for_path(path, repository)
        if entry is not None:
            entries.append(entry)
    return sorted(entries, key=lambda entry: str(entry["path"]))


def inventory_repository(
    repository_root: Path,
    *,
    pack_root: Path | None = None,
    includes: list[str] | None = None,
    inventoried_paths: set[str] | None = None,
    runtime_exclusions: list[dict[str, Any]] | None = None,
    instruction_paths: Iterable[str] = (),
    scaffold_paths: Iterable[str] = (),
    change_paths: Iterable[str] = (),
) -> dict[str, Any]:
    repository = repository_root.expanduser().resolve()
    if not repository.is_dir():
        raise ClonePackError(
            f"repository root is not a directory: {repository}",
            exit_code=2,
            diagnostic="ARG_INVALID",
        )
    selected = list(dict.fromkeys(includes or []))
    runtime_bindings = validate_runtime_exclusions(
        repository,
        runtime_exclusions or [],
        pack_root=pack_root,
        includes=selected,
        instruction_paths=instruction_paths,
        scaffold_paths=scaffold_paths,
        change_paths=change_paths,
    )
    git_root = _git_root(repository)
    if git_root is not None:
        git = _git_metadata(repository, pack_root)
        if runtime_bindings:
            git["status"] = [
                record
                for record in git["status"]
                if not any(
                    _path_overlaps(str(record.get(key, "")), str(binding.contract["path"]))
                    for key in ("path", "original_path")
                    if record.get(key)
                    for binding in runtime_bindings
                )
            ]
            git["status_sha256"] = sha256_bytes(canonical_json(git["status"]).encode("utf-8"))
        entries = _git_entries(
            repository,
            pack_root,
            selected,
            set(inventoried_paths or ()),
            runtime_bindings,
        )
        after_git = _git_metadata(repository, pack_root)
        if runtime_bindings:
            after_git["status"] = [
                record
                for record in after_git["status"]
                if not any(
                    _path_overlaps(str(record.get(key, "")), str(binding.contract["path"]))
                    for key in ("path", "original_path")
                    if record.get(key)
                    for binding in runtime_bindings
                )
            ]
            after_git["status_sha256"] = sha256_bytes(
                canonical_json(after_git["status"]).encode("utf-8")
            )
        if after_git != git:
            raise ClonePackError(
                "Git metadata changed while the repository snapshot was being captured",
                exit_code=4,
                diagnostic="SNAPSHOT_CONCURRENT_MUTATION",
            )
        kind = "git"
        dirty_paths = sorted(
            {
                str(record[path_key])
                for record in git["status"]
                for path_key in ("path", "original_path")
                if path_key in record
            }
        )
        repository_details: dict[str, Any] = {"kind": kind, "git": git}
    else:
        entries = _walk_non_git(repository, pack_root, selected, runtime_bindings)
        kind = "filesystem"
        dirty_paths = []
        repository_details = {"kind": kind, "git": None}
    recheck_runtime_exclusions(runtime_bindings)
    repository_details.update(
        {
            "root": repository.as_posix(),
            "includes": selected,
            "entries": entries,
            "dirty_paths": dirty_paths,
            "agents_files": sorted(
                entry["path"] for entry in entries if Path(str(entry["path"])).name == "AGENTS.md"
            ),
        }
    )
    if runtime_bindings:
        repository_details["runtime_exclusions"] = canonical_runtime_exclusions(runtime_bindings)
    return repository_details


def build_repository_snapshot(
    repository_root: Path,
    *,
    pack_root: Path,
    snapshot_id: str,
    role: str,
    includes: list[str] | None = None,
    inventoried_paths: set[str] | None = None,
    runtime_exclusions: list[dict[str, Any]] | None = None,
    instruction_paths: Iterable[str] = (),
    scaffold_paths: Iterable[str] = (),
    change_paths: Iterable[str] = (),
    timestamp: str | None = None,
) -> dict[str, Any]:
    if role not in SNAPSHOT_ROLES:
        raise ClonePackError(
            "snapshot role must be adopted or candidate",
            exit_code=2,
            diagnostic="ARG_INVALID",
        )
    if re.fullmatch(r"SNAP-[0-9]{3,}", snapshot_id) is None:
        raise ClonePackError("snapshot ID must match SNAP-###", exit_code=2, diagnostic="ARG_INVALID")
    captured_at, _ = utc_now(timestamp)
    inventory = inventory_repository(
        repository_root,
        pack_root=pack_root,
        includes=includes,
        inventoried_paths=inventoried_paths,
        runtime_exclusions=runtime_exclusions,
        instruction_paths=instruction_paths,
        scaffold_paths=scaffold_paths,
        change_paths=change_paths,
    )
    stable = {
        "repository_kind": inventory["kind"],
        "repository": inventory["git"],
        "includes": inventory["includes"],
        "entries": inventory["entries"],
    }
    snapshot = {
        "schema_version": "clone-repository-snapshot/v2",
        "snapshot_id": snapshot_id,
        "role": role,
        "captured_at": captured_at,
        "repository_kind": inventory["kind"],
        "repository_root": Path(repository_root).expanduser().resolve().as_posix(),
        "repository": inventory["git"],
        "includes": inventory["includes"],
        "entries": inventory["entries"],
        "content_sha256": sha256_bytes(canonical_json(stable).encode("utf-8")),
    }
    if inventory.get("runtime_exclusions"):
        snapshot["runtime_exclusions"] = inventory["runtime_exclusions"]
    _require_schema(snapshot, "repository-snapshot-v2.schema.json", "SNAPSHOT_INVALID")
    return snapshot


def recover_transactions(pack: Path) -> list[str]:
    return recover_atomic_transactions(pack.expanduser().resolve())


def write_transaction(pack: Path, operation: str, files: dict[Path, bytes]) -> str:
    pack = pack.expanduser().resolve()
    if not files:
        raise ClonePackError("transaction requires at least one target", diagnostic="TRANSACTION_INVALID")
    recover_transactions(pack)
    text_files: dict[Path, str] = {}
    for path, value in files.items():
        try:
            text_files[path] = value.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise ClonePackError(
                "shared pack transactions accept canonical UTF-8 evidence files only",
                diagnostic="TRANSACTION_INVALID",
            ) from exc
    atomic_write_many(text_files, transaction_root=pack, operation=operation)
    return operation


def _snapshot_pointer(plan: dict[str, Any], role: str) -> dict[str, Any] | None:
    snapshots = plan.get("snapshots")
    value = snapshots.get(role) if isinstance(snapshots, dict) else None
    if value is None:
        return None
    if not isinstance(value, dict):
        raise ClonePackError(f"enhancement plan snapshot pointer is invalid: {role}", diagnostic="PLAN_INVALID")
    return value


def _load_retained_snapshot(pack: Path, pointer: dict[str, Any], role: str) -> dict[str, Any]:
    path_value = pointer.get("path")
    expected = pointer.get("sha256")
    if not isinstance(path_value, str) or not isinstance(expected, str):
        raise ClonePackError(f"snapshot pointer is invalid: {role}", diagnostic="SNAPSHOT_POINTER_INVALID")
    path = resolve_inside(pack, path_value, must_exist=True)
    if sha256_file(path) != expected:
        raise ClonePackError(
            f"retained {role} snapshot hash differs from its pointer",
            exit_code=4,
            diagnostic="SNAPSHOT_HASH_MISMATCH",
        )
    snapshot = load_json(path)
    _require_schema(snapshot, "repository-snapshot-v2.schema.json", "SNAPSHOT_INVALID")
    retained_runtime = snapshot.get("runtime_exclusions", [])
    if retained_runtime:
        try:
            canonical_runtime = [_canonical_runtime_contract(item) for item in retained_runtime]
        except ClonePackError as exc:
            raise ClonePackError(
                f"retained {role} snapshot runtime exclusion is invalid: {exc}",
                exit_code=4,
                diagnostic="SNAPSHOT_INVALID",
            ) from exc
        canonical_runtime.sort(key=lambda item: (str(item["path"]), str(item["id"])))
        if retained_runtime != canonical_runtime:
            raise ClonePackError(
                f"retained {role} snapshot runtime exclusions are not canonical",
                exit_code=4,
                diagnostic="SNAPSHOT_INVALID",
            )
    if snapshot.get("snapshot_id") != pointer.get("snapshot_id") or snapshot.get("role") != role:
        raise ClonePackError(
            f"retained {role} snapshot identity differs from its pointer",
            exit_code=4,
            diagnostic="SNAPSHOT_POINTER_INVALID",
        )
    if snapshot.get("content_sha256") != pointer.get("content_sha256"):
        raise ClonePackError(
            f"retained {role} snapshot content identity differs from its pointer",
            exit_code=4,
            diagnostic="SNAPSHOT_HASH_MISMATCH",
        )
    return snapshot


def retained_snapshot(pack: Path, role: str) -> tuple[dict[str, Any], dict[str, Any]]:
    manifest = _require_enhancement_manifest(pack)
    plan = load_json(_plan_path(pack, manifest))
    pointer = _snapshot_pointer(plan, role)
    if pointer is None:
        raise ClonePackError(
            f"{role} repository snapshot has not been recorded",
            diagnostic="SNAPSHOT_MISSING",
        )
    snapshot = _load_retained_snapshot(pack, pointer, role)
    if role == "candidate":
        adopted_pointer = _snapshot_pointer(plan, "adopted")
        if adopted_pointer is not None:
            adopted = _load_retained_snapshot(pack, adopted_pointer, "adopted")
            if adopted.get("runtime_exclusions", []) != snapshot.get("runtime_exclusions", []):
                raise ClonePackError(
                    "candidate runtime exclusions differ from the adopted snapshot",
                    exit_code=4,
                    diagnostic="RUNTIME_EXCLUSION_POLICY_DRIFT",
                )
    return pointer, snapshot


def record_repository_snapshot(
    pack: Path,
    role: str,
    *,
    includes: list[str] | None = None,
    timestamp: str | None = None,
) -> tuple[dict[str, Any], int]:
    pack = pack.expanduser().resolve()
    recover_transactions(pack)
    manifest = _require_enhancement_manifest(pack)
    plan_path = _plan_path(pack, manifest)
    plan = load_json(plan_path)
    existing_pointer = _snapshot_pointer(plan, role)
    if role == "adopted" and existing_pointer is not None:
        raise ClonePackError(
            "the adopted repository snapshot is immutable",
            diagnostic="ADOPTED_SNAPSHOT_IMMUTABLE",
        )
    status = plan.get("status")
    if role == "adopted" and status not in {"DRAFT", "READY"}:
        raise ClonePackError(
            f"adopted snapshot recording is forbidden while enhancement status is {status!r}",
            exit_code=4,
            diagnostic="SNAPSHOT_STATE_INVALID",
        )
    if role == "candidate" and status != "IN_PROGRESS":
        raise ClonePackError(
            "candidate snapshot recording requires enhancement status IN_PROGRESS; "
            "transition an IMPLEMENTED enhancement back to IN_PROGRESS before replacing its candidate",
            exit_code=4,
            diagnostic="SNAPSHOT_STATE_INVALID",
        )
    index_path = _index_path(pack, manifest)
    index = load_json(index_path)
    records = _record_map(index)
    enhancement_id = str(manifest["workstream"]["enhancement_id"])
    enhancement_record = records.get(enhancement_id)
    if enhancement_record is None or enhancement_record.get("kind") != "ENH":
        raise ClonePackError(
            f"snapshot enhancement record is undefined: {enhancement_id}",
            diagnostic="REF_UNDEFINED",
        )
    snapshot_id = _next_id(records, "SNAP")
    repository = Path(str(manifest.get("repository_root", ""))).expanduser().resolve()
    inventoried_paths = _inventoried_entry_paths(pack, manifest)
    runtime_exclusions, instruction_paths, scaffold_paths, change_paths = _snapshot_runtime_context(
        pack,
        manifest,
    )
    validate_runtime_exclusion_references(runtime_exclusions, index)
    snapshot = build_repository_snapshot(
        repository,
        pack_root=pack,
        snapshot_id=snapshot_id,
        role=role,
        includes=list(dict.fromkeys(includes or [])),
        inventoried_paths=inventoried_paths,
        runtime_exclusions=runtime_exclusions,
        instruction_paths=instruction_paths,
        scaffold_paths=scaffold_paths,
        change_paths=change_paths,
        timestamp=timestamp,
    )
    if role == "candidate":
        adopted_pointer = _snapshot_pointer(plan, "adopted")
        if adopted_pointer is not None:
            adopted = _load_retained_snapshot(pack, adopted_pointer, "adopted")
            if adopted.get("runtime_exclusions", []) != snapshot.get("runtime_exclusions", []):
                raise ClonePackError(
                    "candidate runtime exclusions differ from the adopted snapshot",
                    exit_code=4,
                    diagnostic="RUNTIME_EXCLUSION_POLICY_DRIFT",
                )
    snapshot_path = pack / "evidence" / "snapshots" / f"{snapshot_id}.json"
    if snapshot_path.exists():
        raise ClonePackError(
            f"snapshot output already exists: {snapshot_path.relative_to(pack)}",
            diagnostic="OUTPUT_EXISTS",
        )
    snapshot_bytes = canonical_json(snapshot).encode("utf-8")
    pointer = {
        "snapshot_id": snapshot_id,
        "path": snapshot_path.relative_to(pack).as_posix(),
        "sha256": sha256_bytes(snapshot_bytes),
        "content_sha256": snapshot["content_sha256"],
    }
    snapshots = plan.setdefault("snapshots", {"adopted": None, "candidate": None})
    if not isinstance(snapshots, dict):
        raise ClonePackError("enhancement plan snapshots must be an object", diagnostic="PLAN_INVALID")
    snapshots[role] = pointer
    anchor = f'"snapshot_id": "{snapshot_id}"'
    anchor_line = next(line for line in canonical_json(snapshot).splitlines(keepends=True) if anchor in line)
    enhancement_record.setdefault("links", {}).setdefault("snapshots", []).append(snapshot_id)
    enhancement_record["links"]["snapshots"] = sorted(
        set(enhancement_record["links"]["snapshots"])
    )
    index["records"].append(
        {
            "id": snapshot_id,
            "kind": "SNAP",
            "locator": {
                "path": pointer["path"],
                "anchor": anchor,
                "sha256": sha256_bytes(anchor_line.encode("utf-8")),
            },
            "links": {"enhancements": [enhancement_id]},
            "applicability": "REQUIRED",
            "state": "VERIFIED",
            "attributes": {
                "role": role,
                "content_sha256": snapshot["content_sha256"],
                "repository_kind": snapshot["repository_kind"],
            },
        }
    )
    transaction_files = {
        snapshot_path: snapshot_bytes,
        plan_path: canonical_json(plan).encode("utf-8"),
        index_path: canonical_json(index).encode("utf-8"),
    }
    if role == "candidate":
        manifest["repository_state"] = {
            "kind": "working-tree",
            "revision": snapshot_id,
            "diff_sha256": snapshot["content_sha256"],
        }
        transaction_files[pack / "clone_pack.json"] = canonical_json(manifest).encode("utf-8")
    transaction_id = write_transaction(
        pack,
        f"repo-snapshot:{role}:{snapshot_id}",
        transaction_files,
    )
    return (
        {
            "schema_version": "clone-repository-snapshot-command/v2",
            "snapshot_id": snapshot_id,
            "snapshot_path": pointer["path"],
            "repository_kind": snapshot["repository_kind"],
            "role": role,
            "status": "RECORDED",
            "content_sha256": snapshot["content_sha256"],
            "transaction_id": transaction_id,
        },
        0,
    )


def check_repository_snapshot(
    pack: Path,
    role: str,
    *,
    includes: list[str] | None = None,
) -> tuple[dict[str, Any], int]:
    pack = pack.expanduser().resolve()
    manifest = _require_enhancement_manifest(pack)
    plan = load_json(_plan_path(pack, manifest))
    pointer = _snapshot_pointer(plan, role)
    if pointer is None:
        raise ClonePackError(f"{role} repository snapshot has not been recorded", diagnostic="SNAPSHOT_MISSING")
    retained = _load_retained_snapshot(pack, pointer, role)
    selected = list(dict.fromkeys(includes or []))
    retained_includes = retained.get("includes")
    if selected and selected != retained_includes:
        raise ClonePackError(
            "--include values must exactly match the recorded snapshot includes",
            exit_code=2,
            diagnostic="SNAPSHOT_INCLUDE_MISMATCH",
        )
    repository = Path(str(manifest.get("repository_root", ""))).expanduser().resolve()
    inventoried_paths = _inventoried_entry_paths(pack, manifest)
    runtime_exclusions, instruction_paths, scaffold_paths, change_paths = _snapshot_runtime_context(
        pack,
        manifest,
    )
    validate_runtime_exclusion_references(
        runtime_exclusions,
        load_json(_index_path(pack, manifest)),
    )
    current = build_repository_snapshot(
        repository,
        pack_root=pack,
        snapshot_id=str(pointer["snapshot_id"]),
        role=role,
        includes=list(retained_includes or []),
        inventoried_paths=inventoried_paths,
        runtime_exclusions=runtime_exclusions,
        instruction_paths=instruction_paths,
        scaffold_paths=scaffold_paths,
        change_paths=change_paths,
        timestamp="1970-01-01T00:00:00+00:00",
    )
    matches = (
        current["content_sha256"] == retained["content_sha256"]
        and current.get("runtime_exclusions", []) == retained.get("runtime_exclusions", [])
    )
    return (
        {
            "schema_version": "clone-repository-snapshot-check/v2",
            "snapshot_id": pointer["snapshot_id"],
            "role": role,
            "status": "MATCH" if matches else "DRIFT",
            "expected_sha256": retained["content_sha256"],
            "actual_sha256": current["content_sha256"],
            "repository_kind": current["repository_kind"],
        },
        0 if matches else 4,
    )


def repository_snapshot(
    pack: Path,
    role: str,
    *,
    record: bool,
    check: bool,
    includes: list[str] | None = None,
    timestamp: str | None = None,
) -> tuple[dict[str, Any], int]:
    if record == check:
        raise ClonePackError(
            "repo-snapshot requires exactly one of --record or --check",
            exit_code=2,
            diagnostic="ARG_INVALID",
        )
    if record:
        return record_repository_snapshot(pack, role, includes=includes, timestamp=timestamp)
    return check_repository_snapshot(pack, role, includes=includes)
