#!/usr/bin/env bash

set -Eeuo pipefail

readonly DEFAULT_REPOSITORY_URL="https://github.com/bankielewicz/clone-software.git"
readonly DEFAULT_REF="main"
readonly PROMPT_SOURCE="assets/prompts/minecraft-clean-room-mvp.md"
readonly PROMPT_DESTINATION="MINECRAFT_CLONE_PROMPT.md"

destination=""
repository_url="$DEFAULT_REPOSITORY_URL"
requested_ref="$DEFAULT_REF"
verification="smoke"
codex_bin="codex"
allow_non_wsl=0
trust_custom_source_code=0
owned_stage=""
owned_stage_identity=""
owned_stage_name=""
destination_parent_fd=""
destination_parent_anchor=""
destination_parent_identity=""

usage() {
  cat <<'EOF'
Install clone-software and create an isolated Minecraft-inspired MVP trial workspace.

Usage:
  install_clone_software_wsl.sh --destination <absolute-absent-directory> [options]

Required:
  --destination <path>   Absolute path for the new installation root. The path
                         must not exist; its immediate parent must exist.

Options:
  --repo-url <url/path>  Git source. Default:
                         https://github.com/bankielewicz/clone-software.git
  --ref <branch/tag>     Branch or tag to clone. Default: main
  --verify <mode>        smoke or full. Default: smoke
  --codex-bin <command>  Codex executable name or absolute path. Default: codex
  --trust-custom-source-code
                         Required with a non-default --repo-url. Confirms that
                         the selected clone's Python code may execute as the
                         current WSL user during verification.
  --allow-non-wsl        Permit Linux execution outside WSL for CI/test use.
  -h, --help             Print this help and exit without writing.

Published layout:
  <destination>/clone-software/
  <destination>/minecraft-clone/.agents/skills/clone-software -> ../../../clone-software
  <destination>/minecraft-clone/MINECRAFT_CLONE_PROMPT.md
  <destination>/installation-receipt.json

Installer-authored steps do not install Codex, Node packages, Playwright,
browsers, Python packages, or operating-system packages. Verification executes
Python from the cloned source as the current WSL user; use only trusted code.
The script never replaces an existing destination.
EOF
}

diagnostic() {
  local code="$1"
  shift
  printf '%s: %s\n' "$code" "$*" >&2
}

die() {
  local exit_code="$1"
  local diagnostic_code="$2"
  shift 2
  diagnostic "$diagnostic_code" "$*"
  exit "$exit_code"
}

cleanup_owned_stage() {
  local current_identity
  local current_parent_identity
  local durable_stage
  local durable_stage_identity
  if [[ -z "${owned_stage:-}" || (! -e "$owned_stage" && ! -L "$owned_stage") ]]; then
    return
  fi
  if [[ -L "$owned_stage" || ! -d "$owned_stage" ]]; then
    diagnostic "STAGE_CLEANUP_REFUSED" \
      "owned staging path is no longer a non-symlink directory: $owned_stage"
    return
  fi
  if ! current_identity="$(stat -Lc '%d:%i' -- "$owned_stage" 2>/dev/null)"; then
    diagnostic "STAGE_CLEANUP_REFUSED" \
      "could not identify owned staging path: $owned_stage"
    return
  fi
  if [[ -z "${owned_stage_identity:-}" || "$current_identity" != "$owned_stage_identity" ]]; then
    diagnostic "STAGE_CLEANUP_REFUSED" \
      "staging path identity changed; expected $owned_stage_identity, observed $current_identity"
    return
  fi
  case "$owned_stage" in
    "$destination_parent_anchor"/.clone-software-wsl-install.*)
      durable_stage="$destination_parent/$owned_stage_name"
      if [[ ! -L "$destination_parent" && -d "$destination_parent" && \
            ! -L "$durable_stage" && -d "$durable_stage" ]] && \
         current_parent_identity="$(stat -Lc '%d:%i' -- "$destination_parent" 2>/dev/null)" && \
         durable_stage_identity="$(stat -Lc '%d:%i' -- "$durable_stage" 2>/dev/null)" && \
         [[ "$current_parent_identity" == "$destination_parent_identity" && \
            "$durable_stage_identity" == "$owned_stage_identity" ]]; then
        diagnostic "INSTALL_STAGE_RETAINED" \
          "failed-install staging directory was retained for explicit inspection: $durable_stage"
      else
        diagnostic "STAGE_CLEANUP_REFUSED" \
          "stage was retained but no durable pathname can be inferred after parent mutation; requested_parent=$destination_parent stage_basename=$owned_stage_name"
      fi
      ;;
    *)
      diagnostic "STAGE_CLEANUP_REFUSED" "refusing to remove unexpected path: $owned_stage"
      ;;
  esac
}

unexpected_error() {
  local prior_exit="$1"
  local line="$2"
  trap - ERR
  diagnostic "INSTALL_INTERNAL_ERROR" "unexpected exit $prior_exit at script line $line"
  exit 70
}

resolve_executable() {
  local requested="$1"
  local resolved
  if [[ "$requested" == */* ]]; then
    if ! resolved="$(realpath -- "$requested")"; then
      return 1
    fi
  else
    if ! resolved="$(type -P -- "$requested")"; then
      return 1
    fi
    if ! resolved="$(realpath -- "$resolved")"; then
      return 1
    fi
  fi
  [[ "$resolved" == /* && -f "$resolved" && -x "$resolved" && ! -L "$resolved" ]] || return 1
  printf '%s\n' "$resolved"
}

reject_symlinked_directory_path() {
  local absolute_path="$1"
  local current="/"
  local component
  local -a components=()
  IFS='/' read -r -a components <<< "${absolute_path#/}"
  for component in "${components[@]}"; do
    [[ -n "$component" ]] || continue
    if [[ "$current" == "/" ]]; then
      current="/$component"
    else
      current="$current/$component"
    fi
    if [[ -L "$current" ]]; then
      die 4 "DESTINATION_SYMLINK" \
        "destination ancestry must not contain a symlink: $current"
    fi
    if [[ -e "$current" && ! -d "$current" ]]; then
      die 6 "INSTALL_DESTINATION_FAILURE" \
        "destination ancestor is not a directory: $current"
    fi
  done
}

assert_destination_parent_binding() {
  local current_identity
  reject_symlinked_directory_path "$destination_parent"
  if ! current_identity="$(stat -Lc '%d:%i' -- "$destination_parent" 2>/dev/null)"; then
    die 4 "INSTALL_DESTINATION_PARENT_CHANGED" \
      "destination parent is no longer available: $destination_parent"
  fi
  if [[ "$current_identity" != "$destination_parent_identity" ]]; then
    die 4 "INSTALL_DESTINATION_PARENT_CHANGED" \
      "destination parent identity changed; expected $destination_parent_identity, observed $current_identity"
  fi
}

check_duplicate_skill_discovery() {
  local candidate
  local ancestor
  local codex_home_parent
  local codex_home_probe
  local codex_home_resolved
  local codex_home_value
  local -a candidates=()

  [[ -n "${HOME:-}" && "$HOME" == /* ]] || \
    die 4 "INSTALL_SKILL_DUPLICATE" \
      "HOME must be an absolute path so existing user-scope skills can be checked"
  candidates+=("$HOME/.agents/skills/clone-software")
  candidates+=("$HOME/.codex/skills/clone-software")
  candidates+=("/etc/codex/skills/clone-software")

  codex_home_value="${CODEX_HOME:-}"
  if [[ -n "$codex_home_value" ]]; then
    if [[ "$codex_home_value" != /* ]] || ! python3 -c '
import sys

value = sys.argv[1]
raise SystemExit(1 if any(ord(character) < 32 or ord(character) == 127 for character in value) else 0)
' "$codex_home_value"; then
      die 4 "INSTALL_CODEX_HOME_INVALID" \
        "CODEX_HOME must be an absolute path without control characters"
    fi
    codex_home_probe="$codex_home_value"
    while [[ ! -e "$codex_home_probe" && ! -L "$codex_home_probe" ]]; do
      if ! codex_home_parent="$(dirname -- "$codex_home_probe")" || \
         [[ "$codex_home_parent" == "$codex_home_probe" ]]; then
        die 4 "INSTALL_CODEX_HOME_INVALID" \
          "CODEX_HOME has no resolvable directory ancestor"
      fi
      codex_home_probe="$codex_home_parent"
    done
    if [[ (-L "$codex_home_probe" && ! -e "$codex_home_probe") || \
          (-e "$codex_home_probe" && ! -d "$codex_home_probe") || \
          (-d "$codex_home_probe" && ! -x "$codex_home_probe") ]]; then
      die 4 "INSTALL_CODEX_HOME_INVALID" \
        "CODEX_HOME must resolve to a directory or an absent path beneath a directory"
    fi
    if ! codex_home_resolved="$(realpath -m -- "$codex_home_value")" || \
       [[ "$codex_home_resolved" != /* ]]; then
      die 4 "INSTALL_CODEX_HOME_INVALID" \
        "CODEX_HOME could not be resolved to an absolute discovery root"
    fi
    candidates+=("$codex_home_resolved/skills/clone-software")
  fi

  ancestor="$destination_parent"
  while :; do
    candidates+=("$ancestor/.agents/skills/clone-software")
    [[ "$ancestor" == "/" ]] && break
    if ! ancestor="$(dirname -- "$ancestor")"; then
      die 7 "INSTALL_EXECUTABLE_FAILURE" \
        "dirname failed while checking ancestor skill discovery"
    fi
  done

  for candidate in "${candidates[@]}"; do
    if [[ -e "$candidate" || -L "$candidate" ]]; then
      die 4 "INSTALL_SKILL_DUPLICATE" \
        "clone-software is already discoverable at $candidate; move it outside Codex discovery or use an isolated profile before installing"
    fi
  done
}

checkout_identity() {
  python3 - "$1" <<'PY'
from __future__ import annotations

import hashlib
import os
import stat
import struct
import sys
from pathlib import Path


root = Path(sys.argv[1])
digest = hashlib.sha256()


def add_field(kind: bytes, value: bytes) -> None:
    digest.update(kind)
    digest.update(struct.pack(">Q", len(value)))
    digest.update(value)


def stable_fields(value: os.stat_result) -> tuple[int, int, int, int, int, int]:
    return (
        value.st_dev,
        value.st_ino,
        value.st_mode,
        value.st_size,
        value.st_mtime_ns,
        value.st_ctime_ns,
    )


def scan(directory: Path, relative: Path) -> None:
    before = directory.stat(follow_symlinks=False)
    add_field(b"D", os.fsencode(str(relative)))
    add_field(b"M", oct(stat.S_IMODE(before.st_mode)).encode("ascii"))
    entries = sorted(os.scandir(directory), key=lambda entry: os.fsencode(entry.name))
    for entry in entries:
        child_relative = relative / entry.name
        encoded_relative = os.fsencode(str(child_relative))
        observed = entry.stat(follow_symlinks=False)
        mode = observed.st_mode
        if stat.S_ISLNK(mode):
            if not child_relative.parts or child_relative.parts[0] != ".git":
                raise RuntimeError(f"working-tree symlink is not permitted: {child_relative}")
            add_field(b"L", encoded_relative)
            add_field(b"M", oct(stat.S_IMODE(mode)).encode("ascii"))
            add_field(b"T", os.fsencode(os.readlink(entry.path)))
        elif stat.S_ISDIR(mode):
            scan(Path(entry.path), child_relative)
        elif stat.S_ISREG(mode):
            flags = os.O_RDONLY
            if hasattr(os, "O_NOFOLLOW"):
                flags |= os.O_NOFOLLOW
            descriptor = os.open(entry.path, flags)
            try:
                opened = os.fstat(descriptor)
                if stable_fields(opened) != stable_fields(observed):
                    raise RuntimeError(f"concurrent file mutation detected: {child_relative}")
                add_field(b"F", encoded_relative)
                add_field(b"M", oct(stat.S_IMODE(mode)).encode("ascii"))
                while True:
                    chunk = os.read(descriptor, 1024 * 1024)
                    if not chunk:
                        break
                    add_field(b"B", chunk)
                after = os.fstat(descriptor)
                if stable_fields(after) != stable_fields(opened):
                    raise RuntimeError(f"concurrent file mutation detected: {child_relative}")
            finally:
                os.close(descriptor)
        else:
            raise RuntimeError(f"unsupported filesystem object: {child_relative}")
    after = directory.stat(follow_symlinks=False)
    directory_before = (
        before.st_dev,
        before.st_ino,
        before.st_mode,
        before.st_mtime_ns,
        before.st_ctime_ns,
    )
    directory_after = (
        after.st_dev,
        after.st_ino,
        after.st_mode,
        after.st_mtime_ns,
        after.st_ctime_ns,
    )
    if directory_after != directory_before:
        raise RuntimeError(f"concurrent directory mutation detected: {relative}")


try:
    scan(root, Path("."))
except (OSError, RuntimeError) as error:
    print(str(error), file=sys.stderr)
    raise SystemExit(1)
print(digest.hexdigest())
PY
}

workspace_inventory_json() {
  python3 - "$1" <<'PY'
from __future__ import annotations

import hashlib
import json
import os
import stat
import sys


root = sys.argv[1]
directory_flags = os.O_RDONLY | os.O_DIRECTORY
file_flags = os.O_RDONLY
if hasattr(os, "O_NOFOLLOW"):
    directory_flags |= os.O_NOFOLLOW
    file_flags |= os.O_NOFOLLOW


def stable_fields(value: os.stat_result) -> tuple[int, int, int, int, int, int]:
    return (
        value.st_dev,
        value.st_ino,
        value.st_mode,
        value.st_size,
        value.st_mtime_ns,
        value.st_ctime_ns,
    )


def stable_directory_fields(value: os.stat_result) -> tuple[int, int, int, int, int]:
    return (
        value.st_dev,
        value.st_ino,
        value.st_mode,
        value.st_mtime_ns,
        value.st_ctime_ns,
    )


def scan(directory_fd: int, prefix: str, records: list[dict[str, object]]) -> None:
    before = os.fstat(directory_fd)
    with os.scandir(directory_fd) as iterator:
        entries = sorted(iterator, key=lambda entry: os.fsencode(entry.name))
    for entry in entries:
        relative = f"{prefix}/{entry.name}" if prefix else entry.name
        if not prefix and entry.name == ".git":
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
                if stable_fields(opened) != stable_fields(observed):
                    raise RuntimeError(f"concurrent directory mutation detected: {relative}")
                scan(child_fd, relative, records)
                if stable_fields(os.fstat(child_fd)) != stable_fields(opened):
                    raise RuntimeError(f"concurrent directory mutation detected: {relative}")
            finally:
                os.close(child_fd)
        elif stat.S_ISREG(mode):
            descriptor = os.open(entry.name, file_flags, dir_fd=directory_fd)
            try:
                opened = os.fstat(descriptor)
                if stable_fields(opened) != stable_fields(observed):
                    raise RuntimeError(f"concurrent file mutation detected: {relative}")
                digest = hashlib.sha256()
                size = 0
                while True:
                    chunk = os.read(descriptor, 1024 * 1024)
                    if not chunk:
                        break
                    digest.update(chunk)
                    size += len(chunk)
                after = os.fstat(descriptor)
                if stable_fields(after) != stable_fields(opened) or size != opened.st_size:
                    raise RuntimeError(f"concurrent file mutation detected: {relative}")
            finally:
                os.close(descriptor)
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
            if stable_fields(after) != stable_fields(observed):
                raise RuntimeError(f"concurrent symlink mutation detected: {relative}")
            target_bytes = target.encode("utf-8")
            records.append(
                {
                    "mode": stat.S_IMODE(mode),
                    "path": relative,
                    "sha256": hashlib.sha256(target_bytes).hexdigest(),
                    "target": target,
                    "type": "symlink",
                }
            )
        else:
            raise RuntimeError(f"unsupported filesystem object: {relative}")
    if stable_directory_fields(os.fstat(directory_fd)) != stable_directory_fields(before):
        raise RuntimeError(f"concurrent directory mutation detected: {prefix or '.'}")


try:
    root_fd = os.open(root, directory_flags)
    try:
        if not stat.S_ISDIR(os.fstat(root_fd).st_mode):
            raise RuntimeError("workspace is not a real directory")
        inventory: list[dict[str, object]] = []
        scan(root_fd, "", inventory)
    finally:
        os.close(root_fd)
except (OSError, RuntimeError, UnicodeError) as error:
    print(str(error), file=sys.stderr)
    raise SystemExit(1)

inventory.sort(key=lambda record: str(record["path"]).encode("utf-8"))
print(json.dumps(inventory, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
PY
}

validate_install_tree() {
  python3 - "$1" <<'PY'
from __future__ import annotations

import json
import re
import stat
import sys
from pathlib import Path


root = Path(sys.argv[1]).resolve(strict=True)
required_files = (
    "LICENSE",
    "SKILL.md",
    "agents/openai.yaml",
    "scripts/check_wsl_trial_workspace.py",
    "scripts/clone_pack.py",
    "scripts/run_skill_tests.py",
    "assets/prompts/minecraft-clean-room-mvp.md",
    "assets/scaffolds/catalog.json",
    "references/evidence-and-fidelity.md",
    "references/document-contracts.md",
    "references/greenfield.md",
    "references/game-simulation.md",
    "references/security-and-provenance.md",
    "references/pack-evolution.md",
    "assets/scaffolds/static-web-esm/README.md",
    "assets/scaffolds/static-web-esm/package.json",
    "assets/scaffolds/static-web-esm/index.html",
    "assets/scaffolds/static-web-esm/styles.css",
    "assets/scaffolds/static-web-esm/src/app.js",
    "assets/scaffolds/static-web-esm/tests/smoke.test.mjs",
    "assets/scaffolds/static-web-esm-allowlist/README.md",
    "assets/scaffolds/static-web-esm-allowlist/package.json",
    "assets/scaffolds/static-web-esm-allowlist/index.html",
    "assets/scaffolds/static-web-esm-allowlist/styles.css",
    "assets/scaffolds/static-web-esm-allowlist/src/app.js",
    "assets/scaffolds/static-web-esm-allowlist/tests/smoke.test.mjs",
    "assets/scaffolds/static-web-esm-allowlist/tools/serve_static.py",
    "assets/scaffolds/static-web-esm-allowlist/serve_manifest.json",
)
required_directories = (
    "scripts/clonepack",
    "assets/schemas",
    "assets/templates-v2",
)


def contained(path: Path) -> None:
    try:
        path.resolve(strict=True).relative_to(root)
    except (OSError, ValueError) as error:
        raise RuntimeError(f"path escapes the checkout: {path.relative_to(root)}") from error


for relative in required_files:
    path = root / relative
    if not path.exists():
        raise RuntimeError(f"required file is absent: {relative}")
    contained(path)
    observed = path.lstat()
    if not stat.S_ISREG(observed.st_mode):
        raise RuntimeError(f"required path is not a regular file: {relative}")
    try:
        path.read_bytes().decode("utf-8")
    except UnicodeDecodeError as error:
        raise RuntimeError(f"required file is not UTF-8: {relative}") from error

for relative in required_directories:
    path = root / relative
    if not path.exists():
        raise RuntimeError(f"required directory is absent: {relative}")
    contained(path)
    observed = path.lstat()
    if not stat.S_ISDIR(observed.st_mode):
        raise RuntimeError(f"required path is not a directory: {relative}")
    if not any(child.is_file() and not child.is_symlink() for child in path.iterdir()):
        raise RuntimeError(f"required directory has no regular files: {relative}")

def yaml_scalar(raw: str) -> str | None:
    value = re.split(r"\s+#", raw.strip(), maxsplit=1)[0].strip()
    if not value or value.startswith("#"):
        return None
    if value[0] == '"':
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            return None
        return parsed if isinstance(parsed, str) and parsed else None
    if value[0] == "'":
        if len(value) < 2 or value[-1] != "'":
            return None
        inner = value[1:-1]
        output = []
        index = 0
        while index < len(inner):
            if inner[index] != "'":
                output.append(inner[index])
                index += 1
                continue
            if index + 1 >= len(inner) or inner[index + 1] != "'":
                return None
            output.append("'")
            index += 2
        parsed = "".join(output)
        return parsed or None
    if not value or value[0] in "[{&*!|>%@`" or value.lower() in {
        "null",
        "~",
        "true",
        "false",
        "yes",
        "no",
        "on",
        "off",
    }:
        return None
    if re.fullmatch(r"[A-Za-z$][A-Za-z0-9 $.,;/()_+\-!?@]*", value) is None:
        return None
    return value


skill_text = (root / "SKILL.md").read_text(encoding="utf-8")
lines = skill_text.splitlines()
if not lines or lines[0] != "---":
    raise RuntimeError("SKILL.md must begin with exact YAML frontmatter")
try:
    close_index = lines.index("---", 1)
except ValueError as error:
    raise RuntimeError("SKILL.md frontmatter is not closed") from error
frontmatter = lines[1:close_index]
name_values = [yaml_scalar(line.split(":", 1)[1]) for line in frontmatter if line.startswith("name:")]
description_values = [yaml_scalar(line.split(":", 1)[1]) for line in frontmatter if line.startswith("description:")]
if name_values != ["clone-software"] or len(description_values) != 1 or description_values[0] is None:
    raise RuntimeError("SKILL.md must declare exact name clone-software and one nonempty description")

agent_text = (root / "agents/openai.yaml").read_text(encoding="utf-8")
if not re.search(r"(?m)^interface:\s*$", agent_text):
    raise RuntimeError("agents/openai.yaml must declare interface")
agent_values = {}
for field in ("display_name", "short_description", "default_prompt"):
    matches = re.findall(rf"(?m)^\s{{2}}{field}:\s*(.*?)\s*$", agent_text)
    scalar = yaml_scalar(matches[0]) if len(matches) == 1 else None
    if scalar is None:
        raise RuntimeError(f"agents/openai.yaml has no nonempty interface.{field}")
    agent_values[field] = scalar
if "$clone-software" not in agent_values["default_prompt"]:
    raise RuntimeError("agents/openai.yaml default prompt must invoke $clone-software")

catalog = json.loads((root / "assets/scaffolds/catalog.json").read_text(encoding="utf-8"))
if catalog.get("schema_version") != "clone-scaffold-catalog/v2":
    raise RuntimeError("scaffold catalog has an unexpected schema_version")
profiles = [item for item in catalog.get("profiles", []) if item.get("id") == "static-web-esm"]
if len(profiles) != 1:
    raise RuntimeError("scaffold catalog must contain exactly one static-web-esm profile")
profile = profiles[0]
expected_paths = [
    "README.md",
    "package.json",
    "index.html",
    "styles.css",
    "src/app.js",
    "tests/smoke.test.mjs",
]
expected_commands = {
    "setup": None,
    "test": ["npm", "test"],
    "build": None,
    "run": ["npm", "start"],
}
if profile.get("template") != "static-web-esm":
    raise RuntimeError("static-web-esm profile has an unexpected template")
if profile.get("required_paths") != expected_paths:
    raise RuntimeError("static-web-esm profile has unexpected required_paths")
if profile.get("commands") != expected_commands:
    raise RuntimeError("static-web-esm profile has unexpected commands")

allowlist_profiles = [
    item
    for item in catalog.get("profiles", [])
    if item.get("id") == "static-web-esm-allowlist"
]
if len(allowlist_profiles) != 1:
    raise RuntimeError(
        "scaffold catalog must contain exactly one static-web-esm-allowlist profile"
    )
allowlist_profile = allowlist_profiles[0]
allowlist_expected_paths = [
    "README.md",
    "package.json",
    "index.html",
    "styles.css",
    "src/app.js",
    "tests/smoke.test.mjs",
    "tools/serve_static.py",
    "serve_manifest.json",
]
if allowlist_profile.get("template") != "static-web-esm-allowlist":
    raise RuntimeError("static-web-esm-allowlist profile has an unexpected template")
if allowlist_profile.get("required_paths") != allowlist_expected_paths:
    raise RuntimeError("static-web-esm-allowlist profile has unexpected required_paths")
if allowlist_profile.get("commands") != expected_commands:
    raise RuntimeError("static-web-esm-allowlist profile has unexpected commands")

allowlist_root = root / "assets/scaffolds/static-web-esm-allowlist"
allowlist_package = json.loads(
    (allowlist_root / "package.json").read_text(encoding="utf-8")
)
allowlist_scripts = allowlist_package.get("scripts")
expected_start = (
    "python3 tools/serve_static.py --manifest serve_manifest.json "
    "--bind 127.0.0.1 --port 8000"
)
if (
    not isinstance(allowlist_scripts, dict)
    or allowlist_scripts.get("start") != expected_start
):
    raise RuntimeError(
        "static-web-esm-allowlist package has an unexpected scripts.start"
    )

serve_manifest = json.loads(
    (allowlist_root / "serve_manifest.json").read_text(encoding="utf-8")
)
expected_serve_manifest = {
    "schema_version": "allowlisted-static-server-manifest/v1",
    "routes": {
        "/": "index.html",
        "/styles.css": "styles.css",
        "/src/app.js": "src/app.js",
    },
}
if serve_manifest != expected_serve_manifest:
    raise RuntimeError("static-web-esm-allowlist has an unexpected serve_manifest")
PY
}

git_checkout_state() {
  local root="$1"
  local head
  local branch
  if ! head="$(git -C "$root" rev-parse --verify HEAD)"; then
    return 1
  fi
  if branch="$(git -C "$root" symbolic-ref --quiet --short HEAD)"; then
    printf 'head=%s;branch=%s\n' "$head" "$branch"
    return
  fi
  local branch_exit=$?
  [[ "$branch_exit" -eq 1 ]] || return "$branch_exit"
  printf 'head=%s;detached=true\n' "$head"
}

verify_checkout_unchanged() {
  local phase="$1"
  local observed_status
  local observed_state
  local observed_identity
  if ! observed_status="$(git -C "$project_stage" status --porcelain=v1 --untracked-files=all --ignored=matching)"; then
    die 4 "INSTALL_CHECKOUT_MUTATED" \
      "could not inspect the checkout during $phase"
  fi
  if ! observed_state="$(git_checkout_state "$project_stage")"; then
    die 4 "INSTALL_CHECKOUT_MUTATED" \
      "could not resolve HEAD and branch state during $phase"
  fi
  if ! validate_install_tree "$project_stage"; then
    die 4 "INSTALL_CHECKOUT_MUTATED" \
      "install-tree semantics changed during $phase"
  fi
  if ! observed_identity="$(checkout_identity "$project_stage")"; then
    die 4 "INSTALL_CHECKOUT_MUTATED" \
      "the checkout became unreadable, unsupported, or concurrently changed during $phase"
  fi
  if [[ -n "$observed_status" || "$observed_state" != "$checkout_state" || \
        "$observed_identity" != "$initial_checkout_identity" ]]; then
    die 4 "INSTALL_CHECKOUT_MUTATED" \
      "checkout bytes, modes, paths, ignored state, Git metadata, HEAD, or branch changed during $phase"
  fi
  verified_checkout_identity="$observed_identity"
}

create_staged_workspace() {
  python3 - "$owned_stage" "$owned_stage_identity" \
    "$project_stage/$PROMPT_SOURCE" "$PROMPT_DESTINATION" <<'PY'
from __future__ import annotations

import os
import stat
import sys


stage_path, expected_identity, source_path, prompt_name = sys.argv[1:]
directory_flags = os.O_RDONLY | os.O_DIRECTORY
file_read_flags = os.O_RDONLY
file_write_flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
if hasattr(os, "O_NOFOLLOW"):
    directory_flags |= os.O_NOFOLLOW
    file_read_flags |= os.O_NOFOLLOW
    file_write_flags |= os.O_NOFOLLOW


def identity(value: os.stat_result) -> str:
    return f"{value.st_dev}:{value.st_ino}"


stage_fd = os.open(stage_path, directory_flags)
try:
    if identity(os.fstat(stage_fd)) != expected_identity:
        raise RuntimeError("staging directory identity changed")
    os.mkdir("minecraft-clone", mode=0o755, dir_fd=stage_fd)
    workspace_fd = os.open("minecraft-clone", directory_flags, dir_fd=stage_fd)
    try:
        os.mkdir(".agents", mode=0o755, dir_fd=workspace_fd)
        agents_fd = os.open(".agents", directory_flags, dir_fd=workspace_fd)
        try:
            os.mkdir("skills", mode=0o755, dir_fd=agents_fd)
            skills_fd = os.open("skills", directory_flags, dir_fd=agents_fd)
            try:
                os.symlink("../../../clone-software", "clone-software", dir_fd=skills_fd)
            finally:
                os.close(skills_fd)

            source_fd = os.open(source_path, file_read_flags)
            try:
                if not stat.S_ISREG(os.fstat(source_fd).st_mode):
                    raise RuntimeError("prompt source is not a regular file")
                destination_fd = os.open(prompt_name, file_write_flags, 0o644, dir_fd=workspace_fd)
                try:
                    while True:
                        chunk = os.read(source_fd, 1024 * 1024)
                        if not chunk:
                            break
                        view = memoryview(chunk)
                        while view:
                            written = os.write(destination_fd, view)
                            view = view[written:]
                    os.fsync(destination_fd)
                finally:
                    os.close(destination_fd)
            finally:
                os.close(source_fd)
        finally:
            os.close(agents_fd)
    finally:
        os.close(workspace_fd)
finally:
    os.close(stage_fd)
PY
}

validate_staged_handoff() {
  local inventory_after
  local inventory_before
  if ! inventory_before="$(workspace_inventory_json "$workspace_stage")"; then
    return 1
  fi
  if ! python3 - "$owned_stage" "$owned_stage_identity" "$PROMPT_SOURCE" \
    "$PROMPT_DESTINATION" "$repository_url" "$requested_ref" "$resolved_head" \
    "$checkout_state" "$receipt_checkout_identity" "$project_final" \
    "$workspace_final" "$skill_link_final" "$prompt_final" "$prompt_sha256" \
    "$verification" "$codex_resolved" "$inventory_before" <<'PY'
from __future__ import annotations

import hashlib
import json
import os
import stat
import sys
from pathlib import Path


(
    stage_text,
    expected_stage_identity,
    prompt_source,
    prompt_name,
    source_url,
    requested_ref,
    resolved_head,
    checkout_state,
    checkout_identity,
    project_final,
    workspace_final,
    skill_link_final,
    prompt_final,
    prompt_sha256,
    verification,
    codex_executable,
    installed_workspace_inventory_json,
) = sys.argv[1:]
stage = Path(stage_text)


def identity(value: os.stat_result) -> str:
    return f"{value.st_dev}:{value.st_ino}"


def require_directory(path: Path) -> None:
    if not stat.S_ISDIR(path.lstat().st_mode):
        raise RuntimeError(f"not a non-symlink directory: {path}")


def require_regular(path: Path) -> bytes:
    if not stat.S_ISREG(path.lstat().st_mode):
        raise RuntimeError(f"not a regular file: {path}")
    return path.read_bytes()


if identity(stage.lstat()) != expected_stage_identity:
    raise RuntimeError("staging directory identity changed")
if {entry.name for entry in os.scandir(stage)} != {
    "clone-software",
    "minecraft-clone",
    "installation-receipt.json",
}:
    raise RuntimeError("staging root inventory changed")

project = stage / "clone-software"
workspace = stage / "minecraft-clone"
require_directory(project)
require_directory(workspace)
if {entry.name for entry in os.scandir(workspace)} != {".agents", prompt_name}:
    raise RuntimeError("workspace inventory changed")
agents = workspace / ".agents"
skills = agents / "skills"
require_directory(agents)
require_directory(skills)
if {entry.name for entry in os.scandir(agents)} != {"skills"}:
    raise RuntimeError(".agents inventory changed")
if {entry.name for entry in os.scandir(skills)} != {"clone-software"}:
    raise RuntimeError("skills inventory changed")

skill_link = skills / "clone-software"
if not stat.S_ISLNK(skill_link.lstat().st_mode):
    raise RuntimeError("workspace skill entry is not a symlink")
if os.readlink(skill_link) != "../../../clone-software":
    raise RuntimeError("workspace skill link text changed")
if skill_link.resolve(strict=True) != project.resolve(strict=True):
    raise RuntimeError("workspace skill link target changed")

prompt_bytes = require_regular(workspace / prompt_name)
source_prompt_bytes = require_regular(project / prompt_source)
if prompt_bytes != source_prompt_bytes:
    raise RuntimeError("copied prompt differs from the verified project prompt")
if hashlib.sha256(prompt_bytes).hexdigest() != prompt_sha256:
    raise RuntimeError("copied prompt digest changed")

expected_receipt = {
    "schema_version": "clone-software-wsl-test-install/v2",
    "source_url": source_url,
    "requested_ref": requested_ref,
    "resolved_head": resolved_head,
    "checkout_state": checkout_state,
    "checkout_identity_sha256": checkout_identity,
    "project_dir": project_final,
    "workspace_dir": workspace_final,
    "skill_link": skill_link_final,
    "prompt_path": prompt_final,
    "prompt_sha256": prompt_sha256,
    "verification": verification,
    "codex_executable": codex_executable,
    "installed_workspace_inventory": json.loads(installed_workspace_inventory_json),
}
expected_bytes = (
    json.dumps(expected_receipt, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    + "\n"
).encode("utf-8")
receipt_bytes = require_regular(stage / "installation-receipt.json")
if receipt_bytes != expected_bytes:
    raise RuntimeError("installation receipt bytes changed or are noncanonical")
PY
  then
    return 1
  fi
  if ! inventory_after="$(workspace_inventory_json "$workspace_stage")"; then
    return 1
  fi
  if [[ "$inventory_after" != "$inventory_before" ]]; then
    diagnostic "INSTALL_HANDOFF_MUTATED" \
      "workspace inventory changed during final handoff validation"
    return 1
  fi
}

while (($# > 0)); do
  case "$1" in
    --destination)
      (($# >= 2)) || die 2 "INSTALL_USAGE" "--destination requires one value"
      destination="$2"
      shift 2
      ;;
    --repo-url)
      (($# >= 2)) || die 2 "INSTALL_USAGE" "--repo-url requires one value"
      repository_url="$2"
      shift 2
      ;;
    --ref)
      (($# >= 2)) || die 2 "INSTALL_USAGE" "--ref requires one value"
      requested_ref="$2"
      shift 2
      ;;
    --verify)
      (($# >= 2)) || die 2 "INSTALL_USAGE" "--verify requires one value"
      verification="$2"
      shift 2
      ;;
    --codex-bin)
      (($# >= 2)) || die 2 "INSTALL_USAGE" "--codex-bin requires one value"
      codex_bin="$2"
      shift 2
      ;;
    --allow-non-wsl)
      allow_non_wsl=1
      shift
      ;;
    --trust-custom-source-code)
      trust_custom_source_code=1
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      die 2 "INSTALL_USAGE" "unknown argument: $1"
      ;;
  esac
done

[[ -n "$destination" ]] || die 2 "INSTALL_USAGE" "--destination is required"
[[ "$destination" == /* ]] || die 2 "INSTALL_PATH_INVALID" "--destination must be absolute"
[[ -n "$repository_url" ]] || die 2 "INSTALL_USAGE" "--repo-url must not be empty"
[[ -n "$requested_ref" ]] || die 2 "INSTALL_USAGE" "--ref must not be empty"
if [[ "$repository_url" != "$DEFAULT_REPOSITORY_URL" && "$trust_custom_source_code" -ne 1 ]]; then
  die 2 "INSTALL_SOURCE_TRUST_REQUIRED" \
    "a non-default --repo-url requires --trust-custom-source-code"
fi
[[ "$verification" == "smoke" || "$verification" == "full" ]] || \
  die 2 "INSTALL_USAGE" "--verify must be smoke or full"
[[ "$destination" != *$'\n'* && "$repository_url" != *$'\n'* && \
   "$requested_ref" != *$'\n'* && "$codex_bin" != *$'\n'* ]] || \
  die 2 "INSTALL_ARGUMENT_INVALID" "arguments must not contain newlines"

for required_command in uname realpath dirname basename mktemp git python3 node npm mv stat; do
  command -v "$required_command" >/dev/null 2>&1 || \
    die 7 "INSTALL_EXECUTABLE_MISSING" "required executable is unavailable: $required_command"
done

if ! kernel_name="$(uname -s)"; then
  die 7 "INSTALL_EXECUTABLE_FAILURE" "uname failed while reading the kernel name"
fi
[[ "$kernel_name" == "Linux" ]] || \
  die 3 "INSTALL_PLATFORM_UNSUPPORTED" "Linux is required; observed kernel name: $kernel_name"
if ! kernel_release="$(uname -r)"; then
  die 7 "INSTALL_EXECUTABLE_FAILURE" "uname failed while reading the kernel release"
fi
if ((allow_non_wsl == 0)); then
  shopt -s nocasematch
  [[ "$kernel_release" == *microsoft* ]] || \
    die 3 "INSTALL_PLATFORM_UNSUPPORTED" "WSL is required; observed kernel release: $kernel_release"
  shopt -u nocasematch
fi

python3 -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)' || \
  die 7 "INSTALL_PYTHON_UNSUPPORTED" "Python 3.10 or later is required"

python3 -c '
import sys

value = sys.argv[1]
unsafe = "?" in value or "#" in value or any(ord(character) < 32 or ord(character) == 127 for character in value)
raise SystemExit(1 if unsafe else 0)
' "$repository_url" || \
  die 2 "INSTALL_SOURCE_UNSAFE" \
    "repository sources must not contain query, fragment, or control characters"

if [[ "$repository_url" == *://* ]]; then
  python3 -c '
import sys
from urllib.parse import urlsplit

source = urlsplit(sys.argv[1])
unsafe = bool(source.username or source.password or source.query or source.fragment)
raise SystemExit(1 if unsafe else 0)
' "$repository_url" || \
    die 2 "INSTALL_SOURCE_UNSAFE" \
      "repository URLs must not contain userinfo, credentials, query text, or fragments"
elif [[ "$repository_url" =~ ^[^/@:]+@[^/:]+:.+ ]]; then
  die 2 "INSTALL_SOURCE_UNSAFE" \
    "SCP-style repository URLs with user information are not accepted"
fi

node_major="$(node -p 'Number(process.versions.node.split(".")[0])' 2>/dev/null)" || \
  die 7 "INSTALL_NODE_UNAVAILABLE" "Node.js could not report its version"
[[ "$node_major" =~ ^[0-9]+$ ]] || \
  die 7 "INSTALL_NODE_UNAVAILABLE" "Node.js returned an invalid major version: $node_major"
((node_major >= 18)) || \
  die 7 "INSTALL_NODE_UNSUPPORTED" "Node.js 18 or later is required; observed major: $node_major"
npm --version >/dev/null 2>&1 || \
  die 7 "INSTALL_NPM_UNAVAILABLE" "npm could not report its version"

codex_resolved="$(resolve_executable "$codex_bin")" || \
  die 7 "INSTALL_CODEX_UNAVAILABLE" "Codex executable is unavailable: $codex_bin"

if ! destination="$(realpath -m -s -- "$destination")"; then
  die 2 "INSTALL_PATH_INVALID" "could not normalize destination lexically"
fi
[[ "$destination" != "/" ]] || \
  die 2 "INSTALL_PATH_INVALID" "filesystem root is not a legal destination"
if [[ -L "$destination" ]]; then
  die 4 "DESTINATION_SYMLINK" "destination must not be a symlink: $destination"
fi
if [[ -e "$destination" ]]; then
  die 4 "DESTINATION_EXISTS" "destination must be absent: $destination"
fi

if ! destination_parent="$(dirname -- "$destination")"; then
  die 7 "INSTALL_EXECUTABLE_FAILURE" "dirname failed while resolving destination"
fi
if ! destination_name="$(basename -- "$destination")"; then
  die 7 "INSTALL_EXECUTABLE_FAILURE" "basename failed while resolving destination"
fi
[[ "$destination_name" != "." && "$destination_name" != ".." ]] || \
  die 2 "INSTALL_PATH_INVALID" "destination basename is invalid: $destination_name"
reject_symlinked_directory_path "$destination_parent"
[[ -d "$destination_parent" && ! -L "$destination_parent" ]] || \
  die 6 "INSTALL_DESTINATION_FAILURE" \
    "destination parent must already exist as a non-symlink directory: $destination_parent"
reject_symlinked_directory_path "$destination_parent"
if ! preopen_parent_identity="$(stat -Lc '%d:%i' -- "$destination_parent" 2>/dev/null)"; then
  die 6 "INSTALL_DESTINATION_FAILURE" \
    "could not identify the destination parent before binding: $destination_parent"
fi
if ! exec {destination_parent_fd}<"$destination_parent"; then
  die 6 "INSTALL_DESTINATION_FAILURE" \
    "could not open and bind the destination parent: $destination_parent"
fi
destination_parent_anchor="/proc/$$/fd/$destination_parent_fd"
if ! destination_parent_identity="$(stat -Lc '%d:%i' -- "$destination_parent_anchor")"; then
  die 6 "INSTALL_DESTINATION_FAILURE" \
    "could not identify the bound destination parent: $destination_parent"
fi
if ! postopen_parent_identity="$(stat -Lc '%d:%i' -- "$destination_parent" 2>/dev/null)"; then
  die 4 "INSTALL_DESTINATION_PARENT_CHANGED" \
    "destination parent disappeared while it was being bound: $destination_parent"
fi
if [[ "$preopen_parent_identity" != "$destination_parent_identity" || \
      "$postopen_parent_identity" != "$destination_parent_identity" ]]; then
  die 4 "INSTALL_DESTINATION_PARENT_CHANGED" \
    "destination parent changed while it was being bound"
fi
assert_destination_parent_binding
if [[ -L "$destination" ]]; then
  die 4 "DESTINATION_SYMLINK" "destination appeared as a symlink: $destination"
fi
if [[ -e "$destination" ]]; then
  die 4 "DESTINATION_EXISTS" "destination appeared before installation: $destination"
fi
check_duplicate_skill_discovery
assert_destination_parent_binding

trap cleanup_owned_stage EXIT
trap 'unexpected_error $? $LINENO' ERR

owned_stage="$(mktemp -d -- "$destination_parent_anchor/.clone-software-wsl-install.XXXXXXXX")" || \
  die 6 "INSTALL_DESTINATION_FAILURE" "could not create owned staging directory"
owned_stage_name="${owned_stage##*/}"
owned_stage_identity="$(stat -Lc '%d:%i' -- "$owned_stage")" || \
  die 6 "INSTALL_DESTINATION_FAILURE" "could not identify owned staging directory"
assert_destination_parent_binding
project_stage="$owned_stage/clone-software"
workspace_stage="$owned_stage/minecraft-clone"

if ! git clone --quiet --no-hardlinks --branch "$requested_ref" --single-branch -- \
  "$repository_url" "$project_stage"; then
  die 7 "INSTALL_CLONE_BLOCKED" "git could not clone ref '$requested_ref' from '$repository_url'"
fi

required_files=(
  "LICENSE"
  "SKILL.md"
  "agents/openai.yaml"
  "scripts/clone_pack.py"
  "scripts/run_skill_tests.py"
  "$PROMPT_SOURCE"
  "assets/scaffolds/catalog.json"
  "references/evidence-and-fidelity.md"
  "references/document-contracts.md"
  "references/greenfield.md"
  "references/game-simulation.md"
  "references/security-and-provenance.md"
  "references/pack-evolution.md"
  "assets/scaffolds/static-web-esm/README.md"
  "assets/scaffolds/static-web-esm/package.json"
  "assets/scaffolds/static-web-esm/index.html"
  "assets/scaffolds/static-web-esm/styles.css"
  "assets/scaffolds/static-web-esm/src/app.js"
  "assets/scaffolds/static-web-esm/tests/smoke.test.mjs"
  "assets/scaffolds/static-web-esm-allowlist/README.md"
  "assets/scaffolds/static-web-esm-allowlist/package.json"
  "assets/scaffolds/static-web-esm-allowlist/index.html"
  "assets/scaffolds/static-web-esm-allowlist/styles.css"
  "assets/scaffolds/static-web-esm-allowlist/src/app.js"
  "assets/scaffolds/static-web-esm-allowlist/tests/smoke.test.mjs"
  "assets/scaffolds/static-web-esm-allowlist/tools/serve_static.py"
  "assets/scaffolds/static-web-esm-allowlist/serve_manifest.json"
)
for relative_path in "${required_files[@]}"; do
  candidate="$project_stage/$relative_path"
  if [[ ! -f "$candidate" || -L "$candidate" ]]; then
    die 4 "INSTALL_ASSET_MISSING" "required regular non-symlink file is absent: $relative_path"
  fi
done

if ! checkout_identity "$project_stage" >/dev/null; then
  die 4 "INSTALL_TREE_INVALID" \
    "the cloned checkout contains a symlink, special file, unreadable path, or concurrent mutation"
fi
if ! validate_install_tree "$project_stage"; then
  die 4 "INSTALL_TREE_INVALID" \
    "the cloned checkout does not satisfy the installable skill and scaffold contract"
fi
if ! checkout_state="$(git_checkout_state "$project_stage")"; then
  die 4 "INSTALL_GIT_INVALID" "cloned checkout has no stable HEAD and branch state"
fi
resolved_head="${checkout_state#head=}"
resolved_head="${resolved_head%%;*}"
if ! initial_status="$(git -C "$project_stage" status --porcelain=v1 --untracked-files=all --ignored=matching)"; then
  die 4 "INSTALL_GIT_INVALID" "could not inspect the fresh cloned checkout"
fi
[[ -z "$initial_status" ]] || \
  die 4 "INSTALL_GIT_DIRTY" "fresh cloned checkout is not clean"
if ! initial_checkout_identity="$(checkout_identity "$project_stage")"; then
  die 4 "INSTALL_TREE_INVALID" "could not bind the complete fresh checkout identity"
fi

if ! help_output="$(PYTHONDONTWRITEBYTECODE=1 python3 "$project_stage/scripts/clone_pack.py" --help)"; then
  die 4 "INSTALL_SMOKE_FAILED" "clone_pack.py --help did not exit 0"
fi
commands=(
  init validate migrate capture parity scaffold record-run record-manual gap-transition
  assure seal diff enhancement-init repo-snapshot baseline-run regression verify-scope
  enhancement-transition rehash
)
for command_name in "${commands[@]}"; do
  command_pattern="(^|[{},[:space:]])${command_name}($|[{},[:space:]])"
  [[ "$help_output" =~ $command_pattern ]] || \
    die 4 "INSTALL_COMMAND_MISSING" "clone_pack.py --help omitted command: $command_name"
done

if [[ "$verification" == "full" ]]; then
  if ! (
    cd "$project_stage"
    PYTHONDONTWRITEBYTECODE=1 python3 scripts/run_skill_tests.py
  ); then
    die 4 "INSTALL_FULL_VERIFICATION_FAILED" "the cloned offline regression suite failed"
  fi
fi

verify_checkout_unchanged "post-verification check"

if ! create_staged_workspace; then
  die 6 "INSTALL_DESTINATION_FAILURE" \
    "could not create the descriptor-anchored staged workspace"
fi
if ! resolved_skill_link="$(realpath -- "$workspace_stage/.agents/skills/clone-software")"; then
  die 4 "INSTALL_SKILL_LINK_INVALID" "the staged skill link cannot be resolved"
fi
if ! resolved_project_stage="$(realpath -- "$project_stage")"; then
  die 4 "INSTALL_SKILL_LINK_INVALID" "the staged project cannot be resolved"
fi
[[ "$resolved_skill_link" == "$resolved_project_stage" ]] || \
  die 4 "INSTALL_SKILL_LINK_INVALID" "the staged skill link does not resolve to the cloned project"

prompt_sha256="$(python3 -c \
  'import hashlib,os,stat,sys
flags = os.O_RDONLY | (os.O_NOFOLLOW if hasattr(os, "O_NOFOLLOW") else 0)
descriptor = os.open(sys.argv[1], flags)
with os.fdopen(descriptor, "rb") as handle:
    observed = os.fstat(handle.fileno())
    if not stat.S_ISREG(observed.st_mode):
        raise SystemExit(1)
    print(hashlib.sha256(handle.read()).hexdigest())' \
  "$workspace_stage/$PROMPT_DESTINATION")" || \
  die 4 "INSTALL_PROMPT_HASH_FAILED" "could not hash the copied prompt"

verify_checkout_unchanged "pre-receipt check"
receipt_checkout_identity="$verified_checkout_identity"

project_final="$destination/clone-software"
workspace_final="$destination/minecraft-clone"
prompt_final="$workspace_final/$PROMPT_DESTINATION"
skill_link_final="$workspace_final/.agents/skills/clone-software"

if ! installed_workspace_inventory_json="$(workspace_inventory_json "$workspace_stage")"; then
  die 4 "INSTALL_HANDOFF_MUTATED" \
    "could not capture the complete staged workspace inventory"
fi

python3 -c '
import json
import os
import sys

keys = (
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
)
receipt = {
    "schema_version": "clone-software-wsl-test-install/v2",
    **dict(zip(keys, sys.argv[3:15])),
    "installed_workspace_inventory": json.loads(sys.argv[15]),
}
directory_flags = os.O_RDONLY | os.O_DIRECTORY
flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
if hasattr(os, "O_NOFOLLOW"):
    directory_flags |= os.O_NOFOLLOW
    flags |= os.O_NOFOLLOW
stage_fd = os.open(sys.argv[1], directory_flags)
observed = os.fstat(stage_fd)
if f"{observed.st_dev}:{observed.st_ino}" != sys.argv[2]:
    os.close(stage_fd)
    raise SystemExit(1)
descriptor = os.open("installation-receipt.json", flags, 0o600, dir_fd=stage_fd)
os.close(stage_fd)
with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
    json.dump(receipt, handle, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    handle.write("\n")
' "$owned_stage" "$owned_stage_identity" \
  "$repository_url" "$requested_ref" "$resolved_head" "$checkout_state" \
  "$receipt_checkout_identity" "$project_final" \
  "$workspace_final" "$skill_link_final" "$prompt_final" "$prompt_sha256" \
  "$verification" "$codex_resolved" "$installed_workspace_inventory_json" || \
  die 6 "INSTALL_RECEIPT_FAILURE" "could not write the installation receipt"

verify_checkout_unchanged "pre-publish check"
if [[ "$verified_checkout_identity" != "$receipt_checkout_identity" ]]; then
  die 4 "INSTALL_CHECKOUT_MUTATED" \
    "the receipt checkout identity is stale before publication"
fi
if ! validate_staged_handoff; then
  die 4 "INSTALL_HANDOFF_MUTATED" \
    "the staged root, prompt, skill link, or canonical receipt changed before publication"
fi

assert_destination_parent_binding
anchored_destination="$destination_parent_anchor/$destination_name"
if [[ -e "$anchored_destination" || -L "$anchored_destination" || \
      -e "$destination" || -L "$destination" ]]; then
  die 4 "DESTINATION_EXISTS" "destination appeared during installation and was not replaced: $destination"
fi
if ! mv -T -n -- "$owned_stage" "$anchored_destination"; then
  die 6 "INSTALL_DESTINATION_FAILURE" "could not publish the staged installation: $destination"
fi
if ! published_identity="$(stat -Lc '%d:%i' -- "$anchored_destination" 2>/dev/null)"; then
  die 6 "INSTALL_DESTINATION_FAILURE" \
    "published destination could not be identified: $destination"
fi
if [[ "$published_identity" != "$owned_stage_identity" ]]; then
  die 4 "DESTINATION_EXISTS" "destination appeared during publish and was not replaced: $destination"
fi
published_stage_path="$owned_stage"
owned_stage=""
owned_stage_identity=""
if [[ -e "$published_stage_path" || -L "$published_stage_path" ]]; then
  die 4 "STAGE_CLEANUP_REFUSED" \
    "the former staging pathname was replaced during publish and was not removed: $published_stage_path"
fi
assert_destination_parent_binding
if [[ -L "$destination" || ! -d "$destination" ]]; then
  die 4 "INSTALL_DESTINATION_PARENT_CHANGED" \
    "published destination is no longer reachable through the requested non-symlink path: $destination"
fi
if ! requested_destination_identity="$(stat -Lc '%d:%i' -- "$destination" 2>/dev/null)"; then
  die 4 "INSTALL_DESTINATION_PARENT_CHANGED" \
    "could not identify the requested destination after publish: $destination"
fi
if [[ "$requested_destination_identity" != "$published_identity" ]]; then
  die 4 "INSTALL_DESTINATION_PARENT_CHANGED" \
    "requested destination identity differs from the bound published directory"
fi

printf 'clone-software WSL test installation complete\n'
printf 'project_dir=%s\n' "$project_final"
printf 'workspace_dir=%s\n' "$workspace_final"
printf 'prompt_file=%s\n' "$prompt_final"
printf 'receipt_file=%s\n' "$destination/installation-receipt.json"
printf 'resolved_head=%s\n' "$resolved_head"
printf 'verification=%s\n' "$verification"
printf '\nNext commands in this WSL terminal:\n'
printf '  cd -- %q\n' "$workspace_final"
printf '  %q\n' "$codex_resolved"
printf '\nInside Codex:\n'
printf '  1. Run /skills and confirm clone-software is listed.\n'
printf '  2. Paste: Use $clone-software. Read ./MINECRAFT_CLONE_PROMPT.md completely and execute it exactly.\n'
