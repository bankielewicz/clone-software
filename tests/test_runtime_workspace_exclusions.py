from __future__ import annotations

import copy
import json
import os
import stat
import subprocess
import tempfile
import unittest
from pathlib import Path
from typing import Any
from unittest import mock

from scripts.clonepack import repository as repository_module
from scripts.clonepack.common import ClonePackError, canonical_json, sha256_bytes
from scripts.clonepack.enhancement import initialize_enhancement_v2
from scripts.clonepack.repository import (
    build_repository_snapshot,
    check_repository_snapshot,
    record_repository_snapshot,
)
from scripts.clonepack.schema import validate_schema_file


ROOT = Path(__file__).resolve().parents[1]
INVENTORY_SCHEMA = ROOT / "assets" / "schemas" / "repository-inventory-v2.schema.json"
SNAPSHOT_SCHEMA = ROOT / "assets" / "schemas" / "repository-snapshot-v2.schema.json"
CAPTURE_SCHEMA = ROOT / "assets" / "schemas" / "capture-plan-v2.schema.json"
PINNED_TIMESTAMP = "2026-07-20T12:00:00+00:00"


def run_git(repository: Path, *arguments: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(repository), *arguments],
        check=False,
        text=True,
        encoding="utf-8",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise AssertionError(f"expected object: {path}")
    return value


def write_json(path: Path, value: Any) -> None:
    path.write_text(canonical_json(value), encoding="utf-8", newline="\n")


def index_record(identifier: str, kind: str) -> dict[str, Any]:
    return {
        "id": identifier,
        "kind": kind,
        "locator": {"path": "clone_brief.md", "anchor": None, "sha256": None},
        "links": {},
        "applicability": "MVP",
        "state": "READY",
        "attributes": {},
    }


def runtime_exclusion(path: Path, repository: Path, *, identifier: str = "RUNTIME-001") -> dict[str, object]:
    metadata = path.lstat()
    return {
        "id": identifier,
        "path": path.relative_to(repository).as_posix(),
        "reason": "User-authorized empty tool-runtime directory excluded from product identity.",
        "authority_ids": ["DEC-004"],
        "kind": "tool-runtime",
        "evidence_ids": ["E-004"],
        "pre_session_presence": False,
        "expected_identity": {
            "type": "directory",
            "device": metadata.st_dev,
            "inode": metadata.st_ino,
            "mode": stat.S_IMODE(metadata.st_mode),
            "empty": True,
        },
    }


def minimal_inventory(exclusions: list[dict[str, object]]) -> dict[str, object]:
    return {
        "schema_version": "clone-repository-inventory/v2",
        "pack_id": "PACK-001",
        "pack_revision": 1,
        "enhancement_id": "ENH-001",
        "inspected_at": PINNED_TIMESTAMP,
        "repository_root": "/tmp/repository",
        "repository_kind": "filesystem",
        "git": None,
        "entries": [],
        "dirty_paths": [],
        "protected_dirty_paths": [],
        "agents_files": [],
        "scope_roots": ["."],
        "exclusions": exclusions,
        "instructions": [],
        "components": [],
        "entrypoints": [],
        "public_interfaces": [],
        "data_stores": [],
        "configuration": [],
        "background_jobs": [],
        "manifests": [],
        "lockfiles": [],
        "ci_surfaces": [],
        "deployment_surfaces": [],
        "telemetry": [],
        "verification_commands": [],
        "unknowns": [],
        "adoption_blockers": [],
    }


class RuntimeWorkspaceExclusionTests(unittest.TestCase):
    maxDiff = None

    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.repository = self.root / "repository"
        self.repository.mkdir()
        (self.repository / "product.txt").write_text("product\n", encoding="utf-8", newline="\n")

    def make_runtime_directory(self, name: str = ".codex") -> Path:
        runtime = self.repository / name
        runtime.mkdir()
        runtime.chmod(0o555)
        return runtime

    def snapshot(self, exclusions: list[dict[str, object]], **kwargs: object) -> dict[str, object]:
        return build_repository_snapshot(
            self.repository,
            pack_root=self.root / "outside-pack",
            snapshot_id="SNAP-001",
            role="adopted",
            runtime_exclusions=exclusions,
            timestamp=PINNED_TIMESTAMP,
            **kwargs,
        )

    def test_schema_preserves_omitted_kind_and_requires_complete_tool_runtime_contract(self) -> None:
        legacy = {
            "id": "EXC-001",
            "path": "generated",
            "reason": " \x7f",
            "authority_ids": [],
        }
        self.assertEqual(validate_schema_file(minimal_inventory([legacy]), INVENTORY_SCHEMA), [])

        runtime = self.make_runtime_directory()
        governed = runtime_exclusion(runtime, self.repository)
        self.assertEqual(validate_schema_file(minimal_inventory([governed]), INVENTORY_SCHEMA), [])

        for field in ("evidence_ids", "pre_session_presence", "expected_identity"):
            with self.subTest(field=field):
                malformed = copy.deepcopy(governed)
                malformed.pop(field)
                pointers = {
                    violation.pointer
                    for violation in validate_schema_file(minimal_inventory([malformed]), INVENTORY_SCHEMA)
                }
                self.assertIn(f"/exclusions/0/{field}", pointers)

        no_authority = copy.deepcopy(governed)
        no_authority["authority_ids"] = []
        pointers = {
            violation.pointer
            for violation in validate_schema_file(minimal_inventory([no_authority]), INVENTORY_SCHEMA)
        }
        self.assertIn("/exclusions/0/authority_ids", pointers)

    def test_non_git_snapshot_binds_exclusion_separately_and_keeps_product_hash_product_only(self) -> None:
        baseline = build_repository_snapshot(
            self.repository,
            pack_root=self.root / "outside-pack",
            snapshot_id="SNAP-001",
            role="adopted",
            timestamp=PINNED_TIMESTAMP,
        )
        runtime = self.make_runtime_directory()
        governed = runtime_exclusion(runtime, self.repository)

        snapshot = self.snapshot([governed])

        self.assertEqual(snapshot["content_sha256"], baseline["content_sha256"])
        self.assertEqual(snapshot["runtime_exclusions"], [governed])
        self.assertEqual([entry["path"] for entry in snapshot["entries"]], ["product.txt"])
        self.assertEqual(validate_schema_file(snapshot, SNAPSHOT_SCHEMA), [])

    def test_runtime_exclusion_rejects_include_and_reserved_or_tracked_collisions(self) -> None:
        runtime = self.make_runtime_directory("runtime-cache")
        governed = runtime_exclusion(runtime, self.repository)
        with self.assertRaises(ClonePackError) as included:
            self.snapshot([governed], includes=["runtime-cache"])
        self.assertEqual(included.exception.diagnostic, "SNAPSHOT_INCLUDE_EXCLUDED")
        self.assertEqual(included.exception.exit_code, 4)

        (self.repository / ".git").mkdir()
        git_contract = runtime_exclusion(self.repository / ".git", self.repository)
        git_contract["expected_identity"]["mode"] = 0o555  # collision must win over writability
        with self.assertRaises(ClonePackError) as reserved:
            self.snapshot([git_contract])
        self.assertEqual(reserved.exception.diagnostic, "RUNTIME_EXCLUSION_COLLISION")
        self.assertEqual(reserved.exception.exit_code, 4)

        git_repository = self.root / "tracked-repository"
        git_repository.mkdir()
        initialized = run_git(git_repository, "init", "-q")
        self.assertEqual(initialized.returncode, 0, initialized.stderr)
        run_git(git_repository, "config", "user.name", "Runtime Fixture")
        run_git(git_repository, "config", "user.email", "runtime@example.invalid")
        tracked_runtime = git_repository / "runtime-cache"
        tracked_runtime.mkdir()
        tracked_file = tracked_runtime / "tracked.txt"
        tracked_file.write_text("tracked\n", encoding="utf-8", newline="\n")
        self.assertEqual(run_git(git_repository, "add", ".").returncode, 0)
        self.assertEqual(run_git(git_repository, "commit", "-q", "-m", "fixture").returncode, 0)
        tracked_file.unlink()
        tracked_runtime.chmod(0o555)
        tracked_contract = runtime_exclusion(tracked_runtime, git_repository)
        with self.assertRaises(ClonePackError) as tracked:
            build_repository_snapshot(
                git_repository,
                pack_root=self.root / "outside-pack",
                snapshot_id="SNAP-001",
                role="adopted",
                runtime_exclusions=[tracked_contract],
                timestamp=PINNED_TIMESTAMP,
            )
        self.assertEqual(tracked.exception.diagnostic, "RUNTIME_EXCLUSION_COLLISION")
        self.assertEqual(tracked.exception.exit_code, 4)

    def test_runtime_exclusion_rejects_writable_nonempty_symlink_and_identity_drift(self) -> None:
        writable = self.repository / "writable-runtime"
        writable.mkdir()
        writable_contract = runtime_exclusion(writable, self.repository)
        with self.assertRaises(ClonePackError) as writable_error:
            self.snapshot([writable_contract])
        self.assertEqual(writable_error.exception.diagnostic, "RUNTIME_EXCLUSION_WRITABLE")
        self.assertEqual(writable_error.exception.exit_code, 4)

        nonempty = self.make_runtime_directory("nonempty-runtime")
        nonempty_contract = runtime_exclusion(nonempty, self.repository)
        nonempty.chmod(0o755)
        (nonempty / "cache.bin").write_bytes(b"runtime")
        nonempty.chmod(0o555)
        with self.assertRaises(ClonePackError) as nonempty_error:
            self.snapshot([nonempty_contract])
        self.assertEqual(nonempty_error.exception.diagnostic, "RUNTIME_EXCLUSION_NOT_EMPTY")
        self.assertEqual(nonempty_error.exception.exit_code, 4)

        target = self.make_runtime_directory("runtime-target")
        target_contract = runtime_exclusion(target, self.repository)
        link = self.repository / "runtime-link"
        link.symlink_to(target, target_is_directory=True)
        symlink_contract = copy.deepcopy(target_contract)
        symlink_contract["path"] = "runtime-link"
        with self.assertRaises(ClonePackError) as symlink_error:
            self.snapshot([symlink_contract])
        self.assertEqual(symlink_error.exception.diagnostic, "RUNTIME_EXCLUSION_UNSAFE")
        self.assertEqual(symlink_error.exception.exit_code, 4)

        original = self.make_runtime_directory("replaced-runtime")
        stale_contract = runtime_exclusion(original, self.repository)
        stale_contract["expected_identity"]["inode"] += 1
        with self.assertRaises(ClonePackError) as identity_error:
            self.snapshot([stale_contract])
        self.assertEqual(identity_error.exception.diagnostic, "RUNTIME_EXCLUSION_IDENTITY_DRIFT")
        self.assertEqual(identity_error.exception.exit_code, 4)

    def test_snapshot_rechecks_runtime_directory_after_tree_walk(self) -> None:
        runtime = self.make_runtime_directory("zz-runtime")
        governed = runtime_exclusion(runtime, self.repository)
        original_entry = repository_module._entry_for_path

        def mutate_after_product(path: Path, repository: Path) -> dict[str, object] | None:
            entry = original_entry(path, repository)
            if path.name == "product.txt":
                runtime.chmod(0o755)
                (runtime / "late-cache").write_bytes(b"late")
                runtime.chmod(0o555)
            return entry

        with mock.patch(
            "scripts.clonepack.repository._entry_for_path",
            side_effect=mutate_after_product,
        ):
            with self.assertRaises(ClonePackError) as raised:
                self.snapshot([governed])

        self.assertIn(
            raised.exception.diagnostic,
            {"RUNTIME_EXCLUSION_IDENTITY_DRIFT", "RUNTIME_EXCLUSION_NOT_EMPTY"},
        )
        self.assertEqual(raised.exception.exit_code, 4)

    def test_missing_descriptor_capability_blocks_before_git_or_snapshot_collection(self) -> None:
        runtime = self.make_runtime_directory("runtime-capability")
        governed = runtime_exclusion(runtime, self.repository)
        (self.repository / ".git").mkdir()

        with mock.patch.object(
            repository_module,
            "RUNTIME_DESCRIPTOR_CAPABLE",
            False,
        ), mock.patch.object(
            repository_module,
            "_run_git",
            side_effect=AssertionError("Git collection must not run"),
        ) as git_collection, mock.patch.object(
            repository_module,
            "_walk_non_git",
            side_effect=AssertionError("filesystem collection must not run"),
        ) as filesystem_collection, mock.patch.object(
            repository_module,
            "_git_entries",
            side_effect=AssertionError("Git entry collection must not run"),
        ) as git_entries:
            with self.assertRaises(ClonePackError) as raised:
                self.snapshot([governed])

        self.assertEqual(raised.exception.diagnostic, "RUNTIME_EXCLUSION_CAPABILITY_MISSING")
        self.assertEqual(raised.exception.exit_code, 3)
        git_collection.assert_not_called()
        filesystem_collection.assert_not_called()
        git_entries.assert_not_called()

    @unittest.skipUnless(hasattr(os, "symlink"), "symlinks are unavailable")
    def test_runtime_validation_never_enumerates_a_final_directory_swapped_to_a_symlink(self) -> None:
        runtime = self.make_runtime_directory("runtime-final-race")
        governed = runtime_exclusion(runtime, self.repository)
        external = self.root / "external-final-target"
        external.mkdir()
        (external / "secret.txt").write_text("must not be enumerated\n", encoding="utf-8", newline="\n")
        original_lstat = Path.lstat
        original_open = repository_module.os.open
        original_scandir = repository_module.os.scandir
        swapped = False
        externally_enumerated: list[str] = []

        def swap_after_final_lstat(path: Path) -> os.stat_result:
            nonlocal swapped
            metadata = original_lstat(path)
            if path == runtime and not swapped:
                runtime.rmdir()
                runtime.symlink_to(external, target_is_directory=True)
                swapped = True
            return metadata

        def observe_scandir(path: os.PathLike[str] | str) -> object:
            entries = list(original_scandir(path))
            if isinstance(path, (str, os.PathLike)) and Path(path) == runtime and runtime.is_symlink():
                externally_enumerated.extend(entry.name for entry in entries)
            return iter(entries)

        def swap_before_final_open(path, flags, *args, **kwargs):
            nonlocal swapped
            if path == runtime.name and kwargs.get("dir_fd") is not None and not swapped:
                runtime.rmdir()
                runtime.symlink_to(external, target_is_directory=True)
                swapped = True
            return original_open(path, flags, *args, **kwargs)

        with mock.patch.object(Path, "lstat", swap_after_final_lstat), mock.patch.object(
            repository_module.os, "open", side_effect=swap_before_final_open
        ), mock.patch.object(repository_module.os, "scandir", side_effect=observe_scandir):
            with self.assertRaises(ClonePackError):
                repository_module.validate_runtime_exclusions(self.repository, [governed])

        self.assertEqual(
            externally_enumerated,
            [],
            "runtime validation followed the swapped symlink and enumerated external data",
        )

    @unittest.skipUnless(hasattr(os, "symlink"), "symlinks are unavailable")
    def test_runtime_validation_never_returns_a_binding_after_ancestor_symlink_swap(self) -> None:
        ancestor = self.repository / "runtime-parent"
        runtime = ancestor / "runtime"
        runtime.mkdir(parents=True)
        runtime.chmod(0o555)
        governed = runtime_exclusion(runtime, self.repository)
        moved_ancestor = self.root / "moved-runtime-parent"
        original_lstat = Path.lstat
        original_open = repository_module.os.open
        original_scandir = repository_module.os.scandir
        swapped = False
        followed_external_ancestor = False

        def swap_after_ancestor_lstat(path: Path) -> os.stat_result:
            nonlocal swapped
            metadata = original_lstat(path)
            if path == ancestor and not swapped:
                ancestor.rename(moved_ancestor)
                ancestor.symlink_to(moved_ancestor, target_is_directory=True)
                swapped = True
            return metadata

        def observe_scandir(path: os.PathLike[str] | str) -> object:
            nonlocal followed_external_ancestor
            if (
                isinstance(path, (str, os.PathLike))
                and Path(path) == runtime
                and Path(path).resolve().is_relative_to(moved_ancestor)
            ):
                followed_external_ancestor = True
            return original_scandir(path)

        def swap_before_ancestor_open(path, flags, *args, **kwargs):
            nonlocal swapped
            if path == ancestor.name and kwargs.get("dir_fd") is not None and not swapped:
                ancestor.rename(moved_ancestor)
                ancestor.symlink_to(moved_ancestor, target_is_directory=True)
                swapped = True
            return original_open(path, flags, *args, **kwargs)

        error: ClonePackError | None = None
        bindings: tuple[object, ...] = ()
        with mock.patch.object(Path, "lstat", swap_after_ancestor_lstat), mock.patch.object(
            repository_module.os, "open", side_effect=swap_before_ancestor_open
        ), mock.patch.object(repository_module.os, "scandir", side_effect=observe_scandir):
            try:
                bindings = repository_module.validate_runtime_exclusions(self.repository, [governed])
            except ClonePackError as exc:
                error = exc

        self.assertEqual(
            (error is not None, bool(bindings), followed_external_ancestor),
            (True, False, False),
            "runtime validation followed a swapped ancestor and returned a live binding",
        )
        if error is not None:
            self.assertEqual(error.exit_code, 4)

    def test_snapshot_record_requires_governed_user_authority_and_evidence(self) -> None:
        cases = (
            ("unresolved-authority", "DEC-MISSING", "E-004", {"E-004": "E"}),
            ("wrong-authority-kind", "DEC-004", "E-004", {"DEC-004": "E", "E-004": "E"}),
            ("unresolved-evidence", "DEC-004", "E-MISSING", {"DEC-004": "DEC"}),
            ("wrong-evidence-kind", "DEC-004", "E-004", {"DEC-004": "DEC", "E-004": "DEC"}),
        )
        for name, authority_id, evidence_id, record_kinds in cases:
            with self.subTest(case=name):
                repository = self.root / f"record-{name}"
                repository.mkdir()
                (repository / "product.txt").write_text("product\n", encoding="utf-8", newline="\n")
                request = repository / "request.md"
                request.write_text("# Runtime exclusion\n", encoding="utf-8", newline="\n")
                initialize_enhancement_v2(
                    skill_root=ROOT,
                    product_name="Runtime authority fixture",
                    product_type="cli",
                    playbooks=["cli"],
                    enhancement_id="ENH-001",
                    title="Runtime authority fixture",
                    change_types=["behavior-change"],
                    request_file=request,
                    repo_root=repository,
                    output_dir=Path("clone-pack"),
                    timestamp=PINNED_TIMESTAMP,
                )
                runtime = repository / ".codex"
                runtime.mkdir()
                runtime.chmod(0o555)
                governed = runtime_exclusion(runtime, repository)
                governed["authority_ids"] = [authority_id]
                governed["evidence_ids"] = [evidence_id]
                pack = repository / "clone-pack"
                inventory_path = pack / "repository_inventory.json"
                inventory = read_json(inventory_path)
                inventory["exclusions"] = [governed]
                write_json(inventory_path, inventory)
                index_path = pack / "clone_index.json"
                index = read_json(index_path)
                existing = {record["id"] for record in index["records"]}
                index["records"].extend(
                    index_record(identifier, kind)
                    for identifier, kind in record_kinds.items()
                    if identifier not in existing
                )
                write_json(index_path, index)

                with self.assertRaises(ClonePackError) as raised:
                    record_repository_snapshot(pack, "adopted", timestamp=PINNED_TIMESTAMP)

                self.assertEqual(raised.exception.exit_code, 4)
                self.assertEqual(list((pack / "evidence" / "snapshots").glob("SNAP-*.json")), [])

    def test_runtime_reason_is_exact_and_rejects_provenance_synonyms(self) -> None:
        runtime = self.make_runtime_directory("reason-runtime")
        valid = runtime_exclusion(runtime, self.repository)
        rejected = (
            "Trustworthy runtime directory.",
            "Authentication-proven runtime directory.",
            "Belonging to the service vendor.",
            "The vendor runtime is certified.",
            "Provider-owned Codex runtime directory.",
            "Owned by OpenAI for this session.",
            "This directory belongs to Codex.",
            "Trusted OpenAI runtime directory.",
            " ",
            "User-authorized empty tool-runtime directory\x7f excluded from product identity.",
        )

        self.assertEqual(
            repository_module._canonical_runtime_contract(valid)["reason"],
            "User-authorized empty tool-runtime directory excluded from product identity.",
        )
        for reason in rejected:
            with self.subTest(reason=reason):
                malformed = copy.deepcopy(valid)
                malformed["reason"] = reason
                with self.assertRaises(ClonePackError) as raised:
                    repository_module._canonical_runtime_contract(malformed)
                self.assertEqual(raised.exception.diagnostic, "RUNTIME_EXCLUSION_REASON_INVALID")
                self.assertEqual(raised.exception.exit_code, 4)

    def test_snapshot_check_revalidates_current_runtime_authority_and_evidence_before_traversal(self) -> None:
        repository = self.root / "check-reference-tamper"
        repository.mkdir()
        (repository / "product.txt").write_text("product\n", encoding="utf-8", newline="\n")
        request = repository / "request.md"
        request.write_text("# Runtime exclusion\n", encoding="utf-8", newline="\n")
        initialize_enhancement_v2(
            skill_root=ROOT,
            product_name="Runtime check reference fixture",
            product_type="cli",
            playbooks=["cli"],
            enhancement_id="ENH-001",
            title="Runtime check reference fixture",
            change_types=["behavior-change"],
            request_file=request,
            repo_root=repository,
            output_dir=Path("clone-pack"),
            timestamp=PINNED_TIMESTAMP,
        )
        runtime = repository / ".codex"
        runtime.mkdir()
        runtime.chmod(0o555)
        pack = repository / "clone-pack"
        inventory_path = pack / "repository_inventory.json"
        inventory = read_json(inventory_path)
        inventory["exclusions"] = [runtime_exclusion(runtime, repository)]
        write_json(inventory_path, inventory)
        index_path = pack / "clone_index.json"
        index = read_json(index_path)
        index["records"].extend(
            (
                index_record("DEC-004", "DEC"),
                index_record("E-004", "E"),
            )
        )
        write_json(index_path, index)
        record_repository_snapshot(pack, "adopted", timestamp=PINNED_TIMESTAMP)
        valid_index = read_json(index_path)

        def remove(identifier: str) -> dict[str, Any]:
            tampered = copy.deepcopy(valid_index)
            tampered["records"] = [
                record for record in tampered["records"] if record.get("id") != identifier
            ]
            return tampered

        def wrong_kind(identifier: str, kind: str) -> dict[str, Any]:
            tampered = copy.deepcopy(valid_index)
            next(record for record in tampered["records"] if record.get("id") == identifier)[
                "kind"
            ] = kind
            return tampered

        cases = (
            ("missing-authority", remove("DEC-004"), "REF_UNDEFINED"),
            ("wrong-authority-kind", wrong_kind("DEC-004", "E"), "REF_WRONG_KIND"),
            ("missing-evidence", remove("E-004"), "REF_UNDEFINED"),
            ("wrong-evidence-kind", wrong_kind("E-004", "DEC"), "REF_WRONG_KIND"),
        )
        for name, tampered, expected_diagnostic in cases:
            with self.subTest(case=name):
                write_json(index_path, tampered)
                with mock.patch(
                    "scripts.clonepack.repository.build_repository_snapshot",
                    wraps=build_repository_snapshot,
                ) as traversal:
                    with self.assertRaises(ClonePackError) as raised:
                        check_repository_snapshot(pack, "adopted")
                self.assertEqual(raised.exception.diagnostic, expected_diagnostic)
                self.assertEqual(raised.exception.exit_code, 4)
                traversal.assert_not_called()

    def test_snapshot_schema_rejects_noncanonical_runtime_path(self) -> None:
        runtime = self.make_runtime_directory("schema-runtime")
        malformed = self.snapshot([runtime_exclusion(runtime, self.repository)])
        malformed["runtime_exclusions"][0]["path"] = "schema-runtime//child"

        self.assertNotEqual(validate_schema_file(malformed, SNAPSHOT_SCHEMA), [])

    def test_all_runtime_exclusion_schemas_reject_del_without_tightening_legacy_paths(self) -> None:
        runtime = self.make_runtime_directory("schema-del-runtime")
        governed = runtime_exclusion(runtime, self.repository)
        governed["path"] = "schema-del\x7fruntime"

        inventory_pointers = {
            violation.pointer
            for violation in validate_schema_file(minimal_inventory([governed]), INVENTORY_SCHEMA)
        }
        self.assertIn("/exclusions/0/path", inventory_pointers)

        snapshot = self.snapshot([runtime_exclusion(runtime, self.repository)])
        snapshot["runtime_exclusions"][0]["path"] = governed["path"]
        snapshot_pointers = {
            violation.pointer
            for violation in validate_schema_file(snapshot, SNAPSHOT_SCHEMA)
        }
        self.assertIn("/runtime_exclusions/0/path", snapshot_pointers)

        capture_plan = {
            "schema_version": "clone-capture-plan/v2",
            "pack_id": "PACK-001",
            "pack_revision": 1,
            "cases": [
                {
                    "id": "CAP-001",
                    "adapter": "filesystem",
                    "side": "clone",
                    "environment_id": "ENV-001",
                    "required": True,
                    "authorization_decision_ids": ["DEC-004"],
                    "safe_test_environment": True,
                    "timeout_seconds": 10,
                    "input": {"path": ".", "runtime_exclusions": [governed]},
                    "lifecycle": {"setup": None, "teardown": None},
                    "redactions": [],
                    "result": None,
                }
            ],
        }
        capture_pointers = {
            violation.pointer
            for violation in validate_schema_file(capture_plan, CAPTURE_SCHEMA)
        }
        self.assertIn("/cases/0/input/runtime_exclusions/0/path", capture_pointers)

        legacy_capture = copy.deepcopy(capture_plan)
        legacy_capture["cases"][0]["input"] = {"path": "legacy\x7fpath"}
        self.assertEqual(validate_schema_file(legacy_capture, CAPTURE_SCHEMA), [])

    def test_all_runtime_exclusion_schemas_require_the_controlled_reason(self) -> None:
        runtime = self.make_runtime_directory("schema-reason-runtime")
        governed = runtime_exclusion(runtime, self.repository)
        snapshot = self.snapshot([governed])
        capture_plan = {
            "schema_version": "clone-capture-plan/v2",
            "pack_id": "PACK-001",
            "pack_revision": 1,
            "cases": [
                {
                    "id": "CAP-001",
                    "adapter": "filesystem",
                    "side": "clone",
                    "environment_id": "ENV-001",
                    "required": True,
                    "authorization_decision_ids": ["DEC-004"],
                    "safe_test_environment": True,
                    "timeout_seconds": 10,
                    "input": {"path": ".", "runtime_exclusions": [governed]},
                    "lifecycle": {"setup": None, "teardown": None},
                    "redactions": [],
                    "result": None,
                }
            ],
        }
        rejected = (
            " ",
            "Uncontrolled\nreason.",
            "Uncontrolled\x7freason.",
            "Trustworthy runtime directory.",
            "Authentication-proven runtime directory.",
            "Belonging to the service vendor.",
            "The vendor runtime is certified.",
        )

        for reason in rejected:
            with self.subTest(reason=reason):
                inventory_case = minimal_inventory([copy.deepcopy(governed)])
                inventory_case["exclusions"][0]["reason"] = reason
                inventory_pointers = {
                    violation.pointer
                    for violation in validate_schema_file(inventory_case, INVENTORY_SCHEMA)
                }
                self.assertIn("/exclusions/0/reason", inventory_pointers)

                snapshot_case = copy.deepcopy(snapshot)
                snapshot_case["runtime_exclusions"][0]["reason"] = reason
                snapshot_pointers = {
                    violation.pointer
                    for violation in validate_schema_file(snapshot_case, SNAPSHOT_SCHEMA)
                }
                self.assertIn("/runtime_exclusions/0/reason", snapshot_pointers)

                capture_case = copy.deepcopy(capture_plan)
                capture_case["cases"][0]["input"]["runtime_exclusions"][0]["reason"] = reason
                capture_pointers = {
                    violation.pointer
                    for violation in validate_schema_file(capture_case, CAPTURE_SCHEMA)
                }
                self.assertIn("/cases/0/input/runtime_exclusions/0/reason", capture_pointers)

    def test_retained_snapshot_loader_rejects_noncanonical_and_writable_runtime_contracts(self) -> None:
        runtime = self.make_runtime_directory("retained-runtime")
        valid = self.snapshot([runtime_exclusion(runtime, self.repository)])
        pack = self.root / "retained-pack"
        snapshot_directory = pack / "evidence" / "snapshots"
        snapshot_directory.mkdir(parents=True)
        malformed_cases = {
            "noncanonical": ("path", "retained-runtime//child"),
            "writable": ("mode", 0o777),
        }
        for name, (field, value) in malformed_cases.items():
            with self.subTest(case=name):
                malformed = copy.deepcopy(valid)
                if field == "path":
                    malformed["runtime_exclusions"][0]["path"] = value
                else:
                    malformed["runtime_exclusions"][0]["expected_identity"][field] = value
                snapshot_path = snapshot_directory / f"{name}.json"
                snapshot_bytes = canonical_json(malformed).encode("utf-8")
                snapshot_path.write_bytes(snapshot_bytes)
                pointer = {
                    "snapshot_id": malformed["snapshot_id"],
                    "path": snapshot_path.relative_to(pack).as_posix(),
                    "sha256": sha256_bytes(snapshot_bytes),
                    "content_sha256": malformed["content_sha256"],
                }

                with self.assertRaises(ClonePackError):
                    repository_module._load_retained_snapshot(pack, pointer, "adopted")


if __name__ == "__main__":
    unittest.main()
