from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
from pathlib import Path, PurePosixPath
from typing import Any


class ClonePackError(Exception):
    """An expected, user-actionable clone-pack failure."""

    def __init__(self, message: str, *, exit_code: int = 1, diagnostic: str = "CONTRACT_INVALID") -> None:
        super().__init__(message)
        self.exit_code = exit_code
        self.diagnostic = diagnostic


def reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ClonePackError(
                f"duplicate JSON key: {key}", exit_code=1, diagnostic="JSON_DUPLICATE_KEY"
            )
        result[key] = value
    return result


def load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=reject_duplicate_keys)
    except FileNotFoundError as exc:
        raise ClonePackError(f"required JSON file is missing: {path}", diagnostic="FILE_MISSING") from exc
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ClonePackError(f"cannot read JSON file {path}: {exc}", diagnostic="JSON_INVALID") from exc
    if not isinstance(value, dict):
        raise ClonePackError(f"JSON root must be an object: {path}", diagnostic="JSON_WRONG_TYPE")
    return value


def canonical_json(value: Any) -> str:
    return json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def case_contract_sha256(case: dict[str, Any]) -> str:
    """Hash every plan-case field except its mutable retained-result pointer."""

    if not isinstance(case, dict):
        raise ClonePackError("plan case must be an object", diagnostic="PLAN_INVALID")
    contract = {key: value for key, value in case.items() if key != "result"}
    return sha256_bytes(canonical_json(contract).encode("utf-8"))


def contract_hashes_for_records(
    records_by_id: dict[str, dict[str, Any]],
    identifiers: list[str] | set[str] | tuple[str, ...],
) -> dict[str, str]:
    """Return sorted current locator hashes for an exact set of index records."""

    hashes: dict[str, str] = {}
    for identifier in sorted(set(identifiers)):
        record = records_by_id.get(identifier)
        if record is None:
            raise ClonePackError(
                f"governing index record is missing: {identifier}",
                diagnostic="REF_UNDEFINED",
            )
        locator = record.get("locator")
        digest = locator.get("sha256") if isinstance(locator, dict) else None
        if not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest):
            raise ClonePackError(
                f"governing index record lacks a current locator hash: {identifier}",
                diagnostic="HASH_ANCHOR_MISSING",
            )
        hashes[identifier] = digest
    return hashes


def atomic_write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temp_path = Path(temporary)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_path, path)
    except BaseException:
        temp_path.unlink(missing_ok=True)
        raise


def atomic_write_json(path: Path, value: Any) -> None:
    atomic_write_text(path, canonical_json(value))


def atomic_write_many(files: dict[Path, str]) -> None:
    """Stage every file before replacing any destination."""
    staged: list[tuple[Path, Path]] = []
    try:
        for path, content in files.items():
            path.parent.mkdir(parents=True, exist_ok=True)
            descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
            temporary_path = Path(temporary)
            with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
                handle.write(content)
                handle.flush()
                os.fsync(handle.fileno())
            staged.append((temporary_path, path))
        for temporary_path, path in staged:
            os.replace(temporary_path, path)
    except BaseException:
        for temporary_path, _ in staged:
            temporary_path.unlink(missing_ok=True)
        raise


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    try:
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
    except (OSError, RuntimeError) as exc:
        raise ClonePackError(f"cannot hash {path}: {exc}", exit_code=4, diagnostic="ARTIFACT_UNREADABLE") from exc
    return digest.hexdigest()


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    if not slug:
        slug = "product-" + sha256_bytes(value.encode("utf-8"))[:12]
    return slug[:80].rstrip("-")


def clean_line(field: str, value: str) -> str:
    value = value.strip()
    if not value or any(character in value for character in "\r\n"):
        raise ClonePackError(f"{field} must be a non-empty single line", exit_code=2, diagnostic="ARG_INVALID")
    if any(ord(character) < 32 or ord(character) == 127 for character in value):
        raise ClonePackError(f"{field} contains a control character", exit_code=2, diagnostic="ARG_INVALID")
    return value


def safe_relative_path(value: str) -> PurePosixPath:
    if (
        not isinstance(value, str)
        or not value
        or "\\" in value
        or any(ord(character) < 32 or ord(character) == 127 for character in value)
    ):
        raise ClonePackError(f"path must be a non-empty POSIX relative path: {value!r}", exit_code=4, diagnostic="PATH_UNSAFE")
    segments = value.split("/")
    path = PurePosixPath(value)
    if path.is_absolute() or any(part in {"", ".", ".."} for part in segments):
        raise ClonePackError(f"unsafe relative path: {value}", exit_code=4, diagnostic="PATH_UNSAFE")
    if re.match(r"^[A-Za-z]:", value):
        raise ClonePackError(f"drive-prefixed path is forbidden: {value}", exit_code=4, diagnostic="PATH_UNSAFE")
    return path


def resolve_inside(root: Path, value: str, *, must_exist: bool = False) -> Path:
    relative = safe_relative_path(value)
    root = root.resolve()
    candidate = root.joinpath(*relative.parts)
    try:
        resolved = candidate.resolve(strict=must_exist)
    except FileNotFoundError as exc:
        raise ClonePackError(
            f"required path does not exist: {value}",
            diagnostic="FILE_MISSING",
        ) from exc
    except (OSError, RuntimeError) as exc:
        raise ClonePackError(
            f"cannot resolve path {value}: {exc}",
            exit_code=4,
            diagnostic="PATH_UNSAFE",
        ) from exc
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise ClonePackError(f"path escapes pack root: {value}", exit_code=4, diagnostic="PATH_ESCAPE") from exc
    return resolved


def require_keys(value: dict[str, Any], required: set[str], *, context: str) -> list[str]:
    return [f"{context}: missing required field {key}" for key in sorted(required - set(value))]


def exact_keys(value: dict[str, Any], allowed: set[str], *, context: str) -> list[str]:
    return [f"{context}: unexpected field {key}" for key in sorted(set(value) - allowed)]


def parse_frontmatter(text: str) -> dict[str, str]:
    lines = text.splitlines()
    if not lines or lines[0] != "---":
        return {}
    try:
        end = lines.index("---", 1)
    except ValueError:
        return {}
    result: dict[str, str] = {}
    for line in lines[1:end]:
        match = re.fullmatch(r"([A-Za-z0-9_-]+):\s*(.*?)\s*", line)
        if not match:
            raise ClonePackError(
                f"frontmatter contains an invalid line: {line!r}",
                diagnostic="FRONTMATTER_INVALID",
            )
        key = match.group(1)
        if key in result:
            raise ClonePackError(
                f"frontmatter contains duplicate key: {key}",
                diagnostic="FRONTMATTER_INVALID",
            )
        raw = match.group(2)
        if raw.startswith('"') and raw.endswith('"'):
            try:
                raw = json.loads(raw)
            except json.JSONDecodeError as exc:
                raise ClonePackError(
                    f"frontmatter has invalid quoted value for {key}",
                    diagnostic="FRONTMATTER_INVALID",
                ) from exc
        result[key] = str(raw)
    return result


def render_template(text: str, replacements: dict[str, str]) -> str:
    for marker, value in replacements.items():
        text = text.replace(marker, value)
    unresolved = sorted(set(re.findall(r"\{\{[A-Z0-9_]+\}\}", text)))
    if unresolved:
        raise ClonePackError(
            "unresolved generator marker(s): " + ", ".join(unresolved),
            diagnostic="TEMPLATE_UNRESOLVED",
        )
    return text
