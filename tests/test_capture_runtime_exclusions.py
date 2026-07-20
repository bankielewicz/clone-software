from __future__ import annotations

import copy
import json
import os
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any
from unittest import mock

from scripts.clonepack import operations as operations_module
from scripts.clonepack.common import ClonePackError, canonical_json, case_contract_sha256
from scripts.clonepack.schema import validate_schema_file


ROOT = Path(__file__).resolve().parents[1]
CLONE_PACK = ROOT / "scripts" / "clone_pack.py"
CAPTURE_SCHEMA = ROOT / "assets" / "schemas" / "capture-plan-v2.schema.json"
PINNED_TIMESTAMP = "2026-07-20T12:00:00+00:00"


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise AssertionError(f"expected object: {path}")
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
        check=False,
        text=True,
        encoding="utf-8",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=30,
    )


def index_record(
    identifier: str,
    kind: str,
    *,
    links: dict[str, list[str]] | None = None,
    attributes: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "id": identifier,
        "kind": kind,
        "locator": {"path": "clone_brief.md", "anchor": None, "sha256": None},
        "links": links or {},
        "applicability": "MVP",
        "state": "READY",
        "attributes": attributes or {},
    }


class CaptureRuntimeExclusionTests(unittest.TestCase):
    maxDiff = None

    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.repository = self.root / "repository"
        self.repository.mkdir()
        self.product = self.repository / "product"
        self.product.mkdir()
        (self.product / "app.txt").write_text("product\n", encoding="utf-8", newline="\n")
        initialized = run_cli(
            "init",
            "--product-name",
            "Runtime capture fixture",
            "--product-type",
            "cli",
            "--source-description",
            "Authorized local fixture",
            "--repo-root",
            self.repository,
            "--output-dir",
            "pack",
            "--timestamp",
            PINNED_TIMESTAMP,
        )
        self.assertEqual(initialized.returncode, 0, initialized.stderr)
        self.pack = self.repository / "pack"

    def make_runtime_directory(self) -> Path:
        runtime = self.product / ".codex"
        runtime.mkdir()
        runtime.chmod(0o555)
        return runtime

    def exclusion(self, runtime: Path, *, authority_ids: list[str] | None = None) -> dict[str, Any]:
        metadata = runtime.lstat()
        return {
            "id": "RUNTIME-001",
            "path": runtime.relative_to(self.repository).as_posix(),
            "reason": "User-authorized empty tool-runtime directory excluded from product identity.",
            "authority_ids": authority_ids or ["DEC-004"],
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

    def case(
        self,
        exclusion: dict[str, Any],
        *,
        authorization_ids: list[str] | None = None,
    ) -> dict[str, Any]:
        return {
            "id": "CAP-001",
            "adapter": "filesystem",
            "side": "clone",
            "environment_id": "ENV-001",
            "required": True,
            "authorization_decision_ids": authorization_ids or ["DEC-004"],
            "safe_test_environment": True,
            "timeout_seconds": 10,
            "input": {
                "path": "product",
                "runtime_exclusions": [exclusion],
            },
            "lifecycle": {"setup": None, "teardown": None},
            "redactions": [],
            "result": None,
        }

    def install_case(self, case: dict[str, Any]) -> None:
        plan = read_json(self.pack / "capture_plan.json")
        plan["cases"] = [case]
        write_json(self.pack / "capture_plan.json", plan)
        decision_ids = sorted(set(case["authorization_decision_ids"]))
        records = [index_record("ENV-001", "ENV"), index_record("E-004", "E")]
        records.extend(index_record(identifier, "DEC") for identifier in decision_ids)
        records.append(
            index_record(
                "CAP-001",
                "CAP",
                links={"environments": ["ENV-001"], "decisions": decision_ids},
                attributes={"case_sha256": case_contract_sha256(case)},
            )
        )
        index = read_json(self.pack / "clone_index.json")
        index["records"] = records
        write_json(self.pack / "clone_index.json", index)

    def test_capture_schema_and_result_bind_canonical_runtime_exclusions(self) -> None:
        runtime = self.make_runtime_directory()
        exclusion = self.exclusion(runtime)
        case = self.case(exclusion)
        plan = read_json(self.pack / "capture_plan.json")
        plan["cases"] = [case]
        self.assertEqual(validate_schema_file(plan, CAPTURE_SCHEMA), [])
        expected_case_hash = case_contract_sha256(case)
        self.install_case(case)

        completed = run_cli(
            "capture",
            self.pack,
            "--case",
            "CAP-001",
            "--timestamp",
            PINNED_TIMESTAMP,
        )

        self.assertEqual(completed.returncode, 0, completed.stderr)
        result = json.loads(completed.stdout)
        self.assertEqual(result["case_sha256"], expected_case_hash)
        self.assertEqual(result["summary"]["runtime_exclusions"], [exclusion])
        filesystem_artifact = next(
            self.pack / artifact["path"]
            for artifact in result["artifacts"]
            if str(artifact["path"]).endswith("filesystem.json")
        )
        snapshot = read_json(filesystem_artifact)
        self.assertEqual(snapshot["runtime_exclusions"], [exclusion])
        self.assertEqual([entry["path"] for entry in snapshot["entries"]], ["app.txt"])

    def test_capture_requires_every_runtime_authority_in_case_authorization(self) -> None:
        runtime = self.make_runtime_directory()
        exclusion = self.exclusion(runtime, authority_ids=["DEC-004", "DEC-005"])
        case = self.case(exclusion, authorization_ids=["DEC-004"])
        self.install_case(case)

        completed = run_cli("capture", self.pack, "--case", "CAP-001")

        self.assertNotEqual(completed.returncode, 0)
        self.assertIn("AUTHORIZATION_REQUIRED", completed.stderr)
        self.assertFalse((self.pack / "evidence" / "captures" / "CAP-001").exists())
        self.assertFalse((self.pack / "evidence" / "captures" / ".CAP-001.staging").exists())

    def test_populated_runtime_directory_blocks_before_capture_output(self) -> None:
        runtime = self.make_runtime_directory()
        exclusion = self.exclusion(runtime)
        runtime.chmod(0o755)
        (runtime / "session.json").write_text("{}\n", encoding="utf-8", newline="\n")
        runtime.chmod(0o555)
        case = self.case(exclusion)
        self.install_case(case)

        completed = run_cli("capture", self.pack, "--case", "CAP-001")

        self.assertNotEqual(completed.returncode, 0)
        self.assertIn("RUNTIME_EXCLUSION_NOT_EMPTY", completed.stderr)
        self.assertFalse((self.pack / "evidence" / "captures" / "CAP-001").exists())
        self.assertFalse((self.pack / "evidence" / "captures" / ".CAP-001.staging").exists())

    def test_missing_descriptor_capability_blocks_before_context_or_capture_collection(self) -> None:
        runtime = self.make_runtime_directory()
        exclusion = self.exclusion(runtime)
        case = self.case(exclusion)
        self.install_case(case)
        manifest = read_json(self.pack / "clone_pack.json")

        with mock.patch(
            "scripts.clonepack.repository.RUNTIME_DESCRIPTOR_CAPABLE",
            False,
        ), mock.patch.object(
            operations_module,
            "_capture_governed_paths",
            side_effect=AssertionError("governed-path collection must not run"),
        ) as governed_collection, mock.patch.object(
            operations_module,
            "_snapshot_tree",
            side_effect=AssertionError("filesystem capture must not run"),
        ) as filesystem_collection:
            with self.assertRaises(ClonePackError) as raised:
                operations_module._execute_capture_case(
                    self.pack,
                    manifest,
                    case,
                    PINNED_TIMESTAMP,
                )

        self.assertEqual(raised.exception.diagnostic, "RUNTIME_EXCLUSION_CAPABILITY_MISSING")
        self.assertEqual(raised.exception.exit_code, 3)
        governed_collection.assert_not_called()
        filesystem_collection.assert_not_called()
        self.assertFalse((self.pack / "evidence" / "captures" / "CAP-001").exists())
        self.assertFalse((self.pack / "evidence" / "captures" / ".CAP-001.staging").exists())

    def test_capture_rechecks_runtime_identity_after_filesystem_walk(self) -> None:
        runtime = self.make_runtime_directory()
        exclusion = self.exclusion(runtime)
        case = self.case(exclusion)
        self.install_case(case)
        manifest = read_json(self.pack / "clone_pack.json")
        output = self.root / "capture-output"
        output.mkdir()
        original_recheck = operations_module.recheck_runtime_exclusions
        calls = 0

        def mutate_after_first_recheck(bindings: object) -> None:
            nonlocal calls
            original_recheck(bindings)
            calls += 1
            if calls == 1:
                runtime.chmod(0o755)
                (runtime / "late.json").write_text("{}\n", encoding="utf-8", newline="\n")
                runtime.chmod(0o555)

        with mock.patch(
            "scripts.clonepack.operations.recheck_runtime_exclusions",
            side_effect=mutate_after_first_recheck,
        ):
            with self.assertRaises(ClonePackError) as raised:
                operations_module._capture_filesystem(self.pack, manifest, case, output)

        self.assertIn(
            raised.exception.diagnostic,
            {"RUNTIME_EXCLUSION_IDENTITY_DRIFT", "RUNTIME_EXCLUSION_NOT_EMPTY"},
        )
        self.assertEqual(raised.exception.exit_code, 4)
        self.assertFalse((output / "filesystem.json").exists())

    def test_capture_rechecks_runtime_identity_after_teardown_before_promotion(self) -> None:
        runtime = self.make_runtime_directory()
        exclusion = self.exclusion(runtime)
        case = self.case(exclusion)
        mutator = self.repository / "mutate-runtime.py"
        mutator.write_text(
            "from pathlib import Path\n"
            "runtime = Path('product/.codex')\n"
            "runtime.chmod(0o755)\n"
            "(runtime / 'late.txt').write_text('late\\n', encoding='utf-8')\n"
            "runtime.chmod(0o555)\n",
            encoding="utf-8",
            newline="\n",
        )
        case["lifecycle"]["teardown"] = {
            "argv": [sys.executable, "mutate-runtime.py"],
            "cwd": ".",
            "environment": {},
            "expected_exit": 0,
            "timeout_seconds": 10,
        }
        self.install_case(case)

        completed = run_cli(
            "capture",
            self.pack,
            "--case",
            "CAP-001",
            "--timestamp",
            PINNED_TIMESTAMP,
        )

        self.assertEqual(completed.returncode, 4, completed.stderr)
        result = json.loads(completed.stdout)
        self.assertEqual(result["status"], "FAIL")
        self.assertEqual(result["acquisition_exit_code"], 4)
        self.assertEqual(result["summary"]["failure_phase"], "runtime-exclusion")
        self.assertEqual(
            [failure["diagnostic"] for failure in result["summary"]["failures"]],
            ["RUNTIME_EXCLUSION_NOT_EMPTY"],
        )
        self.assertEqual(result["summary"]["runtime_exclusions"], [exclusion])
        self.assertTrue((runtime / "late.txt").is_file())
        retained = read_json(self.pack / "evidence" / "captures" / "CAP-001" / "manifest.json")
        self.assertEqual(retained, result)

    def test_capture_allows_setup_to_create_and_remove_sibling_of_root_runtime(self) -> None:
        runtime = self.repository / ".codex"
        runtime.mkdir()
        runtime.chmod(0o555)
        exclusion = self.exclusion(runtime)
        case = self.case(exclusion)
        case["input"]["path"] = "."
        setup = self.repository / "setup-sibling.py"
        setup.write_text(
            "from pathlib import Path\n"
            "fixture = Path('setup-sibling.tmp')\n"
            "fixture.write_text('fixture\\n', encoding='utf-8')\n"
            "fixture.unlink()\n",
            encoding="utf-8",
            newline="\n",
        )
        case["lifecycle"]["setup"] = {
            "argv": [sys.executable, "setup-sibling.py"],
            "cwd": ".",
            "environment": {},
            "expected_exit": 0,
            "timeout_seconds": 10,
        }
        self.install_case(case)

        completed = run_cli(
            "capture",
            self.pack,
            "--case",
            "CAP-001",
            "--timestamp",
            PINNED_TIMESTAMP,
        )

        self.assertEqual(completed.returncode, 0, completed.stderr)
        result = json.loads(completed.stdout)
        self.assertEqual(result["status"], "PASS")
        self.assertEqual(result["summary"]["runtime_exclusions"], [exclusion])
        self.assertFalse((self.repository / "setup-sibling.tmp").exists())
        filesystem_artifact = next(
            self.pack / artifact["path"]
            for artifact in result["artifacts"]
            if str(artifact["path"]).endswith("filesystem.json")
        )
        snapshot = read_json(filesystem_artifact)
        self.assertNotIn(".codex", {entry["path"] for entry in snapshot["entries"]})

    def test_capture_rejects_inventory_instruction_and_generated_path_collisions(self) -> None:
        runtime = self.make_runtime_directory()
        exclusion = self.exclusion(runtime)
        case = self.case(exclusion)
        self.install_case(case)
        base_manifest = read_json(self.pack / "clone_pack.json")
        path = exclusion["path"]
        context_cases = {
            "repository-instruction": (
                "runtime_inventory.json",
                {"exclusions": [], "instructions": [path], "agents_files": [], "entries": []},
            ),
            "generated-path": (
                "runtime_enhancement.json",
                {"change_map": [], "scope": {"generated_paths": [path]}},
            ),
        }
        for name, (filename, payload) in context_cases.items():
            with self.subTest(case=name):
                write_json(self.pack / filename, payload)
                manifest = copy.deepcopy(base_manifest)
                plans = manifest.setdefault("plans", {})
                if name == "repository-instruction":
                    plans["repository_inventory"] = filename
                else:
                    plans["enhancement"] = filename

                with self.assertRaises(ClonePackError) as raised:
                    operations_module._capture_runtime_bindings(self.pack, manifest, case)

                self.assertEqual(raised.exception.diagnostic, "RUNTIME_EXCLUSION_COLLISION")
                self.assertEqual(raised.exception.exit_code, 4)

    def test_capture_redactions_cannot_modify_canonical_runtime_exclusions(self) -> None:
        runtime = self.make_runtime_directory()
        exclusion = self.exclusion(runtime)
        case = self.case(exclusion)
        case["redactions"] = [
            {
                "pattern": r"product/\.codex",
                "replacement": "MASKED-RUNTIME-PATH",
                "authority_ids": ["DEC-004"],
            }
        ]
        self.install_case(case)

        completed = run_cli(
            "capture",
            self.pack,
            "--case",
            "CAP-001",
            "--timestamp",
            PINNED_TIMESTAMP,
        )

        self.assertEqual(completed.returncode, 0, completed.stderr)
        result = json.loads(completed.stdout)
        filesystem_artifact = next(
            self.pack / artifact["path"]
            for artifact in result["artifacts"]
            if str(artifact["path"]).endswith("filesystem.json")
        )
        snapshot = read_json(filesystem_artifact)
        self.assertEqual(snapshot["runtime_exclusions"], [exclusion])
        self.assertEqual(result["summary"]["runtime_exclusions"], [exclusion])


if __name__ == "__main__":
    unittest.main()
