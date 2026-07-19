from __future__ import annotations

import hashlib
import json
import os
import signal
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from typing import Any


SKILL_ROOT = Path(__file__).resolve().parents[1]
CLONE_PACK = SKILL_ROOT / "scripts" / "clone_pack.py"
PINNED_TIMESTAMP = "2026-07-18T12:34:56+00:00"


def canonical_json(value: Any) -> str:
    return json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise AssertionError(f"expected object in {path}")
    return value


def write_json(path: Path, value: Any) -> None:
    path.write_text(canonical_json(value), encoding="utf-8", newline="\n")


def command_environment() -> dict[str, str]:
    environment = os.environ.copy()
    environment["LC_ALL"] = "C"
    environment["PYTHONHASHSEED"] = "0"
    return environment


def run_cli(*arguments: object, timeout: float = 20) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(CLONE_PACK), *(str(argument) for argument in arguments)],
        cwd=SKILL_ROOT,
        env=command_environment(),
        text=True,
        encoding="utf-8",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=timeout,
        check=False,
    )


class CaptureLifecycleBatchTests(unittest.TestCase):
    maxDiff = None

    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)
        self.temp_root = Path(self.temporary_directory.name)
        self.repository = self.temp_root / "repository"
        self.repository.mkdir()
        initialized = run_cli(
            "init",
            "--product-name",
            "Capture Lifecycle Contract",
            "--product-type",
            "cli",
            "--source-description",
            "Pinned authorized local fixture",
            "--repo-root",
            self.repository,
            "--output-dir",
            "pack",
            "--timestamp",
            PINNED_TIMESTAMP,
        )
        self.assertEqual(initialized.returncode, 0, initialized.stderr)
        self.pack = self.repository / "pack"

    @staticmethod
    def case_sha256(case: dict[str, Any]) -> str:
        contract = {key: value for key, value in case.items() if key != "result"}
        return hashlib.sha256(canonical_json(contract).encode("utf-8")).hexdigest()

    @staticmethod
    def command(*argv: str) -> dict[str, Any]:
        return {
            "argv": list(argv),
            "cwd": ".",
            "environment": {},
            "expected_exit": 0,
            "timeout_seconds": 10,
        }

    def manual_case(
        self,
        case_id: str,
        source_path: str,
        *,
        side: str = "clone",
        setup: dict[str, Any] | None = None,
        teardown: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return {
            "id": case_id,
            "adapter": "manual",
            "side": side,
            "environment_id": "ENV-001",
            "required": True,
            "authorization_decision_ids": [],
            "safe_test_environment": True,
            "timeout_seconds": 10,
            "lifecycle": {
                "setup": setup,
                "teardown": teardown,
            },
            "input": {"source_path": source_path},
            "redactions": [],
            "result": None,
        }

    def process_case(
        self,
        case_id: str,
        argv: list[str],
        *,
        setup: dict[str, Any] | None = None,
        teardown: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        case = self.manual_case(case_id, "unused", setup=setup, teardown=teardown)
        case["adapter"] = "process"
        case["input"] = {"argv": argv, "cwd": ".", "environment": {}}
        return case

    def set_capture_cases(self, cases: list[dict[str, Any]]) -> None:
        plan = read_json(self.pack / "capture_plan.json")
        plan["cases"] = cases
        write_json(self.pack / "capture_plan.json", plan)

        index = read_json(self.pack / "clone_index.json")
        index["records"] = [
            {
                "id": "ENV-001",
                "kind": "ENV",
                "locator": {"path": "clone_brief.md", "anchor": None, "sha256": None},
                "links": {},
                "applicability": "MVP",
                "state": "READY",
                "attributes": {},
            }
        ]
        for case in cases:
            index["records"].append(
                {
                    "id": case["id"],
                    "kind": "CAP",
                    "locator": {"path": "clone_brief.md", "anchor": None, "sha256": None},
                    "links": {
                        "environments": [case["environment_id"]],
                        "decisions": sorted(case["authorization_decision_ids"]),
                    },
                    "applicability": "MVP",
                    "state": "READY",
                    "attributes": {"case_sha256": self.case_sha256(case)},
                }
            )
        write_json(self.pack / "clone_index.json", index)

    def test_timestamp_pins_capture_started_and_completed_at(self) -> None:
        (self.pack / "source.bin").write_bytes(b"deterministic fixture")
        self.set_capture_cases([self.manual_case("CAP-001", "source.bin")])

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
        self.assertEqual(result["started_at"], PINNED_TIMESTAMP)
        self.assertEqual(result["completed_at"], PINNED_TIMESTAMP)
        retained = read_json(self.pack / "evidence" / "captures" / "CAP-001" / "manifest.json")
        self.assertEqual(retained["started_at"], PINNED_TIMESTAMP)
        self.assertEqual(retained["completed_at"], PINNED_TIMESTAMP)

    def test_setup_failure_blocks_adapter_but_still_runs_teardown(self) -> None:
        main_marker = self.repository / "main-ran"
        teardown_marker = self.repository / "teardown-ran"
        case = self.process_case(
            "CAP-001",
            [
                sys.executable,
                "-c",
                "from pathlib import Path; Path('main-ran').write_text('yes', encoding='utf-8')",
            ],
            setup=self.command(sys.executable, "-c", "import sys; sys.exit(9)"),
            teardown=self.command(
                sys.executable,
                "-c",
                "from pathlib import Path; Path('teardown-ran').write_text('yes', encoding='utf-8')",
            ),
        )
        self.set_capture_cases([case])

        completed = run_cli(
            "capture",
            self.pack,
            "--case",
            "CAP-001",
            "--timestamp",
            PINNED_TIMESTAMP,
        )

        self.assertNotEqual(completed.returncode, 0)
        result = json.loads(completed.stdout)
        self.assertEqual(result["status"], "FAIL")
        self.assertEqual(result["summary"]["failure_phase"], "setup")
        self.assertFalse(main_marker.exists())
        self.assertTrue(teardown_marker.is_file())
        self.assertEqual(result["started_at"], PINNED_TIMESTAMP)
        self.assertEqual(result["completed_at"], PINNED_TIMESTAMP)

    def test_teardown_failure_overrides_successful_acquisition(self) -> None:
        source = self.pack / "source.bin"
        source.write_bytes(b"captured before teardown")
        setup_marker = self.repository / "setup-ran"
        case = self.manual_case(
            "CAP-001",
            "source.bin",
            setup=self.command(
                sys.executable,
                "-c",
                "from pathlib import Path; Path('setup-ran').write_text('yes', encoding='utf-8')",
            ),
            teardown=self.command(sys.executable, "-c", "import sys; sys.exit(8)"),
        )
        self.set_capture_cases([case])

        completed = run_cli(
            "capture",
            self.pack,
            "--case",
            "CAP-001",
            "--timestamp",
            PINNED_TIMESTAMP,
        )

        self.assertNotEqual(completed.returncode, 0)
        result = json.loads(completed.stdout)
        self.assertEqual(result["status"], "FAIL")
        self.assertEqual(result["summary"]["failure_phase"], "teardown")
        self.assertTrue(setup_marker.is_file())
        self.assertTrue(result["artifacts"], "successful acquisition evidence must remain auditable")
        retained = read_json(self.pack / "evidence" / "captures" / "CAP-001" / "manifest.json")
        self.assertEqual(retained["status"], "FAIL")

    def test_batch_preflight_failure_has_no_capture_side_effects(self) -> None:
        (self.pack / "first.bin").write_bytes(b"first")
        (self.pack / "second.bin").write_bytes(b"second")
        cases = [
            self.manual_case("CAP-001", "first.bin"),
            self.manual_case("CAP-002", "second.bin"),
        ]
        self.set_capture_cases(cases)
        index = read_json(self.pack / "clone_index.json")
        index["records"] = [record for record in index["records"] if record["id"] != "CAP-002"]
        write_json(self.pack / "clone_index.json", index)
        before = (self.pack / "capture_plan.json").read_bytes()

        completed = run_cli(
            "capture",
            self.pack,
            "--all",
            "--timestamp",
            PINNED_TIMESTAMP,
        )

        self.assertNotEqual(completed.returncode, 0)
        captures_root = self.pack / "evidence" / "captures"
        self.assertEqual(list(captures_root.iterdir()) if captures_root.exists() else [], [])
        self.assertEqual((self.pack / "capture_plan.json").read_bytes(), before)

    def test_batch_preflights_later_manual_source_before_first_execution(self) -> None:
        (self.pack / "first.bin").write_bytes(b"first")
        cases = [
            self.manual_case("CAP-001", "first.bin"),
            self.manual_case("CAP-002", "missing.bin"),
        ]
        self.set_capture_cases(cases)
        before = (self.pack / "capture_plan.json").read_bytes()

        completed = run_cli(
            "capture",
            self.pack,
            "--all",
            "--timestamp",
            PINNED_TIMESTAMP,
        )

        self.assertNotEqual(completed.returncode, 0)
        self.assertIn("FILE_MISSING", completed.stderr)
        captures_root = self.pack / "evidence" / "captures"
        self.assertEqual(list(captures_root.iterdir()) if captures_root.exists() else [], [])
        self.assertEqual((self.pack / "capture_plan.json").read_bytes(), before)

    def test_empty_all_is_not_reported_as_pass(self) -> None:
        self.set_capture_cases([])

        completed = run_cli(
            "capture",
            self.pack,
            "--all",
            "--timestamp",
            PINNED_TIMESTAMP,
        )

        self.assertNotEqual(completed.returncode, 0)
        self.assertIn("PLAN_INVALID", completed.stderr)
        self.assertEqual(completed.stdout, "")

    def test_all_emits_ordered_batch_json_and_nonzero_aggregate(self) -> None:
        (self.pack / "first.bin").write_bytes(b"first")
        (self.pack / "second.bin").write_bytes(b"second")
        cases = [
            self.manual_case("CAP-002", "second.bin"),
            self.manual_case(
                "CAP-001",
                "first.bin",
                teardown=self.command(sys.executable, "-c", "import sys; sys.exit(8)"),
            ),
        ]
        self.set_capture_cases(cases)

        completed = run_cli(
            "capture",
            self.pack,
            "--all",
            "--timestamp",
            PINNED_TIMESTAMP,
        )

        self.assertNotEqual(completed.returncode, 0)
        batch = json.loads(completed.stdout)
        self.assertEqual(batch["schema_version"], "clone-capture-batch-result/v2")
        self.assertEqual(batch["started_at"], PINNED_TIMESTAMP)
        self.assertEqual(batch["completed_at"], PINNED_TIMESTAMP)
        self.assertEqual([item["capture_id"] for item in batch["results"]], ["CAP-001", "CAP-002"])
        self.assertEqual(
            {item["capture_id"]: item["status"] for item in batch["results"]},
            {"CAP-001": "FAIL", "CAP-002": "PASS"},
        )

    def test_resume_skips_current_complete_and_discards_only_owned_interrupted_staging(self) -> None:
        (self.pack / "first.bin").write_bytes(b"first")
        resume_marker = self.repository / "resume-marker"
        sleeper = (
            "from pathlib import Path; import time; "
            "p=Path('resume-marker'); first=not p.exists(); p.write_text('started', encoding='utf-8'); "
            "time.sleep(30) if first else None; print('complete')"
        )
        cases = [
            self.manual_case("CAP-001", "first.bin"),
            self.process_case("CAP-002", [sys.executable, "-c", sleeper]),
        ]
        self.set_capture_cases(cases)
        first = run_cli(
            "capture",
            self.pack,
            "--case",
            "CAP-001",
            "--timestamp",
            PINNED_TIMESTAMP,
        )
        self.assertEqual(first.returncode, 0, first.stderr)
        complete_manifest = self.pack / "evidence" / "captures" / "CAP-001" / "manifest.json"
        complete_bytes = complete_manifest.read_bytes()

        captures_root = self.pack / "evidence" / "captures"
        unrelated = captures_root / "user-owned-notes"
        unrelated.mkdir()
        (unrelated / "keep.txt").write_text("do not delete", encoding="utf-8")

        interrupted = subprocess.Popen(
            [
                sys.executable,
                str(CLONE_PACK),
                "capture",
                str(self.pack),
                "--all",
                "--resume",
                "--timestamp",
                PINNED_TIMESTAMP,
            ],
            cwd=SKILL_ROOT,
            env=command_environment(),
            text=True,
            encoding="utf-8",
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        try:
            for _ in range(200):
                if resume_marker.exists():
                    break
                if interrupted.poll() is not None:
                    break
                time.sleep(0.025)
            self.assertTrue(resume_marker.exists(), "capture never entered the interruptible adapter")
            interrupted.send_signal(signal.SIGINT)
            stdout, stderr = interrupted.communicate(timeout=10)
        finally:
            if interrupted.poll() is None:
                interrupted.kill()
                interrupted.communicate(timeout=5)
        self.assertEqual(interrupted.returncode, 130, stderr or stdout)
        self.assertEqual(complete_manifest.read_bytes(), complete_bytes)
        self.assertEqual((unrelated / "keep.txt").read_text(encoding="utf-8"), "do not delete")

        resumed = run_cli(
            "capture",
            self.pack,
            "--all",
            "--resume",
            "--timestamp",
            PINNED_TIMESTAMP,
        )
        self.assertEqual(resumed.returncode, 0, resumed.stderr)
        batch = json.loads(resumed.stdout)
        self.assertEqual([item["capture_id"] for item in batch["results"]], ["CAP-001", "CAP-002"])
        self.assertTrue(batch["results"][0]["skipped"])
        self.assertFalse(batch["results"][1]["skipped"])
        self.assertEqual(complete_manifest.read_bytes(), complete_bytes)
        self.assertEqual((unrelated / "keep.txt").read_text(encoding="utf-8"), "do not delete")
        second_manifest = read_json(captures_root / "CAP-002" / "manifest.json")
        self.assertEqual(second_manifest["status"], "PASS")


if __name__ == "__main__":
    unittest.main()
