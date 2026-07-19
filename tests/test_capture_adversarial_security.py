from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
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


def command_environment(extra: dict[str, str] | None = None) -> dict[str, str]:
    environment = os.environ.copy()
    environment["LC_ALL"] = "C"
    environment["PYTHONHASHSEED"] = "0"
    environment.update(extra or {})
    return environment


def run_cli(
    *arguments: object,
    extra_environment: dict[str, str] | None = None,
    timeout: float = 20,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(CLONE_PACK), *(str(argument) for argument in arguments)],
        cwd=SKILL_ROOT,
        env=command_environment(extra_environment),
        text=True,
        encoding="utf-8",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=timeout,
        check=False,
    )


class CaptureAdversarialSecurityTests(unittest.TestCase):
    maxDiff = None

    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)
        self.temp_root = Path(self.temporary_directory.name)
        self.repository = self.temp_root / "repository"
        self.repository.mkdir()
        self.pack = self.initialize_pack("pack")

    def initialize_pack(self, output_name: str) -> Path:
        initialized = run_cli(
            "init",
            "--product-name",
            "Adversarial Capture Contract",
            "--product-type",
            "cli",
            "--source-description",
            "Pinned authorized local fixture",
            "--repo-root",
            self.repository,
            "--output-dir",
            output_name,
            "--timestamp",
            PINNED_TIMESTAMP,
        )
        self.assertEqual(initialized.returncode, 0, initialized.stderr)
        return self.repository / output_name

    @staticmethod
    def case_sha256(case: dict[str, Any]) -> str:
        contract = {key: value for key, value in case.items() if key != "result"}
        return hashlib.sha256(canonical_json(contract).encode("utf-8")).hexdigest()

    @staticmethod
    def lifecycle_command(*argv: str) -> dict[str, Any]:
        return {
            "argv": list(argv),
            "cwd": ".",
            "environment": {},
            "expected_exit": 0,
            "timeout_seconds": 10,
        }

    @staticmethod
    def manual_case(
        case_id: str,
        source_path: str,
        *,
        side: str = "clone",
        redactions: list[dict[str, Any]] | None = None,
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
            "input": {"source_path": source_path},
            "lifecycle": {"setup": setup, "teardown": teardown},
            "redactions": redactions or [],
            "result": None,
        }

    @staticmethod
    def web_case(
        case_id: str,
        driver_path: str,
        *,
        redactions: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        return {
            "id": case_id,
            "adapter": "web",
            "side": "clone",
            "environment_id": "ENV-001",
            "required": True,
            "authorization_decision_ids": [],
            "safe_test_environment": True,
            "timeout_seconds": 10,
            "input": {
                "driver_argv": [sys.executable, driver_path],
                "cwd": ".",
                "environment": {},
            },
            "lifecycle": {"setup": None, "teardown": None},
            "redactions": redactions or [],
            "result": None,
        }

    @staticmethod
    def http_case(
        case_id: str,
        url: str,
        method: str,
        *,
        decision_ids: list[str],
        safe_test_environment: bool,
    ) -> dict[str, Any]:
        return {
            "id": case_id,
            "adapter": "http",
            "side": "reference",
            "environment_id": "ENV-001",
            "required": True,
            "authorization_decision_ids": decision_ids,
            "safe_test_environment": safe_test_environment,
            "timeout_seconds": 10,
            "input": {
                "method": method,
                "url": url,
                "headers": {"Authorization": "env:CLONE_TEST_CREDENTIAL"},
            },
            "lifecycle": {"setup": None, "teardown": None},
            "redactions": [],
            "result": None,
        }

    def set_capture_cases(self, cases: list[dict[str, Any]], *, pack: Path | None = None) -> None:
        selected_pack = pack or self.pack
        plan = read_json(selected_pack / "capture_plan.json")
        plan["cases"] = cases
        write_json(selected_pack / "capture_plan.json", plan)

        authority_ids = sorted(
            {
                str(authority_id)
                for case in cases
                for authority_id in case.get("authorization_decision_ids", [])
            }
            | {
                str(authority_id)
                for case in cases
                for rule in case.get("redactions", [])
                if isinstance(rule, dict)
                for authority_id in rule.get("authority_ids", [])
            }
        )
        records: list[dict[str, Any]] = [self.index_record("ENV-001", "ENV")]
        records.extend(self.index_record(identifier, "DEC") for identifier in authority_ids)
        for case in cases:
            decisions = sorted(
                set(str(value) for value in case.get("authorization_decision_ids", []))
                | {
                    str(value)
                    for rule in case.get("redactions", [])
                    if isinstance(rule, dict)
                    for value in rule.get("authority_ids", [])
                }
            )
            records.append(
                self.index_record(
                    str(case["id"]),
                    "CAP",
                    links={"environments": [str(case["environment_id"])], "decisions": decisions},
                    attributes={"case_sha256": self.case_sha256(case)},
                )
            )
        index = read_json(selected_pack / "clone_index.json")
        index["records"] = records
        write_json(selected_pack / "clone_index.json", index)

    @staticmethod
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

    def capture(self, case_id: str, *, pack: Path | None = None, resume: bool = False, extra_environment: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
        arguments: list[object] = ["capture", pack or self.pack, "--case", case_id, "--timestamp", PINNED_TIMESTAMP]
        if resume:
            arguments.append("--resume")
        return run_cli(*arguments, extra_environment=extra_environment)

    @staticmethod
    def result_artifact_paths(pack: Path, result: dict[str, Any]) -> list[Path]:
        return [pack / str(artifact["path"]) for artifact in result.get("artifacts", [])]

    def fake_http_environment(self, name: str) -> tuple[dict[str, str], Path]:
        """Install a child-process HTTP transport shim without opening a socket."""

        shim = self.temp_root / f"http-shim-{name}"
        shim.mkdir()
        log_path = self.temp_root / f"http-{name}.log"
        (shim / "sitecustomize.py").write_text(
            "import os, urllib.request\n"
            "class _Headers:\n"
            "    def items(self): return [('Content-Type', 'application/json')]\n"
            "class _Response:\n"
            "    status = 200\n"
            "    headers = _Headers()\n"
            "    def read(self): return b'{\"observed\":true}\\n'\n"
            "class _Opener:\n"
            "    def open(self, request, timeout=None):\n"
            "        with open(os.environ['CLONE_HTTP_LOG'], 'a', encoding='utf-8') as handle:\n"
            "            handle.write(request.get_method() + '\\n')\n"
            "        return _Response()\n"
            "urllib.request.build_opener = lambda *args, **kwargs: _Opener()\n",
            encoding="utf-8",
        )
        existing_python_path = os.environ.get("PYTHONPATH")
        python_path = str(shim) if not existing_python_path else str(shim) + os.pathsep + existing_python_path
        return {
            "PYTHONPATH": python_path,
            "CLONE_HTTP_LOG": str(log_path),
            "CLONE_TEST_CREDENTIAL": "fixture-token",
        }, log_path

    def test_resume_binds_current_case_result_pointer_before_staging_cleanup(self) -> None:
        (self.pack / "source.bin").write_bytes(b"immutable observation")
        case = self.manual_case("CAP-001", "source.bin")
        self.set_capture_cases([case])
        first = self.capture("CAP-001")
        self.assertEqual(first.returncode, 0, first.stderr)
        final_manifest = self.pack / "evidence" / "captures" / "CAP-001" / "manifest.json"
        final_bytes = final_manifest.read_bytes()

        plan = read_json(self.pack / "capture_plan.json")
        pointer = plan["cases"][0]["result"]
        self.assertIsInstance(pointer, dict)
        pointer["sha256"] = "0" * 64
        write_json(self.pack / "capture_plan.json", plan)

        stage = self.pack / "evidence" / "captures" / ".CAP-001.staging"
        stage.mkdir()
        shutil.copy2(
            self.pack / "evidence" / "captures" / "CAP-001" / ".clone-capture-staging.json",
            stage / ".clone-capture-staging.json",
        )
        sentinel = stage / "must-not-be-deleted.txt"
        sentinel.write_text("pointer preflight precedes cleanup", encoding="utf-8")

        rejected = self.capture("CAP-001", resume=True)

        self.assertNotEqual(rejected.returncode, 0)
        self.assertEqual(final_manifest.read_bytes(), final_bytes)
        self.assertEqual(sentinel.read_text(encoding="utf-8"), "pointer preflight precedes cleanup")

    def test_resume_rejects_noncanonical_pointer_path_and_status(self) -> None:
        for position, mutation in enumerate(
            (
                {"path": "clone_index.json"},
                {"status": "FAIL"},
                {"unexpected": "field"},
            ),
            1,
        ):
            with self.subTest(mutation=mutation):
                pack = self.initialize_pack(f"pointer-{position}")
                (pack / "source.bin").write_bytes(b"observation")
                case = self.manual_case("CAP-001", "source.bin")
                self.set_capture_cases([case], pack=pack)
                first = self.capture("CAP-001", pack=pack)
                self.assertEqual(first.returncode, 0, first.stderr)
                final_manifest = pack / "evidence" / "captures" / "CAP-001" / "manifest.json"
                final_bytes = final_manifest.read_bytes()
                plan = read_json(pack / "capture_plan.json")
                plan["cases"][0]["result"].update(mutation)
                write_json(pack / "capture_plan.json", plan)

                rejected = self.capture("CAP-001", pack=pack, resume=True)

                self.assertNotEqual(rejected.returncode, 0)
                self.assertEqual(final_manifest.read_bytes(), final_bytes)
                self.assertFalse((pack / "evidence" / "captures" / ".CAP-001.staging").exists())

    def test_capture_rejects_manifest_plan_remapping_before_external_read_or_write(self) -> None:
        (self.pack / "source.bin").write_bytes(b"observation")
        case = self.manual_case("CAP-001", "source.bin")
        self.set_capture_cases([case])
        alternate = self.pack / "alternate"
        alternate.mkdir()
        shutil.copy2(self.pack / "capture_plan.json", alternate / "capture.json")
        manifest = read_json(self.pack / "clone_pack.json")
        manifest["plans"]["capture"] = "alternate/capture.json"
        write_json(self.pack / "clone_pack.json", manifest)

        rejected = self.capture("CAP-001")

        self.assertNotEqual(rejected.returncode, 0)
        self.assertFalse((self.pack / "evidence" / "captures" / "CAP-001").exists())
        self.assertFalse((self.pack / "evidence" / "captures" / ".CAP-001.staging").exists())

    def test_symlinked_captures_root_is_rejected_without_touching_target(self) -> None:
        (self.pack / "source.bin").write_bytes(b"observation")
        self.set_capture_cases([self.manual_case("CAP-001", "source.bin")])
        captures = self.pack / "evidence" / "captures"
        captures.rmdir()
        external = self.temp_root / "external-captures"
        external.mkdir()
        sentinel = external / "sentinel.txt"
        sentinel.write_text("outside ownership", encoding="utf-8")
        try:
            captures.symlink_to(external, target_is_directory=True)
        except OSError as exc:
            self.skipTest(f"symlinks unavailable: {exc}")

        rejected = self.capture("CAP-001")

        self.assertNotEqual(rejected.returncode, 0)
        self.assertEqual(sentinel.read_text(encoding="utf-8"), "outside ownership")
        self.assertEqual(sorted(path.name for path in external.iterdir()), ["sentinel.txt"])

    def test_resume_rejects_symlinked_stage_without_deleting_target(self) -> None:
        (self.pack / "source.bin").write_bytes(b"observation")
        case = self.manual_case("CAP-001", "source.bin")
        self.set_capture_cases([case])
        stage = self.pack / "evidence" / "captures" / ".CAP-001.staging"
        external = self.temp_root / "external-stage"
        external.mkdir()
        marker = {
            "schema_version": "clone-capture-staging/v1",
            "runner": "clone-software",
            "pack_id": read_json(self.pack / "clone_pack.json")["pack_id"],
            "pack_revision": 1,
            "capture_id": "CAP-001",
            "case_sha256": self.case_sha256(case),
        }
        write_json(external / ".clone-capture-staging.json", marker)
        sentinel = external / "sentinel.txt"
        sentinel.write_text("must survive", encoding="utf-8")
        try:
            stage.symlink_to(external, target_is_directory=True)
        except OSError as exc:
            self.skipTest(f"symlinks unavailable: {exc}")

        rejected = self.capture("CAP-001", resume=True)

        self.assertNotEqual(rejected.returncode, 0)
        self.assertEqual(sentinel.read_text(encoding="utf-8"), "must survive")
        self.assertTrue(stage.is_symlink())

    def test_declared_redactions_cover_lifecycle_outputs_invocation_and_manual_observation(self) -> None:
        literals = ["SENSITIVE-LIFECYCLE", "SENSITIVE-ERR", "SENSITIVE-OBSERVATION"]
        (self.pack / "source.txt").write_text(literals[2], encoding="utf-8")
        setup_code = (
            "import sys; "
            f"print({literals[0]!r}); "
            f"print({literals[1]!r}, file=sys.stderr)"
        )
        rules = [
            {
                "pattern": "SENSITIVE-[A-Z]+",
                "replacement": "[REDACTED]",
                "authority_ids": ["DEC-001"],
            }
        ]
        case = self.manual_case(
            "CAP-001",
            "source.txt",
            redactions=rules,
            setup=self.lifecycle_command(sys.executable, "-c", setup_code),
        )
        self.set_capture_cases([case])

        completed = self.capture("CAP-001")

        self.assertEqual(completed.returncode, 0, completed.stderr)
        result = json.loads(completed.stdout)
        final = self.pack / "evidence" / "captures" / "CAP-001"
        retained_text = "\n".join(
            path.read_bytes().decode("utf-8", errors="ignore")
            for path in sorted(final.rglob("*"))
            if path.is_file()
        )
        for literal in literals:
            self.assertNotIn(literal, retained_text)
        self.assertIn("[REDACTED]", retained_text)
        positive_events = [event for event in result["redactions"] if event.get("count", 0) > 0]
        self.assertTrue(positive_events)
        self.assertIn("lifecycle", canonical_json(positive_events).lower())

    def test_declared_redaction_rejects_binary_lifecycle_artifact(self) -> None:
        (self.pack / "source.txt").write_text("ordinary observation", encoding="utf-8")
        binary_code = "import sys; sys.stdout.buffer.write(bytes([255, 254]))"
        rules = [
            {"pattern": "secret", "replacement": "[REDACTED]", "authority_ids": ["DEC-001"]}
        ]
        case = self.manual_case(
            "CAP-001",
            "source.txt",
            redactions=rules,
            setup=self.lifecycle_command(sys.executable, "-c", binary_code),
        )
        self.set_capture_cases([case])

        rejected = self.capture("CAP-001")

        self.assertNotEqual(rejected.returncode, 0)
        retained = self.pack / "evidence" / "captures" / "CAP-001"
        diagnostic_text = rejected.stderr
        if rejected.stdout:
            diagnostic_text += rejected.stdout
        if retained.exists():
            diagnostic_text += "\n".join(
                path.read_bytes().decode("utf-8", errors="ignore")
                for path in retained.rglob("*")
                if path.is_file()
            )
        self.assertIn("REDACTION_UNSUPPORTED", diagnostic_text)

    def test_web_redaction_covers_emitted_text_and_structured_summary(self) -> None:
        driver = self.repository / "redacting-driver.py"
        driver.write_text(
            "from pathlib import Path\n"
            "import json, os\n"
            "root = Path(os.environ['CLONE_CAPTURE_OUTPUT'])\n"
            "root.mkdir(parents=True, exist_ok=True)\n"
            "(root / 'observation.txt').write_text('WEB-SECRET-CONTENT', encoding='utf-8')\n"
            "(root / 'web-driver-result.json').write_text(json.dumps({\n"
            "  'schema_version': 'clone-web-capture-result/v1',\n"
            "  'artifacts': ['observation.txt'],\n"
            "  'summary': {'token': 'WEB-SECRET-SUMMARY'}\n"
            "}), encoding='utf-8')\n",
            encoding="utf-8",
        )
        rules = [
            {"pattern": "WEB-SECRET-[A-Z]+", "replacement": "[REDACTED]", "authority_ids": ["DEC-001"]}
        ]
        self.set_capture_cases([self.web_case("CAP-001", driver.name, redactions=rules)])

        completed = self.capture("CAP-001")

        self.assertEqual(completed.returncode, 0, completed.stderr)
        result = json.loads(completed.stdout)
        final = self.pack / "evidence" / "captures" / "CAP-001"
        retained_text = "\n".join(
            path.read_bytes().decode("utf-8", errors="ignore")
            for path in final.rglob("*")
            if path.is_file()
        )
        self.assertNotIn("WEB-SECRET-CONTENT", retained_text)
        self.assertNotIn("WEB-SECRET-SUMMARY", retained_text)
        self.assertIn("[REDACTED]", retained_text)
        self.assertTrue(any(event.get("count", 0) > 0 for event in result["redactions"]))

    def test_web_capture_with_no_declared_observation_cannot_pass(self) -> None:
        driver = self.repository / "empty-driver.py"
        driver.write_text(
            "from pathlib import Path\n"
            "import json, os\n"
            "root = Path(os.environ['CLONE_CAPTURE_OUTPUT'])\n"
            "root.mkdir(parents=True, exist_ok=True)\n"
            "(root / 'web-driver-result.json').write_text(json.dumps({\n"
            "  'schema_version': 'clone-web-capture-result/v1',\n"
            "  'artifacts': [],\n"
            "  'summary': {}\n"
            "}), encoding='utf-8')\n",
            encoding="utf-8",
        )
        self.set_capture_cases([self.web_case("CAP-001", driver.name)])

        rejected = self.capture("CAP-001")

        self.assertNotEqual(rejected.returncode, 0)
        if rejected.stdout:
            self.assertNotEqual(json.loads(rejected.stdout).get("status"), "PASS")

    def test_manual_reserved_names_never_replace_runner_marker_or_manifest(self) -> None:
        for position, source_name in enumerate((".clone-capture-staging.json", "manifest.json"), 1):
            with self.subTest(source_name=source_name):
                pack = self.initialize_pack(f"reserved-{position}")
                source_bytes = f"declared observation for {source_name}".encode()
                (pack / source_name).write_bytes(source_bytes)
                self.set_capture_cases([self.manual_case("CAP-001", source_name)], pack=pack)

                completed = self.capture("CAP-001", pack=pack)

                final = pack / "evidence" / "captures" / "CAP-001"
                if completed.returncode != 0:
                    self.assertFalse(final.exists())
                    continue
                result = json.loads(completed.stdout)
                try:
                    marker = read_json(final / ".clone-capture-staging.json")
                except (OSError, UnicodeError, json.JSONDecodeError) as exc:
                    self.fail(f"runner marker was overwritten by the adapter: {exc}")
                self.assertEqual(marker["runner"], "clone-software")
                retained = [path.read_bytes() for path in self.result_artifact_paths(pack, result)]
                self.assertIn(source_bytes, retained)
                for artifact, path in zip(result["artifacts"], self.result_artifact_paths(pack, result), strict=True):
                    self.assertTrue(path.is_file())
                    self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), artifact["sha256"])
                    self.assertEqual(len(path.read_bytes()), artifact["size"])

    def test_manual_symlink_source_is_rejected_before_output(self) -> None:
        target = self.pack / "target.txt"
        target.write_text("not a direct observation", encoding="utf-8")
        link = self.pack / "source-link.txt"
        try:
            link.symlink_to(target.name)
        except OSError as exc:
            self.skipTest(f"symlinks unavailable: {exc}")
        self.set_capture_cases([self.manual_case("CAP-001", link.name)])

        rejected = self.capture("CAP-001")

        self.assertNotEqual(rejected.returncode, 0)
        self.assertFalse((self.pack / "evidence" / "captures" / "CAP-001").exists())

    def test_resume_rejects_declared_artifact_replaced_by_in_directory_symlink(self) -> None:
        (self.pack / "source.txt").write_text("immutable bytes", encoding="utf-8")
        self.set_capture_cases([self.manual_case("CAP-001", "source.txt")])
        first = self.capture("CAP-001")
        self.assertEqual(first.returncode, 0, first.stderr)
        result = json.loads(first.stdout)
        artifact_path = self.result_artifact_paths(self.pack, result)[0]
        target = artifact_path.with_name("target-" + artifact_path.name)
        artifact_path.rename(target)
        try:
            artifact_path.symlink_to(target.name)
        except OSError as exc:
            target.rename(artifact_path)
            self.skipTest(f"symlinks unavailable: {exc}")

        rejected = self.capture("CAP-001", resume=True)

        self.assertNotEqual(rejected.returncode, 0)
        self.assertTrue(artifact_path.is_symlink())
        self.assertEqual(target.read_text(encoding="utf-8"), "immutable bytes")

    def test_credentialed_reference_read_requires_resolved_decision_trace(self) -> None:
        environment, log_path = self.fake_http_environment("missing-decision")
        case = self.http_case(
            "CAP-001",
            "https://authorized.example.invalid/fixture",
            "GET",
            decision_ids=[],
            safe_test_environment=False,
        )
        self.set_capture_cases([case])

        rejected = self.capture(
            "CAP-001",
            extra_environment=environment,
        )

        self.assertNotEqual(rejected.returncode, 0)
        self.assertFalse(log_path.exists())
        self.assertFalse((self.pack / "evidence" / "captures" / "CAP-001").exists())

    def test_credentialed_reference_read_with_decision_does_not_require_mutation_sandbox(self) -> None:
        environment, log_path = self.fake_http_environment("authorized-read")
        case = self.http_case(
            "CAP-001",
            "https://authorized.example.invalid/fixture",
            "GET",
            decision_ids=["DEC-001"],
            safe_test_environment=False,
        )
        self.set_capture_cases([case])

        completed = self.capture(
            "CAP-001",
            extra_environment=environment,
        )

        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(log_path.read_text(encoding="utf-8").splitlines(), ["GET"])

    def test_credentialed_reference_mutation_additionally_requires_safe_environment(self) -> None:
        environment, log_path = self.fake_http_environment("unsafe-mutation")
        case = self.http_case(
            "CAP-001",
            "https://authorized.example.invalid/fixture",
            "POST",
            decision_ids=["DEC-001"],
            safe_test_environment=False,
        )
        self.set_capture_cases([case])

        rejected = self.capture(
            "CAP-001",
            extra_environment=environment,
        )

        self.assertNotEqual(rejected.returncode, 0)
        self.assertFalse(log_path.exists())
        self.assertFalse((self.pack / "evidence" / "captures" / "CAP-001").exists())


if __name__ == "__main__":
    unittest.main()
