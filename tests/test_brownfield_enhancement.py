from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any

from scripts.clonepack.common import case_contract_sha256


ROOT = Path(__file__).resolve().parents[1]
CLONE_PACK = ROOT / "scripts" / "clone_pack.py"
PINNED_TIMESTAMP = "2026-07-19T12:00:00+00:00"


def canonical_json(value: Any) -> str:
    return json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise AssertionError(f"expected a JSON object in {path}")
    return value


def write_json(path: Path, value: Any) -> None:
    path.write_text(canonical_json(value), encoding="utf-8", newline="\n")


def run_cli(*arguments: object) -> subprocess.CompletedProcess[str]:
    environment = os.environ.copy()
    environment["LC_ALL"] = "C"
    environment["PYTHONHASHSEED"] = "0"
    return subprocess.run(
        [sys.executable, str(CLONE_PACK), *(str(argument) for argument in arguments)],
        cwd=ROOT,
        env=environment,
        text=True,
        encoding="utf-8",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )


def run_git(repository: Path, *arguments: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(repository), *arguments],
        text=True,
        encoding="utf-8",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )


def file_tree(root: Path) -> dict[str, bytes]:
    return {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


class BrownfieldEnhancementTests(unittest.TestCase):
    """Executable contract for the clone-pack/v2 brownfield extension.

    Successful public commands return canonical JSON. The deliberately small
    result shapes asserted below are the stable fields consumers need; commands
    may add fields without breaking this contract.
    """

    maxDiff = None

    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)
        self.temp_root = Path(self.temporary_directory.name)

    def make_repository(self, name: str, *, git: bool) -> Path:
        repository = self.temp_root / name
        repository.mkdir()
        (repository / "app.txt").write_text("version one\n", encoding="utf-8", newline="\n")
        (repository / "request.md").write_text(
            "# Authorized enhancement\n\nAdd deterministic status output.\n",
            encoding="utf-8",
            newline="\n",
        )
        (repository / "secrets.txt").write_text("unchanged\n", encoding="utf-8", newline="\n")
        if git:
            initialized = run_git(repository, "init", "-q")
            self.assertEqual(initialized.returncode, 0, initialized.stderr)
            for key, value in (("user.name", "Fixture User"), ("user.email", "fixture@example.invalid")):
                configured = run_git(repository, "config", key, value)
                self.assertEqual(configured.returncode, 0, configured.stderr)
            added = run_git(repository, "add", "app.txt", "request.md", "secrets.txt")
            self.assertEqual(added.returncode, 0, added.stderr)
            committed = run_git(repository, "commit", "-q", "-m", "fixture baseline")
            self.assertEqual(committed.returncode, 0, committed.stderr)
        return repository

    def enhancement_init(
        self,
        repository: Path,
        *,
        output_dir: str = "clone-pack",
        request_file: Path | None = None,
        adopt_dirty: bool = False,
    ) -> tuple[Path, subprocess.CompletedProcess[str]]:
        arguments: list[object] = [
            "enhancement-init",
            "--product-name",
            "Brownfield Fixture",
            "--product-type",
            "cli",
            "--playbook",
            "cli",
            "--enhancement-id",
            "ENH-001",
            "--title",
            "Add status output",
            "--change-type",
            "feature",
            "--request-file",
            request_file or repository / "request.md",
            "--repo-root",
            repository,
            "--output-dir",
            output_dir,
            "--timestamp",
            PINNED_TIMESTAMP,
        ]
        if adopt_dirty:
            arguments.append("--adopt-dirty")
        result = run_cli(*arguments)
        return (repository / output_dir).resolve(), result

    def assert_canonical_payload(self, result: subprocess.CompletedProcess[str]) -> dict[str, Any]:
        self.assertNotEqual(result.stdout, "", result.stderr)
        payload = json.loads(result.stdout)
        self.assertIsInstance(payload, dict)
        self.assertEqual(result.stdout, canonical_json(payload))
        return payload

    def assert_init_success(self, repository: Path, *, output_dir: str = "clone-pack") -> Path:
        pack, initialized = self.enhancement_init(repository, output_dir=output_dir)
        self.assertEqual(initialized.returncode, 0, initialized.stderr)
        self.assertEqual(initialized.stderr, "")
        payload = self.assert_canonical_payload(initialized)
        self.assertEqual(
            {key: payload[key] for key in ("enhancement_id", "pack_path", "status")},
            {
                "enhancement_id": "ENH-001",
                "pack_path": pack.as_posix(),
                "status": "DRAFT",
            },
        )
        return pack

    def snapshot(
        self,
        pack: Path,
        role: str,
        operation: str,
        *includes: str,
    ) -> subprocess.CompletedProcess[str]:
        arguments: list[object] = ["repo-snapshot", pack, "--role", role, operation]
        for include in includes:
            arguments.extend(("--include", include))
        return run_cli(*arguments)

    def retained_result(self, pack: Path, relative_path: str) -> dict[str, Any]:
        candidate = Path(relative_path)
        self.assertFalse(candidate.is_absolute())
        resolved = (pack / candidate).resolve()
        self.assertTrue(resolved.is_relative_to(pack.resolve()))
        self.assertTrue(resolved.is_file(), relative_path)
        return read_json(resolved)

    def configure_preservation_case(self, pack: Path) -> None:
        plan_path = pack / "enhancement_plan.json"
        plan = read_json(plan_path)
        case = {
            "id": "PRES-001",
            "required": True,
            "argv": [
                sys.executable,
                "-c",
                "from pathlib import Path; print(Path('app.txt').read_text(encoding='utf-8'), end='')",
            ],
            "cwd": ".",
            "environment": {},
            "timeout_seconds": 30,
            "expected_exit": 0,
            "artifact_paths": [],
            "comparator": "exact",
            "normalizations": [],
            "options": {},
            "known_failure": None,
            "baseline_result": None,
            "regression_result": None,
        }
        plan["preservation_cases"] = [case]
        write_json(plan_path, plan)

        lines = plan_path.read_text(encoding="utf-8").splitlines(keepends=True)
        anchor = '"id": "PRES-001"'
        matches = [line for line in lines if anchor in line]
        self.assertEqual(len(matches), 1)
        index_path = pack / "clone_index.json"
        index = read_json(index_path)
        enhancement = next(record for record in index["records"] if record["id"] == "ENH-001")
        enhancement.setdefault("links", {})["preservations"] = ["PRES-001"]
        index["records"].append(
            {
                "id": "PRES-001",
                "kind": "PRES",
                "locator": {
                    "path": "enhancement_plan.json",
                    "anchor": anchor,
                    "sha256": hashlib.sha256(matches[0].encode("utf-8")).hexdigest(),
                },
                "links": {"enhancements": ["ENH-001"]},
                "applicability": "REQUIRED",
                "state": "READY",
                "attributes": {"case_sha256": case_contract_sha256(case)},
            }
        )
        write_json(index_path, index)

    def configure_scope(self, pack: Path) -> None:
        plan_path = pack / "enhancement_plan.json"
        plan = read_json(plan_path)
        plan["scope"] = {
            "allowed_paths": ["app.txt"],
            "forbidden_paths": ["secrets.txt"],
            "generated_paths": [],
            "rename_policy": "forbid",
            "protected_dirty_paths": [],
        }
        plan["change_map"] = [
            {
                "id": "CHANGE-001",
                "operation": "modify",
                "paths": ["app.txt"],
                "generated": False,
                "requirement_ids": [],
                "slice_ids": [],
            }
        ]
        write_json(plan_path, plan)
        lines = plan_path.read_text(encoding="utf-8").splitlines(keepends=True)
        anchor = '"id": "CHANGE-001"'
        matches = [line for line in lines if anchor in line]
        self.assertEqual(len(matches), 1)
        index_path = pack / "clone_index.json"
        index = read_json(index_path)
        enhancement = next(record for record in index["records"] if record["id"] == "ENH-001")
        enhancement.setdefault("links", {})["changes"] = ["CHANGE-001"]
        index["records"].append(
            {
                "id": "CHANGE-001",
                "kind": "CHANGE",
                "locator": {
                    "path": "enhancement_plan.json",
                    "anchor": anchor,
                    "sha256": hashlib.sha256(matches[0].encode("utf-8")).hexdigest(),
                },
                "links": {"enhancements": ["ENH-001"]},
                "applicability": "REQUIRED",
                "state": "READY",
                "attributes": {"operation": "modify", "paths": ["app.txt"]},
            }
        )
        write_json(index_path, index)

    def set_fixture_state(self, pack: Path, status: str) -> None:
        """Place a focused command fixture at an exact lifecycle boundary.

        Lifecycle behavior itself is covered separately. Preservation and scope
        tests use this helper to isolate the command contract without claiming a
        complete enhancement-ready plan.
        """

        plan_path = pack / "enhancement_plan.json"
        plan = read_json(plan_path)
        plan["status"] = status
        plan["blocked_prior_state"] = None
        write_json(plan_path, plan)
        index_path = pack / "clone_index.json"
        index = read_json(index_path)
        enhancement = next(record for record in index["records"] if record["id"] == "ENH-001")
        enhancement["state"] = status
        enhancement["attributes"]["status"] = status
        write_json(index_path, index)

    def test_enhancement_init_creates_a_clean_draft_without_mutating_product_files(self) -> None:
        repository = self.make_repository("clean-git", git=True)
        before = {
            name: (repository / name).read_bytes()
            for name in ("app.txt", "request.md", "secrets.txt")
        }

        pack = self.assert_init_success(repository)

        manifest = read_json(pack / "clone_pack.json")
        self.assertEqual(
            {key: manifest["workstream"][key] for key in ("kind", "mode", "enhancement_id")},
            {
                "kind": "brownfield-enhancement",
                "mode": "enhancement-plan",
                "enhancement_id": "ENH-001",
            },
        )
        self.assertEqual(manifest["plans"]["repository_inventory"], "repository_inventory.json")
        self.assertEqual(manifest["plans"]["enhancement"], "enhancement_plan.json")
        inventory = read_json(pack / "repository_inventory.json")
        enhancement = read_json(pack / "enhancement_plan.json")
        self.assertEqual(inventory["schema_version"], "clone-repository-inventory/v2")
        self.assertEqual(enhancement["schema_version"], "clone-enhancement-plan/v2")
        self.assertEqual(enhancement["enhancement_id"], "ENH-001")
        self.assertEqual(enhancement["status"], "DRAFT")
        self.assertEqual(
            enhancement["request"],
            {
                "source_path": "request.md",
                "evidence_path": "evidence/requests/ENH-001/request.md",
                "sha256": hashlib.sha256((repository / "request.md").read_bytes()).hexdigest(),
            },
        )
        self.assertEqual(
            (pack / enhancement["request"]["evidence_path"]).read_bytes(),
            (repository / "request.md").read_bytes(),
        )
        self.assertEqual(
            before,
            {name: (repository / name).read_bytes() for name in before},
        )

    def test_enhancement_init_rejects_dirty_git_by_default_and_records_explicit_adoption(self) -> None:
        repository = self.make_repository("dirty-git", git=True)
        (repository / "app.txt").write_text("owner work in progress\n", encoding="utf-8", newline="\n")
        product_bytes = (repository / "app.txt").read_bytes()

        pack, rejected = self.enhancement_init(repository)
        self.assertEqual(rejected.returncode, 4)
        self.assertIn("REPOSITORY_DIRTY:", rejected.stderr)
        self.assertEqual(rejected.stdout, "")
        self.assertFalse(pack.exists())

        pack, adopted = self.enhancement_init(repository, adopt_dirty=True)
        self.assertEqual(adopted.returncode, 0, adopted.stderr)
        self.assert_canonical_payload(adopted)
        inventory = read_json(pack / "repository_inventory.json")
        plan = read_json(pack / "enhancement_plan.json")
        self.assertEqual(inventory["dirty_paths"], ["app.txt"])
        self.assertEqual(plan["scope"]["protected_dirty_paths"], ["app.txt"])
        self.assertEqual((repository / "app.txt").read_bytes(), product_bytes)

    def test_enhancement_init_rejects_outside_non_utf8_and_empty_requests(self) -> None:
        outside_repository = self.make_repository("outside-request", git=True)
        outside = self.temp_root / "outside.md"
        outside.write_text("not repository-contained\n", encoding="utf-8")
        outside_pack, outside_result = self.enhancement_init(
            outside_repository,
            request_file=outside,
        )
        self.assertEqual(outside_result.returncode, 2)
        self.assertIn("REQUEST_OUTSIDE_REPOSITORY:", outside_result.stderr)
        self.assertFalse(outside_pack.exists())

        non_utf8_repository = self.make_repository("non-utf8-request", git=True)
        bad_request = non_utf8_repository / "request.md"
        bad_request.write_bytes(b"\xff\xfe")
        self.assertEqual(run_git(non_utf8_repository, "add", "request.md").returncode, 0)
        self.assertEqual(run_git(non_utf8_repository, "commit", "-q", "-m", "invalid request fixture").returncode, 0)
        non_utf8_pack, non_utf8_result = self.enhancement_init(non_utf8_repository)
        self.assertEqual(non_utf8_result.returncode, 2)
        self.assertIn("REQUEST_NOT_UTF8:", non_utf8_result.stderr)
        self.assertFalse(non_utf8_pack.exists())

        empty_repository = self.make_repository("empty-request", git=True)
        (empty_repository / "request.md").write_text("", encoding="utf-8")
        self.assertEqual(run_git(empty_repository, "add", "request.md").returncode, 0)
        self.assertEqual(run_git(empty_repository, "commit", "-q", "-m", "empty request fixture").returncode, 0)
        empty_pack, empty_result = self.enhancement_init(empty_repository)
        self.assertEqual(empty_result.returncode, 2)
        self.assertIn("REQUEST_EMPTY:", empty_result.stderr)
        self.assertFalse(empty_pack.exists())

    def test_legacy_v2_manifest_remains_valid_without_optional_enhancement_fields(self) -> None:
        repository = self.make_repository("legacy-v2", git=False)
        initialized = run_cli(
            "init",
            "--product-name",
            "Legacy V2 Fixture",
            "--product-type",
            "cli",
            "--playbook",
            "cli",
            "--source-description",
            "authorized local fixture",
            "--repo-root",
            repository,
            "--output-dir",
            "legacy-pack",
            "--timestamp",
            PINNED_TIMESTAMP,
        )
        self.assertEqual(initialized.returncode, 0, initialized.stderr)
        pack = repository / "legacy-pack"
        manifest = read_json(pack / "clone_pack.json")
        self.assertEqual(manifest["workstream"], {"kind": "clone-mvp"})
        # A 2.0-authored v2 manifest may omit the optional 2.1 workstream.
        manifest.pop("workstream")
        write_json(pack / "clone_pack.json", manifest)
        self.assertNotIn("repository_inventory", manifest["plans"])
        self.assertNotIn("enhancement", manifest["plans"])

        validated = run_cli("validate", pack, "--profile", "scaffold", "--format", "json")
        self.assertEqual(validated.returncode, 0, validated.stderr)
        payload = self.assert_canonical_payload(validated)
        self.assertEqual(payload["status"], "PASS")

    def test_profiles_reject_noninitial_or_tampered_enhancement_history(self) -> None:
        repository = self.make_repository("history-profile", git=True)
        pack = self.assert_init_success(repository)
        self.set_fixture_state(pack, "IN_PROGRESS")

        missing = run_cli("validate", pack, "--profile", "implementation", "--format", "json")
        missing_payload = self.assert_canonical_payload(missing)
        self.assertNotEqual(missing.returncode, 0)
        self.assertIn(
            "ENHANCEMENT_HISTORY_INCOMPLETE",
            {item["code"] for item in missing_payload["diagnostics"]},
        )

        (pack / "history" / "enhancement_events.jsonl").write_text(
            '{"not":"a valid enhancement event"}\n',
            encoding="utf-8",
            newline="\n",
        )
        tampered = run_cli("validate", pack, "--profile", "implementation", "--format", "json")
        tampered_payload = self.assert_canonical_payload(tampered)
        self.assertNotEqual(tampered.returncode, 0)
        self.assertIn(
            "ENHANCEMENT_HISTORY_INVALID",
            {item["code"] for item in tampered_payload["diagnostics"]},
        )

    def test_enhancement_ready_reports_a_malformed_optional_plan(self) -> None:
        repository = self.make_repository("malformed-plan", git=False)
        pack = self.assert_init_success(repository)
        write_json(pack / "enhancement_plan.json", {})

        validated = run_cli("validate", pack, "--profile", "enhancement-ready", "--format", "json")
        self.assertEqual(validated.returncode, 1, validated.stderr)
        payload = self.assert_canonical_payload(validated)
        self.assertIn(
            "SCHEMA_INVALID",
            {
                diagnostic["code"]
                for diagnostic in payload["diagnostics"]
                if diagnostic["path"].startswith("enhancement_plan.json#")
            },
        )

    def test_enhancement_profiles_validate_every_mandatory_legacy_plan_schema(self) -> None:
        repository = self.make_repository("enhancement-plan-schemas", git=False)
        pack = self.assert_init_success(repository)
        capture_path = pack / "capture_plan.json"
        capture = read_json(capture_path)
        capture["schema_version"] = "GARBAGE/v99"
        capture["cases"] = "not-an-array"
        capture["bogus_field"] = True
        write_json(capture_path, capture)

        expected = {
            (
                "capture_plan.json#/bogus_field",
                "additional property is not allowed",
            ),
            ("capture_plan.json#/cases", "expected type array"),
            (
                "capture_plan.json#/schema_version",
                "value must equal const 'clone-capture-plan/v2'",
            ),
        }
        for profile in (
            "repository-adopted",
            "enhancement-ready",
            "implementation",
            "verified-enhancement",
        ):
            with self.subTest(profile=profile):
                validated = run_cli("validate", pack, "--profile", profile, "--format", "json")
                payload = self.assert_canonical_payload(validated)
                schema_diagnostics = {
                    (diagnostic["path"], diagnostic["message"])
                    for diagnostic in payload["diagnostics"]
                    if diagnostic["code"] == "SCHEMA_INVALID"
                }
                self.assertEqual(schema_diagnostics, expected)

        initialized = run_cli(
            "init",
            "--product-name",
            "Greenfield Schema Control",
            "--product-type",
            "cli",
            "--playbook",
            "cli",
            "--source-description",
            "authorized local fixture",
            "--repo-root",
            repository,
            "--output-dir",
            "greenfield-pack",
            "--timestamp",
            PINNED_TIMESTAMP,
        )
        self.assertEqual(initialized.returncode, 0, initialized.stderr)
        greenfield_capture_path = repository / "greenfield-pack" / "capture_plan.json"
        greenfield_capture = read_json(greenfield_capture_path)
        greenfield_capture["schema_version"] = "GARBAGE/v99"
        greenfield_capture["cases"] = "not-an-array"
        greenfield_capture["bogus_field"] = True
        write_json(greenfield_capture_path, greenfield_capture)

        control = run_cli(
            "validate",
            repository / "greenfield-pack",
            "--profile",
            "baseline-ready",
            "--format",
            "json",
        )
        control_payload = self.assert_canonical_payload(control)
        control_schema_diagnostics = {
            (diagnostic["path"], diagnostic["message"])
            for diagnostic in control_payload["diagnostics"]
            if diagnostic["code"] == "SCHEMA_INVALID"
        }
        self.assertEqual(control_schema_diagnostics, expected)

    def test_git_snapshot_record_check_drift_and_pack_self_exclusion(self) -> None:
        repository = self.make_repository("git-snapshot", git=True)
        pack = self.assert_init_success(repository)

        recorded = self.snapshot(pack, "adopted", "--record")
        self.assertEqual(recorded.returncode, 0, recorded.stderr)
        payload = self.assert_canonical_payload(recorded)
        self.assertEqual(
            {key: payload[key] for key in ("repository_kind", "role", "status")},
            {"repository_kind": "git", "role": "adopted", "status": "RECORDED"},
        )
        self.assertRegex(payload["snapshot_id"], r"^SNAP-[0-9]{3,}$")
        snapshot = self.retained_result(pack, payload["snapshot_path"])
        self.assertEqual(
            [entry["path"] for entry in snapshot["entries"]],
            ["app.txt", "request.md", "secrets.txt"],
        )
        self.assertFalse(any(entry["path"].startswith(".git/") for entry in snapshot["entries"]))
        self.assertFalse(any(entry["path"].startswith("clone-pack/") for entry in snapshot["entries"]))

        (pack / "self-excluded.tmp").write_text("pack-only mutation\n", encoding="utf-8")
        before_check = file_tree(pack)
        matching = self.snapshot(pack, "adopted", "--check")
        self.assertEqual(matching.returncode, 0, matching.stderr)
        match_payload = self.assert_canonical_payload(matching)
        self.assertEqual(match_payload["status"], "MATCH")
        self.assertEqual(file_tree(pack), before_check)

        (repository / "app.txt").write_text("version two\n", encoding="utf-8", newline="\n")
        before_drift_check = file_tree(pack)
        drift = self.snapshot(pack, "adopted", "--check")
        self.assertEqual(drift.returncode, 4, drift.stderr)
        drift_payload = self.assert_canonical_payload(drift)
        self.assertEqual(drift_payload["status"], "DRIFT")
        self.assertNotEqual(drift_payload["expected_sha256"], drift_payload["actual_sha256"])
        self.assertEqual(file_tree(pack), before_drift_check)

    def test_non_git_snapshot_is_full_tree_deterministic_and_self_excluding(self) -> None:
        repository = self.make_repository("filesystem-snapshot", git=False)
        pack = self.assert_init_success(repository)

        recorded = self.snapshot(pack, "adopted", "--record")
        self.assertEqual(recorded.returncode, 0, recorded.stderr)
        payload = self.assert_canonical_payload(recorded)
        self.assertEqual(payload["repository_kind"], "filesystem")
        snapshot = self.retained_result(pack, payload["snapshot_path"])
        self.assertEqual(
            [entry["path"] for entry in snapshot["entries"]],
            ["app.txt", "request.md", "secrets.txt"],
        )

        (pack / "ignored-by-snapshot.txt").write_text("self excluded\n", encoding="utf-8")
        matching = self.snapshot(pack, "adopted", "--check")
        self.assertEqual(matching.returncode, 0, matching.stderr)
        self.assertEqual(self.assert_canonical_payload(matching)["status"], "MATCH")

        (repository / "secrets.txt").write_text("changed\n", encoding="utf-8", newline="\n")
        drift = self.snapshot(pack, "adopted", "--check")
        self.assertEqual(drift.returncode, 4, drift.stderr)
        self.assertEqual(self.assert_canonical_payload(drift)["status"], "DRIFT")

    def test_enhancement_lifecycle_starts_at_draft_and_hash_chains_legal_events(self) -> None:
        repository = self.make_repository("lifecycle", git=False)
        pack = self.assert_init_success(repository)
        recorded = self.snapshot(pack, "adopted", "--record")
        self.assertEqual(recorded.returncode, 0, recorded.stderr)
        history_path = pack / "history" / "enhancement_events.jsonl"
        self.assertEqual(history_path.read_text(encoding="utf-8"), "")
        index = read_json(pack / "clone_index.json")
        enhancement = next(record for record in index["records"] if record["id"] == "ENH-001")
        self.assertEqual(enhancement["state"], "DRAFT")

        ready = run_cli(
            "enhancement-transition",
            pack,
            "ENH-001",
            "--to",
            "READY",
            "--actor",
            "fixture-user",
            "--reason",
            "repository adoption is recorded",
            "--timestamp",
            PINNED_TIMESTAMP,
        )
        self.assertEqual(ready.returncode, 0, ready.stderr)
        ready_event = self.assert_canonical_payload(ready)
        self.assertEqual(
            {key: ready_event[key] for key in ("enhancement_id", "sequence", "from", "to", "previous_event_sha256")},
            {
                "enhancement_id": "ENH-001",
                "sequence": 1,
                "from": "DRAFT",
                "to": "READY",
                "previous_event_sha256": "",
            },
        )
        hash_input = dict(ready_event)
        supplied_hash = hash_input.pop("event_sha256")
        self.assertEqual(supplied_hash, hashlib.sha256(canonical_json(hash_input).encode("utf-8")).hexdigest())
        self.assertEqual(json.loads(history_path.read_text(encoding="utf-8")), ready_event)

        history_before_illegal = history_path.read_bytes()
        illegal = run_cli(
            "enhancement-transition",
            pack,
            "ENH-001",
            "--to",
            "VERIFIED",
            "--actor",
            "fixture-user",
            "--reason",
            "illegal shortcut",
        )
        self.assertEqual(illegal.returncode, 1)
        self.assertIn("ENHANCEMENT_ILLEGAL_TRANSITION:", illegal.stderr)
        self.assertEqual(history_path.read_bytes(), history_before_illegal)

        in_progress = run_cli(
            "enhancement-transition",
            pack,
            "ENH-001",
            "--to",
            "IN_PROGRESS",
            "--actor",
            "fixture-user",
            "--reason",
            "implementation begins",
            "--timestamp",
            "2026-07-19T12:01:00+00:00",
        )
        self.assertEqual(in_progress.returncode, 1)
        self.assertIn("ENHANCEMENT_PROFILE_GATE:", in_progress.stderr)
        self.assertEqual(
            json.loads(history_path.read_text(encoding="utf-8")),
            ready_event,
        )

    def test_baseline_is_immutable_and_regression_compares_candidate_to_adopted_output(self) -> None:
        repository = self.make_repository("preservation", git=False)
        pack = self.assert_init_success(repository)
        self.configure_preservation_case(pack)
        adopted = self.snapshot(pack, "adopted", "--record")
        self.assertEqual(adopted.returncode, 0, adopted.stderr)
        adopted_id = self.assert_canonical_payload(adopted)["snapshot_id"]
        self.set_fixture_state(pack, "READY")

        baseline = run_cli("baseline-run", pack, "--case", "PRES-001")
        self.assertEqual(baseline.returncode, 0, baseline.stderr)
        baseline_payload = self.assert_canonical_payload(baseline)
        self.assertEqual(
            {key: baseline_payload[key] for key in ("case_id", "status", "adopted_snapshot_id")},
            {"case_id": "PRES-001", "status": "PASS", "adopted_snapshot_id": adopted_id},
        )
        baseline_result = self.retained_result(pack, baseline_payload["result_path"])
        baseline_sha256 = hashlib.sha256(canonical_json(baseline_result).encode("utf-8")).hexdigest()

        repeated = run_cli("baseline-run", pack, "--case", "PRES-001")
        self.assertEqual(repeated.returncode, 1)
        self.assertIn("BASELINE_IMMUTABLE:", repeated.stderr)
        self.assertEqual(
            hashlib.sha256(canonical_json(self.retained_result(pack, baseline_payload["result_path"])).encode("utf-8")).hexdigest(),
            baseline_sha256,
        )

        self.set_fixture_state(pack, "IN_PROGRESS")
        (repository / "app.txt").write_text("version two\n", encoding="utf-8", newline="\n")
        candidate = self.snapshot(pack, "candidate", "--record")
        self.assertEqual(candidate.returncode, 0, candidate.stderr)
        candidate_id = self.assert_canonical_payload(candidate)["snapshot_id"]
        self.set_fixture_state(pack, "IMPLEMENTED")
        regressed = run_cli("regression", pack, "--case", "PRES-001")
        self.assertEqual(regressed.returncode, 5, regressed.stderr)
        regression_payload = self.assert_canonical_payload(regressed)
        self.assertEqual(
            {key: regression_payload[key] for key in ("case_id", "status", "candidate_snapshot_id")},
            {"case_id": "PRES-001", "status": "FAIL", "candidate_snapshot_id": candidate_id},
        )
        self.assertEqual(regression_payload["baseline_result_path"], baseline_payload["result_path"])

    def test_verify_scope_accepts_declared_path_and_rejects_unrelated_change(self) -> None:
        repository = self.make_repository("scope", git=False)
        pack = self.assert_init_success(repository)
        self.configure_scope(pack)
        adopted = self.snapshot(pack, "adopted", "--record")
        self.assertEqual(adopted.returncode, 0, adopted.stderr)

        self.set_fixture_state(pack, "IN_PROGRESS")
        (repository / "app.txt").write_text("version two\n", encoding="utf-8", newline="\n")
        candidate = self.snapshot(pack, "candidate", "--record")
        self.assertEqual(candidate.returncode, 0, candidate.stderr)
        self.set_fixture_state(pack, "IMPLEMENTED")
        accepted = run_cli("verify-scope", pack, "--enhancement", "ENH-001")
        self.assertEqual(accepted.returncode, 0, accepted.stderr)
        accepted_payload = self.assert_canonical_payload(accepted)
        self.assertEqual(accepted_payload["status"], "PASS")
        self.assertEqual(accepted_payload["changed_paths"], ["app.txt"])
        self.assertRegex(accepted_payload["scope_id"], r"^SCOPE-[0-9]{3,}$")
        self.retained_result(pack, accepted_payload["result_path"])

        self.set_fixture_state(pack, "IN_PROGRESS")
        (repository / "secrets.txt").write_text("unauthorized change\n", encoding="utf-8", newline="\n")
        second_candidate = self.snapshot(pack, "candidate", "--record")
        self.assertEqual(second_candidate.returncode, 0, second_candidate.stderr)
        self.set_fixture_state(pack, "IMPLEMENTED")
        rejected = run_cli("verify-scope", pack, "--enhancement", "ENH-001")
        self.assertEqual(rejected.returncode, 5, rejected.stderr)
        rejected_payload = self.assert_canonical_payload(rejected)
        self.assertEqual(rejected_payload["status"], "FAIL")
        self.assertEqual(rejected_payload["unauthorized_paths"], ["secrets.txt"])

    def test_cli_help_exposes_every_brownfield_command_and_exact_selector_flags(self) -> None:
        root_help = run_cli("--help")
        self.assertEqual(root_help.returncode, 0, root_help.stderr)
        commands = {
            "enhancement-init": (
                "--product-name",
                "--product-type",
                "--playbook",
                "--enhancement-id",
                "--title",
                "--change-type",
                "--request-file",
                "--repo-root",
                "--output-dir",
                "--adopt-dirty",
                "--timestamp",
            ),
            "repo-snapshot": ("--role", "--record", "--check", "--include"),
            "baseline-run": ("--case", "--all"),
            "regression": ("--case", "--all"),
            "verify-scope": ("--enhancement",),
            "enhancement-transition": (
                "--to",
                "--actor",
                "--reason",
                "--evidence",
                "--decision",
                "--timestamp",
            ),
            "rehash": ("--record", "--case"),
        }
        for command, flags in commands.items():
            with self.subTest(command=command):
                self.assertIn(command, root_help.stdout)
                help_result = run_cli(command, "--help")
                self.assertEqual(help_result.returncode, 0, help_result.stderr)
                for flag in flags:
                    self.assertIn(flag, help_result.stdout)


if __name__ == "__main__":
    unittest.main()
