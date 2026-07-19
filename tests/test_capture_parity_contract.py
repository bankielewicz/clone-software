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
from unittest.mock import patch

from scripts.clonepack.operations import execute_capture, execute_parity


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


def run_cli(*arguments: object) -> subprocess.CompletedProcess[str]:
    environment = os.environ.copy()
    environment["LC_ALL"] = "C"
    environment["PYTHONHASHSEED"] = "0"
    return subprocess.run(
        [sys.executable, str(CLONE_PACK), *(str(argument) for argument in arguments)],
        cwd=SKILL_ROOT,
        env=environment,
        text=True,
        encoding="utf-8",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )


class CaptureParityContractTests(unittest.TestCase):
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
            "Parity Contract",
            "--product-type",
            "cli",
            "--source-description",
            "Pinned local test reference",
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

    def upsert_index_record(
        self,
        identifier: str,
        kind: str,
        *,
        links: dict[str, list[str]] | None = None,
        attributes: dict[str, Any] | None = None,
    ) -> None:
        index = read_json(self.pack / "clone_index.json")
        existing = next((record for record in index["records"] if record["id"] == identifier), None)
        if existing is None:
            existing = {
                "id": identifier,
                "kind": kind,
                "locator": {"path": "clone_brief.md", "anchor": None, "sha256": None},
                "links": {},
                "applicability": "MVP",
                "state": "READY",
                "attributes": {},
            }
            index["records"].append(existing)
        existing["kind"] = kind
        existing["links"].update(links or {})
        existing["attributes"].update(attributes or {})
        write_json(self.pack / "clone_index.json", index)

    def set_capture_cases(self, cases: list[dict[str, Any]]) -> None:
        plan = read_json(self.pack / "capture_plan.json")
        plan["cases"] = cases
        write_json(self.pack / "capture_plan.json", plan)
        self.upsert_index_record("ENV-001", "ENV")
        for case in cases:
            authority_ids = {
                str(item) for item in case.get("authorization_decision_ids", [])
            }
            authority_ids.update(
                str(item)
                for rule in case.get("redactions", [])
                if isinstance(rule, dict)
                for item in rule.get("authority_ids", [])
            )
            for authority_id in sorted(authority_ids):
                self.upsert_index_record(str(authority_id), "DEC")
            self.upsert_index_record(
                str(case["id"]),
                "CAP",
                links={
                    "environments": [str(case["environment_id"])],
                    "decisions": sorted(authority_ids),
                },
                attributes={"case_sha256": self.case_sha256(case)},
            )

    def set_parity_cases(self, cases: list[dict[str, Any]]) -> None:
        plan = read_json(self.pack / "parity_plan.json")
        plan["cases"] = cases
        write_json(self.pack / "parity_plan.json", plan)
        for case in cases:
            authority_ids = sorted(
                {
                    str(item)
                    for rule in case.get("normalizations", [])
                    if isinstance(rule, dict)
                    for item in rule.get("authority_ids", [])
                }
            )
            for authority_id in authority_ids:
                self.upsert_index_record(authority_id, "DEC")
            self.upsert_index_record(
                str(case["id"]),
                "PAR",
                links={
                    "captures": sorted([str(case["reference_capture_id"]), str(case["clone_capture_id"])]),
                    "decisions": authority_ids,
                },
                attributes={"case_sha256": self.case_sha256(case)},
            )

    def capture_manual_pair(self, expected: bytes, actual: bytes, *, filename: str = "value.bin") -> None:
        for directory, content in (("reference", expected), ("clone", actual)):
            source = self.pack / directory / filename
            source.parent.mkdir()
            source.write_bytes(content)
        self.set_capture_cases(
            [
                {
                    "id": "CAP-001",
                    "adapter": "manual",
                    "side": "reference",
                    "environment_id": "ENV-001",
                    "required": True,
                    "authorization_decision_ids": [],
                    "safe_test_environment": True,
                    "timeout_seconds": 10,
                    "input": {"source_path": f"reference/{filename}"},
                    "lifecycle": {"setup": None, "teardown": None},
                    "redactions": [],
                    "result": None,
                },
                {
                    "id": "CAP-002",
                    "adapter": "manual",
                    "side": "clone",
                    "environment_id": "ENV-001",
                    "required": True,
                    "authorization_decision_ids": [],
                    "safe_test_environment": True,
                    "timeout_seconds": 10,
                    "input": {"source_path": f"clone/{filename}"},
                    "lifecycle": {"setup": None, "teardown": None},
                    "redactions": [],
                    "result": None,
                },
            ]
        )
        for case_id in ("CAP-001", "CAP-002"):
            captured = run_cli("capture", self.pack, "--case", case_id)
            self.assertEqual(captured.returncode, 0, captured.stderr)

    def remove_index_record(self, identifier: str) -> None:
        index = read_json(self.pack / "clone_index.json")
        index["records"] = [record for record in index["records"] if record["id"] != identifier]
        write_json(self.pack / "clone_index.json", index)

    def test_capture_rejects_missing_counterpart_environment_and_authority_before_output(self) -> None:
        source = self.pack / "source.bin"
        source.write_bytes(b"authorized fixture")
        case = {
            "id": "CAP-001",
            "adapter": "manual",
            "side": "reference",
            "environment_id": "ENV-001",
            "required": True,
            "authorization_decision_ids": ["DEC-001"],
            "safe_test_environment": True,
            "timeout_seconds": 10,
            "input": {"source_path": "source.bin"},
            "lifecycle": {"setup": None, "teardown": None},
            "redactions": [],
            "result": None,
        }
        self.set_capture_cases([case])
        for missing_id, expected in (
            ("ENV-001", "capture environment references missing record"),
            ("DEC-001", "capture authority references missing record"),
            ("CAP-001", "capture case references missing record"),
        ):
            self.remove_index_record(missing_id)
            rejected = run_cli("capture", self.pack, "--case", "CAP-001")
            self.assertEqual(rejected.returncode, 1)
            self.assertIn(expected, rejected.stderr)
            self.assertFalse((self.pack / "evidence" / "captures" / "CAP-001").exists())
            if missing_id == "ENV-001":
                self.upsert_index_record("ENV-001", "ENV")
            elif missing_id == "DEC-001":
                self.upsert_index_record("DEC-001", "DEC")

    def test_redaction_authority_is_resolved_before_capture_output(self) -> None:
        (self.pack / "source.txt").write_text("secret=fixture\n", encoding="utf-8")
        case = {
            "id": "CAP-001", "adapter": "manual", "side": "reference",
            "environment_id": "ENV-001", "required": True,
            "authorization_decision_ids": [], "safe_test_environment": True,
            "timeout_seconds": 10, "input": {"source_path": "source.txt"},
            "lifecycle": {"setup": None, "teardown": None},
            "redactions": [{"pattern": "fixture", "replacement": "[REDACTED]", "authority_ids": ["DEC-001"]}],
            "result": None,
        }
        self.set_capture_cases([case])
        self.remove_index_record("DEC-001")
        missing = run_cli("capture", self.pack, "--case", "CAP-001")
        self.assertEqual(missing.returncode, 1)
        self.assertIn("capture authority references missing record", missing.stderr)
        self.assertFalse((self.pack / "evidence" / "captures" / "CAP-001").exists())
        self.upsert_index_record("DEC-001", "E")
        wrong = run_cli("capture", self.pack, "--case", "CAP-001")
        self.assertEqual(wrong.returncode, 1)
        self.assertIn("must have kind ADR, DEC, GAPDEC", wrong.stderr)
        self.assertFalse((self.pack / "evidence" / "captures" / "CAP-001").exists())

    def test_parity_rejects_missing_cap_index_record_before_output(self) -> None:
        self.capture_manual_pair(b"same", b"same")
        self.set_parity_cases(
            [
                {
                    "id": "PAR-001",
                    "comparator": "exact",
                    "required": True,
                    "reference_capture_id": "CAP-001",
                    "clone_capture_id": "CAP-002",
                    "normalizations": [],
                    "options": {},
                    "result": None,
                }
            ]
        )
        self.remove_index_record("CAP-002")
        rejected = run_cli("parity", self.pack, "--case", "PAR-001")
        self.assertEqual(rejected.returncode, 1)
        self.assertIn("capture case references missing record", rejected.stderr)
        self.assertFalse((self.pack / "evidence" / "parity" / "PAR-001").exists())

    def test_normalization_authority_is_resolved_before_parity_output(self) -> None:
        self.capture_manual_pair(b'{"dynamic":1,"value":2}', b'{"dynamic":9,"value":2}', filename="value.json")
        case = {
            "id": "PAR-001", "comparator": "json", "required": True,
            "reference_capture_id": "CAP-001", "clone_capture_id": "CAP-002",
            "normalizations": [{
                "kind": "json-pointer-remove", "artifact_names": ["value.json"],
                "path": "/dynamic", "reason": "Authorized fixture variance", "authority_ids": ["DEC-001"],
            }],
            "options": {}, "result": None,
        }
        self.set_parity_cases([case])
        self.remove_index_record("DEC-001")
        missing = run_cli("parity", self.pack, "--case", "PAR-001")
        self.assertEqual(missing.returncode, 1)
        self.assertIn("parity normalization authority references missing record", missing.stderr)
        self.assertFalse((self.pack / "evidence" / "parity" / "PAR-001").exists())
        self.upsert_index_record("DEC-001", "E")
        wrong = run_cli("parity", self.pack, "--case", "PAR-001")
        self.assertEqual(wrong.returncode, 1)
        self.assertIn("must have kind ADR, DEC, GAPDEC", wrong.stderr)
        self.assertFalse((self.pack / "evidence" / "parity" / "PAR-001").exists())

    def test_malformed_redaction_and_normalization_are_deterministic(self) -> None:
        source = self.pack / "source.txt"
        source.write_text("secret", encoding="utf-8")
        self.set_capture_cases(
            [
                {
                    "id": "CAP-001",
                    "adapter": "manual",
                    "side": "reference",
                    "environment_id": "ENV-001",
                    "required": True,
                    "authorization_decision_ids": [],
                    "safe_test_environment": True,
                    "timeout_seconds": 10,
                    "input": {"source_path": "source.txt"},
                    "lifecycle": {"setup": None, "teardown": None},
                    "redactions": ["secret"],
                    "result": None,
                }
            ]
        )
        redaction = run_cli("capture", self.pack, "--case", "CAP-001")
        self.assertEqual(redaction.returncode, 1)
        self.assertEqual(redaction.stdout, "")
        self.assertIn("CAPTURE_PLAN_INVALID", redaction.stderr)
        self.assertFalse((self.pack / "evidence" / "captures" / "CAP-001").exists())
        self.assertNotIn("INTERNAL_ERROR", redaction.stderr + redaction.stdout)

        other_pack = self.repository / "pack-normalization"
        initialized = run_cli(
            "init",
            "--product-name",
            "Normalization Contract",
            "--product-type",
            "cli",
            "--source-description",
            "Pinned local test reference",
            "--repo-root",
            self.repository,
            "--output-dir",
            "pack-normalization",
            "--timestamp",
            PINNED_TIMESTAMP,
        )
        self.assertEqual(initialized.returncode, 0, initialized.stderr)
        self.pack = other_pack
        self.capture_manual_pair(b'{"value": 1}', b'{"value": 1}', filename="value.json")
        self.set_parity_cases(
            [
                {
                    "id": "PAR-001",
                    "comparator": "json",
                    "required": True,
                    "reference_capture_id": "CAP-001",
                    "clone_capture_id": "CAP-002",
                    "normalizations": ["/dynamic"],
                    "options": {},
                    "result": None,
                }
            ]
        )
        normalization = run_cli("parity", self.pack, "--case", "PAR-001")
        self.assertEqual(normalization.returncode, 1)
        self.assertIn("PARITY_PLAN_INVALID", normalization.stderr)
        self.assertNotIn("INTERNAL_ERROR", normalization.stderr)
        self.assertFalse((self.pack / "evidence" / "parity" / "PAR-001").exists())

    def test_adapter_input_schema_rejects_malformed_cases_before_output(self) -> None:
        common = {
            "id": "CAP-001",
            "side": "clone",
            "environment_id": "ENV-001",
            "required": True,
            "authorization_decision_ids": [],
            "safe_test_environment": True,
            "timeout_seconds": 10,
            "lifecycle": {"setup": None, "teardown": None},
            "redactions": [],
            "result": None,
        }
        malformed = [
            ("http", {"method": "GET", "url": "https://example.invalid", "headers": []}),
            ("http", {"method": "POST", "url": "https://example.invalid", "headers": {}, "body_base64": "%%%="}),
            ("process", {"argv": [sys.executable, "-c", "pass"], "cwd": ".", "environment": {}, "stdin_base64": "not-base64"}),
            ("cli", {"argv": [], "cwd": ".", "environment": {}}),
            ("custom", {"argv": [sys.executable], "cwd": "../escape", "environment": {}}),
            ("filesystem", {"path": "/absolute"}),
            ("manual", {"source_path": "../outside.bin"}),
            ("web", {"driver_argv": [], "cwd": ".", "environment": {}}),
        ]
        for adapter, input_value in malformed:
            with self.subTest(adapter=adapter, input=input_value):
                self.set_capture_cases([{**common, "adapter": adapter, "input": input_value}])
                result = run_cli("capture", self.pack, "--case", "CAP-001")
                self.assertEqual(result.returncode, 1)
                self.assertEqual(result.stdout, "")
                self.assertIn("CAPTURE_PLAN_INVALID", result.stderr)
                self.assertNotIn("INTERNAL_ERROR", result.stderr)
                self.assertFalse((self.pack / "evidence" / "captures" / "CAP-001").exists())

    def test_http_secret_inputs_are_rejected_before_output(self) -> None:
        base_case = {
            "id": "CAP-001",
            "adapter": "http",
            "side": "clone",
            "environment_id": "ENV-001",
            "required": True,
            "authorization_decision_ids": [],
            "safe_test_environment": True,
            "timeout_seconds": 10,
            "input": {"method": "GET", "url": "https://example.invalid", "headers": {}},
            "lifecycle": {"setup": None, "teardown": None},
            "redactions": [],
            "result": None,
        }
        for url in (
            "https://user:password@example.invalid/path",
            "https://example.invalid/path?access_token=forbidden",
            "https://example.invalid/path?AUTH=forbidden",
        ):
            with self.subTest(url=url):
                case = json.loads(json.dumps(base_case))
                case["input"]["url"] = url
                self.set_capture_cases([case])
                result = run_cli("capture", self.pack, "--case", "CAP-001")
                self.assertEqual(result.returncode, 1)
                self.assertIn("SECRET_INPUT_FORBIDDEN", result.stderr)
                self.assertFalse((self.pack / "evidence" / "captures" / "CAP-001").exists())
        for value, diagnostic in (
            ("Bearer raw-secret", "CAPTURE_PLAN_INVALID"),
            ("env:invalid-name", "CAPTURE_PLAN_INVALID"),
            ("env:CLONE_TEST_MISSING_AUTHORIZATION", "SECRET_ENV_MISSING"),
        ):
            with self.subTest(header_value=value):
                case = json.loads(json.dumps(base_case))
                case["input"]["headers"] = {"Authorization": value}
                self.set_capture_cases([case])
                with patch.dict(os.environ, {}, clear=False):
                    os.environ.pop("CLONE_TEST_MISSING_AUTHORIZATION", None)
                    result = run_cli("capture", self.pack, "--case", "CAP-001")
                self.assertEqual(result.returncode, 1)
                self.assertIn(diagnostic, result.stderr)
                self.assertFalse((self.pack / "evidence" / "captures" / "CAP-001").exists())

    def test_http_metadata_never_retains_credentials(self) -> None:
        self.set_capture_cases(
            [
                {
                    "id": "CAP-001",
                    "adapter": "http",
                    "side": "clone",
                    "environment_id": "ENV-001",
                    "required": True,
                    "authorization_decision_ids": [],
                    "safe_test_environment": True,
                    "timeout_seconds": 10,
                    "input": {
                        "method": "GET",
                        "url": "https://example.invalid/path?page=1",
                        "headers": {
                            "Authorization": "env:CLONE_TEST_AUTHORIZATION",
                            "Cookie": "env:CLONE_TEST_COOKIE",
                            "X-API-Key": "env:CLONE_TEST_API_KEY",
                            "X-Trace": "trace-id-123",
                        },
                    },
                    "lifecycle": {"setup": None, "teardown": None},
                    "redactions": [
                        {
                            "pattern": "trace-id-[0-9]+",
                            "replacement": "[TRACE]",
                            "authority_ids": ["DEC-001"],
                        }
                    ],
                    "result": None,
                }
            ]
        )

        class FakeResponse:
            status = 200

            def __init__(self) -> None:
                self.headers = {
                    "Set-Cookie": "server-session=private",
                    "Proxy-Authorization": "Basic private-proxy",
                    "X-Trace": "trace-id-456",
                    "Content-Type": "application/json",
                }

            def read(self) -> bytes:
                return b'{"ok":true}'

        class FakeOpener:
            request: Any = None

            def open(self, request: Any, timeout: float) -> FakeResponse:
                self.request = request
                return FakeResponse()

        opener = FakeOpener()
        secret_environment = {
            "CLONE_TEST_AUTHORIZATION": "Bearer top-secret",
            "CLONE_TEST_COOKIE": "session=private",
            "CLONE_TEST_API_KEY": "private-api-key",
        }
        with (
            patch.dict(os.environ, secret_environment, clear=False),
            patch("scripts.clonepack.operations.urllib.request.build_opener", return_value=opener),
        ):
            result, exit_code = execute_capture(self.pack, "CAP-001")
        self.assertEqual(exit_code, 0)
        sent_headers = {name.lower(): value for name, value in opener.request.header_items()}
        self.assertEqual(sent_headers["authorization"], "Bearer top-secret")
        self.assertEqual(sent_headers["cookie"], "session=private")
        self.assertEqual(sent_headers["x-api-key"], "private-api-key")
        metadata = read_json(self.pack / "evidence" / "captures" / "CAP-001" / "http.json")
        rendered = canonical_json(metadata)
        for forbidden in (
            "top-secret",
            "session=private",
            "private-api-key",
            "server-session=private",
            "private-proxy",
            "trace-id-123",
            "trace-id-456",
        ):
            self.assertNotIn(forbidden, rendered)
        request_headers = dict(metadata["request_headers"])
        response_headers = dict(metadata["response_headers"])
        self.assertEqual(request_headers["authorization"], "[REDACTED]")
        self.assertEqual(request_headers["cookie"], "[REDACTED]")
        self.assertEqual(request_headers["x-api-key"], "[REDACTED]")
        self.assertEqual(request_headers["x-trace"], "[TRACE]")
        self.assertEqual(response_headers["set-cookie"], "[REDACTED]")
        self.assertEqual(response_headers["proxy-authorization"], "[REDACTED]")
        self.assertEqual(response_headers["x-trace"], "[TRACE]")
        self.assertEqual(metadata["redirect_policy"], "disabled")
        sensitive_names = {
            event["name"]
            for event in result["redactions"]
            if event.get("kind") == "sensitive-header"
        }
        self.assertEqual(
            sensitive_names,
            {"authorization", "cookie", "x-api-key", "set-cookie", "proxy-authorization"},
        )
        plan_at_rest = (self.pack / "capture_plan.json").read_text(encoding="utf-8")
        for secret in secret_environment.values():
            self.assertNotIn(secret, plan_at_rest)

    def test_secret_like_capture_environment_requires_transient_indirection(self) -> None:
        common = {
            "id": "CAP-001",
            "side": "clone",
            "environment_id": "ENV-001",
            "required": True,
            "authorization_decision_ids": [],
            "safe_test_environment": True,
            "timeout_seconds": 10,
            "lifecycle": {"setup": None, "teardown": None},
            "redactions": [],
            "result": None,
        }
        for adapter in ("process", "cli", "custom", "web"):
            input_value = (
                {"driver_argv": [sys.executable, "driver.py"], "cwd": ".", "environment": {"API_TOKEN": "raw-secret"}}
                if adapter == "web"
                else {"argv": [sys.executable, "-c", "pass"], "cwd": ".", "environment": {"API_TOKEN": "raw-secret"}}
            )
            with self.subTest(adapter=adapter, state="raw"):
                self.set_capture_cases([{**common, "adapter": adapter, "input": input_value}])
                rejected = run_cli("capture", self.pack, "--case", "CAP-001")
                self.assertEqual(rejected.returncode, 1)
                self.assertIn("CAPTURE_PLAN_INVALID", rejected.stderr)
                self.assertFalse((self.pack / "evidence" / "captures" / "CAP-001").exists())

        missing_case = {
            **common,
            "adapter": "process",
            "input": {
                "argv": [sys.executable, "-c", "pass"],
                "cwd": ".",
                "environment": {"API_TOKEN": "env:CLONE_TEST_MISSING_TOKEN"},
            },
        }
        self.set_capture_cases([missing_case])
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("CLONE_TEST_MISSING_TOKEN", None)
            missing = run_cli("capture", self.pack, "--case", "CAP-001")
        self.assertEqual(missing.returncode, 1)
        self.assertIn("SECRET_ENV_MISSING", missing.stderr)
        self.assertFalse((self.pack / "evidence" / "captures" / "CAP-001").exists())

        positive_case = {
            **common,
            "adapter": "process",
            "input": {
                "argv": [
                    sys.executable,
                    "-c",
                    "import os; assert os.environ['API_TOKEN']; print('resolved')",
                ],
                "cwd": ".",
                "environment": {"API_TOKEN": "env:CLONE_TEST_PROCESS_TOKEN"},
            },
        }
        self.set_capture_cases([positive_case])
        with patch.dict(os.environ, {"CLONE_TEST_PROCESS_TOKEN": "transient-process-secret"}, clear=False):
            result, exit_code = execute_capture(self.pack, "CAP-001")
        self.assertEqual(exit_code, 0)
        self.assertEqual(result["status"], "PASS")
        self.assertEqual(
            (self.pack / "evidence" / "captures" / "CAP-001" / "stdout.bin").read_text(encoding="utf-8"),
            "resolved\n",
        )
        retained = canonical_json(result) + (self.pack / "capture_plan.json").read_text(encoding="utf-8")
        self.assertNotIn("transient-process-secret", retained)

    def test_comparator_environment_requires_transient_indirection(self) -> None:
        self.capture_manual_pair(b"same", b"same", filename="value.bin")
        driver = self.repository / "secret_comparator.py"
        driver.write_text(
            """from __future__ import annotations
import json
import os
from pathlib import Path

assert os.environ[\"API_TOKEN\"]
Path(os.environ[\"CLONE_PARITY_RESULT_PATH\"]).write_text(json.dumps({
    \"schema_version\": \"clone-comparator-result/v1\",
    \"equal\": True,
    \"details\": [],
    \"artifacts\": [],
}), encoding=\"utf-8\")
""",
            encoding="utf-8",
            newline="\n",
        )
        case = {
            "id": "PAR-001",
            "comparator": "custom",
            "required": True,
            "reference_capture_id": "CAP-001",
            "clone_capture_id": "CAP-002",
            "normalizations": [],
            "options": {
                "driver_argv": [sys.executable, "secret_comparator.py"],
                "artifact_pairs": [{"reference_name": "value.bin", "clone_name": "value.bin"}],
                "cwd": ".",
                "environment": {"API_TOKEN": "raw-secret"},
                "timeout_seconds": 10,
            },
            "result": None,
        }
        self.set_parity_cases([case])
        rejected = run_cli("parity", self.pack, "--case", "PAR-001")
        self.assertEqual(rejected.returncode, 1)
        self.assertIn("PARITY_PLAN_INVALID", rejected.stderr)
        self.assertFalse((self.pack / "evidence" / "parity" / "PAR-001").exists())

        case["options"]["environment"] = {"API_TOKEN": "env:CLONE_TEST_COMPARATOR_TOKEN"}
        self.set_parity_cases([case])
        with patch.dict(os.environ, {"CLONE_TEST_COMPARATOR_TOKEN": "transient-comparator-secret"}, clear=False):
            result, exit_code = execute_parity(self.pack, "PAR-001")
        self.assertEqual(exit_code, 0)
        self.assertEqual(result["status"], "PASS")
        retained = canonical_json(result) + (self.pack / "parity_plan.json").read_text(encoding="utf-8")
        self.assertNotIn("transient-comparator-secret", retained)

    def test_gate_environment_rejects_raw_or_missing_secrets_before_run_output(self) -> None:
        index_path = self.pack / "clone_index.json"
        index = read_json(index_path)
        gate = {
            "id": "GATE-001",
            "kind": "GATE",
            "attributes": {
                "argv": [sys.executable, "-c", "print('not reached')"],
                "cwd": ".",
                "environment": {"API_TOKEN": "raw-secret"},
                "timeout_seconds": 10,
                "expected_exit": 0,
                "covered_ids": [],
                "oracle_ids": [],
            },
        }
        index["records"] = [gate, {"id": "ENV-001", "kind": "ENV"}]
        write_json(index_path, index)
        rejected = run_cli("record-run", self.pack, "--gate", "GATE-001", "--environment", "ENV-001")
        self.assertEqual(rejected.returncode, 1)
        self.assertIn("SECRET_INPUT_FORBIDDEN", rejected.stderr)
        self.assertFalse(any((self.pack / "runs").glob("RUN-*.json")))

        index = read_json(index_path)
        index["records"][0]["attributes"]["environment"] = {"API_TOKEN": "env:CLONE_TEST_MISSING_GATE_TOKEN"}
        write_json(index_path, index)
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("CLONE_TEST_MISSING_GATE_TOKEN", None)
            missing = run_cli("record-run", self.pack, "--gate", "GATE-001", "--environment", "ENV-001")
        self.assertEqual(missing.returncode, 1)
        self.assertIn("SECRET_ENV_MISSING", missing.stderr)
        self.assertFalse(any((self.pack / "runs").glob("RUN-*.json")))

    def test_parity_prevalidates_selected_capture_cases_before_output(self) -> None:
        self.capture_manual_pair(b"same", b"same", filename="value.bin")
        self.set_parity_cases(
            [
                {
                    "id": "PAR-001",
                    "comparator": "exact",
                    "required": True,
                    "reference_capture_id": "CAP-001",
                    "clone_capture_id": "CAP-002",
                    "normalizations": [],
                    "options": {},
                    "result": None,
                }
            ]
        )
        capture_plan = read_json(self.pack / "capture_plan.json")
        capture_plan["cases"][1]["input"] = {"source_path": "../escape"}
        write_json(self.pack / "capture_plan.json", capture_plan)
        result = run_cli("parity", self.pack, "--case", "PAR-001")
        self.assertEqual(result.returncode, 1)
        self.assertIn("CAPTURE_PLAN_INVALID", result.stderr)
        self.assertNotIn("INTERNAL_ERROR", result.stderr)
        self.assertFalse((self.pack / "evidence" / "parity" / "PAR-001").exists())

    def test_web_driver_output_contract_is_retained_and_hashed(self) -> None:
        driver = self.repository / "web_driver.py"
        driver.write_text(
            """from __future__ import annotations
import json
import os
from pathlib import Path

output = Path(os.environ[\"CLONE_CAPTURE_OUTPUT\"])
(output / \"screenshot.bin\").write_bytes(b\"synthetic screenshot\")
(output / \"web-driver-result.json\").write_text(json.dumps({
    \"schema_version\": \"clone-web-capture-result/v1\",
    \"artifacts\": [\"screenshot.bin\"],
    \"summary\": {\"state\": \"loaded\"},
}), encoding=\"utf-8\")
print(\"web driver complete\")
""",
            encoding="utf-8",
            newline="\n",
        )
        self.set_capture_cases(
            [
                {
                    "id": "CAP-001",
                    "adapter": "web",
                    "side": "clone",
                    "environment_id": "ENV-001",
                    "required": True,
                    "authorization_decision_ids": [],
                    "safe_test_environment": True,
                    "timeout_seconds": 10,
                    "input": {
                        "driver_argv": [sys.executable, "web_driver.py"],
                        "cwd": ".",
                        "environment": {},
                    },
                    "lifecycle": {"setup": None, "teardown": None},
                    "redactions": [],
                    "result": None,
                }
            ]
        )
        captured = run_cli("capture", self.pack, "--case", "CAP-001")
        self.assertEqual(captured.returncode, 0, captured.stderr)
        result = json.loads(captured.stdout)
        self.assertEqual(result["summary"]["web"], {"state": "loaded"})
        names = {Path(artifact["path"]).name for artifact in result["artifacts"]}
        self.assertEqual(
            names,
            {"process.json", "stdout.bin", "stderr.bin", "web-driver-result.json", "screenshot.bin"},
        )
        for artifact in result["artifacts"]:
            path = self.pack / artifact["path"]
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), artifact["sha256"])

    def test_http_extensionless_json_body_uses_pinned_semantic_mode(self) -> None:
        bodies = [b'{"a":1,"b":2}', b'{\n  "b": 2, "a": 1\n}']
        pack_manifest = read_json(self.pack / "clone_pack.json")
        cases: list[dict[str, Any]] = []
        for position, (case_id, side, body) in enumerate(
            (("CAP-001", "reference", bodies[0]), ("CAP-002", "clone", bodies[1])), 1
        ):
            case: dict[str, Any] = {
                "id": case_id,
                "adapter": "http",
                "side": side,
                "environment_id": "ENV-001",
                "required": True,
                "authorization_decision_ids": [],
                "safe_test_environment": True,
                "timeout_seconds": 10,
                "input": {"method": "GET", "url": "https://authorized.invalid/value", "headers": {}},
                "lifecycle": {"setup": None, "teardown": None},
                "redactions": [],
                "result": None,
            }
            case_sha256 = hashlib.sha256(
                canonical_json({key: value for key, value in case.items() if key != "result"}).encode("utf-8")
            ).hexdigest()
            directory = self.pack / "evidence" / "captures" / case_id
            directory.mkdir(parents=True)
            metadata_path = directory / "http.json"
            write_json(
                metadata_path,
                {
                    "method": "GET",
                    "url": "https://authorized.invalid/value",
                    "request_headers": [],
                    "status": 200,
                    "response_headers": [["content-type", "application/json"]],
                    "elapsed_ms_context": float(position),
                },
            )
            body_path = directory / "response.body"
            body_path.write_bytes(body)
            artifacts = []
            for artifact_number, path in enumerate((metadata_path, body_path), 1):
                artifacts.append(
                    {
                        "id": f"ART-{case_id}-{artifact_number:02d}",
                        "path": path.relative_to(self.pack).as_posix(),
                        "size": path.stat().st_size,
                        "media_type": "application/json",
                        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                    }
                )
            result_path = directory / "manifest.json"
            write_json(
                result_path,
                {
                    "schema_version": "clone-capture-result/v2",
                    "capture_id": case_id,
                    "pack_id": pack_manifest["pack_id"],
                    "pack_revision": pack_manifest["pack_revision"],
                    "reference_baseline_id": pack_manifest["reference_baseline_id"],
                    "adapter": "http",
                    "side": side,
                    "environment_id": "ENV-001",
                    "case_sha256": case_sha256,
                    "clone_revision": pack_manifest["repository_state"]["revision"] if side == "clone" else None,
                    "clone_diff_sha256": pack_manifest["repository_state"]["diff_sha256"] if side == "clone" else None,
                    "status": "PASS",
                    "summary": {},
                    "artifacts": artifacts,
                    "redactions": [],
                    "runner_version": "synthetic-test-fixture",
                },
            )
            case["result"] = {
                "status": "PASS",
                "path": result_path.relative_to(self.pack).as_posix(),
                "sha256": hashlib.sha256(result_path.read_bytes()).hexdigest(),
            }
            cases.append(case)
        self.set_capture_cases(cases)
        self.set_parity_cases(
            [
                {
                    "id": "PAR-001",
                    "comparator": "http",
                    "required": True,
                    "reference_capture_id": "CAP-001",
                    "clone_capture_id": "CAP-002",
                    "normalizations": [
                        {
                            "kind": "json-pointer-remove",
                            "artifact_names": ["http.json"],
                            "path": "/elapsed_ms_context",
                            "reason": "Wall-clock duration is not part of this behavior oracle",
                            "authority_ids": ["DEC-001"],
                        }
                    ],
                    "options": {"json_artifact_names": ["response.body"]},
                    "result": None,
                }
            ]
        )
        parity = run_cli("parity", self.pack, "--case", "PAR-001")
        self.assertEqual(parity.returncode, 0, parity.stderr)
        self.assertEqual(json.loads(parity.stdout)["status"], "PASS")

    def test_performance_tolerances_are_pinned_and_enforced(self) -> None:
        self.capture_manual_pair(b'{"latency_ms": 100}', b'{"latency_ms": 104}', filename="metrics.json")
        self.set_parity_cases(
            [
                {
                    "id": case_id,
                    "comparator": "performance",
                    "required": True,
                    "reference_capture_id": "CAP-001",
                    "clone_capture_id": "CAP-002",
                    "normalizations": [],
                    "options": {"absolute_tolerance": 1, "relative_tolerance": relative},
                    "result": None,
                }
                for case_id, relative in (("PAR-001", 0.05), ("PAR-002", 0.01))
            ]
        )
        passing = run_cli("parity", self.pack, "--case", "PAR-001")
        failing = run_cli("parity", self.pack, "--case", "PAR-002")
        self.assertEqual(passing.returncode, 0, passing.stderr)
        self.assertEqual(json.loads(passing.stdout)["status"], "PASS")
        self.assertEqual(failing.returncode, 5)
        self.assertEqual(json.loads(failing.stdout)["status"], "FAIL")

    def test_case_hashes_prevent_stale_capture_and_parity_reuse(self) -> None:
        self.capture_manual_pair(b"same", b"same", filename="value.bin")
        parity_cases = [
            {
                "id": case_id,
                "comparator": "exact",
                "required": True,
                "reference_capture_id": "CAP-001",
                "clone_capture_id": "CAP-002",
                "normalizations": [],
                "options": {},
                "result": None,
            }
            for case_id in ("PAR-001", "PAR-002")
        ]
        self.set_parity_cases(parity_cases)
        passing = run_cli("parity", self.pack, "--case", "PAR-001")
        self.assertEqual(passing.returncode, 0, passing.stderr)
        passing_result = json.loads(passing.stdout)
        expected_hash = hashlib.sha256(
            canonical_json({key: value for key, value in parity_cases[0].items() if key != "result"}).encode("utf-8")
        ).hexdigest()
        self.assertEqual(passing_result["case_sha256"], expected_hash)

        capture_plan = read_json(self.pack / "capture_plan.json")
        capture_plan["cases"][1]["timeout_seconds"] = 11
        write_json(self.pack / "capture_plan.json", capture_plan)
        stale_capture = run_cli("parity", self.pack, "--case", "PAR-002")
        self.assertEqual(stale_capture.returncode, 1)
        self.assertIn("PLAN_CASE_INDEX_STALE", stale_capture.stderr)

        parity_plan = read_json(self.pack / "parity_plan.json")
        parity_plan["cases"][0]["comparator"] = "text"
        write_json(self.pack / "parity_plan.json", parity_plan)
        validation = run_cli("validate", self.pack, "--profile", "verified-mvp", "--format", "json")
        diagnostics = json.loads(validation.stdout)["diagnostics"]
        self.assertTrue(
            any(item["code"] == "PARITY_CONTRACT_STALE" and item["record_id"] == "PAR-001" for item in diagnostics),
            diagnostics,
        )

    def test_clone_repository_identity_prevents_stale_capture_and_parity_reuse(self) -> None:
        self.capture_manual_pair(b"same", b"same", filename="value.bin")
        self.set_parity_cases(
            [
                {
                    "id": case_id,
                    "comparator": "exact",
                    "required": True,
                    "reference_capture_id": "CAP-001",
                    "clone_capture_id": "CAP-002",
                    "normalizations": [],
                    "options": {},
                    "result": None,
                }
                for case_id in ("PAR-001", "PAR-002")
            ]
        )
        passing = run_cli("parity", self.pack, "--case", "PAR-001")
        self.assertEqual(passing.returncode, 0, passing.stderr)
        reference_capture = read_json(self.pack / "evidence" / "captures" / "CAP-001" / "manifest.json")
        clone_capture = read_json(self.pack / "evidence" / "captures" / "CAP-002" / "manifest.json")
        parity_result = json.loads(passing.stdout)
        self.assertIsNone(reference_capture["clone_revision"])
        self.assertIsNone(reference_capture["clone_diff_sha256"])
        self.assertEqual(clone_capture["clone_revision"], "UNRESOLVED")
        self.assertIsNone(clone_capture["clone_diff_sha256"])
        self.assertEqual(parity_result["clone_revision"], "UNRESOLVED")
        self.assertIsNone(parity_result["clone_diff_sha256"])

        manifest_path = self.pack / "clone_pack.json"
        manifest = read_json(manifest_path)
        manifest["repository_state"] = {
            "kind": "working-tree",
            "revision": "revision-2",
            "diff_sha256": "2" * 64,
        }
        write_json(manifest_path, manifest)

        stale = run_cli("parity", self.pack, "--case", "PAR-002")
        self.assertEqual(stale.returncode, 5)
        self.assertIn("CAPTURE_CLONE_STALE", stale.stderr)
        self.assertFalse((self.pack / "evidence" / "parity" / "PAR-002").exists())

        validation = run_cli("validate", self.pack, "--profile", "verified-mvp", "--format", "json")
        diagnostics = json.loads(validation.stdout)["diagnostics"]
        codes = {item["code"] for item in diagnostics}
        self.assertIn("CAPTURE_CLONE_STALE", codes)
        self.assertIn("PARITY_CLONE_STALE", codes)

    def test_local_custom_and_perceptual_drivers_retain_evidence(self) -> None:
        self.capture_manual_pair(b"reference", b"clone", filename="image.bin")
        driver = self.repository / "comparator.py"
        driver.write_text(
            """from __future__ import annotations
import json
import os
from pathlib import Path

result_path = Path(os.environ[\"CLONE_PARITY_RESULT_PATH\"])
(result_path.parent / \"metric.txt\").write_text(\"0.25\\n\", encoding=\"utf-8\")
comparator = os.environ[\"CLONE_PARITY_COMPARATOR\"]
result = {
    \"schema_version\": \"clone-comparator-result/v1\",
    \"details\": [\"synthetic independent result\"],
    \"artifacts\": [\"metric.txt\"],
}
if comparator == \"perceptual-image\":
    result[\"distance\"] = 0.25
else:
    result[\"equal\"] = False
result_path.write_text(json.dumps(result), encoding=\"utf-8\")
print(\"driver stdout retained\")
""",
            encoding="utf-8",
            newline="\n",
        )
        common_options = {
            "driver_argv": [sys.executable, "comparator.py"],
            "artifact_pairs": [{"reference_name": "image.bin", "clone_name": "image.bin"}],
            "cwd": ".",
            "environment": {},
            "timeout_seconds": 10,
        }
        self.set_parity_cases(
            [
                {
                    "id": "PAR-001",
                    "comparator": "perceptual-image",
                    "required": True,
                    "reference_capture_id": "CAP-001",
                    "clone_capture_id": "CAP-002",
                    "normalizations": [],
                    "options": {**common_options, "threshold": 0.3},
                    "result": None,
                },
                {
                    "id": "PAR-002",
                    "comparator": "custom",
                    "required": True,
                    "reference_capture_id": "CAP-001",
                    "clone_capture_id": "CAP-002",
                    "normalizations": [],
                    "options": common_options,
                    "result": None,
                },
            ]
        )
        perceptual = run_cli("parity", self.pack, "--case", "PAR-001")
        custom = run_cli("parity", self.pack, "--case", "PAR-002")
        self.assertEqual(perceptual.returncode, 0, perceptual.stderr)
        perceptual_result = json.loads(perceptual.stdout)
        self.assertEqual(perceptual_result["status"], "PASS")
        self.assertIn("distance 0.25 <= threshold 0.3: true", perceptual_result["details"][-1])
        self.assertEqual(custom.returncode, 5, custom.stderr)
        self.assertEqual(json.loads(custom.stdout)["status"], "FAIL")
        for case_id in ("PAR-001", "PAR-002"):
            driver_dir = self.pack / "evidence" / "parity" / case_id / "driver-01"
            self.assertEqual((driver_dir / "stdout.bin").read_text(encoding="utf-8"), "driver stdout retained\n")
            self.assertTrue((driver_dir / "invocation.json").is_file())
            self.assertEqual((driver_dir / "metric.txt").read_text(encoding="utf-8"), "0.25\n")
            result = read_json(self.pack / "evidence" / "parity" / case_id / "result.json")
            for artifact in result["artifacts"]:
                path = self.pack / artifact["path"]
                self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), artifact["sha256"])

    def test_driver_failure_is_deterministic_and_retains_process_evidence(self) -> None:
        self.capture_manual_pair(b"reference", b"clone", filename="value.bin")
        driver = self.repository / "failing.py"
        driver.write_text(
            "import sys\nprint('retained stdout')\nprint('retained stderr', file=sys.stderr)\nraise SystemExit(9)\n",
            encoding="utf-8",
            newline="\n",
        )
        self.set_parity_cases(
            [
                {
                    "id": "PAR-001",
                    "comparator": "custom",
                    "required": True,
                    "reference_capture_id": "CAP-001",
                    "clone_capture_id": "CAP-002",
                    "normalizations": [],
                    "options": {
                        "driver_argv": [sys.executable, "failing.py"],
                        "artifact_pairs": [{"reference_name": "value.bin", "clone_name": "value.bin"}],
                        "cwd": ".",
                        "environment": {},
                        "timeout_seconds": 10,
                    },
                    "result": None,
                }
            ]
        )
        failed = run_cli("parity", self.pack, "--case", "PAR-001")
        self.assertEqual(failed.returncode, 7)
        self.assertIn("COMPARATOR_DRIVER_FAILED", failed.stderr)
        self.assertNotIn("INTERNAL_ERROR", failed.stderr)
        driver_dir = self.pack / "evidence" / "parity" / "PAR-001" / "driver-01"
        self.assertEqual((driver_dir / "stdout.bin").read_text(encoding="utf-8"), "retained stdout\n")
        self.assertEqual((driver_dir / "stderr.bin").read_text(encoding="utf-8"), "retained stderr\n")
        self.assertEqual(read_json(driver_dir / "invocation.json")["exit_code"], 9)


if __name__ == "__main__":
    unittest.main()
