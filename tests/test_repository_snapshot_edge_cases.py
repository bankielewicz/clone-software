from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from scripts.clonepack import repository as repository_module
from scripts.clonepack.common import ClonePackError, canonical_json
from scripts.clonepack.enhancement import initialize_enhancement_v2
from scripts.clonepack.repository import (
    build_repository_snapshot,
    inventory_repository,
    record_repository_snapshot,
)
from scripts.clonepack.schema import validate_schema_file


ROOT = Path(__file__).resolve().parents[1]
SNAPSHOT_SCHEMA = ROOT / "assets" / "schemas" / "repository-snapshot-v2.schema.json"
SCOPE_SCHEMA = ROOT / "assets" / "schemas" / "scope-result-v2.schema.json"
PINNED_TIMESTAMP = "2026-07-19T20:00:00+00:00"


def run_git(repository: Path, *arguments: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(repository), *arguments],
        check=False,
        text=True,
        encoding="utf-8",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def write_json(path: Path, value: object) -> None:
    path.write_text(canonical_json(value), encoding="utf-8", newline="\n")


def read_json(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise AssertionError(f"expected object: {path}")
    return value


class RepositorySnapshotEdgeCaseTests(unittest.TestCase):
    maxDiff = None

    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.temporary_root = Path(temporary.name)

    def make_git_repository(self, name: str) -> Path:
        repository = self.temporary_root / name
        repository.mkdir()
        initialized = run_git(repository, "init", "-q")
        self.assertEqual(initialized.returncode, 0, initialized.stderr)
        for key, value in (
            ("user.name", "Snapshot Fixture"),
            ("user.email", "snapshot@example.invalid"),
        ):
            configured = run_git(repository, "config", key, value)
            self.assertEqual(configured.returncode, 0, configured.stderr)
        return repository

    def commit_all(self, repository: Path, message: str = "fixture") -> str:
        added = run_git(repository, "add", ".")
        self.assertEqual(added.returncode, 0, added.stderr)
        committed = run_git(repository, "commit", "-q", "-m", message)
        self.assertEqual(committed.returncode, 0, committed.stderr)
        head = run_git(repository, "rev-parse", "HEAD")
        self.assertEqual(head.returncode, 0, head.stderr)
        return head.stdout.strip()

    def test_sha1_git_head_is_a_valid_snapshot_oid(self) -> None:
        repository = self.make_git_repository("sha1")
        (repository / "tracked.txt").write_text("tracked\n", encoding="utf-8", newline="\n")
        head = self.commit_all(repository)
        self.assertRegex(head, r"^[0-9a-f]{40}$")

        snapshot = build_repository_snapshot(
            repository,
            pack_root=self.temporary_root / "outside-pack",
            snapshot_id="SNAP-001",
            role="adopted",
            timestamp=PINNED_TIMESTAMP,
        )

        self.assertEqual(snapshot["repository"]["head"], head)
        self.assertEqual(validate_schema_file(snapshot, SNAPSHOT_SCHEMA), [])

    def test_git_snapshot_rejects_mutation_between_metadata_and_entry_capture(self) -> None:
        repository = self.make_git_repository("concurrent-metadata-entry")
        tracked = repository / "tracked.txt"
        tracked.write_text("adopted\n", encoding="utf-8", newline="\n")
        self.commit_all(repository)
        original_git_metadata = repository_module._git_metadata

        def mutate_after_metadata(root: Path, pack: Path | None) -> dict[str, object]:
            metadata = original_git_metadata(root, pack)
            tracked.write_text("candidate\n", encoding="utf-8", newline="\n")
            return metadata

        with mock.patch(
            "scripts.clonepack.repository._git_metadata",
            side_effect=mutate_after_metadata,
        ):
            with self.assertRaises(ClonePackError) as raised:
                build_repository_snapshot(
                    repository,
                    pack_root=self.temporary_root / "outside-pack",
                    snapshot_id="SNAP-001",
                    role="adopted",
                    timestamp=PINNED_TIMESTAMP,
                )

        self.assertEqual(raised.exception.diagnostic, "SNAPSHOT_CONCURRENT_MUTATION")
        self.assertEqual(raised.exception.exit_code, 4)

    def test_git_is_not_invoked_without_marker_but_is_required_with_marker(self) -> None:
        repository = self.temporary_root / "filesystem"
        repository.mkdir()
        (repository / "file.txt").write_text("bytes\n", encoding="utf-8", newline="\n")

        with mock.patch(
            "scripts.clonepack.repository.subprocess.run",
            side_effect=AssertionError("Git must not be invoked for an unmarked filesystem repository"),
        ):
            inventory = inventory_repository(repository)
        self.assertEqual(inventory["kind"], "filesystem")

        (repository / ".git").mkdir()
        with mock.patch(
            "scripts.clonepack.repository.subprocess.run",
            side_effect=FileNotFoundError("git"),
        ):
            with self.assertRaises(ClonePackError) as raised:
                inventory_repository(repository)
        self.assertEqual(raised.exception.diagnostic, "CAPABILITY_MISSING")
        self.assertEqual(raised.exception.exit_code, 7)

    def test_uninitialized_submodule_blocks_snapshot_capture(self) -> None:
        submodule = self.make_git_repository("submodule-source")
        (submodule / "module.txt").write_text("module\n", encoding="utf-8", newline="\n")
        submodule_head = self.commit_all(submodule)

        repository = self.make_git_repository("superproject")
        (repository / ".gitmodules").write_text(
            '[submodule "vendor/module"]\n\tpath = vendor/module\n\turl = ../submodule-source\n',
            encoding="utf-8",
            newline="\n",
        )
        added_metadata = run_git(repository, "add", ".gitmodules")
        self.assertEqual(added_metadata.returncode, 0, added_metadata.stderr)
        gitlink = run_git(
            repository,
            "update-index",
            "--add",
            "--cacheinfo",
            f"160000,{submodule_head},vendor/module",
        )
        self.assertEqual(gitlink.returncode, 0, gitlink.stderr)
        committed = run_git(repository, "commit", "-q", "-m", "uninitialized submodule")
        self.assertEqual(committed.returncode, 0, committed.stderr)

        with self.assertRaises(ClonePackError) as raised:
            build_repository_snapshot(
                repository,
                pack_root=self.temporary_root / "outside-pack",
                snapshot_id="SNAP-001",
                role="adopted",
                timestamp=PINNED_TIMESTAMP,
            )
        self.assertEqual(raised.exception.diagnostic, "SUBMODULE_UNINITIALIZED")
        self.assertEqual(raised.exception.exit_code, 4)
        self.assertIn("vendor/module", str(raised.exception))

    def test_ignored_include_requires_a_governed_inventory_entry(self) -> None:
        repository = self.make_git_repository("ignored")
        (repository / ".gitignore").write_text("ignored.txt\n", encoding="utf-8", newline="\n")
        (repository / "tracked.txt").write_text("tracked\n", encoding="utf-8", newline="\n")
        self.commit_all(repository)
        (repository / "ignored.txt").write_text("governed ignored bytes\n", encoding="utf-8", newline="\n")

        with self.assertRaises(ClonePackError) as raised:
            build_repository_snapshot(
                repository,
                pack_root=self.temporary_root / "outside-pack",
                snapshot_id="SNAP-001",
                role="adopted",
                includes=["ignored.txt"],
                timestamp=PINNED_TIMESTAMP,
            )
        self.assertEqual(raised.exception.diagnostic, "SNAPSHOT_INCLUDE_NOT_INVENTORIED")
        self.assertEqual(raised.exception.exit_code, 2)

        snapshot = build_repository_snapshot(
            repository,
            pack_root=self.temporary_root / "outside-pack",
            snapshot_id="SNAP-001",
            role="adopted",
            includes=["ignored.txt"],
            inventoried_paths={"ignored.txt"},
            timestamp=PINNED_TIMESTAMP,
        )
        self.assertEqual(snapshot["includes"], ["ignored.txt"])
        self.assertEqual(
            [entry["path"] for entry in snapshot["entries"]],
            [".gitignore", "ignored.txt", "tracked.txt"],
        )

    def test_git_include_adds_governed_input_without_narrowing_tracked_entries(self) -> None:
        repository = self.make_git_repository("additive-git-include")
        (repository / "src").mkdir()
        (repository / "src" / "a.txt").write_text("A\n", encoding="utf-8", newline="\n")
        (repository / "other").mkdir()
        (repository / "other" / "b.txt").write_text("B\n", encoding="utf-8", newline="\n")
        (repository / "request.md").write_text("request\n", encoding="utf-8", newline="\n")
        self.commit_all(repository)

        snapshot = build_repository_snapshot(
            repository,
            pack_root=self.temporary_root / "outside-pack",
            snapshot_id="SNAP-001",
            role="adopted",
            includes=["src"],
            timestamp=PINNED_TIMESTAMP,
        )

        self.assertEqual(snapshot["includes"], ["src"])
        self.assertEqual(
            [entry["path"] for entry in snapshot["entries"]],
            ["other/b.txt", "request.md", "src/a.txt"],
        )

    def test_filesystem_include_does_not_narrow_the_full_tree_inventory(self) -> None:
        repository = self.temporary_root / "additive-filesystem-include"
        repository.mkdir()
        (repository / "src").mkdir()
        (repository / "src" / "a.txt").write_text("A\n", encoding="utf-8", newline="\n")
        (repository / "other.txt").write_text("B\n", encoding="utf-8", newline="\n")

        snapshot = build_repository_snapshot(
            repository,
            pack_root=self.temporary_root / "outside-pack",
            snapshot_id="SNAP-001",
            role="adopted",
            includes=["src"],
            timestamp=PINNED_TIMESTAMP,
        )

        self.assertEqual(snapshot["includes"], ["src"])
        self.assertEqual(
            [entry["path"] for entry in snapshot["entries"]],
            ["other.txt", "src/a.txt"],
        )

    def test_candidate_recording_is_state_gated_and_binds_manifest_repository_state(self) -> None:
        repository = self.temporary_root / "candidate-state"
        repository.mkdir()
        (repository / "app.txt").write_text("one\n", encoding="utf-8", newline="\n")
        (repository / "request.md").write_text(
            "# Change app\n\nChange the exact app bytes.\n",
            encoding="utf-8",
            newline="\n",
        )
        initialize_enhancement_v2(
            skill_root=ROOT,
            product_name="Candidate state fixture",
            product_type="cli",
            playbooks=["cli"],
            enhancement_id="ENH-001",
            title="Change app bytes",
            change_types=["behavior-change"],
            request_file=repository / "request.md",
            repo_root=repository,
            output_dir=Path("clone-pack"),
            timestamp=PINNED_TIMESTAMP,
        )
        pack = repository / "clone-pack"
        adopted, adopted_exit = record_repository_snapshot(
            pack,
            "adopted",
            timestamp=PINNED_TIMESTAMP,
        )
        self.assertEqual(adopted_exit, 0, adopted)
        initial_manifest = read_json(pack / "clone_pack.json")

        with self.assertRaises(ClonePackError) as draft_error:
            record_repository_snapshot(pack, "candidate", timestamp=PINNED_TIMESTAMP)
        self.assertEqual(draft_error.exception.diagnostic, "SNAPSHOT_STATE_INVALID")
        self.assertEqual(read_json(pack / "clone_pack.json"), initial_manifest)

        plan_path = pack / "enhancement_plan.json"
        plan = read_json(plan_path)
        plan["status"] = "IN_PROGRESS"
        write_json(plan_path, plan)
        (repository / "app.txt").write_text("two\n", encoding="utf-8", newline="\n")

        candidate, candidate_exit = record_repository_snapshot(
            pack,
            "candidate",
            timestamp=PINNED_TIMESTAMP,
        )
        self.assertEqual(candidate_exit, 0, candidate)
        manifest = read_json(pack / "clone_pack.json")
        self.assertEqual(
            manifest["repository_state"],
            {
                "kind": "working-tree",
                "revision": candidate["snapshot_id"],
                "diff_sha256": candidate["content_sha256"],
            },
        )

        plan = read_json(plan_path)
        plan["status"] = "IMPLEMENTED"
        write_json(plan_path, plan)
        manifest_before_rejected_replace = (pack / "clone_pack.json").read_bytes()
        with self.assertRaises(ClonePackError) as implemented_error:
            record_repository_snapshot(pack, "candidate", timestamp=PINNED_TIMESTAMP)
        self.assertEqual(implemented_error.exception.diagnostic, "SNAPSHOT_STATE_INVALID")
        self.assertEqual((pack / "clone_pack.json").read_bytes(), manifest_before_rejected_replace)

    def test_scope_schema_requires_signed_matches_and_machine_violations(self) -> None:
        result = {
            "schema_version": "clone-scope-result/v2",
            "scope_id": "SCOPE-001",
            "pack_id": "PACK-001",
            "pack_revision": 1,
            "enhancement_id": "ENH-001",
            "verified_at": PINNED_TIMESTAMP,
            "enhancement_plan_sha256": "a" * 64,
            "adopted_snapshot_id": "SNAP-001",
            "adopted_content_sha256": "b" * 64,
            "candidate_snapshot_id": "SNAP-002",
            "candidate_content_sha256": "c" * 64,
            "status": "FAIL",
            "changed_paths": ["app.txt"],
            "added_paths": [],
            "removed_paths": [],
            "modified_paths": ["app.txt"],
            "renames": [],
            "matches": [
                {"operation": "modify", "paths": ["app.txt"], "change_id": "CHANGE-001"}
            ],
            "unauthorized_paths": ["app.txt"],
            "violations": [
                {
                    "code": "PATH_FORBIDDEN",
                    "path": "app.txt",
                    "message": "path is inside the forbidden fence",
                }
            ],
            "details": ["path is inside the forbidden fence"],
            "runner_version": "2.1.0",
        }
        self.assertEqual(validate_schema_file(result, SCOPE_SCHEMA), [])

        unsigned = dict(result)
        unsigned.pop("matches")
        pointers = {violation.pointer for violation in validate_schema_file(unsigned, SCOPE_SCHEMA)}
        self.assertIn("/matches", pointers)

        malformed = dict(result)
        malformed["violations"] = [{"path": "app.txt", "message": "missing code"}]
        pointers = {violation.pointer for violation in validate_schema_file(malformed, SCOPE_SCHEMA)}
        self.assertIn("/violations/0/code", pointers)


if __name__ == "__main__":
    unittest.main()
