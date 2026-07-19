from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import stat
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
    """Hash every plan-case field except mutable retained-result pointers."""

    if not isinstance(case, dict):
        raise ClonePackError("plan case must be an object", diagnostic="PLAN_INVALID")
    contract = {
        key: value
        for key, value in case.items()
        if key not in {"result", "baseline_result", "regression_result"}
    }
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


TRANSACTION_DIRECTORY = ".clonepack-transactions"
TRANSACTION_SCHEMA_VERSION = "clone-atomic-transaction/v1"


def _fsync_directory(path: Path) -> None:
    """Persist directory-entry changes when the host supports directory fsync."""

    flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0)
    try:
        descriptor = os.open(path, flags)
    except OSError:
        return
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _transaction_error(message: str) -> ClonePackError:
    return ClonePackError(message, exit_code=4, diagnostic="TRANSACTION_DIVERGED")


def _validate_transaction_root(transaction_root: Path) -> Path:
    supplied = transaction_root.expanduser()
    try:
        supplied_metadata = supplied.lstat()
        root = supplied.resolve(strict=True)
    except (OSError, RuntimeError) as exc:
        raise _transaction_error(f"transaction root is unavailable: {transaction_root}: {exc}") from exc
    if os.path.islink(supplied) or not stat.S_ISDIR(supplied_metadata.st_mode) or not root.is_dir():
        raise _transaction_error(f"transaction root is not a real directory: {transaction_root}")
    return root


def _infer_transaction_root(paths: list[Path]) -> Path:
    parents = [str(path.expanduser().absolute().parent) for path in paths]
    try:
        common_parent = Path(os.path.commonpath(parents))
    except (OSError, ValueError) as exc:
        raise _transaction_error(f"cannot infer one transaction root: {exc}") from exc
    return _validate_transaction_root(common_parent)


def _transaction_destination(root: Path, relative_value: str) -> Path:
    try:
        relative = safe_relative_path(relative_value)
    except ClonePackError as exc:
        raise _transaction_error(f"transaction destination is unsafe: {relative_value}") from exc
    candidate = root.joinpath(*relative.parts)
    current = root
    for part in relative.parts:
        current = current / part
        try:
            metadata = current.lstat()
        except FileNotFoundError:
            if current != candidate:
                raise _transaction_error(f"transaction destination parent is missing: {relative_value}")
            continue
        except OSError as exc:
            raise _transaction_error(f"cannot inspect transaction destination {relative_value}: {exc}") from exc
        if os.path.islink(current):
            raise _transaction_error(f"transaction destination traverses a symlink: {relative_value}")
        if current != candidate and not current.is_dir():
            raise _transaction_error(f"transaction destination parent is not a directory: {relative_value}")
        if current == candidate and not stat.S_ISREG(metadata.st_mode):
            raise _transaction_error(f"transaction destination is not a regular file: {relative_value}")
    return candidate


def _ensure_transaction_parent(root: Path, relative_value: str) -> None:
    """Create missing destination parents without traversing an existing symlink."""

    try:
        relative = safe_relative_path(relative_value)
    except ClonePackError as exc:
        raise _transaction_error(f"transaction destination is unsafe: {relative_value}") from exc
    current = root
    for part in relative.parts[:-1]:
        candidate = current / part
        try:
            metadata = candidate.lstat()
        except FileNotFoundError:
            try:
                candidate.mkdir(mode=0o700)
            except FileExistsError:
                pass
            except OSError as exc:
                raise _transaction_error(
                    f"cannot create transaction destination parent: {relative_value}: {exc}"
                ) from exc
            try:
                metadata = candidate.lstat()
            except OSError as exc:
                raise _transaction_error(
                    f"transaction destination parent is unavailable: {relative_value}: {exc}"
                ) from exc
            _fsync_directory(current)
        except OSError as exc:
            raise _transaction_error(
                f"cannot inspect transaction destination parent: {relative_value}: {exc}"
            ) from exc
        if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISDIR(metadata.st_mode):
            raise _transaction_error(
                f"transaction destination parent is not a real directory: {relative_value}"
            )
        current = candidate


def _destination_state(
    destination: Path,
    *,
    before_exists: bool,
    before_sha256: str | None,
    after_sha256: str,
) -> str:
    try:
        metadata = destination.lstat()
    except FileNotFoundError:
        if before_exists:
            raise _transaction_error(f"transaction destination disappeared: {destination}")
        return "before"
    except OSError as exc:
        raise _transaction_error(f"cannot inspect transaction destination {destination}: {exc}") from exc
    if destination.is_symlink() or not stat.S_ISREG(metadata.st_mode):
        raise _transaction_error(f"transaction destination is not a regular file: {destination}")
    digest = sha256_file(destination)
    if digest == after_sha256:
        return "after"
    if before_exists and digest == before_sha256:
        return "before"
    raise _transaction_error(f"transaction destination differs from both recorded images: {destination}")


def _replace_from_stage(stage: Path, destination: Path) -> None:
    descriptor, temporary = tempfile.mkstemp(prefix=f".{destination.name}.transaction-", dir=destination.parent)
    temporary_path = Path(temporary)
    try:
        with stage.open("rb") as source, os.fdopen(descriptor, "wb") as target:
            shutil.copyfileobj(source, target)
            target.flush()
            os.fsync(target.fileno())
        os.replace(temporary_path, destination)
        _fsync_directory(destination.parent)
    except BaseException:
        temporary_path.unlink(missing_ok=True)
        raise


def _remove_completed_transaction(transaction: Path, journal_root: Path) -> None:
    shutil.rmtree(transaction)
    _fsync_directory(journal_root)
    try:
        journal_root.rmdir()
    except OSError:
        return
    _fsync_directory(journal_root.parent)


def _read_transaction_journal(transaction: Path, root: Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    if transaction.is_symlink() or not transaction.is_dir():
        raise _transaction_error(f"transaction entry is not a real directory: {transaction}")
    try:
        journal = load_json(transaction / "journal.json")
    except ClonePackError as exc:
        raise _transaction_error(f"transaction journal is unreadable: {transaction / 'journal.json'}") from exc
    if set(journal) != {"schema_version", "operation", "state", "entries"}:
        raise _transaction_error(f"transaction journal has unexpected fields: {transaction / 'journal.json'}")
    if journal.get("schema_version") != TRANSACTION_SCHEMA_VERSION or journal.get("state") != "PREPARED":
        raise _transaction_error(f"transaction journal has an unsupported identity or state: {transaction / 'journal.json'}")
    if not isinstance(journal.get("operation"), str) or not journal["operation"]:
        raise _transaction_error(f"transaction journal operation is invalid: {transaction / 'journal.json'}")
    entries = journal.get("entries")
    if not isinstance(entries, list) or not entries:
        raise _transaction_error(f"transaction journal entries are invalid: {transaction / 'journal.json'}")

    retained: list[dict[str, Any]] = []
    seen_destinations: set[str] = set()
    seen_stages: set[str] = set()
    for position, raw_entry in enumerate(entries, 1):
        if not isinstance(raw_entry, dict) or set(raw_entry) != {
            "destination",
            "before_exists",
            "before_sha256",
            "after_sha256",
            "staged_path",
        }:
            raise _transaction_error(f"transaction journal entry {position} is invalid")
        destination_value = raw_entry.get("destination")
        staged_value = raw_entry.get("staged_path")
        before_exists = raw_entry.get("before_exists")
        before_digest = raw_entry.get("before_sha256")
        after_digest = raw_entry.get("after_sha256")
        if (
            not isinstance(destination_value, str)
            or destination_value in seen_destinations
            or not isinstance(staged_value, str)
            or staged_value in seen_stages
            or not isinstance(before_exists, bool)
            or (before_exists and not isinstance(before_digest, str))
            or (not before_exists and before_digest is not None)
            or not isinstance(after_digest, str)
            or (isinstance(before_digest, str) and not re.fullmatch(r"[0-9a-f]{64}", before_digest))
            or not re.fullmatch(r"[0-9a-f]{64}", after_digest)
        ):
            raise _transaction_error(f"transaction journal entry {position} has invalid values")
        destination = _transaction_destination(root, destination_value)
        try:
            staged_relative = safe_relative_path(staged_value)
        except ClonePackError as exc:
            raise _transaction_error(f"transaction staged path is unsafe: {staged_value}") from exc
        stage = transaction.joinpath(*staged_relative.parts)
        try:
            stage_metadata = stage.lstat()
        except OSError as exc:
            raise _transaction_error(f"transaction staged image is unavailable: {stage}: {exc}") from exc
        if stage.is_symlink() or not stat.S_ISREG(stage_metadata.st_mode) or sha256_file(stage) != after_digest:
            raise _transaction_error(f"transaction staged image differs from its digest: {stage}")
        seen_destinations.add(destination_value)
        seen_stages.add(staged_value)
        retained.append(
            {
                **raw_entry,
                "destination_path": destination,
                "stage_path": stage,
                "current_state": _destination_state(
                    destination,
                    before_exists=before_exists,
                    before_sha256=before_digest,
                    after_sha256=after_digest,
                ),
            }
        )
    return journal, retained


def recover_atomic_transactions(transaction_root: Path) -> list[str]:
    """Roll every prepared transaction forward, or change no destination on divergence."""

    root = _validate_transaction_root(Path(transaction_root))
    journal_root = root / TRANSACTION_DIRECTORY
    if journal_root.is_symlink():
        raise _transaction_error(f"transaction journal root is unsafe: {journal_root}")
    if not journal_root.exists():
        return []
    if not journal_root.is_dir():
        raise _transaction_error(f"transaction journal root is unsafe: {journal_root}")
    transactions = sorted(journal_root.iterdir(), key=lambda item: item.name)
    if not transactions:
        try:
            journal_root.rmdir()
        except OSError as exc:
            raise _transaction_error(f"empty transaction journal root cannot be removed: {journal_root}: {exc}") from exc
        _fsync_directory(root)
        return []

    # Classify and validate every retained transaction before changing any destination.
    prepared: list[tuple[Path, list[dict[str, Any]]]] = []
    for transaction in transactions:
        _, entries = _read_transaction_journal(transaction, root)
        prepared.append((transaction, entries))

    recovered: list[str] = []
    for transaction, entries in prepared:
        for entry in entries:
            if entry["current_state"] == "before":
                _replace_from_stage(entry["stage_path"], entry["destination_path"])
        for entry in entries:
            if _destination_state(
                entry["destination_path"],
                before_exists=entry["before_exists"],
                before_sha256=entry["before_sha256"],
                after_sha256=entry["after_sha256"],
            ) != "after":
                raise _transaction_error(f"transaction did not reach its after image: {entry['destination']}")
        recovered.append(transaction.name)
        _remove_completed_transaction(transaction, journal_root)
    return recovered


def atomic_write_many(
    files: dict[Path, str | bytes],
    *,
    transaction_root: Path | None = None,
    operation: str = "atomic-write-many",
) -> None:
    """Durably prepare all after-images, then replace destinations as a recoverable transaction."""

    if not files:
        return
    if not isinstance(operation, str) or not operation or any(character in operation for character in "\r\n"):
        raise ClonePackError("transaction operation must be a non-empty single line", diagnostic="TRANSACTION_INVALID")
    raw_paths = [Path(path) for path in files]
    root = (
        _validate_transaction_root(Path(transaction_root))
        if transaction_root is not None
        else _infer_transaction_root(raw_paths)
    )
    prepared_files: list[tuple[Path, str, bytes, bool, str | None]] = []
    seen: set[str] = set()
    for raw_path, content in files.items():
        if not isinstance(content, (str, bytes)):
            raise ClonePackError("atomic transaction content must be text or bytes", diagnostic="TRANSACTION_INVALID")
        supplied = Path(raw_path).expanduser()
        supplied = supplied if supplied.is_absolute() else supplied.absolute()
        try:
            relative_value = supplied.relative_to(root).as_posix()
        except ValueError as exc:
            raise _transaction_error(f"transaction destination escapes its root: {supplied}") from exc
        if relative_value in seen:
            raise _transaction_error(f"transaction destination is duplicated: {relative_value}")
        _ensure_transaction_parent(root, relative_value)
        destination = _transaction_destination(root, relative_value)
        try:
            destination_metadata = destination.lstat()
        except FileNotFoundError:
            before_exists = False
            before_digest = None
        else:
            if destination.is_symlink() or not stat.S_ISREG(destination_metadata.st_mode):
                raise _transaction_error(f"transaction destination is not a regular file: {relative_value}")
            before_exists = True
            before_digest = sha256_file(destination)
        seen.add(relative_value)
        after_bytes = content.encode("utf-8") if isinstance(content, str) else content
        prepared_files.append((destination, relative_value, after_bytes, before_exists, before_digest))

    journal_root = root / TRANSACTION_DIRECTORY
    journal_root.mkdir(mode=0o700, exist_ok=True)
    if journal_root.is_symlink() or not journal_root.is_dir():
        raise _transaction_error(f"transaction journal root is unsafe: {journal_root}")
    transaction = Path(tempfile.mkdtemp(prefix="transaction-", dir=journal_root))
    entries: list[dict[str, Any]] = []
    journal_written = False
    try:
        for position, (_, relative_value, after_bytes, before_exists, before_digest) in enumerate(prepared_files, 1):
            staged_name = f"after-{position:04d}.bin"
            stage = transaction / staged_name
            with stage.open("xb") as handle:
                handle.write(after_bytes)
                handle.flush()
                os.fsync(handle.fileno())
            entries.append(
                {
                    "destination": relative_value,
                    "before_exists": before_exists,
                    "before_sha256": before_digest,
                    "after_sha256": sha256_bytes(after_bytes),
                    "staged_path": staged_name,
                }
            )
        _fsync_directory(transaction)
        atomic_write_json(
            transaction / "journal.json",
            {
                "schema_version": TRANSACTION_SCHEMA_VERSION,
                "operation": operation,
                "state": "PREPARED",
                "entries": entries,
            },
        )
        _fsync_directory(transaction)
        _fsync_directory(journal_root)
        journal_written = True
        for (destination, _, _, _, _), entry in zip(prepared_files, entries, strict=True):
            state = _destination_state(
                destination,
                before_exists=entry["before_exists"],
                before_sha256=entry["before_sha256"],
                after_sha256=entry["after_sha256"],
            )
            if state == "before":
                _replace_from_stage(transaction / entry["staged_path"], destination)
        for (destination, _, _, _, _), entry in zip(prepared_files, entries, strict=True):
            if _destination_state(
                destination,
                before_exists=entry["before_exists"],
                before_sha256=entry["before_sha256"],
                after_sha256=entry["after_sha256"],
            ) != "after":
                raise _transaction_error(f"transaction did not reach its after image: {entry['destination']}")
        _remove_completed_transaction(transaction, journal_root)
    except BaseException:
        if not journal_written:
            shutil.rmtree(transaction, ignore_errors=True)
            try:
                journal_root.rmdir()
            except OSError:
                pass
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
