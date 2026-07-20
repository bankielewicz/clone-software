from __future__ import annotations

import os
import re
import stat
from pathlib import Path
from typing import Any

from .common import ClonePackError, atomic_write_json, load_json, resolve_inside, safe_relative_path
from .schema import validate_schema_file


AUDITED_PROFILE_IDS = (
    "static-web-esm",
    "static-web-esm-allowlist",
    "python-src",
    "typescript-src",
    "rust-crate",
)
PROFILE_FIELDS = {"id", "description", "template", "required_paths", "commands"}
COMMAND_FIELDS = {"setup", "test", "build", "run"}
NOT_APPLICABLE_COMMANDS = {"setup": None, "test": None, "build": None, "run": None}


def _catalog_error(message: str) -> ClonePackError:
    return ClonePackError(message, diagnostic="SCAFFOLD_CATALOG_INVALID")


def _validate_commands(value: Any, *, context: str) -> None:
    if not isinstance(value, dict) or set(value) != COMMAND_FIELDS:
        raise _catalog_error(f"{context} commands must contain exactly setup, test, build, and run")
    for name in sorted(COMMAND_FIELDS):
        command = value[name]
        if command is None:
            continue
        if (
            not isinstance(command, list)
            or not command
            or any(not isinstance(argument, str) or not argument for argument in command)
        ):
            raise _catalog_error(f"{context} command {name} must be null or a non-empty argv array")


def _template_files(template_root: Path) -> list[Path]:
    files: list[Path] = []
    for source in sorted(path for path in template_root.rglob("*") if path.is_file()):
        try:
            source.resolve().relative_to(template_root.resolve())
        except ValueError as exc:
            raise _catalog_error(f"scaffold template file escapes its template root: {source}") from exc
        files.append(source)
    return files


def _catalog(skill_root: Path) -> tuple[Path, dict[str, Any]]:
    root = skill_root / "assets" / "scaffolds"
    catalog = load_json(root / "catalog.json")
    if set(catalog) != {"schema_version", "profiles"}:
        raise _catalog_error("scaffold catalog must contain exactly schema_version and profiles")
    if catalog.get("schema_version") != "clone-scaffold-catalog/v2":
        raise _catalog_error("unsupported scaffold catalog schema_version")
    profiles = catalog.get("profiles")
    if not isinstance(profiles, list):
        raise _catalog_error("scaffold catalog profiles must be an array")
    identifiers = [profile.get("id") if isinstance(profile, dict) else None for profile in profiles]
    if identifiers != list(AUDITED_PROFILE_IDS):
        raise _catalog_error(
            "scaffold catalog must contain the audited profiles in canonical order: "
            + ", ".join(AUDITED_PROFILE_IDS)
        )
    for profile in profiles:
        identifier = str(profile["id"])
        if set(profile) != PROFILE_FIELDS:
            raise _catalog_error(f"scaffold profile {identifier} has unexpected or missing fields")
        if not isinstance(profile["description"], str) or not profile["description"]:
            raise _catalog_error(f"scaffold profile {identifier} description must be non-empty")
        if not isinstance(profile["template"], str):
            raise _catalog_error(f"scaffold profile {identifier} template must be a string")
        if profile["template"] != identifier:
            raise _catalog_error(f"scaffold profile {identifier} template must equal its profile id")
        try:
            template_root = resolve_inside(root, profile["template"], must_exist=True)
        except ClonePackError as exc:
            raise _catalog_error(f"scaffold profile {identifier} template is invalid: {exc}") from exc
        if not template_root.is_dir():
            raise _catalog_error(f"scaffold profile {identifier} template must be a directory")
        required_paths = profile["required_paths"]
        if (
            not isinstance(required_paths, list)
            or not required_paths
            or any(not isinstance(path, str) for path in required_paths)
            or len(required_paths) != len(set(required_paths))
        ):
            raise _catalog_error(f"scaffold profile {identifier} required_paths must be unique strings")
        try:
            normalized_required = [safe_relative_path(path).as_posix() for path in required_paths]
        except ClonePackError as exc:
            raise _catalog_error(f"scaffold profile {identifier} required_paths are invalid: {exc}") from exc
        actual_paths = [path.relative_to(template_root).as_posix() for path in _template_files(template_root)]
        if set(normalized_required) != set(actual_paths):
            raise _catalog_error(f"scaffold profile {identifier} required_paths do not match template files")
        _validate_commands(profile["commands"], context=f"scaffold profile {identifier}")
    return root, catalog


def _load_plan(skill_root: Path, pack: Path, manifest: dict[str, Any]) -> tuple[Path, dict[str, Any]]:
    try:
        plan_path = resolve_inside(pack, str(manifest["plans"]["scaffold"]), must_exist=True)
    except (KeyError, TypeError) as exc:
        raise ClonePackError(
            "manifest does not define plans.scaffold",
            diagnostic="SCAFFOLD_PLAN_INVALID",
        ) from exc
    plan = load_json(plan_path)
    schema_path = skill_root / "assets" / "schemas" / "scaffold-plan-v2.schema.json"
    violations = validate_schema_file(plan, schema_path)
    if violations:
        details = "; ".join(f"{item.pointer or '/'}: {item.message}" for item in violations)
        raise ClonePackError(
            f"scaffold plan schema violations: {details}",
            diagnostic="SCAFFOLD_PLAN_INVALID",
        )
    return plan_path, plan


def _require_exact_metadata(plan: dict[str, Any], expected: dict[str, Any], fields: tuple[str, ...]) -> None:
    mismatched = [field for field in fields if plan.get(field) != expected.get(field)]
    if mismatched:
        raise ClonePackError(
            "scaffold plan metadata differs from the selected profile: " + ", ".join(mismatched),
            diagnostic="SCAFFOLD_PLAN_CATALOG_MISMATCH",
        )


def _destination(repository: Path, relative: Path) -> Path:
    destination = repository / relative
    try:
        destination.resolve().relative_to(repository)
    except ValueError as exc:
        raise ClonePackError(
            f"scaffold path escapes repository: {relative.as_posix()}",
            exit_code=4,
            diagnostic="PATH_ESCAPE",
        ) from exc
    return destination


def _identity(path: Path) -> tuple[int, int] | None:
    try:
        metadata = path.lstat()
    except FileNotFoundError:
        return None
    return metadata.st_dev, metadata.st_ino


def _remove_owned_file(path: Path, identity: tuple[int, int]) -> None:
    """Remove only the exact filesystem object created by this apply attempt."""

    if _identity(path) != identity:
        return
    try:
        if stat.S_ISREG(path.lstat().st_mode):
            path.unlink()
    except FileNotFoundError:
        return


def _remove_owned_directory(path: Path, identity: tuple[int, int]) -> None:
    """Remove an empty directory only while it is still the object we created."""

    if _identity(path) != identity:
        return
    try:
        path.rmdir()
    except OSError:
        return


def _require_directory_parents(repository: Path, destination: Path) -> None:
    parent = destination.parent
    while parent != repository:
        if parent.exists() and not parent.is_dir():
            raise ClonePackError(
                f"scaffold parent is not a directory: {parent.relative_to(repository).as_posix()}",
                diagnostic="SCAFFOLD_COLLISION",
            )
        parent = parent.parent


def scaffold_preview(skill_root: Path, pack: Path) -> dict[str, Any]:
    pack = pack.expanduser().resolve()
    manifest = load_json(pack / "clone_pack.json")
    plan_path, plan = _load_plan(skill_root, pack, manifest)
    if not plan.get("stack_decision_id") or not re.fullmatch(r"STACK-\d{3,}", str(plan.get("stack_decision_id"))):
        raise ClonePackError("scaffold requires a resolved STACK-### decision", diagnostic="STACK_DECISION_REQUIRED")
    repository = Path(str(manifest["repository_root"])).expanduser().resolve()
    if not repository.is_dir():
        raise ClonePackError("scaffold repository_root must be an existing directory", diagnostic="SCAFFOLD_REPOSITORY_INVALID")

    if plan["profile_id"] == "not-applicable":
        expected = {
            "template": "not-applicable",
            "output_root": ".",
            "required_paths": [],
            "commands": NOT_APPLICABLE_COMMANDS,
            "applied": False,
        }
        _require_exact_metadata(
            plan,
            expected,
            ("template", "output_root", "required_paths", "commands", "applied"),
        )
        return {
            "plan": plan,
            "profile": {
                "id": "not-applicable",
                "template": "not-applicable",
                "required_paths": [],
                "commands": dict(NOT_APPLICABLE_COMMANDS),
            },
            "disposition": "not-applicable",
            "repository": repository,
            "output_root": repository,
            "files": [],
            "plan_path": plan_path,
        }

    root, catalog = _catalog(skill_root)
    profile = next((item for item in catalog["profiles"] if item.get("id") == plan.get("profile_id")), None)
    if profile is None:
        raise ClonePackError(f"unknown scaffold profile: {plan.get('profile_id')}", diagnostic="SCAFFOLD_PROFILE_UNKNOWN")
    _require_exact_metadata(plan, profile, ("template", "required_paths", "commands"))
    template_root = resolve_inside(root, str(profile["template"]), must_exist=True)
    if not template_root.is_dir():
        raise ClonePackError("scaffold template must be a directory", diagnostic="SCAFFOLD_TEMPLATE_INVALID")
    output_value = str(plan.get("output_root", ""))
    if output_value in {"", "."}:
        output_root = repository
    else:
        output_root = resolve_inside(repository, output_value, must_exist=False)
    variables = plan.get("variables") if isinstance(plan.get("variables"), dict) else {}
    files: list[dict[str, str]] = []
    for source in _template_files(template_root):
        relative = source.relative_to(template_root)
        destination = _destination(repository, output_root.relative_to(repository) / relative)
        _require_directory_parents(repository, destination)
        try:
            content = source.read_text(encoding="utf-8")
        except (OSError, UnicodeError) as exc:
            raise ClonePackError(
                f"scaffold template is not readable UTF-8 text: {relative.as_posix()}",
                diagnostic="SCAFFOLD_TEMPLATE_INVALID",
            ) from exc
        for key, value in variables.items():
            content = content.replace("{{" + str(key) + "}}", str(value))
        unresolved = sorted(set(re.findall(r"\{\{[A-Za-z0-9_-]+\}\}", content)))
        if unresolved:
            raise ClonePackError(
                f"unresolved scaffold tokens in {relative.as_posix()}: {', '.join(unresolved)}",
                diagnostic="SCAFFOLD_TOKEN_UNRESOLVED",
            )
        files.append({"source": source.relative_to(root).as_posix(), "destination": destination.relative_to(repository).as_posix(), "content": content})
    return {
        "plan": plan,
        "profile": profile,
        "disposition": "catalog",
        "repository": repository,
        "output_root": output_root,
        "files": files,
        "plan_path": plan_path,
    }


def apply_scaffold(skill_root: Path, pack: Path, *, apply: bool) -> dict[str, Any]:
    preview = scaffold_preview(skill_root, pack)
    result = {
        "profile_id": preview["profile"]["id"],
        "disposition": preview["disposition"],
        "files": [item["destination"] for item in preview["files"]],
        "commands": preview["profile"]["commands"],
        "applied": False,
    }
    if preview["disposition"] == "not-applicable":
        return result
    if apply and preview["plan"]["applied"]:
        raise ClonePackError("scaffold plan is already applied", diagnostic="SCAFFOLD_ALREADY_APPLIED")
    collisions = [item["destination"] for item in preview["files"] if (preview["repository"] / item["destination"]).exists()]
    if collisions:
        raise ClonePackError("scaffold collisions: " + ", ".join(collisions), diagnostic="SCAFFOLD_COLLISION")
    if not apply:
        return result
    created_files: list[tuple[Path, tuple[int, int]]] = []
    created_directories: list[tuple[Path, tuple[int, int]]] = []
    try:
        for item in preview["files"]:
            destination = _destination(preview["repository"], Path(item["destination"]))
            _require_directory_parents(preview["repository"], destination)
            missing_parents: list[Path] = []
            parent = destination.parent
            while parent != preview["repository"] and not parent.exists():
                missing_parents.append(parent)
                parent = parent.parent
            for directory in reversed(missing_parents):
                try:
                    directory.mkdir()
                except FileExistsError:
                    pass
                except OSError as exc:
                    raise ClonePackError(
                        f"cannot create scaffold directory: {directory.relative_to(preview['repository']).as_posix()}",
                        diagnostic="SCAFFOLD_WRITE_FAILED",
                    ) from exc
                else:
                    identity = _identity(directory)
                    if identity is None:  # pragma: no cover - immediate external deletion
                        raise ClonePackError(
                            f"scaffold directory disappeared during apply: {directory.relative_to(preview['repository']).as_posix()}",
                            diagnostic="SCAFFOLD_COLLISION",
                        )
                    created_directories.append((directory, identity))
                try:
                    directory.resolve().relative_to(preview["repository"])
                except ValueError as exc:
                    raise ClonePackError(
                        f"scaffold directory escapes repository: {directory}",
                        exit_code=4,
                        diagnostic="PATH_ESCAPE",
                    ) from exc
                if not directory.is_dir():
                    raise ClonePackError(
                        f"scaffold parent is not a directory: {directory}",
                        diagnostic="SCAFFOLD_COLLISION",
                    )
            try:
                descriptor = os.open(destination, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o666)
            except FileExistsError as exc:
                raise ClonePackError(
                    f"scaffold collision during apply: {item['destination']}",
                    diagnostic="SCAFFOLD_COLLISION",
                ) from exc
            except (IsADirectoryError, NotADirectoryError) as exc:
                raise ClonePackError(
                    f"scaffold collision during apply: {item['destination']}",
                    diagnostic="SCAFFOLD_COLLISION",
                ) from exc
            except OSError as exc:
                raise ClonePackError(
                    f"cannot create scaffold file: {item['destination']}",
                    diagnostic="SCAFFOLD_WRITE_FAILED",
                ) from exc
            metadata = os.fstat(descriptor)
            created_files.append((destination, (metadata.st_dev, metadata.st_ino)))
            try:
                with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
                    handle.write(item["content"])
                    handle.flush()
                    os.fsync(handle.fileno())
            except BaseException:
                raise
        replaced = [
            path.relative_to(preview["repository"]).as_posix()
            for path, identity in created_files
            if _identity(path) != identity
        ]
        if replaced:
            raise ClonePackError(
                "scaffold paths changed during apply: " + ", ".join(replaced),
                diagnostic="SCAFFOLD_COLLISION",
            )
        required = preview["plan"].get("required_paths", [])
        missing = [
            path
            for path in required
            if not (preview["output_root"] / safe_relative_path(str(path))).is_file()
        ]
        if missing:
            raise ClonePackError(
                "scaffold required paths missing after apply: " + ", ".join(missing),
                diagnostic="SCAFFOLD_INCOMPLETE",
            )
        preview["plan"]["applied"] = True
        try:
            atomic_write_json(preview["plan_path"], preview["plan"])
        except OSError as exc:
            raise ClonePackError(
                "cannot mark scaffold plan applied",
                diagnostic="SCAFFOLD_PLAN_WRITE_FAILED",
            ) from exc
        result["applied"] = True
    except BaseException:
        for path, identity in reversed(created_files):
            _remove_owned_file(path, identity)
        for directory, identity in reversed(created_directories):
            _remove_owned_directory(directory, identity)
        raise
    return result
