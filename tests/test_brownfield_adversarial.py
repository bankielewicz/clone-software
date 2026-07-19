from __future__ import annotations

import copy
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any

from scripts.clonepack.common import ClonePackError, canonical_json, case_contract_sha256
from scripts.clonepack.enhancement import (
    enhancement_profile_diagnostics,
    initialize_enhancement_v2,
    rehash_targets,
    run_preservation_baseline,
    transition_enhancement,
    verify_enhancement_scope,
)
from scripts.clonepack.repository import (
    build_repository_snapshot,
    repository_snapshot,
    retained_snapshot,
)
from scripts.clonepack.schema import validate_schema_file


ROOT = Path(__file__).resolve().parents[1]
PLAN_SCHEMA = ROOT / "assets" / "schemas" / "enhancement-plan-v2.schema.json"
PINNED_TIMESTAMP = "2026-07-19T18:00:00+00:00"


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise AssertionError(f"expected object in {path}")
    return value


def write_json(path: Path, value: Any) -> None:
    path.write_text(canonical_json(value), encoding="utf-8", newline="\n")


def run_git(repository: Path, *arguments: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(repository), *arguments],
        text=True,
        encoding="utf-8",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )


class BrownfieldAdversarialTests(unittest.TestCase):
    """Hostile-path contracts omitted by the compact brownfield smoke suite."""

    maxDiff = None

    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.temporary_root = Path(temporary.name)

    def make_repository(
        self,
        name: str,
        files: dict[str, str] | None = None,
        *,
        git: bool = False,
    ) -> Path:
        repository = self.temporary_root / name
        repository.mkdir()
        contents = {
            "app.txt": "adopted app\n",
            "request.md": "# Authorized request\n\nExercise an exact adversarial contract.\n",
            **(files or {}),
        }
        for relative, content in contents.items():
            path = repository / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8", newline="\n")
        if git:
            initialized = run_git(repository, "init", "-q", "-b", "main")
            self.assertEqual(initialized.returncode, 0, initialized.stderr)
            for key, value in (
                ("user.name", "Adversarial Fixture"),
                ("user.email", "adversarial@example.invalid"),
            ):
                configured = run_git(repository, "config", key, value)
                self.assertEqual(configured.returncode, 0, configured.stderr)
            added = run_git(repository, "add", ".")
            self.assertEqual(added.returncode, 0, added.stderr)
            committed = run_git(repository, "commit", "-q", "-m", "adopted fixture")
            self.assertEqual(committed.returncode, 0, committed.stderr)
        return repository

    def initialize_pack(
        self,
        repository: Path,
        *,
        adopt_dirty: bool = False,
        change_types: list[str] | None = None,
    ) -> Path:
        initialize_enhancement_v2(
            skill_root=ROOT,
            product_name="Adversarial Fixture",
            product_type="cli",
            playbooks=["cli"],
            enhancement_id="ENH-001",
            title="Exercise exact adversarial behavior",
            change_types=change_types or ["feature"],
            request_file=repository / "request.md",
            repo_root=repository,
            output_dir=Path("clone-pack"),
            adopt_dirty=adopt_dirty,
            timestamp=PINNED_TIMESTAMP,
        )
        return repository / "clone-pack"

    def append_records(self, pack: Path, specifications: list[dict[str, Any]]) -> None:
        document = pack / "clone_brief.md"
        text = document.read_text(encoding="utf-8").rstrip("\n") + "\n"
        index_path = pack / "clone_index.json"
        index = read_json(index_path)
        existing = {str(record["id"]) for record in index["records"]}
        for position, specification in enumerate(specifications, 1):
            identifier = str(specification["id"])
            self.assertNotIn(identifier, existing)
            anchor = f"{identifier} adversarial contract {position}"
            line = f"- {anchor}\n"
            text += line
            index["records"].append(
                {
                    "id": identifier,
                    "kind": specification["kind"],
                    "locator": {
                        "path": "clone_brief.md",
                        "anchor": anchor,
                        "sha256": hashlib.sha256(line.encode("utf-8")).hexdigest(),
                    },
                    "links": specification.get("links", {}),
                    "applicability": "REQUIRED",
                    "state": specification.get("state", "READY"),
                    "attributes": specification.get("attributes", {}),
                }
            )
            existing.add(identifier)
        document.write_text(text, encoding="utf-8", newline="\n")
        write_json(index_path, index)
        manifest_path = pack / "clone_pack.json"
        manifest = read_json(manifest_path)
        brief = next(item for item in manifest["documents"] if item["path"] == "clone_brief.md")
        brief["sha256"] = hashlib.sha256(document.read_bytes()).hexdigest()
        write_json(manifest_path, manifest)

    def set_status(self, pack: Path, status: str) -> None:
        plan_path = pack / "enhancement_plan.json"
        plan = read_json(plan_path)
        plan["status"] = status
        plan["blocked_prior_state"] = None
        write_json(plan_path, plan)
        index_path = pack / "clone_index.json"
        index = read_json(index_path)
        enhancement = next(record for record in index["records"] if record["id"] == "ENH-001")
        enhancement["state"] = status
        enhancement.setdefault("attributes", {})["status"] = status
        write_json(index_path, index)

    @staticmethod
    def preservation_case(
        argv: list[str],
        *,
        timeout: float = 30,
        artifact_paths: list[str] | None = None,
        redactions: list[dict[str, Any]] | None = None,
        normalizations: list[dict[str, Any]] | None = None,
        known_failure: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return {
            "id": "PRES-001",
            "required": True,
            "argv": argv,
            "cwd": ".",
            "environment": {},
            "timeout_seconds": timeout,
            "expected_exit": 0,
            "artifact_paths": artifact_paths or [],
            "comparator": "exact",
            "normalizations": normalizations or [],
            "options": {},
            "redactions": redactions or [],
            "known_failure": known_failure,
            "result": {"baseline": None, "regression": None},
        }

    def configure_preservation(
        self,
        pack: Path,
        case: dict[str, Any],
        *,
        decision_ids: list[str] | None = None,
    ) -> None:
        decisions = list(decision_ids or [])
        plan_path = pack / "enhancement_plan.json"
        plan = read_json(plan_path)
        plan["preservation_cases"] = [case]
        write_json(plan_path, plan)
        index_path = pack / "clone_index.json"
        index = read_json(index_path)
        enhancement = next(record for record in index["records"] if record["id"] == "ENH-001")
        enhancement.setdefault("links", {})["preservations"] = ["PRES-001"]
        write_json(index_path, index)
        self.append_records(
            pack,
            [
                *[
                    {
                        "id": identifier,
                        "kind": "DEC",
                        "state": "APPROVED",
                        "links": {"enhancements": ["ENH-001"]},
                    }
                    for identifier in decisions
                ],
                {
                    "id": "PRES-001",
                    "kind": "PRES",
                    "links": {
                        "enhancements": ["ENH-001"],
                        "decisions": decisions,
                    },
                    "attributes": {"case_sha256": case_contract_sha256(case)},
                },
            ],
        )

    def make_preservation_pack(
        self,
        name: str,
        case: dict[str, Any],
        *,
        files: dict[str, str] | None = None,
        decision_ids: list[str] | None = None,
    ) -> Path:
        repository = self.make_repository(name, files)
        pack = self.initialize_pack(repository)
        self.configure_preservation(pack, case, decision_ids=decision_ids)
        recorded, exit_code = repository_snapshot(
            pack,
            "adopted",
            record=True,
            check=False,
            timestamp=PINNED_TIMESTAMP,
        )
        self.assertEqual(exit_code, 0, recorded)
        self.set_status(pack, "READY")
        return pack

    def configure_scope(
        self,
        pack: Path,
        changes: list[dict[str, Any]],
        *,
        allowed: list[str],
        forbidden: list[str] | None = None,
        generated: list[str] | None = None,
        protected: list[str] | None = None,
        renames: list[dict[str, str]] | None = None,
    ) -> None:
        normalized = [
            {
                **change,
                "generated": change["operation"] == "generate",
                "requirement_ids": [],
                "slice_ids": [],
            }
            for change in changes
        ]
        plan_path = pack / "enhancement_plan.json"
        plan = read_json(plan_path)
        plan["scope"] = {
            "allowed_paths": allowed,
            "forbidden_paths": forbidden or [],
            "generated_paths": generated or [],
            "rename_policy": "allow-declared" if renames else "forbid",
            "declared_renames": renames or [],
            "protected_dirty_paths": protected or [],
        }
        plan["change_map"] = normalized
        write_json(plan_path, plan)
        index_path = pack / "clone_index.json"
        index = read_json(index_path)
        enhancement = next(record for record in index["records"] if record["id"] == "ENH-001")
        enhancement.setdefault("links", {})["changes"] = [str(item["id"]) for item in normalized]
        write_json(index_path, index)
        self.append_records(
            pack,
            [
                {
                    "id": change["id"],
                    "kind": "CHANGE",
                    "links": {"enhancements": ["ENH-001"]},
                    "attributes": {
                        "operation": change["operation"],
                        "paths": change["paths"],
                    },
                }
                for change in normalized
            ],
        )

    def test_git_snapshot_binds_every_dirty_class_detached_head_and_space_paths(self) -> None:
        repository = self.make_repository(
            "git-matrix",
            {
                "staged.txt": "one\n",
                "unstaged.txt": "one\n",
                "rename-old.txt": "rename bytes\n",
                "deleted.txt": "delete bytes\n",
                "committed path with spaces.txt": "spaces\n",
            },
            git=True,
        )
        head = run_git(repository, "rev-parse", "HEAD").stdout.strip()
        detached = run_git(repository, "checkout", "-q", "--detach", "HEAD")
        self.assertEqual(detached.returncode, 0, detached.stderr)
        (repository / "staged.txt").write_text("two\n", encoding="utf-8", newline="\n")
        self.assertEqual(run_git(repository, "add", "staged.txt").returncode, 0)
        (repository / "unstaged.txt").write_text("two\n", encoding="utf-8", newline="\n")
        renamed = run_git(repository, "mv", "rename-old.txt", "rename new.txt")
        self.assertEqual(renamed.returncode, 0, renamed.stderr)
        (repository / "deleted.txt").unlink()
        (repository / "untracked path.txt").write_text("new\n", encoding="utf-8", newline="\n")

        snapshot = build_repository_snapshot(
            repository,
            pack_root=self.temporary_root / "outside-pack",
            snapshot_id="SNAP-001",
            role="candidate",
            timestamp=PINNED_TIMESTAMP,
        )

        self.assertEqual(snapshot["repository"]["head"], head)
        self.assertIsNone(snapshot["repository"]["branch"])
        self.assertTrue(snapshot["repository"]["detached"])
        statuses = {record["path"]: record for record in snapshot["repository"]["status"]}
        self.assertEqual(statuses["staged.txt"]["xy"][0], "M")
        self.assertEqual(statuses["unstaged.txt"]["xy"][1], "M")
        self.assertEqual(statuses["deleted.txt"]["xy"][1], "D")
        self.assertEqual(statuses["rename new.txt"]["kind"], "rename")
        self.assertEqual(statuses["rename new.txt"]["original_path"], "rename-old.txt")
        self.assertEqual(statuses["untracked path.txt"]["kind"], "untracked")
        paths = {entry["path"] for entry in snapshot["entries"]}
        self.assertIn("committed path with spaces.txt", paths)
        self.assertIn("rename new.txt", paths)
        self.assertIn("untracked path.txt", paths)
        self.assertNotIn("deleted.txt", paths)
        self.assertNotIn("rename-old.txt", paths)

    @unittest.skipUnless(hasattr(os, "symlink"), "symlinks are unavailable")
    def test_filesystem_snapshot_hashes_link_text_without_following_the_target(self) -> None:
        outside = self.temporary_root / "outside-secret.txt"
        outside.write_text("must not be captured\n", encoding="utf-8", newline="\n")
        repository = self.make_repository("symlink-no-follow")
        os.symlink("../outside-secret.txt", repository / "external-link")

        snapshot = build_repository_snapshot(
            repository,
            pack_root=self.temporary_root / "outside-pack",
            snapshot_id="SNAP-001",
            role="adopted",
            timestamp=PINNED_TIMESTAMP,
        )

        link = next(entry for entry in snapshot["entries"] if entry["path"] == "external-link")
        self.assertEqual(link["type"], "symlink")
        self.assertEqual(link["target"], "../outside-secret.txt")
        self.assertEqual(
            link["sha256"],
            hashlib.sha256(b"../outside-secret.txt").hexdigest(),
        )
        self.assertNotIn(outside.name, {entry["path"] for entry in snapshot["entries"]})

    @unittest.skipUnless(hasattr(os, "mkfifo"), "FIFO fixtures are unavailable")
    def test_filesystem_snapshot_rejects_special_files(self) -> None:
        repository = self.make_repository("special-file")
        os.mkfifo(repository / "runtime.pipe")
        with self.assertRaises(ClonePackError) as raised:
            build_repository_snapshot(
                repository,
                pack_root=self.temporary_root / "outside-pack",
                snapshot_id="SNAP-001",
                role="adopted",
                timestamp=PINNED_TIMESTAMP,
            )
        self.assertEqual(raised.exception.exit_code, 4)
        self.assertEqual(raised.exception.diagnostic, "SNAPSHOT_SPECIAL_FILE")

    def test_missing_executable_and_timeout_retain_blocked_baseline_evidence(self) -> None:
        missing_case = self.preservation_case(["clone-pack-executable-that-does-not-exist"])
        missing_pack = self.make_preservation_pack("missing-executable", missing_case)
        missing, missing_exit = run_preservation_baseline(
            missing_pack,
            ["PRES-001"],
            timestamp=PINNED_TIMESTAMP,
        )
        self.assertEqual(missing_exit, 7)
        self.assertEqual(missing["status"], "BLOCKED")
        missing_result = read_json(missing_pack / missing["result_path"])
        self.assertEqual(missing_result["diagnostic"]["code"], "CAPABILITY_MISSING")
        self.assertTrue((missing_pack / missing["result_path"]).is_file())

        timeout_case = self.preservation_case(
            [sys.executable, "-c", "import time; time.sleep(5)"],
            timeout=0.05,
        )
        timeout_pack = self.make_preservation_pack("timeout", timeout_case)
        timed_out, timeout_exit = run_preservation_baseline(
            timeout_pack,
            ["PRES-001"],
            timestamp=PINNED_TIMESTAMP,
        )
        self.assertEqual(timeout_exit, 7)
        self.assertEqual(timed_out["status"], "BLOCKED")
        timeout_result = read_json(timeout_pack / timed_out["result_path"])
        self.assertEqual(timeout_result["diagnostic"]["code"], "CAPTURE_TIMEOUT")
        self.assertTrue((timeout_pack / timed_out["result_path"]).is_file())

    def test_text_redaction_is_applied_before_promotion_and_binary_redaction_is_rejected(self) -> None:
        rule = {
            "pattern": "secret-[0-9]+",
            "replacement": "[REDACTED]",
            "reason": "Retained evidence must not contain the fixture secret.",
            "authority_ids": ["DEC-001"],
        }
        textual_case = self.preservation_case(
            [sys.executable, "-c", "print('token=secret-1234')"],
            redactions=[rule],
        )
        textual_pack = self.make_preservation_pack(
            "text-redaction",
            textual_case,
            decision_ids=["DEC-001"],
        )
        textual, textual_exit = run_preservation_baseline(
            textual_pack,
            ["PRES-001"],
            timestamp=PINNED_TIMESTAMP,
        )
        self.assertEqual(textual_exit, 0, textual)
        result = read_json(textual_pack / textual["result_path"])
        stdout = next(item for item in result["artifacts"] if item["name"] == "stdout.bin")
        retained = (textual_pack / stdout["path"]).read_bytes()
        self.assertEqual(retained, b"token=[REDACTED]\n")
        self.assertNotIn(b"secret-1234", retained)

        binary_case = self.preservation_case(
            [sys.executable, "-c", "import sys; sys.stdout.buffer.write(b'\\xff')"],
            redactions=[rule],
        )
        binary_pack = self.make_preservation_pack(
            "binary-redaction",
            binary_case,
            decision_ids=["DEC-001"],
        )
        with self.assertRaises(ClonePackError) as raised:
            run_preservation_baseline(
                binary_pack,
                ["PRES-001"],
                timestamp=PINNED_TIMESTAMP,
            )
        self.assertEqual(raised.exception.diagnostic, "BINARY_REDACTION_UNSUPPORTED")

    def test_normalization_requires_nonempty_authority_at_execution_time(self) -> None:
        normalization = {
            "kind": "regex-replace",
            "artifact_names": ["stdout.bin"],
            "pattern": "[0-9]+",
            "replacement": "<n>",
            "reason": "Ignore an authorized unstable integer.",
            "authority_ids": [],
        }
        case = self.preservation_case(
            [sys.executable, "-c", "print('value=123')"],
            normalizations=[normalization],
        )
        pack = self.make_preservation_pack("normalization-authority", case)
        with self.assertRaises(ClonePackError) as raised:
            run_preservation_baseline(pack, ["PRES-001"], timestamp=PINNED_TIMESTAMP)
        self.assertEqual(raised.exception.diagnostic, "NORMALIZATION_UNAUTHORIZED")

    def test_scope_accepts_create_delete_declared_rename_generated_and_untracked_paths(self) -> None:
        repository = self.make_repository(
            "scope-operations",
            {
                "delete.txt": "remove me\n",
                "rename-old.txt": "rename me\n",
            },
            git=True,
        )
        pack = self.initialize_pack(repository)
        changes = [
            {"id": "CHANGE-001", "operation": "create", "paths": ["created.txt"]},
            {"id": "CHANGE-002", "operation": "delete", "paths": ["delete.txt"]},
            {
                "id": "CHANGE-003",
                "operation": "rename",
                "paths": ["rename-old.txt", "rename-new.txt"],
            },
            {"id": "CHANGE-004", "operation": "generate", "paths": ["generated.txt"]},
        ]
        self.configure_scope(
            pack,
            changes,
            allowed=["created.txt", "delete.txt", "rename-old.txt", "rename-new.txt", "generated.txt"],
            generated=["generated.txt"],
            renames=[
                {
                    "from": "rename-old.txt",
                    "to": "rename-new.txt",
                    "change_id": "CHANGE-003",
                }
            ],
        )
        adopted, adopted_exit = repository_snapshot(
            pack,
            "adopted",
            record=True,
            check=False,
            timestamp=PINNED_TIMESTAMP,
        )
        self.assertEqual(adopted_exit, 0, adopted)
        self.set_status(pack, "IN_PROGRESS")
        (repository / "created.txt").write_text("created\n", encoding="utf-8", newline="\n")
        (repository / "generated.txt").write_text("generated\n", encoding="utf-8", newline="\n")
        (repository / "delete.txt").unlink()
        renamed = run_git(repository, "mv", "rename-old.txt", "rename-new.txt")
        self.assertEqual(renamed.returncode, 0, renamed.stderr)
        candidate, candidate_exit = repository_snapshot(
            pack,
            "candidate",
            record=True,
            check=False,
            timestamp=PINNED_TIMESTAMP,
        )
        self.assertEqual(candidate_exit, 0, candidate)
        _, candidate_snapshot = retained_snapshot(pack, "candidate")
        status_paths = {record["path"] for record in candidate_snapshot["repository"]["status"]}
        self.assertIn("created.txt", status_paths)
        self.assertIn("generated.txt", status_paths)
        self.set_status(pack, "IMPLEMENTED")

        result, exit_code = verify_enhancement_scope(
            pack,
            "ENH-001",
            timestamp=PINNED_TIMESTAMP,
        )
        self.assertEqual(exit_code, 0, result)
        self.assertEqual(result["status"], "PASS")
        self.assertEqual(
            result["changed_paths"],
            ["created.txt", "delete.txt", "generated.txt", "rename-new.txt", "rename-old.txt"],
        )
        self.assertEqual(
            result["renames"],
            [{"from": "rename-old.txt", "to": "rename-new.txt"}],
        )
        self.assertEqual(result["unauthorized_paths"], [])

    def test_scope_holds_for_forbidden_and_unplanned_protected_dirty_mutation(self) -> None:
        repository = self.make_repository(
            "protected-dirty",
            {"owner.txt": "owner work one\n"},
            git=True,
        )
        (repository / "owner.txt").write_text("owner work two\n", encoding="utf-8", newline="\n")
        pack = self.initialize_pack(repository, adopt_dirty=True)
        self.configure_scope(
            pack,
            [{"id": "CHANGE-001", "operation": "modify", "paths": ["app.txt"]}],
            allowed=["app.txt", "owner.txt"],
            forbidden=["owner.txt"],
            protected=["owner.txt"],
        )
        adopted, adopted_exit = repository_snapshot(
            pack,
            "adopted",
            record=True,
            check=False,
            timestamp=PINNED_TIMESTAMP,
        )
        self.assertEqual(adopted_exit, 0, adopted)
        self.set_status(pack, "IN_PROGRESS")
        (repository / "app.txt").write_text("candidate app\n", encoding="utf-8", newline="\n")
        (repository / "owner.txt").write_text("owner work three\n", encoding="utf-8", newline="\n")
        candidate, candidate_exit = repository_snapshot(
            pack,
            "candidate",
            record=True,
            check=False,
            timestamp=PINNED_TIMESTAMP,
        )
        self.assertEqual(candidate_exit, 0, candidate)
        self.set_status(pack, "IMPLEMENTED")

        result, exit_code = verify_enhancement_scope(
            pack,
            "ENH-001",
            timestamp=PINNED_TIMESTAMP,
        )
        self.assertEqual(exit_code, 5)
        self.assertEqual(result["status"], "FAIL")
        retained = read_json(pack / result["result_path"])
        codes = {item["code"] for item in retained["violations"] if item["path"] == "owner.txt"}
        self.assertEqual(
            codes,
            {"CHANGE_MATCH_COUNT", "PATH_FORBIDDEN", "PROTECTED_DIRTY_PATH_CHANGED"},
        )

    def test_compatibility_feature_flag_and_expand_contract_schema_contracts(self) -> None:
        repository = self.make_repository("strategy-schema")
        pack = self.initialize_pack(repository)
        base = read_json(pack / "enhancement_plan.json")
        self.assertEqual(validate_schema_file(base, PLAN_SCHEMA), [])

        for disposition in ("PRESERVE", "ADDITIVE"):
            with self.subTest(disposition=disposition):
                plan = copy.deepcopy(base)
                plan["compatibility"] = [
                    {
                        "surface_id": "IF-001",
                        "disposition": disposition,
                        "decision_ids": [],
                        "reason": "Exact compatibility disposition for the affected interface.",
                    }
                ]
                self.assertEqual(validate_schema_file(plan, PLAN_SCHEMA), [])

        approved_break = copy.deepcopy(base)
        approved_break["compatibility"] = [
            {
                "surface_id": "IF-001",
                "disposition": "BREAK_APPROVED",
                "decision_ids": ["DEC-001"],
                "reason": "The authority approved this exact break.",
                "affected_consumers": ["consumer-a"],
                "migration_procedure": "Move consumer-a to /v2 before the window closes.",
                "deprecation_procedure": "Keep /v1 available during the compatibility window.",
                "version_policy_outcome": "Increment the repository-declared major version.",
                "compatibility_window": "2026-08-01 through 2026-09-01 UTC.",
                "exit_condition": "Consumer-a no longer calls /v1.",
            }
        ]
        self.assertEqual(validate_schema_file(approved_break, PLAN_SCHEMA), [])
        incomplete_break = copy.deepcopy(approved_break)
        incomplete_break["compatibility"][0].pop("exit_condition")
        self.assertNotEqual(validate_schema_file(incomplete_break, PLAN_SCHEMA), [])

        feature_flag = copy.deepcopy(base)
        feature_flag["delivery_strategy"] = "feature-flag"
        feature_flag["feature_flag"] = {
            "key": "export.enabled",
            "default_value": False,
            "existing_mechanism_evidence_ids": ["E-001"],
            "targeting_inputs": [
                {
                    "name": "tenant_id",
                    "source": "authenticated request context",
                    "value_type": "string",
                    "required": True,
                    "sensitive": False,
                }
            ],
            "targeting_authority_ids": ["DEC-001"],
            "off_behavior": "Execute the adopted implementation.",
            "on_behavior": "Execute the candidate implementation.",
            "error_behavior": "Execute the adopted implementation and emit flag.error.",
            "provider_unavailable_behavior": "Use the false default.",
            "telemetry": {
                "evaluation_signal_ids": ["TEL-001"],
                "off_expected_signal": "flag.value=false",
                "on_expected_signal": "flag.value=true",
                "error_signal": "flag.error=true",
                "redaction_policy": "Do not emit tenant_id.",
            },
            "telemetry_ids": ["TEL-001"],
            "owner": "team-export",
            "expiry": None,
            "removal_condition": "All consumers use the candidate path for 30 days.",
            "rollback_action": "Set export.enabled to false.",
            "decision_ids": ["DEC-001"],
        }
        self.assertEqual(validate_schema_file(feature_flag, PLAN_SCHEMA), [])
        incomplete_flag = copy.deepcopy(feature_flag)
        incomplete_flag["feature_flag"].pop("error_behavior")
        self.assertNotEqual(validate_schema_file(incomplete_flag, PLAN_SCHEMA), [])

        def migration_step(identifier: str, order: int) -> dict[str, Any]:
            return {
                "id": identifier,
                "order": order,
                "action": f"Execute exact phase {identifier}.",
                "paths": ["migrations/001.sql"],
                "destructive": False,
                "status": "PLANNED",
                "change_ids": ["CHANGE-001"],
                "verification_ids": ["TEST-001"],
                "completion_condition": f"{identifier} verification passes.",
                "halt_id": None,
                "residual_gap_id": None,
            }

        expand_contract = copy.deepcopy(base)
        expand_contract["delivery_strategy"] = "expand-contract"
        expand_contract["expand_contract"] = {
            "expand": [migration_step("MIGSTEP-001", 1)],
            "backfill": [migration_step("MIGSTEP-002", 2)],
            "switch": [migration_step("MIGSTEP-003", 3)],
            "contract": [migration_step("MIGSTEP-004", 4)],
            "schema_and_data_invariants": ["INV-001"],
            "mixed_version_compatibility": "Old and new application versions accept the expanded schema.",
            "forward_boundary": "The switch phase begins after backfill verification.",
            "rollback_boundary": "Application rollback remains safe until contract begins.",
            "application_rollback": [migration_step("MIGSTEP-005", 5)],
            "data_rollback": [migration_step("MIGSTEP-006", 6)],
            "backup_restore_prerequisites": "A verified backup exists before backfill.",
            "idempotency_contract": "Every backfill step is rerunnable by primary key.",
            "exit_condition": "Contract verification passes after the compatibility window.",
            "validation_command_ids": ["CMD-001"],
            "decision_ids": ["DEC-001"],
        }
        self.assertEqual(validate_schema_file(expand_contract, PLAN_SCHEMA), [])
        incomplete_expand = copy.deepcopy(expand_contract)
        incomplete_expand["expand_contract"]["data_rollback"] = []
        self.assertNotEqual(validate_schema_file(incomplete_expand, PLAN_SCHEMA), [])

    def test_new_high_findings_and_unavailable_vulnerability_data_are_holds(self) -> None:
        repository = self.make_repository("finding-holds")
        pack = self.initialize_pack(repository)
        manifest = read_json(pack / "clone_pack.json")
        plan = read_json(pack / "enhancement_plan.json")
        index = read_json(pack / "clone_index.json")
        plan["security"] = {
            "baseline_findings": [],
            "candidate_findings": [
                {
                    "id": "FIND-001",
                    "tool": "fixture-scanner",
                    "severity": "critical",
                    "status": "open",
                    "summary": "Candidate introduces an exploitable fixture defect.",
                    "path": "app.txt",
                    "evidence_ids": ["E-001"],
                    "decision_ids": [],
                },
                {
                    "id": "FIND-002",
                    "tool": "fixture-scanner",
                    "severity": "high",
                    "status": "open",
                    "summary": "Candidate introduces a high fixture defect.",
                    "path": "app.txt",
                    "evidence_ids": ["E-001"],
                    "decision_ids": [],
                },
            ],
            "unavailable_data": [],
        }
        plan["dependency"]["unavailable_data"] = [
            {
                "code": "VULNERABILITY_DB_UNAVAILABLE",
                "missing_data": "The vulnerability database could not be queried.",
                "investigations": ["The pinned local scanner database is absent."],
                "resolution_question": "When will an approved database be available?",
                "authority": "repository security owner",
            }
        ]

        diagnostics = enhancement_profile_diagnostics(
            pack,
            manifest,
            plan,
            index,
            "verified-enhancement",
            require_seal=False,
        )
        high_holds = [item for item in diagnostics if item["code"] == "NEW_HIGH_FINDING"]
        self.assertEqual({item["record_id"] for item in high_holds}, {"FIND-001", "FIND-002"})
        self.assertTrue(all(item["severity"] == "HOLD" for item in high_holds))
        not_verified = [item for item in diagnostics if item["code"] == "NOT_VERIFIED"]
        self.assertEqual(len(not_verified), 1)
        self.assertEqual(not_verified[0]["severity"], "HOLD")
        self.assertIn("dependency", not_verified[0]["message"])

    def test_blocked_returns_only_to_prior_state_and_decline_requires_authority(self) -> None:
        repository = self.make_repository("lifecycle-authority")
        pack = self.initialize_pack(repository)
        blocked = transition_enhancement(
            pack,
            "ENH-001",
            "BLOCKED",
            actor="fixture-user",
            reason="Required test environment is unavailable.",
            timestamp=PINNED_TIMESTAMP,
        )
        self.assertEqual((blocked["from"], blocked["to"]), ("DRAFT", "BLOCKED"))
        with self.assertRaises(ClonePackError) as unresolved:
            transition_enhancement(
                pack,
                "ENH-001",
                "DRAFT",
                actor="fixture-user",
                reason="Unsupported resolution claim.",
                timestamp="2026-07-19T18:01:00+00:00",
            )
        self.assertEqual(
            unresolved.exception.diagnostic,
            "ENHANCEMENT_RESOLUTION_EVIDENCE_REQUIRED",
        )
        self.append_records(
            pack,
            [
                {"id": "E-001", "kind": "E", "links": {"enhancements": ["ENH-001"]}},
                {
                    "id": "DEC-001",
                    "kind": "DEC",
                    "state": "APPROVED",
                    "links": {"enhancements": ["ENH-001"]},
                },
            ],
        )
        resumed = transition_enhancement(
            pack,
            "ENH-001",
            "DRAFT",
            actor="fixture-user",
            reason="The exact environment is now available.",
            evidence_ids=["E-001"],
            timestamp="2026-07-19T18:01:00+00:00",
        )
        self.assertEqual((resumed["from"], resumed["to"]), ("BLOCKED", "DRAFT"))
        self.assertEqual(resumed["previous_event_sha256"], blocked["event_sha256"])
        with self.assertRaises(ClonePackError) as unauthorized:
            transition_enhancement(
                pack,
                "ENH-001",
                "DECLINED",
                actor="fixture-user",
                reason="No authority supplied.",
                timestamp="2026-07-19T18:02:00+00:00",
            )
        self.assertEqual(
            unauthorized.exception.diagnostic,
            "ENHANCEMENT_DECLINE_AUTHORITY_REQUIRED",
        )
        declined = transition_enhancement(
            pack,
            "ENH-001",
            "DECLINED",
            actor="fixture-user",
            reason="The authority declined the exact request.",
            decision_ids=["DEC-001"],
            timestamp="2026-07-19T18:02:00+00:00",
        )
        self.assertEqual((declined["from"], declined["to"]), ("DRAFT", "DECLINED"))
        self.assertEqual(declined["previous_event_sha256"], resumed["event_sha256"])

    def test_rehash_requires_explicit_selection_and_refuses_finalized_snapshot_evidence(self) -> None:
        repository = self.make_repository("rehash")
        pack = self.initialize_pack(repository)
        with self.assertRaises(ClonePackError) as implicit:
            rehash_targets(pack)
        self.assertEqual(implicit.exception.exit_code, 2)
        self.assertEqual(implicit.exception.diagnostic, "ARG_INVALID")

        updated = rehash_targets(pack, record_ids=["ENH-001"])
        self.assertEqual(updated["status"], "UPDATED")
        self.assertEqual([item["id"] for item in updated["records"]], ["ENH-001"])
        recorded, exit_code = repository_snapshot(
            pack,
            "adopted",
            record=True,
            check=False,
            timestamp=PINNED_TIMESTAMP,
        )
        self.assertEqual(exit_code, 0, recorded)
        with self.assertRaises(ClonePackError) as finalized:
            rehash_targets(pack, record_ids=[recorded["snapshot_id"]])
        self.assertEqual(finalized.exception.exit_code, 4)
        self.assertEqual(finalized.exception.diagnostic, "FINALIZED_EVIDENCE_IMMUTABLE")


if __name__ == "__main__":
    unittest.main()
