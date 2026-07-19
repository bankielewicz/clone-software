from __future__ import annotations

import os
import re
import stat
import subprocess
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


def _is_excluded(path: Path, repository: Path, pack: Path | None) -> bool:
    try:
        relative = path.relative_to(repository)
    except ValueError:
        return True
    if relative.parts and relative.parts[0] == ".git":
        return True
    if pack is None:
        return False
    lexical_pack = pack.resolve()
    if _inside(path, lexical_pack):
        return True
    try:
        resolved = path.resolve(strict=False)
    except (OSError, RuntimeError):
        return False
    return _inside(resolved, lexical_pack)


def _safe_include(repository: Path, value: str, pack: Path | None) -> Path:
    relative = safe_relative_path(value)
    candidate = repository.joinpath(*relative.parts)
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


def _walk_non_git(repository: Path, pack: Path | None, includes: list[str]) -> list[dict[str, Any]]:
    starts = [_safe_include(repository, value, pack) for value in includes]
    if not starts:
        starts = [repository]
    entries: dict[str, dict[str, Any]] = {}

    def visit(path: Path) -> None:
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

    for start in starts:
        visit(start)
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
) -> list[dict[str, Any]]:
    for include in includes:
        _safe_include(repository, include, pack)
    raw = _run_git(repository, ["ls-files", "-c", "-o", "--exclude-standard", "-z"]).stdout
    paths = {value for value in _decode_git(raw, "path list").split("\0") if value}

    # Git intentionally omits ignored paths.  An ignored path may enter a
    # narrowed snapshot only when the governed repository inventory already
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
        if not _path_selected(value, includes) or _path_excluded_by_pack(value, repository, pack):
            continue
        relative = safe_relative_path(value)
        path = repository.joinpath(*relative.parts)
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
) -> dict[str, Any]:
    repository = repository_root.expanduser().resolve()
    if not repository.is_dir():
        raise ClonePackError(
            f"repository root is not a directory: {repository}",
            exit_code=2,
            diagnostic="ARG_INVALID",
        )
    selected = list(dict.fromkeys(includes or []))
    git_root = _git_root(repository)
    if git_root is not None:
        git = _git_metadata(repository, pack_root)
        entries = _git_entries(repository, pack_root, selected, set(inventoried_paths or ()))
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
        entries = _walk_non_git(repository, pack_root, selected)
        kind = "filesystem"
        dirty_paths = []
        repository_details = {"kind": kind, "git": None}
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
    return repository_details


def build_repository_snapshot(
    repository_root: Path,
    *,
    pack_root: Path,
    snapshot_id: str,
    role: str,
    includes: list[str] | None = None,
    inventoried_paths: set[str] | None = None,
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
    return pointer, _load_retained_snapshot(pack, pointer, role)


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
    snapshot = build_repository_snapshot(
        repository,
        pack_root=pack,
        snapshot_id=snapshot_id,
        role=role,
        includes=list(dict.fromkeys(includes or [])),
        inventoried_paths=inventoried_paths,
        timestamp=timestamp,
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
    current = build_repository_snapshot(
        repository,
        pack_root=pack,
        snapshot_id=str(pointer["snapshot_id"]),
        role=role,
        includes=list(retained_includes or []),
        inventoried_paths=inventoried_paths,
        timestamp="1970-01-01T00:00:00+00:00",
    )
    matches = current["content_sha256"] == retained["content_sha256"]
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
