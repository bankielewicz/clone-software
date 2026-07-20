#!/usr/bin/env python3
from __future__ import annotations

import argparse
import dataclasses
import hashlib
import json
import os
import re
import stat
import struct
import sys
from pathlib import Path
from typing import Any


RESULT_SCHEMA = "clone-software-wsl-workspace-check/v1"
RECEIPT_SCHEMA = "clone-software-wsl-test-install/v2"
RUNTIME_PATH = ".codex"
AUTHORITY_ID = "DEC-004"
BASELINE_RELATIVE = "docs/clone/evidence/raw/workspace-check/pre-write.json"
EXPECTED_PATHS = (
    ".agents",
    ".agents/skills",
    ".agents/skills/clone-software",
    "MINECRAFT_CLONE_PROMPT.md",
)
RECEIPT_KEYS = {
    "schema_version",
    "source_url",
    "requested_ref",
    "resolved_head",
    "checkout_state",
    "checkout_identity_sha256",
    "project_dir",
    "workspace_dir",
    "skill_link",
    "prompt_path",
    "prompt_sha256",
    "verification",
    "codex_executable",
    "installed_workspace_inventory",
}
HEX_64 = re.compile(r"\A[0-9a-f]{64}\Z")
GIT_OBJECT_ID = re.compile(r"\A(?:[0-9a-f]{40}|[0-9a-f]{64})\Z")


class ReceiptSchemaError(Exception):
    pass


class HoldError(Exception):
    def __init__(
        self,
        diagnostic: str,
        message: str,
        product_inventory: list[dict[str, object]] | None = None,
    ) -> None:
        super().__init__(message)
        self.diagnostic = diagnostic
        self.message = message
        self.product_inventory = product_inventory or []


@dataclasses.dataclass(frozen=True)
class DirectorySnapshot:
    device: int
    inode: int
    mode: int
    mtime_ns: int
    ctime_ns: int
    empty: bool


@dataclasses.dataclass(frozen=True)
class FileSnapshot:
    identity: tuple[int, int, int, int, int, int]
    content: bytes


@dataclasses.dataclass(frozen=True)
class BoundFileSnapshot:
    directory_identities: tuple[tuple[int, int, int, int, int, int], ...]
    file: FileSnapshot


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Validate one installed clone-software WSL trial workspace without writing."
    )
    parser.add_argument("--workspace", required=True)
    parser.add_argument("--receipt", required=True)
    parser.add_argument("--allow-runtime-path", required=True)
    parser.add_argument("--authority-id", required=True)
    parser.add_argument(
        "--phase",
        choices=("pre-write", "handoff"),
        default="pre-write",
        help=(
            "pre-write requires the exact installer inventory; handoff preserves "
            "those inputs and reports authorized product additions"
        ),
    )
    parser.add_argument(
        "--baseline-result",
        help="canonical pre-write checker result; required only with --phase handoff",
    )
    return parser


def _canonical_json(value: object) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def _payload(
    *,
    status: str,
    diagnostic: str | None,
    workspace: str,
    receipt: str,
    product_inventory: list[dict[str, object]],
    runtime_exclusions: list[dict[str, object]],
) -> dict[str, object]:
    return {
        "schema_version": RESULT_SCHEMA,
        "status": status,
        "diagnostic": diagnostic,
        "workspace": workspace,
        "receipt": receipt,
        "product_inventory": product_inventory,
        "runtime_exclusions": runtime_exclusions,
    }


def _stable_fields(value: os.stat_result) -> tuple[int, int, int, int, int, int]:
    return (
        value.st_dev,
        value.st_ino,
        value.st_mode,
        value.st_size,
        value.st_mtime_ns,
        value.st_ctime_ns,
    )


def _directory_fields(value: os.stat_result) -> tuple[int, int, int, int, int]:
    return (
        value.st_dev,
        value.st_ino,
        value.st_mode,
        value.st_mtime_ns,
        value.st_ctime_ns,
    )


def _read_stable_regular_bytes(path: Path, *, role: str) -> FileSnapshot:
    try:
        observed = os.lstat(path)
    except FileNotFoundError as error:
        raise HoldError("RUNTIME-001", f"{role} is absent") from error
    except OSError as error:
        raise HoldError("RUNTIME-001", f"{role} cannot be identified") from error
    if not stat.S_ISREG(observed.st_mode):
        raise HoldError("RUNTIME-001", f"{role} is not a real regular file")
    flags = os.O_RDONLY
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    try:
        descriptor = os.open(path, flags)
    except OSError as error:
        raise HoldError("RUNTIME-001", f"{role} cannot be opened safely") from error
    try:
        opened = os.fstat(descriptor)
        if _stable_fields(opened) != _stable_fields(observed):
            raise HoldError("RUNTIME-001", f"{role} identity changed before read")
        chunks: list[bytes] = []
        while True:
            chunk = os.read(descriptor, 1024 * 1024)
            if not chunk:
                break
            chunks.append(chunk)
        if _stable_fields(os.fstat(descriptor)) != _stable_fields(opened):
            raise HoldError("RUNTIME-001", f"{role} changed during read")
        return FileSnapshot(identity=_stable_fields(opened), content=b"".join(chunks))
    finally:
        os.close(descriptor)


def _read_receipt_bytes(path: Path) -> FileSnapshot:
    return _read_stable_regular_bytes(path, role="installation receipt")


def _read_baseline_bytes(workspace: Path) -> BoundFileSnapshot:
    required = all(hasattr(os, name) for name in ("O_DIRECTORY", "O_NOFOLLOW"))
    required = required and os.open in os.supports_dir_fd and os.stat in os.supports_dir_fd
    if not required:
        raise HoldError(
            "RUNTIME-001",
            "pre-write checker result requires descriptor-safe path traversal",
        )
    directory_flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
    file_flags = os.O_RDONLY | os.O_NOFOLLOW
    descriptors: list[int] = []
    directory_identities: list[tuple[int, int, int, int, int, int]] = []
    try:
        root_before = os.lstat(workspace)
        if not stat.S_ISDIR(root_before.st_mode) or stat.S_ISLNK(root_before.st_mode):
            raise HoldError("RUNTIME-001", "workspace is not a real directory")
        root_descriptor = os.open(workspace, directory_flags)
        descriptors.append(root_descriptor)
        root_opened = os.fstat(root_descriptor)
        if _stable_fields(root_opened) != _stable_fields(root_before):
            raise HoldError("RUNTIME-001", "workspace identity changed before baseline read")
        directory_identities.append(_stable_fields(root_opened))

        parts = BASELINE_RELATIVE.split("/")
        for part in parts[:-1]:
            before = os.stat(part, dir_fd=descriptors[-1], follow_symlinks=False)
            if stat.S_ISLNK(before.st_mode) or not stat.S_ISDIR(before.st_mode):
                raise HoldError(
                    "RUNTIME-001",
                    "pre-write checker result has a non-directory or symlink ancestor",
                )
            child = os.open(part, directory_flags, dir_fd=descriptors[-1])
            opened = os.fstat(child)
            if _stable_fields(opened) != _stable_fields(before):
                os.close(child)
                raise HoldError(
                    "RUNTIME-001",
                    "pre-write checker result ancestor changed while opening",
                )
            descriptors.append(child)
            directory_identities.append(_stable_fields(opened))

        filename = parts[-1]
        before = os.stat(filename, dir_fd=descriptors[-1], follow_symlinks=False)
        if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1:
            raise HoldError(
                "RUNTIME-001",
                "pre-write checker result is not a private regular file",
            )
        file_descriptor = os.open(filename, file_flags, dir_fd=descriptors[-1])
        try:
            opened = os.fstat(file_descriptor)
            if _stable_fields(opened) != _stable_fields(before):
                raise HoldError(
                    "RUNTIME-001",
                    "pre-write checker result identity changed before read",
                )
            chunks: list[bytes] = []
            while True:
                chunk = os.read(file_descriptor, 1024 * 1024)
                if not chunk:
                    break
                chunks.append(chunk)
            after = os.fstat(file_descriptor)
            if _stable_fields(after) != _stable_fields(opened):
                raise HoldError("RUNTIME-001", "pre-write checker result changed during read")
        finally:
            os.close(file_descriptor)

        for descriptor, expected in zip(descriptors, directory_identities, strict=True):
            if _stable_fields(os.fstat(descriptor)) != expected:
                raise HoldError(
                    "RUNTIME-001",
                    "pre-write checker result ancestor changed during read",
                )
        if _stable_fields(os.lstat(workspace)) != directory_identities[0]:
            raise HoldError("RUNTIME-001", "workspace identity changed during baseline read")
        return BoundFileSnapshot(
            directory_identities=tuple(directory_identities),
            file=FileSnapshot(identity=_stable_fields(opened), content=b"".join(chunks)),
        )
    except HoldError:
        raise
    except (OSError, UnicodeError) as error:
        raise HoldError(
            "RUNTIME-001", "pre-write checker result cannot be opened safely"
        ) from error
    finally:
        for descriptor in reversed(descriptors):
            os.close(descriptor)


def _checkout_identity(project: Path) -> str:
    """Recompute the installer's checkout digest without following tree links."""

    required = all(
        hasattr(os, name)
        for name in ("O_DIRECTORY", "O_NOFOLLOW", "O_NONBLOCK")
    )
    required = (
        required
        and os.open in os.supports_dir_fd
        and os.stat in os.supports_dir_fd
        and os.readlink in os.supports_dir_fd
        and os.scandir in os.supports_fd
    )
    if not required:
        raise HoldError(
            "RUNTIME-001",
            "repository-scoped skill checkout requires descriptor-safe traversal",
        )

    digest = hashlib.sha256()
    directory_flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
    file_flags = os.O_RDONLY | os.O_NONBLOCK | os.O_NOFOLLOW

    def add_field(kind: bytes, value: bytes) -> None:
        digest.update(kind)
        digest.update(struct.pack(">Q", len(value)))
        digest.update(value)

    def scan(directory_fd: int, relative: str) -> None:
        before = os.fstat(directory_fd)
        if not stat.S_ISDIR(before.st_mode):
            raise HoldError(
                "RUNTIME-001", "repository-scoped skill checkout is not a real directory"
            )
        directory_identity = _directory_fields(before)
        add_field(b"D", os.fsencode(relative))
        add_field(b"M", oct(stat.S_IMODE(before.st_mode)).encode("ascii"))
        with os.scandir(directory_fd) as iterator:
            entries = sorted(iterator, key=lambda entry: os.fsencode(entry.name))

        for entry in entries:
            name = entry.name
            child_relative = name if relative == "." else f"{relative}/{name}"
            encoded_relative = os.fsencode(child_relative)
            observed = os.stat(name, dir_fd=directory_fd, follow_symlinks=False)
            mode = observed.st_mode

            if stat.S_ISLNK(mode):
                if child_relative.split("/", 1)[0] != ".git":
                    raise HoldError(
                        "RUNTIME-001",
                        "repository-scoped skill checkout contains a working-tree symlink",
                    )
                target = os.readlink(name, dir_fd=directory_fd)
                after = os.stat(name, dir_fd=directory_fd, follow_symlinks=False)
                if _stable_fields(after) != _stable_fields(observed):
                    raise HoldError(
                        "RUNTIME-001",
                        "repository-scoped skill checkout symlink changed during scan",
                    )
                add_field(b"L", encoded_relative)
                add_field(b"M", oct(stat.S_IMODE(mode)).encode("ascii"))
                add_field(b"T", os.fsencode(target))
                continue

            if stat.S_ISDIR(mode):
                child_fd = os.open(name, directory_flags, dir_fd=directory_fd)
                try:
                    opened = os.fstat(child_fd)
                    if _stable_fields(opened) != _stable_fields(observed):
                        raise HoldError(
                            "RUNTIME-001",
                            "repository-scoped skill checkout directory changed while opening",
                        )
                    scan(child_fd, child_relative)
                    linked = os.stat(
                        name, dir_fd=directory_fd, follow_symlinks=False
                    )
                    if (
                        _directory_fields(linked) != _directory_fields(opened)
                        or _directory_fields(os.fstat(child_fd))
                        != _directory_fields(opened)
                    ):
                        raise HoldError(
                            "RUNTIME-001",
                            "repository-scoped skill checkout directory changed during scan",
                        )
                finally:
                    os.close(child_fd)
                continue

            if stat.S_ISREG(mode):
                if observed.st_nlink != 1:
                    raise HoldError(
                        "RUNTIME-001",
                        "repository-scoped skill checkout contains a hardlinked file",
                    )
                file_fd = os.open(name, file_flags, dir_fd=directory_fd)
                try:
                    opened = os.fstat(file_fd)
                    if (
                        not stat.S_ISREG(opened.st_mode)
                        or opened.st_nlink != 1
                        or _stable_fields(opened) != _stable_fields(observed)
                    ):
                        raise HoldError(
                            "RUNTIME-001",
                            "repository-scoped skill checkout file changed while opening",
                        )
                    add_field(b"F", encoded_relative)
                    add_field(b"M", oct(stat.S_IMODE(mode)).encode("ascii"))
                    while True:
                        chunk = os.read(file_fd, 1024 * 1024)
                        if not chunk:
                            break
                        add_field(b"B", chunk)
                    after = os.fstat(file_fd)
                    linked = os.stat(
                        name, dir_fd=directory_fd, follow_symlinks=False
                    )
                    if (
                        after.st_nlink != 1
                        or linked.st_nlink != 1
                        or _stable_fields(after) != _stable_fields(opened)
                        or _stable_fields(linked) != _stable_fields(opened)
                    ):
                        raise HoldError(
                            "RUNTIME-001",
                            "repository-scoped skill checkout file changed during scan",
                        )
                finally:
                    os.close(file_fd)
                continue

            raise HoldError(
                "RUNTIME-001",
                "repository-scoped skill checkout contains an unsupported object",
            )

        if _directory_fields(os.fstat(directory_fd)) != directory_identity:
            raise HoldError(
                "RUNTIME-001",
                "repository-scoped skill checkout directory changed during scan",
            )

    parent_fd: int | None = None
    project_fd: int | None = None
    try:
        parent_before = os.lstat(project.parent)
        if not stat.S_ISDIR(parent_before.st_mode) or stat.S_ISLNK(parent_before.st_mode):
            raise HoldError("RUNTIME-001", "installation root is not a real directory")
        parent_fd = os.open(project.parent, directory_flags)
        parent_opened = os.fstat(parent_fd)
        if _stable_fields(parent_opened) != _stable_fields(parent_before):
            raise HoldError("RUNTIME-001", "installation root changed while opening")
        project_before = os.stat(
            project.name, dir_fd=parent_fd, follow_symlinks=False
        )
        if stat.S_ISLNK(project_before.st_mode) or not stat.S_ISDIR(
            project_before.st_mode
        ):
            raise HoldError(
                "RUNTIME-001", "repository-scoped skill checkout is not a real directory"
            )
        project_fd = os.open(project.name, directory_flags, dir_fd=parent_fd)
        project_opened = os.fstat(project_fd)
        if _stable_fields(project_opened) != _stable_fields(project_before):
            raise HoldError(
                "RUNTIME-001", "repository-scoped skill checkout changed while opening"
            )

        scan(project_fd, ".")

        linked = os.stat(project.name, dir_fd=parent_fd, follow_symlinks=False)
        if (
            _directory_fields(linked) != _directory_fields(project_opened)
            or _directory_fields(os.fstat(project_fd))
            != _directory_fields(project_opened)
            or _stable_fields(os.fstat(parent_fd)) != _stable_fields(parent_opened)
            or _stable_fields(os.lstat(project.parent)) != _stable_fields(parent_opened)
        ):
            raise HoldError(
                "RUNTIME-001", "repository-scoped skill checkout identity changed"
            )
    except HoldError:
        raise
    except (OSError, UnicodeError, ValueError) as error:
        raise HoldError(
            "RUNTIME-001",
            "repository-scoped skill checkout cannot be verified safely",
        ) from error
    finally:
        if project_fd is not None:
            os.close(project_fd)
        if parent_fd is not None:
            os.close(parent_fd)
    return digest.hexdigest()


def _is_integer(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _validate_inventory(value: object) -> list[dict[str, object]]:
    if not isinstance(value, list):
        raise ReceiptSchemaError("installed_workspace_inventory must be an array")
    validated: list[dict[str, object]] = []
    for position, item in enumerate(value):
        if not isinstance(item, dict):
            raise ReceiptSchemaError(f"inventory record {position} must be an object")
        item_type = item.get("type")
        expected_keys: set[str]
        if item_type == "directory":
            expected_keys = {"path", "type", "mode"}
        elif item_type == "file":
            expected_keys = {"path", "type", "mode", "size", "sha256"}
        elif item_type == "symlink":
            expected_keys = {"path", "type", "mode", "target", "sha256"}
        else:
            raise ReceiptSchemaError(f"inventory record {position} has an invalid type")
        if set(item) != expected_keys:
            raise ReceiptSchemaError(f"inventory record {position} has an invalid field set")
        path = item.get("path")
        mode = item.get("mode")
        if not isinstance(path, str) or not path or path.startswith("/"):
            raise ReceiptSchemaError(f"inventory record {position} has an invalid path")
        parts = path.split("/")
        if any(part in {"", ".", ".."} for part in parts):
            raise ReceiptSchemaError(f"inventory record {position} has an unsafe path")
        if not _is_integer(mode) or not 0 <= mode <= 0o7777:
            raise ReceiptSchemaError(f"inventory record {position} has an invalid mode")
        if item_type == "file":
            size = item.get("size")
            digest = item.get("sha256")
            if not _is_integer(size) or size < 0:
                raise ReceiptSchemaError(f"inventory record {position} has an invalid size")
            if not isinstance(digest, str) or HEX_64.fullmatch(digest) is None:
                raise ReceiptSchemaError(f"inventory record {position} has an invalid sha256")
        if item_type == "symlink":
            target = item.get("target")
            digest = item.get("sha256")
            if not isinstance(target, str) or not target:
                raise ReceiptSchemaError(f"inventory record {position} has an invalid target")
            if not isinstance(digest, str) or HEX_64.fullmatch(digest) is None:
                raise ReceiptSchemaError(f"inventory record {position} has an invalid sha256")
            try:
                target_digest = hashlib.sha256(target.encode("utf-8")).hexdigest()
            except UnicodeError as error:
                raise ReceiptSchemaError(
                    f"inventory record {position} target is not UTF-8"
                ) from error
            if digest != target_digest:
                raise HoldError("RUNTIME-001", "receipt symlink target digest does not match")
        validated.append(dict(item))
    paths = [str(item["path"]) for item in validated]
    if paths != sorted(paths, key=lambda path: path.encode("utf-8")):
        raise ReceiptSchemaError("installed_workspace_inventory is not path-sorted")
    if len(paths) != len(set(paths)):
        raise ReceiptSchemaError("installed_workspace_inventory contains duplicate paths")
    if tuple(paths) != EXPECTED_PATHS:
        raise HoldError(
            "RUNTIME-001",
            "receipt does not contain the exact installed workspace inventory",
            validated,
        )
    expected_types = ("directory", "directory", "symlink", "file")
    if tuple(str(item["type"]) for item in validated) != expected_types:
        raise HoldError(
            "RUNTIME-001",
            "receipt workspace inventory types do not match the installed contract",
            validated,
        )
    return validated


def _load_receipt(
    path: Path, workspace: Path
) -> tuple[dict[str, Any], list[dict[str, object]], FileSnapshot]:
    receipt_snapshot = _read_receipt_bytes(path)
    raw = receipt_snapshot.content
    try:
        text = raw.decode("utf-8")
        value = json.loads(text)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ReceiptSchemaError("receipt is not canonical UTF-8 JSON") from error
    if not isinstance(value, dict):
        raise ReceiptSchemaError("receipt root must be an object")
    raw_inventory = value.get("installed_workspace_inventory")
    provisional_inventory = (
        [dict(item) for item in raw_inventory if isinstance(item, dict)]
        if isinstance(raw_inventory, list)
        else []
    )
    schema_version = value.get("schema_version")
    if schema_version == "clone-software-wsl-test-install/v1":
        raise HoldError(
            "RUNTIME-001",
            "v1 receipt cannot prove pre-session workspace absence",
        )
    if schema_version != RECEIPT_SCHEMA:
        raise ReceiptSchemaError("receipt schema_version is unsupported")
    canonical = (_canonical_json(value) + "\n").encode("utf-8")
    if raw != canonical:
        raise HoldError(
            "RUNTIME-001",
            "receipt bytes are not canonical",
            provisional_inventory,
        )
    if set(value) != RECEIPT_KEYS:
        raise ReceiptSchemaError("receipt has an invalid field set")
    string_fields = RECEIPT_KEYS - {"installed_workspace_inventory"}
    for field in string_fields:
        if not isinstance(value[field], str) or not value[field]:
            raise ReceiptSchemaError(f"receipt field {field} must be a nonempty string")
    if GIT_OBJECT_ID.fullmatch(value["resolved_head"]) is None:
        raise ReceiptSchemaError("receipt resolved_head is invalid")
    for field in ("checkout_identity_sha256", "prompt_sha256"):
        if HEX_64.fullmatch(value[field]) is None:
            raise ReceiptSchemaError(f"receipt field {field} is invalid")
    if value["verification"] not in {"smoke", "full"}:
        raise ReceiptSchemaError("receipt verification is invalid")
    inventory = _validate_inventory(value["installed_workspace_inventory"])

    expected_workspace = str(workspace)
    expected_receipt = workspace.parent / "installation-receipt.json"
    expected_project = workspace.parent / "clone-software"
    expected_skill_link = workspace / ".agents" / "skills" / "clone-software"
    expected_prompt = workspace / "MINECRAFT_CLONE_PROMPT.md"
    bindings = {
        "workspace_dir": expected_workspace,
        "project_dir": str(expected_project),
        "skill_link": str(expected_skill_link),
        "prompt_path": str(expected_prompt),
    }
    if path != expected_receipt:
        raise HoldError("RUNTIME-001", "receipt path is not bound to the workspace", inventory)
    for field, expected in bindings.items():
        if value[field] != expected:
            raise HoldError(
                "RUNTIME-001",
                f"receipt field {field} is not bound to the workspace",
                inventory,
            )
    prompt_records = [item for item in inventory if item["path"] == "MINECRAFT_CLONE_PROMPT.md"]
    if len(prompt_records) != 1 or prompt_records[0].get("sha256") != value["prompt_sha256"]:
        raise HoldError("RUNTIME-001", "receipt prompt digests disagree", inventory)
    return value, inventory, receipt_snapshot


def _load_baseline_result(
    workspace: Path,
    *,
    workspace_display: str,
    receipt_display: str,
    receipt_inventory: list[dict[str, object]],
) -> tuple[list[dict[str, object]], BoundFileSnapshot]:
    snapshot = _read_baseline_bytes(workspace)
    try:
        value = json.loads(snapshot.file.content.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise HoldError("RUNTIME-001", "pre-write checker result is not canonical UTF-8 JSON") from error
    if not isinstance(value, dict) or set(value) != {
        "schema_version",
        "status",
        "diagnostic",
        "workspace",
        "receipt",
        "product_inventory",
        "runtime_exclusions",
    }:
        raise HoldError("RUNTIME-001", "pre-write checker result has an invalid field set")
    if snapshot.file.content != (_canonical_json(value) + "\n").encode("utf-8"):
        raise HoldError("RUNTIME-001", "pre-write checker result bytes are not canonical")
    if (
        value.get("schema_version") != RESULT_SCHEMA
        or value.get("status") != "PASS"
        or value.get("diagnostic") is not None
        or value.get("workspace") != workspace_display
        or value.get("receipt") != receipt_display
        or value.get("product_inventory") != receipt_inventory
    ):
        raise HoldError("RUNTIME-001", "pre-write checker result is not bound to this installation")
    exclusions = value.get("runtime_exclusions")
    if not isinstance(exclusions, list) or len(exclusions) > 1:
        raise HoldError("RUNTIME-001", "pre-write checker result has invalid runtime exclusions")
    if exclusions:
        exclusion = exclusions[0]
        expected_keys = {
            "path",
            "disposition",
            "authority_ids",
            "evidence_ids",
            "pre_session_presence",
            "owner_claim",
            "allowed_operations",
            "expected_identity",
        }
        identity = exclusion.get("expected_identity") if isinstance(exclusion, dict) else None
        if (
            not isinstance(exclusion, dict)
            or set(exclusion) != expected_keys
            or exclusion.get("path") != RUNTIME_PATH
            or exclusion.get("disposition") != "TOOL_RUNTIME_EXCLUDED"
            or exclusion.get("authority_ids") != [AUTHORITY_ID]
            or exclusion.get("evidence_ids") != ["E-002"]
            or exclusion.get("pre_session_presence") is not False
            or exclusion.get("owner_claim") != "USER_PINNED"
            or exclusion.get("allowed_operations") != []
            or not isinstance(identity, dict)
            or set(identity) != {"type", "device", "inode", "mode", "empty"}
            or identity.get("type") != "directory"
            or identity.get("empty") is not True
            or any(
                not _is_integer(identity.get(field))
                for field in ("device", "inode", "mode")
            )
            or int(identity["mode"]) & 0o222
        ):
            raise HoldError("RUNTIME-001", "pre-write checker result has invalid runtime exclusions")
    return [dict(item) for item in exclusions], snapshot


def _scan_inventory(workspace: Path) -> tuple[tuple[int, int, int, int, int], list[dict[str, object]]]:
    directory_flags = os.O_RDONLY | os.O_DIRECTORY
    file_flags = os.O_RDONLY
    if hasattr(os, "O_NOFOLLOW"):
        directory_flags |= os.O_NOFOLLOW
        file_flags |= os.O_NOFOLLOW

    try:
        lexical = os.lstat(workspace)
    except OSError as error:
        raise HoldError("RUNTIME-001", "workspace cannot be identified") from error
    if not stat.S_ISDIR(lexical.st_mode):
        raise HoldError("RUNTIME-001", "workspace is not a real directory")

    def scan(directory_fd: int, prefix: str, records: list[dict[str, object]]) -> None:
        before = os.fstat(directory_fd)
        with os.scandir(directory_fd) as iterator:
            entries = sorted(iterator, key=lambda entry: os.fsencode(entry.name))
        for entry in entries:
            try:
                entry.name.encode("utf-8", errors="strict")
            except UnicodeEncodeError as error:
                raise HoldError(
                    "RUNTIME-001", "workspace entry name is not canonical UTF-8"
                ) from error
            relative = f"{prefix}/{entry.name}" if prefix else entry.name
            if not prefix and entry.name in {".git", RUNTIME_PATH}:
                continue
            observed = os.stat(entry.name, dir_fd=directory_fd, follow_symlinks=False)
            mode = observed.st_mode
            if stat.S_ISDIR(mode):
                records.append(
                    {
                        "mode": stat.S_IMODE(mode),
                        "path": relative,
                        "type": "directory",
                    }
                )
                child_fd = os.open(entry.name, directory_flags, dir_fd=directory_fd)
                try:
                    opened = os.fstat(child_fd)
                    if _stable_fields(opened) != _stable_fields(observed):
                        raise HoldError("RUNTIME-001", "product directory identity changed")
                    scan(child_fd, relative, records)
                    if _stable_fields(os.fstat(child_fd)) != _stable_fields(opened):
                        raise HoldError("RUNTIME-001", "product directory changed during scan")
                finally:
                    os.close(child_fd)
            elif stat.S_ISREG(mode):
                descriptor = os.open(entry.name, file_flags, dir_fd=directory_fd)
                try:
                    opened = os.fstat(descriptor)
                    if _stable_fields(opened) != _stable_fields(observed):
                        raise HoldError("RUNTIME-001", "product file identity changed")
                    digest = hashlib.sha256()
                    size = 0
                    while True:
                        chunk = os.read(descriptor, 1024 * 1024)
                        if not chunk:
                            break
                        digest.update(chunk)
                        size += len(chunk)
                    if _stable_fields(os.fstat(descriptor)) != _stable_fields(opened):
                        raise HoldError("RUNTIME-001", "product file changed during scan")
                finally:
                    os.close(descriptor)
                if size != observed.st_size:
                    raise HoldError("RUNTIME-001", "product file size changed during scan")
                records.append(
                    {
                        "mode": stat.S_IMODE(mode),
                        "path": relative,
                        "sha256": digest.hexdigest(),
                        "size": size,
                        "type": "file",
                    }
                )
            elif stat.S_ISLNK(mode):
                target = os.readlink(entry.name, dir_fd=directory_fd)
                after = os.stat(entry.name, dir_fd=directory_fd, follow_symlinks=False)
                if _stable_fields(after) != _stable_fields(observed):
                    raise HoldError("RUNTIME-001", "product symlink changed during scan")
                records.append(
                    {
                        "mode": stat.S_IMODE(mode),
                        "path": relative,
                        "sha256": hashlib.sha256(target.encode("utf-8")).hexdigest(),
                        "target": target,
                        "type": "symlink",
                    }
                )
            else:
                raise HoldError("RUNTIME-001", "workspace contains an unsupported object")
        if _directory_fields(os.fstat(directory_fd)) != _directory_fields(before):
            raise HoldError("RUNTIME-001", "product directory changed during scan")

    try:
        root_fd = os.open(workspace, directory_flags)
    except OSError as error:
        raise HoldError("RUNTIME-001", "workspace cannot be opened safely") from error
    try:
        opened = os.fstat(root_fd)
        if _stable_fields(opened) != _stable_fields(lexical):
            raise HoldError("RUNTIME-001", "workspace identity changed before scan")
        records: list[dict[str, object]] = []
        scan(root_fd, "", records)
        after = os.fstat(root_fd)
        if _directory_fields(after) != _directory_fields(opened):
            raise HoldError("RUNTIME-001", "workspace changed during scan")
    except (OSError, UnicodeError) as error:
        raise HoldError("RUNTIME-001", "workspace inventory cannot be read safely") from error
    finally:
        os.close(root_fd)
    records.sort(key=lambda record: str(record["path"]).encode("utf-8"))
    return _directory_fields(opened), records


def _root_names(workspace: Path) -> tuple[tuple[int, int, int, int, int], tuple[str, ...]]:
    try:
        observed = os.lstat(workspace)
    except OSError as error:
        raise HoldError("RUNTIME-001", "workspace cannot be identified") from error
    if not stat.S_ISDIR(observed.st_mode):
        raise HoldError("RUNTIME-001", "workspace is not a real directory")
    flags = os.O_RDONLY | os.O_DIRECTORY
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    try:
        descriptor = os.open(workspace, flags)
    except OSError as error:
        raise HoldError("RUNTIME-001", "workspace cannot be opened safely") from error
    try:
        opened = os.fstat(descriptor)
        if _stable_fields(opened) != _stable_fields(observed):
            raise HoldError("RUNTIME-001", "workspace identity changed")
        with os.scandir(descriptor) as iterator:
            names = tuple(sorted((entry.name for entry in iterator), key=os.fsencode))
        if _directory_fields(os.fstat(descriptor)) != _directory_fields(opened):
            raise HoldError("RUNTIME-001", "workspace changed during root inventory")
        return _directory_fields(opened), names
    finally:
        os.close(descriptor)


def _validate_root_names(workspace: Path, names: tuple[str, ...], *, phase: str) -> None:
    expected_root = {".agents", "MINECRAFT_CLONE_PROMPT.md"}
    always_allowed = expected_root | {".git", RUNTIME_PATH}
    if phase == "pre-write":
        unrelated = sorted(set(names) - always_allowed)
    else:
        allowed_dot_entries = always_allowed | {".gitignore"}
        unrelated = sorted(
            name for name in names if name.startswith(".") and name not in allowed_dot_entries
        )
    if unrelated:
        raise HoldError("REPO-001", "workspace contains an unrelated root entry")
    missing = sorted(expected_root - set(names))
    if missing:
        raise HoldError("RUNTIME-001", "installed workspace root entry is missing")
    if ".git" in names:
        git_path = workspace / ".git"
        try:
            observed = os.lstat(git_path)
        except OSError as error:
            raise HoldError("RUNTIME-001", ".git cannot be identified") from error
        if not stat.S_ISDIR(observed.st_mode):
            raise HoldError("RUNTIME-001", ".git is not a real directory")


def _validate_handoff_inventory(
    receipt_inventory: list[dict[str, object]],
    live_inventory: list[dict[str, object]],
) -> None:
    live_by_path = {str(record["path"]): record for record in live_inventory}
    for installed in receipt_inventory:
        path = str(installed["path"])
        if live_by_path.get(path) != installed:
            raise HoldError(
                "RUNTIME-001",
                f"receipt-bound installer input changed at handoff: {path}",
                live_inventory,
            )
    receipt_paths = {str(record["path"]) for record in receipt_inventory}
    unauthorized_skill_inputs = sorted(
        path
        for path in live_by_path
        if path not in receipt_paths and (path == ".agents" or path.startswith(".agents/"))
    )
    if unauthorized_skill_inputs:
        raise HoldError(
            "RUNTIME-001",
            "repository-scoped skill input changed at handoff",
            live_inventory,
        )


def _observe_runtime_directory(path: Path) -> DirectorySnapshot:
    try:
        observed = os.lstat(path)
    except OSError as error:
        raise HoldError("RUNTIME-001", "runtime path cannot be identified") from error
    if not stat.S_ISDIR(observed.st_mode):
        raise HoldError("RUNTIME-001", "runtime path is not a real directory")
    mode = stat.S_IMODE(observed.st_mode)
    if mode & 0o222:
        raise HoldError("RUNTIME-001", "runtime directory has write permission bits")
    flags = os.O_RDONLY | os.O_DIRECTORY
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    try:
        descriptor = os.open(path, flags)
    except OSError as error:
        raise HoldError("RUNTIME-001", "runtime directory cannot be opened safely") from error
    try:
        opened = os.fstat(descriptor)
        if _stable_fields(opened) != _stable_fields(observed):
            raise HoldError("RUNTIME-001", "runtime directory identity changed")
        with os.scandir(descriptor) as entries:
            empty = next(entries, None) is None
        if not empty:
            raise HoldError("RUNTIME-001", "runtime directory is not empty")
        after = os.fstat(descriptor)
        if _directory_fields(after) != _directory_fields(opened):
            raise HoldError("RUNTIME-001", "runtime directory changed during inspection")
        return DirectorySnapshot(
            device=opened.st_dev,
            inode=opened.st_ino,
            mode=stat.S_IMODE(opened.st_mode),
            mtime_ns=opened.st_mtime_ns,
            ctime_ns=opened.st_ctime_ns,
            empty=True,
        )
    finally:
        os.close(descriptor)


def _runtime_record(snapshot: DirectorySnapshot) -> dict[str, object]:
    return {
        "path": RUNTIME_PATH,
        "disposition": "TOOL_RUNTIME_EXCLUDED",
        "authority_ids": [AUTHORITY_ID],
        "evidence_ids": ["E-002"],
        "pre_session_presence": False,
        "owner_claim": "USER_PINNED",
        "allowed_operations": [],
        "expected_identity": {
            "type": "directory",
            "device": snapshot.device,
            "inode": snapshot.inode,
            "mode": snapshot.mode,
            "empty": True,
        },
    }


def _run_check(
    workspace: Path,
    receipt_path: Path,
    workspace_display: str,
    receipt_display: str,
    *,
    phase: str,
    baseline_path: Path | None,
) -> dict[str, object]:
    receipt, receipt_inventory, receipt_snapshot = _load_receipt(receipt_path, workspace)
    checkout_identity: str | None = None
    if phase == "handoff":
        checkout_identity = _checkout_identity(Path(str(receipt["project_dir"])))
        if checkout_identity != receipt["checkout_identity_sha256"]:
            raise HoldError(
                "RUNTIME-001",
                "repository-scoped skill checkout differs from the installation receipt",
                receipt_inventory,
            )
    baseline_exclusions: list[dict[str, object]] | None = None
    baseline_snapshot: BoundFileSnapshot | None = None
    if baseline_path is not None:
        baseline_exclusions, baseline_snapshot = _load_baseline_result(
            workspace,
            workspace_display=workspace_display,
            receipt_display=receipt_display,
            receipt_inventory=receipt_inventory,
        )
    first_root_identity, first_names = _root_names(workspace)
    _validate_root_names(workspace, first_names, phase=phase)
    first_product_identity, live_inventory = _scan_inventory(workspace)
    if phase == "pre-write" and live_inventory != receipt_inventory:
        raise HoldError(
            "RUNTIME-001",
            "live product inventory does not match the installation receipt",
            receipt_inventory,
        )
    if phase == "handoff":
        _validate_handoff_inventory(receipt_inventory, live_inventory)

    runtime_snapshot: DirectorySnapshot | None = None
    if RUNTIME_PATH in first_names:
        runtime_snapshot = _observe_runtime_directory(workspace / RUNTIME_PATH)

    second_root_identity, second_names = _root_names(workspace)
    _validate_root_names(workspace, second_names, phase=phase)
    second_product_identity, second_inventory = _scan_inventory(workspace)
    if (
        second_names != first_names
        or second_root_identity != first_root_identity
        or second_product_identity != first_product_identity
        or second_inventory != live_inventory
    ):
        raise HoldError(
            "RUNTIME-001",
            "workspace identity or inventory changed before result",
            receipt_inventory,
        )
    if runtime_snapshot is not None:
        rechecked_runtime = _observe_runtime_directory(workspace / RUNTIME_PATH)
        if rechecked_runtime != runtime_snapshot:
            raise HoldError(
                "RUNTIME-001",
                "runtime directory identity changed before result",
                receipt_inventory,
            )

    if _read_receipt_bytes(receipt_path) != receipt_snapshot:
        raise HoldError(
            "RUNTIME-001",
            "installation receipt identity or bytes changed before result",
            receipt_inventory,
        )
    if phase == "handoff":
        rechecked_checkout_identity = _checkout_identity(
            Path(str(receipt["project_dir"]))
        )
        if (
            rechecked_checkout_identity != checkout_identity
            or rechecked_checkout_identity != receipt["checkout_identity_sha256"]
        ):
            raise HoldError(
                "RUNTIME-001",
                "repository-scoped skill checkout changed before result",
                live_inventory,
            )

    exclusions = [_runtime_record(runtime_snapshot)] if runtime_snapshot is not None else []
    if baseline_exclusions is not None and exclusions != baseline_exclusions:
        raise HoldError(
            "RUNTIME-001",
            "runtime exclusion differs from the retained pre-write checker result",
            live_inventory,
        )
    if baseline_path is not None and _read_baseline_bytes(workspace) != baseline_snapshot:
        raise HoldError(
            "RUNTIME-001",
            "pre-write checker result identity or bytes changed before result",
            live_inventory,
        )
    return _payload(
        status="PASS",
        diagnostic=None,
        workspace=workspace_display,
        receipt=receipt_display,
        product_inventory=live_inventory,
        runtime_exclusions=exclusions,
    )


def main(argv: list[str] | None = None) -> int:
    parser = _parser()
    arguments = parser.parse_args(argv)
    if arguments.allow_runtime_path != RUNTIME_PATH:
        parser.error("--allow-runtime-path accepts only literal .codex")
    if arguments.authority_id != AUTHORITY_ID:
        parser.error("--authority-id accepts only literal DEC-004")
    if arguments.phase == "handoff" and arguments.baseline_result is None:
        parser.error("--phase handoff requires --baseline-result")
    if arguments.phase == "pre-write" and arguments.baseline_result is not None:
        parser.error("--baseline-result is accepted only with --phase handoff")

    workspace = Path(os.path.abspath(arguments.workspace))
    receipt_path = Path(os.path.abspath(arguments.receipt))
    baseline_path = (
        Path(os.path.abspath(arguments.baseline_result))
        if arguments.baseline_result is not None
        else None
    )
    if baseline_path is not None and baseline_path != workspace / BASELINE_RELATIVE:
        parser.error(f"--baseline-result must equal {BASELINE_RELATIVE} beneath --workspace")
    workspace_display = str(workspace)
    receipt_display = str(receipt_path)
    try:
        result = _run_check(
            workspace,
            receipt_path,
            workspace_display,
            receipt_display,
            phase=arguments.phase,
            baseline_path=baseline_path,
        )
    except ReceiptSchemaError as error:
        print(f"RECEIPT_SCHEMA_INVALID: {error}", file=sys.stderr)
        return 2
    except HoldError as error:
        result = _payload(
            status="HOLD",
            diagnostic=error.diagnostic,
            workspace=workspace_display,
            receipt=receipt_display,
            product_inventory=error.product_inventory,
            runtime_exclusions=[],
        )
        print(_canonical_json(result))
        print(f"{error.diagnostic}: {error.message}", file=sys.stderr)
        return 4
    except Exception as error:
        result = _payload(
            status="ERROR",
            diagnostic="INTERNAL_ERROR",
            workspace=workspace_display,
            receipt=receipt_display,
            product_inventory=[],
            runtime_exclusions=[],
        )
        print(_canonical_json(result))
        print(f"INTERNAL_ERROR: unexpected {type(error).__name__}", file=sys.stderr)
        return 70
    print(_canonical_json(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
