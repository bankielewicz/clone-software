from __future__ import annotations

import copy
import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from scripts.clonepack.common import ClonePackError
from scripts.clonepack.full_stack_qa import (
    FullStackQaIssue,
    full_stack_qa_contract_sha256,
    validate_full_stack_qa_plan,
)
from scripts.clonepack.pack import initialize_v2, validate_v2
from scripts.clonepack.operations import record_run
from scripts.clonepack.schema import validate_schema_file


ROOT = Path(__file__).resolve().parents[1]
PLAN_SCHEMA = ROOT / "assets" / "schemas" / "full-stack-qa-plan-v1.schema.json"
RESULT_SCHEMA = ROOT / "assets" / "schemas" / "full-stack-qa-result-v1.schema.json"
MANIFEST_SCHEMA = ROOT / "assets" / "schemas" / "clone-pack-v2.schema.json"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class FullStackQaContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.repository = Path(self.temporary.name)
        self.pack = self.repository / "docs" / "clone"
        (self.repository / ".github" / "workflows").mkdir(parents=True)
        (self.repository / "qa").mkdir()
        (self.repository / "artifacts").mkdir()
        self.files = {
            ".github/workflows/full-stack-qa.yml": "name: Full-stack QA\n",
            "package-lock.json": '{"lockfileVersion": 3}\n',
            "playwright.config.ts": "export default {};\n",
            "qa/full-stack.spec.ts": "test('vertical journey', async () => {});\n",
            "qa/run.mjs": "// repository-owned Playwright entry point\n",
            "qa/run.py": (
                "from pathlib import Path\n"
                "path = Path('artifacts/QA-001.json')\n"
                "if path.exists():\n"
                "    path.write_bytes(path.read_bytes())\n"
                "print('full-stack gate')\n"
            ),
            "qa/block.py": "import sys\nsys.exit(7)\n",
            "qa/noop.py": "print('no artifact emission')\n",
        }
        for relative, content in self.files.items():
            path = self.repository / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
        self.pack.mkdir(parents=True)
        self.plan = self._plan()
        self._write_plan()
        self.records = self._records()

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def _command(self, argv: list[str]) -> dict[str, object]:
        return {
            "argv": argv,
            "cwd": ".",
            "environment": {},
            "expected_exit": 0,
            "timeout_seconds": 30,
        }

    def _readiness(self, url: str) -> dict[str, object]:
        return {
            "kind": "HTTP",
            "target": url,
            "expected_status": 200,
            "timeout_seconds": 30,
        }

    def _proved_dimension(self, assertion: str) -> dict[str, object]:
        return {
            "disposition": "PROVED",
            "assertion": assertion,
            "artifact_path": "artifacts/QA-001.json",
            "decision_ids": [],
        }

    def _plan(self) -> dict[str, object]:
        plan: dict[str, object] = {
            "schema_version": "clone-full-stack-qa-plan/v1",
            "pack_id": "pack-qa",
            "pack_revision": 1,
            "contract_sha256": "0" * 64,
            "contract_artifact_id": "ART-001",
            "safe_test_environment": True,
            "production_access": False,
            "environment": {
                "environment_id": "ENV-001",
                "synthetic_data": True,
                "fixture_reset": self._command(["python3", "qa/reset.py"]),
                "fixture_seed": self._command(["python3", "qa/seed.py"]),
                "fixture_cleanup": self._command(["python3", "qa/cleanup.py"]),
                "allowed_origins": [
                    {
                        "url": "http://127.0.0.1:3000",
                        "classification": "LOOPBACK",
                        "decision_ids": [],
                    },
                    {
                        "url": "http://127.0.0.1:8080",
                        "classification": "LOOPBACK",
                        "decision_ids": [],
                    }
                ],
            },
            "owned_stack": {
                "frontend": {
                    "service_id": "SERVICE-001",
                    "implementation": "REAL",
                    "readiness": self._readiness("http://127.0.0.1:3000/health"),
                },
                "mid_tier": {
                    "service_id": "SERVICE-002",
                    "implementation": "REAL",
                    "readiness": self._readiness("http://127.0.0.1:8080/ready"),
                },
                "backend": {
                    "service_id": "SERVICE-003",
                    "implementation": "REAL",
                    "readiness": self._readiness("http://127.0.0.1:8080/health"),
                },
                "persistence": {
                    "service_id": "SERVICE-004",
                    "implementation": "REAL",
                    "readiness": {
                        "kind": "COMMAND",
                        "command": self._command(["python3", "qa/check_database.py"]),
                    },
                },
                "supporting_services": [],
            },
            "external_dependencies": [],
            "playwright": {
                "driver_argv": ["node", "qa/run.mjs"],
                "package": "@playwright/test",
                "version": "1.61.0",
                "lockfile_path": "package-lock.json",
                "lockfile_sha256": sha256(self.repository / "package-lock.json"),
                "config_path": "playwright.config.ts",
                "config_sha256": sha256(self.repository / "playwright.config.ts"),
                "browser": "chromium",
                "project": "chromium-desktop",
                "browser_version": "142.0.0",
                "operating_system": "ubuntu-24.04",
                "viewport": {"width": 1280, "height": 720},
                "locale": "en-US",
                "timezone": "UTC",
                "color_scheme": "light",
                "reduced_motion": "reduce",
                "workers": 1,
                "retries": 0,
                "fail_on_flaky_tests": True,
                "trace": "retain-on-failure",
                "screenshot": "only-on-failure",
                "video": "off",
                "preinstalled": True,
                "install_argv": None,
            },
            "ci": {
                "provider": "github-actions",
                "workflow_path": ".github/workflows/full-stack-qa.yml",
                "workflow_sha256": sha256(
                    self.repository / ".github" / "workflows" / "full-stack-qa.yml"
                ),
                "required_check": "Full-stack QA",
                "triggers": ["pull_request"],
                "runner": "ubuntu-24.04",
                "timeout_minutes": 20,
                "permissions": {"contents": "read"},
                "gate_id": "GATE-001",
                "gate_argv": ["python3", "qa/run.py"],
                "gate_cwd": ".",
                "expected_exit": 0,
                "blocked_exit_codes": [7],
                "artifact_paths": ["artifacts/QA-001.json"],
                "fresh_artifact_paths": ["artifacts/QA-001.json"],
                "result_path": "artifacts/QA-001.json",
                "restore_argv": None,
                "restore_authority_decision_ids": [],
            },
            "journeys": [
                {
                    "id": "QA-001",
                    "workflow_id": "WF-001",
                    "actor_id": "ACT-001",
                    "requirement_ids": ["REQ-001"],
                    "acceptance_ids": ["AC-001"],
                    "test_id": "TEST-001",
                    "gate_id": "GATE-001",
                    "environment_id": "ENV-001",
                    "oracle_ids": ["ART-001", "E-001"],
                    "test_path": "qa/full-stack.spec.ts",
                    "test_sha256": sha256(self.repository / "qa" / "full-stack.spec.ts"),
                    "fixture": "fresh synthetic tenant and empty order store",
                    "ui": {
                        "action": "submit the order form through its accessible button",
                        "assertion": "the submitted state is visible after reload",
                        "artifact_path": "artifacts/QA-001.json",
                    },
                    "wire": {
                        "trigger": "submit-order",
                        "method": "POST",
                        "path": "/api/orders",
                        "expected_status": 201,
                        "schema_assertion": "response matches OrderCreatedResponse v1",
                        "artifact_path": "artifacts/QA-001.json",
                        "additional_exchanges": [
                            {
                                "trigger": "reload-order",
                                "method": "GET",
                                "path": "/api/orders/{captured_order_id}",
                                "expected_status": 200,
                                "schema_assertion": "response matches OrderResponse v1",
                            }
                        ],
                    },
                    "service": {
                        "probe": "GET /api/orders/{captured_order_id}",
                        "postcondition": "status is submitted for the captured actor",
                        "artifact_path": "artifacts/QA-001.json",
                    },
                    "persistence": {
                        "verification_event": "reload",
                        "postcondition": "order {captured_order_id} remains submitted after reload",
                        "artifact_path": "artifacts/QA-001.json",
                    },
                    "identity_bindings": [
                        {
                            "id": "BIND-001",
                            "name": "captured_order_id",
                            "source": {
                                "exchange_trigger": "submit-order",
                                "response_json_pointer": "/order_id",
                                "value_type": "string",
                            },
                            "consumers": [
                                {
                                    "kind": "WIRE_PATH",
                                    "contract_pointer": (
                                        "/journeys/0/wire/additional_exchanges/0/path"
                                    ),
                                },
                                {
                                    "kind": "SERVICE",
                                    "contract_pointer": "/journeys/0/service/probe",
                                },
                                {
                                    "kind": "PERSISTENCE",
                                    "contract_pointer": (
                                        "/journeys/0/persistence/postcondition"
                                    ),
                                },
                            ],
                            "artifact_path": "artifacts/QA-001.json",
                        }
                    ],
                    "authorization": self._proved_dimension(
                        "a different tenant receives 404 for the captured order ID"
                    ),
                    "jobs": {
                        "disposition": "NOT_APPLICABLE",
                        "assertion": None,
                        "artifact_path": None,
                        "decision_ids": ["DEC-001"],
                    },
                    "accessibility": self._proved_dimension(
                        "the form and result are operable by role and accessible name"
                    ),
                    "visual": self._proved_dimension(
                        "the pinned viewport snapshot matches its approved baseline"
                    ),
                    "external_dependency_ids": [],
                    "supporting_service_ids": [],
                }
            ],
        }
        plan["contract_sha256"] = full_stack_qa_contract_sha256(plan)
        return plan

    def _result(self) -> dict[str, object]:
        return {
            "schema_version": "clone-full-stack-qa-result/v1",
            "plan_contract_sha256": self.plan["contract_sha256"],
            "gate_id": "GATE-001",
            "environment_id": "ENV-001",
            "playwright_project": "chromium-desktop",
            "status": "PASS",
            "journeys": [
                {
                    "id": "QA-001",
                    "status": "PASS",
                    "ui": {
                        "status": "PASS",
                        "assertion": "the submitted state is visible after reload",
                        "observation": "submitted state visible",
                    },
                    "wire": {
                        "status": "PASS",
                        "trigger": "submit-order",
                        "observed_method": "POST",
                        "observed_path": "/api/orders",
                        "observed_status": 201,
                        "schema_assertion": "response matches OrderCreatedResponse v1",
                        "observation": "response matched OrderCreatedResponse v1",
                        "additional_exchanges": [
                            {
                                "trigger": "reload-order",
                                "status": "PASS",
                                "observed_method": "GET",
                                "observed_path": "/api/orders/order-123",
                                "observed_status": 200,
                                "schema_assertion": "response matches OrderResponse v1",
                                "observation": "reload response matched OrderResponse v1",
                            }
                        ],
                    },
                    "service": {
                        "status": "PASS",
                        "probe": "GET /api/orders/{captured_order_id}",
                        "postcondition": "status is submitted for the captured actor",
                        "observation": "order status is submitted",
                    },
                    "persistence": {
                        "status": "PASS",
                        "verification_event": "reload",
                        "postcondition": "order {captured_order_id} remains submitted after reload",
                        "observation": "same order ID and state remained visible",
                    },
                    "identity_bindings": [
                        {
                            "id": "BIND-001",
                            "status": "PASS",
                            "source": {
                                "exchange_trigger": "submit-order",
                                "response_json_pointer": "/order_id",
                                "value_type": "string",
                            },
                            "captured_value_sha256": hashlib.sha256(b"order-123").hexdigest(),
                            "consumers": [
                                {
                                    "kind": "WIRE_PATH",
                                    "contract_pointer": (
                                        "/journeys/0/wire/additional_exchanges/0/path"
                                    ),
                                    "observed_value_sha256": hashlib.sha256(b"order-123").hexdigest(),
                                    "status": "PASS",
                                    "observation": "reload request used the captured order ID",
                                },
                                {
                                    "kind": "SERVICE",
                                    "contract_pointer": "/journeys/0/service/probe",
                                    "observed_value_sha256": hashlib.sha256(b"order-123").hexdigest(),
                                    "status": "PASS",
                                    "observation": "service probe used the captured order ID",
                                },
                                {
                                    "kind": "PERSISTENCE",
                                    "contract_pointer": (
                                        "/journeys/0/persistence/postcondition"
                                    ),
                                    "observed_value_sha256": hashlib.sha256(b"order-123").hexdigest(),
                                    "status": "PASS",
                                    "observation": "database row used the captured order ID",
                                },
                            ],
                            "observation": "one order identity was preserved through all consumers",
                        }
                    ],
                    "authorization": {
                        "status": "PASS",
                        "assertion": "a different tenant receives 404 for the captured order ID",
                        "observation": "other tenant received 404",
                    },
                    "jobs": {"status": "NOT_APPLICABLE", "assertion": None, "observation": None},
                    "accessibility": {
                        "status": "PASS",
                        "assertion": "the form and result are operable by role and accessible name",
                        "observation": "role and name path passed",
                    },
                    "visual": {
                        "status": "PASS",
                        "assertion": "the pinned viewport snapshot matches its approved baseline",
                        "observation": "pinned snapshot matched",
                    },
                }
            ],
            "external_dependencies": [],
            "supporting_services": [],
        }

    def _attach_result(
        self,
        records: dict[str, dict[str, object]],
        run_id: str,
        result: dict[str, object] | None = None,
    ) -> None:
        retained = self.pack / "runs" / "artifacts" / run_id / "full-stack-result.json"
        retained.parent.mkdir(parents=True, exist_ok=True)
        retained.write_text(
            json.dumps(result or self._result(), sort_keys=True) + "\n",
            encoding="utf-8",
        )
        records[run_id]["artifacts"] = [
            {
                "id": f"ART-{run_id}-03",
                "path": retained.relative_to(self.pack).as_posix(),
                "source_path": "artifacts/QA-001.json",
                "size": retained.stat().st_size,
                "media_type": "application/json",
                "sha256": sha256(retained),
            }
        ]

    def _write_plan(self) -> None:
        (self.pack / "full_stack_qa_plan.json").write_text(
            json.dumps(self.plan, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

    def _record(self, identifier: str, kind: str, *, links: dict[str, list[str]] | None = None,
                attributes: dict[str, object] | None = None, state: str = "READY") -> dict[str, object]:
        return {
            "id": identifier,
            "kind": kind,
            "locator": {"path": "definitions.md", "anchor": identifier, "sha256": "1" * 64},
            "links": links or {},
            "applicability": "MVP",
            "state": state,
            "attributes": attributes or {},
        }

    def _records(self) -> dict[str, dict[str, object]]:
        digest = str(self.plan["contract_sha256"])
        covered = ["REQ-001", "AC-001", "TEST-001"]
        return {
            "ART-001": {
                **self._record("ART-001", "ART"),
                "locator": {
                    "path": "full_stack_qa_plan.json",
                    "anchor": digest,
                    "sha256": "2" * 64,
                },
            },
            "ACT-001": self._record("ACT-001", "ACT"),
            "DEC-001": self._record("DEC-001", "DEC"),
            "ENV-001": self._record("ENV-001", "ENV"),
            "E-001": self._record(
                "E-001",
                "E",
                links={"requirements": ["REQ-001"]},
            ),
            "WF-001": self._record(
                "WF-001",
                "WF",
                links={"requirements": ["REQ-001"]},
                attributes={"disposition": "EQUIVALENT"},
            ),
            "REQ-001": self._record(
                "REQ-001",
                "REQ",
                links={"acceptance": ["AC-001"], "tests": ["TEST-001"], "workflows": ["WF-001"]},
            ),
            "AC-001": self._record(
                "AC-001",
                "AC",
                links={"requirements": ["REQ-001"], "tests": ["TEST-001"]},
            ),
            "TEST-001": self._record(
                "TEST-001",
                "TEST",
                links={
                    "requirements": ["REQ-001"],
                    "acceptance": ["AC-001"],
                    "gates": ["GATE-001"],
                    "oracles": ["ART-001", "E-001"],
                },
            ),
            "GATE-001": self._record(
                "GATE-001",
                "GATE",
                links={"tests": ["TEST-001"], "oracles": ["ART-001", "E-001"]},
                attributes={
                    "argv": ["python3", "qa/run.py"],
                    "cwd": ".",
                    "environment": {},
                    "expected_exit": 0,
                    "blocked_exit_codes": [7],
                    "timeout_seconds": 1200,
                    "covered_ids": covered,
                    "oracle_ids": ["ART-001", "E-001"],
                    "artifact_paths": ["artifacts/QA-001.json"],
                    "fresh_artifact_paths": ["artifacts/QA-001.json"],
                    "normalizations": [],
                    "redactions": [],
                },
            ),
        }

    def _issues(self, plan: dict[str, object] | None = None, *, verified: bool = False,
                records: dict[str, dict[str, object]] | None = None) -> list[str]:
        selected_plan = plan or self.plan
        selected_records = records or self.records
        runs = {
            identifier: record
            for identifier, record in selected_records.items()
            if record.get("kind") == "RUN"
        }
        return [
            issue.code
            for issue in validate_full_stack_qa_plan(
                pack=self.pack,
                repository=self.repository,
                plan=selected_plan,
                records=selected_records,
                runs=runs,
                require_ready=True,
                require_verified=verified,
            )
        ]

    def test_strict_schema_accepts_complete_plan_and_rejects_missing_layer(self) -> None:
        self.assertEqual(validate_schema_file(self.plan, PLAN_SCHEMA), [])
        self.assertEqual(validate_schema_file(self._result(), RESULT_SCHEMA), [])
        incomplete = copy.deepcopy(self.plan)
        del incomplete["journeys"][0]["wire"]  # type: ignore[index]
        self.assertNotEqual(validate_schema_file(incomplete, PLAN_SCHEMA), [])

        unsafe_path = copy.deepcopy(self.plan)
        unsafe_path["ci"]["artifact_paths"] = [".."]  # type: ignore[index]
        self.assertNotEqual(validate_schema_file(unsafe_path, PLAN_SCHEMA), [])

    def test_schema_rejects_owned_mock_retries_and_unauthorized_external_stub(self) -> None:
        owned_mock = copy.deepcopy(self.plan)
        owned_mock["owned_stack"]["backend"]["implementation"] = "STUB"  # type: ignore[index]
        self.assertNotEqual(validate_schema_file(owned_mock, PLAN_SCHEMA), [])

        retries = copy.deepcopy(self.plan)
        retries["playwright"]["retries"] = 1  # type: ignore[index]
        self.assertNotEqual(validate_schema_file(retries, PLAN_SCHEMA), [])

        unrelated_package = copy.deepcopy(self.plan)
        unrelated_package["playwright"]["package"] = "selenium"  # type: ignore[index]
        self.assertNotEqual(validate_schema_file(unrelated_package, PLAN_SCHEMA), [])

        external = copy.deepcopy(self.plan)
        external["external_dependencies"] = [
            {
                "id": "EXTERNAL-001",
                "disposition": "STUBBED",
                "reason": "deterministic provider boundary",
                "decision_ids": [],
                "assertion": "one captured message and no live delivery",
                "interface": {
                    "protocol": "smtp",
                    "endpoint": "127.0.0.1:1025",
                    "classification": "LOOPBACK",
                },
                "readiness": {
                    "kind": "COMMAND",
                    "command": self._command(["python3", "qa/check_email_stub.py"]),
                },
                "artifact_path": "artifacts/QA-001.json",
            }
        ]
        self.assertNotEqual(validate_schema_file(external, PLAN_SCHEMA), [])

        excluded = copy.deepcopy(self.plan)
        excluded["external_dependencies"] = [
            {
                "id": "EXTERNAL-001",
                "disposition": "EXCLUDED",
                "reason": "provider behavior is outside this journey",
                "decision_ids": ["DEC-001"],
                "assertion": None,
                "interface": None,
                "readiness": None,
                "artifact_path": None,
            }
        ]
        excluded["journeys"][0]["external_dependency_ids"] = ["EXTERNAL-001"]  # type: ignore[index]
        self.assertEqual(validate_schema_file(excluded, PLAN_SCHEMA), [])

    def test_monolithic_service_can_fill_multiple_owned_roles(self) -> None:
        monolith = copy.deepcopy(self.plan)
        monolith["owned_stack"]["backend"] = copy.deepcopy(  # type: ignore[index]
            monolith["owned_stack"]["mid_tier"]  # type: ignore[index]
        )
        monolith["contract_sha256"] = full_stack_qa_contract_sha256(monolith)

        self.assertNotIn("QA_SERVICE_DUPLICATE", self._issues(monolith))

        conflicting = copy.deepcopy(monolith)
        conflicting["owned_stack"]["backend"]["readiness"]["target"] = (  # type: ignore[index]
            "http://127.0.0.1:8080/health"
        )
        conflicting["contract_sha256"] = full_stack_qa_contract_sha256(conflicting)
        self.assertIn("QA_SERVICE_CONFLICT", self._issues(conflicting))

    def test_supporting_services_and_external_stub_are_machine_validated(self) -> None:
        extended = copy.deepcopy(self.plan)
        extended["owned_stack"]["supporting_services"] = [  # type: ignore[index]
            {
                "service_id": "SERVICE-005",
                "role": "worker",
                "implementation": "REAL",
                "assertion": "the worker processes the captured order exactly once",
                "artifact_path": "artifacts/QA-001.json",
                "readiness": {
                    "kind": "COMMAND",
                    "command": self._command(["python3", "qa/check_worker.py"]),
                },
            }
        ]
        extended["external_dependencies"] = [
            {
                "id": "EXTERNAL-001",
                "disposition": "STUBBED",
                "reason": "exercise email boundary without live delivery",
                "decision_ids": ["DEC-001"],
                "assertion": "one captured message and no live delivery",
                "interface": {
                    "protocol": "smtp",
                    "endpoint": "127.0.0.1:1025",
                    "classification": "LOOPBACK",
                },
                "readiness": {
                    "kind": "COMMAND",
                    "command": self._command(["python3", "qa/check_email_stub.py"]),
                },
                "artifact_path": "artifacts/QA-001.json",
            }
        ]
        extended["journeys"][0]["external_dependency_ids"] = ["EXTERNAL-001"]  # type: ignore[index]
        extended["journeys"][0]["supporting_service_ids"] = ["SERVICE-005"]  # type: ignore[index]
        extended["contract_sha256"] = full_stack_qa_contract_sha256(extended)
        records = copy.deepcopy(self.records)
        records["ART-001"]["locator"]["anchor"] = extended["contract_sha256"]  # type: ignore[index]

        self.assertEqual(validate_schema_file(extended, PLAN_SCHEMA), [])
        self.assertEqual(self._issues(extended, records=records), [])

        missing_readiness = copy.deepcopy(extended)
        del missing_readiness["external_dependencies"][0]["readiness"]  # type: ignore[index]
        self.assertNotEqual(validate_schema_file(missing_readiness, PLAN_SCHEMA), [])

        production_endpoint = copy.deepcopy(extended)
        production_endpoint["external_dependencies"][0]["interface"] = {  # type: ignore[index]
            "protocol": "https",
            "endpoint": "https://production.example/api",
            "classification": "LOOPBACK",
        }
        production_endpoint["contract_sha256"] = full_stack_qa_contract_sha256(
            production_endpoint
        )
        self.assertIn(
            "QA_EXTERNAL_INTERFACE_INVALID",
            self._issues(production_endpoint, records=records),
        )

        authorized_sandbox = copy.deepcopy(extended)
        authorized_sandbox["environment"]["allowed_origins"].append(  # type: ignore[index]
            {
                "url": "https://sandbox.example.test",
                "classification": "AUTHORIZED_SANDBOX",
                "decision_ids": ["DEC-001"],
            }
        )
        authorized_sandbox["external_dependencies"][0]["interface"] = {  # type: ignore[index]
            "protocol": "https",
            "endpoint": "https://sandbox.example.test/api/messages",
            "classification": "AUTHORIZED_SANDBOX",
        }
        authorized_sandbox["contract_sha256"] = full_stack_qa_contract_sha256(
            authorized_sandbox
        )
        records["ART-001"]["locator"]["anchor"] = authorized_sandbox[  # type: ignore[index]
            "contract_sha256"
        ]
        self.assertEqual(validate_schema_file(authorized_sandbox, PLAN_SCHEMA), [])
        self.assertEqual(self._issues(authorized_sandbox, records=records), [])

        encoded_secret = copy.deepcopy(authorized_sandbox)
        encoded_secret["external_dependencies"][0]["interface"]["endpoint"] = (  # type: ignore[index]
            "https://sandbox.example.test/api/messages?to%6ben=abc123"
        )
        encoded_secret["contract_sha256"] = full_stack_qa_contract_sha256(
            encoded_secret
        )
        records["ART-001"]["locator"]["anchor"] = encoded_secret["contract_sha256"]  # type: ignore[index]
        self.assertIn(
            "QA_EXTERNAL_INTERFACE_INVALID",
            self._issues(encoded_secret, records=records),
        )

    def test_ready_contract_resolves_files_hashes_trace_and_gate(self) -> None:
        self.assertEqual(self._issues(), [])

        stale = copy.deepcopy(self.plan)
        stale["ci"]["workflow_sha256"] = "f" * 64  # type: ignore[index]
        stale["contract_sha256"] = full_stack_qa_contract_sha256(stale)
        self.assertIn("QA_ARTIFACT_HASH_MISMATCH", self._issues(stale))

        mismatched_records = copy.deepcopy(self.records)
        mismatched_records["GATE-001"]["attributes"]["argv"] = ["python3", "qa/other.py"]  # type: ignore[index]
        self.assertIn("QA_GATE_CONTRACT_MISMATCH", self._issues(records=mismatched_records))

        missing_trace = copy.deepcopy(self.records)
        missing_trace["TEST-001"]["links"]["gates"] = []  # type: ignore[index]
        self.assertIn("QA_TRACE_INVALID", self._issues(records=missing_trace))

        missing_oracle_link = copy.deepcopy(self.records)
        missing_oracle_link["GATE-001"]["links"]["oracles"] = ["ART-001"]  # type: ignore[index]
        self.assertIn("QA_GATE_CONTRACT_MISMATCH", self._issues(records=missing_oracle_link))

        mismatched_blocked_exit = copy.deepcopy(self.records)
        mismatched_blocked_exit["GATE-001"]["attributes"]["blocked_exit_codes"] = []  # type: ignore[index]
        self.assertIn(
            "QA_GATE_CONTRACT_MISMATCH",
            self._issues(records=mismatched_blocked_exit),
        )

        mismatched_fresh_artifact = copy.deepcopy(self.records)
        mismatched_fresh_artifact["GATE-001"]["attributes"]["fresh_artifact_paths"] = []  # type: ignore[index]
        self.assertIn(
            "QA_GATE_CONTRACT_MISMATCH",
            self._issues(records=mismatched_fresh_artifact),
        )

        no_independent_oracle = copy.deepcopy(self.plan)
        no_independent_oracle["journeys"][0]["oracle_ids"] = ["ART-001"]  # type: ignore[index]
        no_independent_oracle["contract_sha256"] = full_stack_qa_contract_sha256(no_independent_oracle)
        self.assertIn("QA_ORACLE_INDEPENDENT_MISSING", self._issues(no_independent_oracle))

        unbound_independent_oracle = copy.deepcopy(self.records)
        unbound_independent_oracle["E-001"]["links"]["requirements"] = []  # type: ignore[index]
        self.assertIn(
            "QA_TRACE_INVALID",
            self._issues(records=unbound_independent_oracle),
        )

    def test_ready_contract_rejects_undeclared_origin_and_downloader_shim(self) -> None:
        undeclared_origin = copy.deepcopy(self.plan)
        undeclared_origin["owned_stack"]["backend"]["readiness"]["target"] = (  # type: ignore[index]
            "https://production.example/health"
        )
        undeclared_origin["contract_sha256"] = full_stack_qa_contract_sha256(undeclared_origin)
        self.assertIn("QA_ORIGIN_UNAUTHORIZED", self._issues(undeclared_origin))

        downloader = copy.deepcopy(self.plan)
        downloader["playwright"]["driver_argv"] = ["npm", "exec", "playwright", "test"]  # type: ignore[index]
        downloader["contract_sha256"] = full_stack_qa_contract_sha256(downloader)
        self.assertIn("QA_INSTALLER_SHIM_FORBIDDEN", self._issues(downloader))

        no_pull_request = copy.deepcopy(self.plan)
        no_pull_request["ci"]["triggers"] = ["schedule"]  # type: ignore[index]
        no_pull_request["contract_sha256"] = full_stack_qa_contract_sha256(no_pull_request)
        self.assertIn("QA_CI_TRIGGER_INVALID", self._issues(no_pull_request))

        undeclared_result = copy.deepcopy(self.plan)
        undeclared_result["ci"]["result_path"] = "artifacts/not-declared.json"  # type: ignore[index]
        undeclared_result["contract_sha256"] = full_stack_qa_contract_sha256(undeclared_result)
        self.assertIn("QA_RESULT_UNDECLARED", self._issues(undeclared_result))

        credentialed_origin = copy.deepcopy(self.plan)
        credentialed_origin["environment"]["allowed_origins"][0]["url"] = (  # type: ignore[index]
            "http://user:password@127.0.0.1:3000"
        )
        credentialed_origin["contract_sha256"] = full_stack_qa_contract_sha256(
            credentialed_origin
        )
        self.assertIn("QA_ORIGIN_INVALID", self._issues(credentialed_origin))

    def test_contract_digest_detects_unrehased_plan_change(self) -> None:
        stale = copy.deepcopy(self.plan)
        stale["journeys"][0]["fixture"] = "different fixture"  # type: ignore[index]
        self.assertIn("QA_CONTRACT_HASH_MISMATCH", self._issues(stale))

    def test_ready_contract_rejects_unresolved_template_markers(self) -> None:
        unresolved = copy.deepcopy(self.plan)
        unresolved["journeys"][0]["fixture"] = "[[REQUIRED: exact fixture]]"  # type: ignore[index]
        unresolved["contract_sha256"] = full_stack_qa_contract_sha256(unresolved)
        records = copy.deepcopy(self.records)
        records["ART-001"]["locator"]["anchor"] = unresolved["contract_sha256"]  # type: ignore[index]

        self.assertIn(
            "QA_MARKER_UNRESOLVED",
            self._issues(unresolved, records=records),
        )

    def test_ready_contract_requires_structural_identity_binding(self) -> None:
        missing_placeholder = copy.deepcopy(self.plan)
        missing_placeholder["journeys"][0]["service"]["probe"] = "GET /api/orders/latest"  # type: ignore[index]
        missing_placeholder["contract_sha256"] = full_stack_qa_contract_sha256(
            missing_placeholder
        )
        records = copy.deepcopy(self.records)
        records["ART-001"]["locator"]["anchor"] = missing_placeholder["contract_sha256"]  # type: ignore[index]

        self.assertIn(
            "QA_IDENTITY_BINDING_INVALID",
            self._issues(missing_placeholder, records=records),
        )

        incomplete = copy.deepcopy(self.plan)
        incomplete["journeys"][0]["identity_bindings"][0]["consumers"] = [  # type: ignore[index]
            incomplete["journeys"][0]["identity_bindings"][0]["consumers"][0]  # type: ignore[index]
        ]
        incomplete["contract_sha256"] = full_stack_qa_contract_sha256(incomplete)
        records["ART-001"]["locator"]["anchor"] = incomplete["contract_sha256"]  # type: ignore[index]

        self.assertIn(
            "QA_IDENTITY_BINDING_INCOMPLETE",
            self._issues(incomplete, records=records),
        )

        out_of_order = copy.deepcopy(self.plan)
        out_of_order["journeys"][0]["identity_bindings"][0]["source"][  # type: ignore[index]
            "exchange_trigger"
        ] = "reload-order"
        out_of_order["contract_sha256"] = full_stack_qa_contract_sha256(out_of_order)
        records["ART-001"]["locator"]["anchor"] = out_of_order["contract_sha256"]  # type: ignore[index]
        self.assertIn(
            "QA_IDENTITY_BINDING_INVALID",
            self._issues(out_of_order, records=records),
        )

        unrelated_globals = copy.deepcopy(self.plan)
        unrelated_globals["owned_stack"]["supporting_services"] = [  # type: ignore[index]
            {
                "service_id": "SERVICE-005",
                "role": "worker",
                "implementation": "REAL",
                "readiness": {
                    "kind": "COMMAND",
                    "command": self._command(["python3", "qa/check_worker.py"]),
                },
                "assertion": "worker processed order {captured_order_id}",
                "artifact_path": "artifacts/QA-001.json",
            }
        ]
        unrelated_globals["external_dependencies"] = [
            {
                "id": "EXTERNAL-001",
                "disposition": "STUBBED",
                "reason": "test-only email boundary",
                "decision_ids": ["DEC-001"],
                "assertion": "email captured for order {captured_order_id}",
                "interface": {
                    "protocol": "smtp",
                    "endpoint": "127.0.0.1:1025",
                    "classification": "LOOPBACK",
                },
                "readiness": {
                    "kind": "COMMAND",
                    "command": self._command(["python3", "qa/check_email_stub.py"]),
                },
                "artifact_path": "artifacts/QA-001.json",
            }
        ]
        unrelated_globals["journeys"][0]["identity_bindings"][0]["consumers"].extend(  # type: ignore[index]
            [
                {
                    "kind": "SUPPORTING_SERVICE",
                    "contract_pointer": "/owned_stack/supporting_services/0/assertion",
                },
                {
                    "kind": "EXTERNAL_DEPENDENCY",
                    "contract_pointer": "/external_dependencies/0/assertion",
                },
            ]
        )
        unrelated_globals["contract_sha256"] = full_stack_qa_contract_sha256(
            unrelated_globals
        )
        records["ART-001"]["locator"]["anchor"] = unrelated_globals[  # type: ignore[index]
            "contract_sha256"
        ]
        self.assertGreaterEqual(
            self._issues(unrelated_globals, records=records).count(
                "QA_IDENTITY_BINDING_INVALID"
            ),
            2,
        )

    def test_verified_contract_requires_current_pass_run_for_each_gate(self) -> None:
        self.assertIn("QA_RUN_MISSING", self._issues(verified=True))

        records = copy.deepcopy(self.records)
        records["RUN-001"] = self._record(
            "RUN-001",
            "RUN",
            links={
                "requirements": ["REQ-001"],
                "acceptance": ["AC-001"],
                "tests": ["TEST-001"],
                "gates": ["GATE-001"],
                "oracles": ["ART-001", "E-001"],
            },
            attributes={"result": "PASS", "gate_id": "GATE-001", "environment_id": "ENV-001"},
            state="PASS",
        )
        records["GATE-001"]["links"]["runs"] = ["RUN-001"]  # type: ignore[index]
        self.assertIn("QA_RESULT_MISSING", self._issues(verified=True, records=records))
        self._attach_result(records, "RUN-001")
        self.assertEqual(self._issues(verified=True, records=records), [])

        records["RUN-002"] = self._record(
            "RUN-002",
            "RUN",
            links={
                "requirements": ["REQ-001"],
                "acceptance": ["AC-001"],
                "tests": ["TEST-001"],
                "gates": ["GATE-001"],
                "oracles": ["ART-001", "E-001"],
            },
            attributes={"result": "FAIL", "gate_id": "GATE-001", "environment_id": "ENV-001"},
            state="FAIL",
        )
        records["GATE-001"]["links"]["runs"] = ["RUN-001", "RUN-002"]  # type: ignore[index]
        self.assertIn("QA_RUN_NOT_PASS", self._issues(verified=True, records=records))

    def test_verified_contract_rejects_dimension_result_mismatch(self) -> None:
        records = copy.deepcopy(self.records)
        records["RUN-001"] = self._record(
            "RUN-001",
            "RUN",
            links={
                "requirements": ["REQ-001"],
                "acceptance": ["AC-001"],
                "tests": ["TEST-001"],
                "gates": ["GATE-001"],
                "oracles": ["ART-001", "E-001"],
            },
            attributes={"result": "PASS", "gate_id": "GATE-001", "environment_id": "ENV-001"},
            state="PASS",
        )
        records["GATE-001"]["links"]["runs"] = ["RUN-001"]  # type: ignore[index]
        self._attach_result(records, "RUN-001")
        retained = self.pack / records["RUN-001"]["artifacts"][0]["path"]  # type: ignore[index,operator]
        result = json.loads(retained.read_text(encoding="utf-8"))
        result["journeys"][0]["persistence"]["status"] = "FAIL"
        retained.write_text(json.dumps(result, sort_keys=True) + "\n", encoding="utf-8")
        records["RUN-001"]["artifacts"][0]["size"] = retained.stat().st_size  # type: ignore[index]
        records["RUN-001"]["artifacts"][0]["sha256"] = sha256(retained)  # type: ignore[index]
        self.assertIn("QA_RESULT_NOT_PASS", self._issues(verified=True, records=records))

        result["journeys"][0]["persistence"]["status"] = "PASS"
        result["journeys"][0]["wire"]["additional_exchanges"][0]["observed_status"] = 404
        retained.write_text(json.dumps(result, sort_keys=True) + "\n", encoding="utf-8")
        records["RUN-001"]["artifacts"][0]["size"] = retained.stat().st_size  # type: ignore[index]
        records["RUN-001"]["artifacts"][0]["sha256"] = sha256(retained)  # type: ignore[index]
        self.assertIn("QA_RESULT_CONTRACT_MISMATCH", self._issues(verified=True, records=records))

        result["journeys"][0]["wire"]["additional_exchanges"][0]["observed_status"] = 200
        result["playwright_project"] = "wrong-project"
        retained.write_text(json.dumps(result, sort_keys=True) + "\n", encoding="utf-8")
        records["RUN-001"]["artifacts"][0]["size"] = retained.stat().st_size  # type: ignore[index]
        records["RUN-001"]["artifacts"][0]["sha256"] = sha256(retained)  # type: ignore[index]
        self.assertIn("QA_RESULT_CONTRACT_MISMATCH", self._issues(verified=True, records=records))

    def test_verified_contract_rejects_identity_binding_hash_mismatch(self) -> None:
        records = copy.deepcopy(self.records)
        records["RUN-001"] = self._record(
            "RUN-001",
            "RUN",
            links={
                "requirements": ["REQ-001"],
                "acceptance": ["AC-001"],
                "tests": ["TEST-001"],
                "gates": ["GATE-001"],
                "oracles": ["ART-001", "E-001"],
            },
            attributes={"result": "PASS", "gate_id": "GATE-001", "environment_id": "ENV-001"},
            state="PASS",
        )
        records["GATE-001"]["links"]["runs"] = ["RUN-001"]  # type: ignore[index]
        result = self._result()
        result["journeys"][0]["identity_bindings"][0]["consumers"][1][  # type: ignore[index]
            "observed_value_sha256"
        ] = "b" * 64
        self._attach_result(records, "RUN-001", result)

        self.assertIn(
            "QA_RESULT_CONTRACT_MISMATCH",
            self._issues(verified=True, records=records),
        )

        retained = self.pack / records["RUN-001"]["artifacts"][0]["path"]  # type: ignore[index,operator]
        wrong_path = self._result()
        wrong_path["journeys"][0]["wire"]["additional_exchanges"][0][  # type: ignore[index]
            "observed_path"
        ] = "/api/orders/order-999"
        retained.write_text(json.dumps(wrong_path, sort_keys=True) + "\n", encoding="utf-8")
        records["RUN-001"]["artifacts"][0]["size"] = retained.stat().st_size  # type: ignore[index]
        records["RUN-001"]["artifacts"][0]["sha256"] = sha256(retained)  # type: ignore[index]
        self.assertIn(
            "QA_RESULT_CONTRACT_MISMATCH",
            self._issues(verified=True, records=records),
        )

    def test_record_run_retains_declared_artifact_source_path(self) -> None:
        pack = initialize_v2(
            skill_root=ROOT,
            product_name="QA Run Fixture",
            product_type="web-app-saas",
            playbooks=[],
            source_description="authorized local fixture",
            repo_root=self.repository,
            output_dir=Path("runtime-pack"),
            timestamp="2026-07-19T12:00:00+00:00",
        )
        manifest_path = pack / "clone_pack.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["reference_baseline_id"] = "BASE-001"
        manifest["repository_state"] = {
            "kind": "working-tree",
            "revision": "qa-revision-001",
            "diff_sha256": "a" * 64,
        }
        manifest_path.write_text(json.dumps(manifest, sort_keys=True) + "\n", encoding="utf-8")
        index_path = pack / "clone_index.json"
        index = json.loads(index_path.read_text(encoding="utf-8"))
        records = copy.deepcopy(self.records)
        records["GATE-001"]["attributes"]["argv"] = [sys.executable, "qa/run.py"]  # type: ignore[index]
        index["records"] = list(records.values())
        index_path.write_text(json.dumps(index, sort_keys=True) + "\n", encoding="utf-8")
        emitted = self.repository / "artifacts" / "QA-001.json"
        emitted.write_text(json.dumps(self._result()) + "\n", encoding="utf-8")

        run, exit_code = record_run(pack, "GATE-001", "ENV-001", "2026-07-19T12:01:00+00:00")

        self.assertEqual(exit_code, 0)
        retained = [item for item in run["artifacts"] if item.get("source_path")]
        self.assertEqual([item["source_path"] for item in retained], ["artifacts/QA-001.json"])

    def test_record_run_preserves_declared_preflight_block_as_exit_seven(self) -> None:
        pack = initialize_v2(
            skill_root=ROOT,
            product_name="QA Block Fixture",
            product_type="web-app-saas",
            playbooks=[],
            source_description="authorized local fixture",
            repo_root=self.repository,
            output_dir=Path("blocked-runtime-pack"),
            timestamp="2026-07-19T12:00:00+00:00",
        )
        manifest_path = pack / "clone_pack.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["reference_baseline_id"] = "BASE-001"
        manifest["repository_state"] = {
            "kind": "working-tree",
            "revision": "qa-revision-001",
            "diff_sha256": "a" * 64,
        }
        manifest_path.write_text(json.dumps(manifest, sort_keys=True) + "\n", encoding="utf-8")
        index_path = pack / "clone_index.json"
        index = json.loads(index_path.read_text(encoding="utf-8"))
        records = copy.deepcopy(self.records)
        records["GATE-001"]["attributes"]["argv"] = [sys.executable, "qa/block.py"]  # type: ignore[index]
        records["GATE-001"]["attributes"]["blocked_exit_codes"] = [7]  # type: ignore[index]
        index["records"] = list(records.values())
        index_path.write_text(json.dumps(index, sort_keys=True) + "\n", encoding="utf-8")

        run, exit_code = record_run(
            pack,
            "GATE-001",
            "ENV-001",
            "2026-07-19T12:01:00+00:00",
        )

        self.assertEqual(exit_code, 7)
        self.assertEqual(run["result"], "BLOCKED")
        self.assertEqual(run["observed_exit"], 7)
        self.assertEqual(run["diagnostic"]["code"], "RUN_DECLARED_BLOCK")

    def test_record_run_rejects_a_stale_required_artifact(self) -> None:
        pack = initialize_v2(
            skill_root=ROOT,
            product_name="QA Stale Artifact Fixture",
            product_type="web-app-saas",
            playbooks=[],
            source_description="authorized local fixture",
            repo_root=self.repository,
            output_dir=Path("stale-runtime-pack"),
            timestamp="2026-07-19T12:00:00+00:00",
        )
        manifest_path = pack / "clone_pack.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["reference_baseline_id"] = "BASE-001"
        manifest["repository_state"] = {
            "kind": "working-tree",
            "revision": "qa-revision-001",
            "diff_sha256": "a" * 64,
        }
        manifest_path.write_text(json.dumps(manifest, sort_keys=True) + "\n", encoding="utf-8")
        index_path = pack / "clone_index.json"
        index = json.loads(index_path.read_text(encoding="utf-8"))
        records = copy.deepcopy(self.records)
        records["GATE-001"]["attributes"]["argv"] = [sys.executable, "qa/noop.py"]  # type: ignore[index]
        index["records"] = list(records.values())
        index_path.write_text(json.dumps(index, sort_keys=True) + "\n", encoding="utf-8")
        emitted = self.repository / "artifacts" / "QA-001.json"
        emitted.write_text(json.dumps(self._result()) + "\n", encoding="utf-8")

        with self.assertRaises(ClonePackError) as raised:
            record_run(
                pack,
                "GATE-001",
                "ENV-001",
                "2026-07-19T12:01:00+00:00",
            )

        self.assertEqual(raised.exception.diagnostic, "RUN_ARTIFACT_STALE")
        self.assertEqual(raised.exception.exit_code, 4)

    def test_duplicate_journey_identity_is_rejected(self) -> None:
        duplicate = copy.deepcopy(self.plan)
        duplicate["journeys"].append(copy.deepcopy(duplicate["journeys"][0]))  # type: ignore[union-attr,index]
        duplicate["contract_sha256"] = full_stack_qa_contract_sha256(duplicate)
        self.assertIn("QA_JOURNEY_DUPLICATE", self._issues(duplicate))

    def test_duplicate_wire_trigger_is_rejected(self) -> None:
        duplicate = copy.deepcopy(self.plan)
        duplicate["journeys"][0]["wire"]["additional_exchanges"][0]["trigger"] = (  # type: ignore[index]
            "submit-order"
        )
        duplicate["contract_sha256"] = full_stack_qa_contract_sha256(duplicate)

        self.assertIn("QA_WIRE_TRIGGER_DUPLICATE", self._issues(duplicate))

    def test_verified_contract_binds_external_and_supporting_results(self) -> None:
        plan = copy.deepcopy(self.plan)
        plan["owned_stack"]["supporting_services"] = [  # type: ignore[index]
            {
                "service_id": "SERVICE-005",
                "role": "worker",
                "implementation": "REAL",
                "readiness": {
                    "kind": "COMMAND",
                    "command": self._command(["python3", "qa/check_worker.py"]),
                },
                "assertion": "worker processes the captured order exactly once",
                "artifact_path": "artifacts/QA-001.json",
            }
        ]
        plan["external_dependencies"] = [
            {
                "id": "EXTERNAL-001",
                "disposition": "STUBBED",
                "reason": "exercise email boundary without live delivery",
                "decision_ids": ["DEC-001"],
                "assertion": "one captured message and no live delivery",
                "interface": {
                    "protocol": "smtp",
                    "endpoint": "127.0.0.1:1025",
                    "classification": "LOOPBACK",
                },
                "readiness": {
                    "kind": "COMMAND",
                    "command": self._command(["python3", "qa/check_email_stub.py"]),
                },
                "artifact_path": "artifacts/QA-001.json",
            }
        ]
        plan["journeys"][0]["external_dependency_ids"] = ["EXTERNAL-001"]  # type: ignore[index]
        plan["journeys"][0]["supporting_service_ids"] = ["SERVICE-005"]  # type: ignore[index]
        plan["contract_sha256"] = full_stack_qa_contract_sha256(plan)
        records = copy.deepcopy(self.records)
        records["ART-001"]["locator"]["anchor"] = plan["contract_sha256"]  # type: ignore[index]
        records["RUN-001"] = self._record(
            "RUN-001",
            "RUN",
            links={
                "requirements": ["REQ-001"],
                "acceptance": ["AC-001"],
                "tests": ["TEST-001"],
                "gates": ["GATE-001"],
                "oracles": ["ART-001", "E-001"],
            },
            attributes={"result": "PASS", "gate_id": "GATE-001", "environment_id": "ENV-001"},
            state="PASS",
        )
        records["GATE-001"]["links"]["runs"] = ["RUN-001"]  # type: ignore[index]
        result = self._result()
        result["plan_contract_sha256"] = plan["contract_sha256"]
        result["external_dependencies"] = [
            {
                "id": "EXTERNAL-001",
                "disposition": "STUBBED",
                "status": "PASS",
                "assertion": "one captured message and no live delivery",
                "interface": {
                    "protocol": "smtp",
                    "endpoint": "127.0.0.1:1025",
                    "classification": "LOOPBACK",
                },
                "observation": "one message captured and live delivery disabled",
            }
        ]
        result["supporting_services"] = [
            {
                "service_id": "SERVICE-005",
                "role": "worker",
                "status": "PASS",
                "assertion": "worker processes the captured order exactly once",
                "observation": "captured order processed once",
            }
        ]
        self._attach_result(records, "RUN-001", result)

        self.assertEqual(self._issues(plan, verified=True, records=records), [])

        retained = self.pack / records["RUN-001"]["artifacts"][0]["path"]  # type: ignore[index,operator]
        result["external_dependencies"][0]["status"] = "FAIL"  # type: ignore[index]
        retained.write_text(json.dumps(result, sort_keys=True) + "\n", encoding="utf-8")
        records["RUN-001"]["artifacts"][0]["size"] = retained.stat().st_size  # type: ignore[index]
        records["RUN-001"]["artifacts"][0]["sha256"] = sha256(retained)  # type: ignore[index]
        self.assertIn(
            "QA_RESULT_NOT_PASS",
            self._issues(plan, verified=True, records=records),
        )

        result["external_dependencies"][0]["status"] = "PASS"  # type: ignore[index]
        result["external_dependencies"][0]["interface"]["endpoint"] = "127.0.0.1:2025"  # type: ignore[index]
        retained.write_text(json.dumps(result, sort_keys=True) + "\n", encoding="utf-8")
        records["RUN-001"]["artifacts"][0]["size"] = retained.stat().st_size  # type: ignore[index]
        records["RUN-001"]["artifacts"][0]["sha256"] = sha256(retained)  # type: ignore[index]
        self.assertIn(
            "QA_RESULT_CONTRACT_MISMATCH",
            self._issues(plan, verified=True, records=records),
        )

        result["external_dependencies"][0]["interface"]["endpoint"] = "127.0.0.1:1025"  # type: ignore[index]
        result["supporting_services"][0]["status"] = "FAIL"  # type: ignore[index]
        retained.write_text(json.dumps(result, sort_keys=True) + "\n", encoding="utf-8")
        records["RUN-001"]["artifacts"][0]["size"] = retained.stat().st_size  # type: ignore[index]
        records["RUN-001"]["artifacts"][0]["sha256"] = sha256(retained)  # type: ignore[index]
        self.assertIn(
            "QA_RESULT_NOT_PASS",
            self._issues(plan, verified=True, records=records),
        )

    def test_semantic_validator_never_crashes_on_schema_invalid_collections(self) -> None:
        malformed = copy.deepcopy(self.plan)
        malformed["environment"]["allowed_origins"] = None  # type: ignore[index]
        malformed["external_dependencies"] = None
        malformed["playwright"]["driver_argv"] = [1]  # type: ignore[index]
        malformed["ci"]["triggers"] = None  # type: ignore[index]
        malformed["journeys"] = None
        malformed["contract_sha256"] = full_stack_qa_contract_sha256(malformed)

        self.assertIsInstance(self._issues(malformed), list)

        malformed_binding = copy.deepcopy(self.plan)
        malformed_binding["journeys"][0]["identity_bindings"][0]["source"][  # type: ignore[index]
            "exchange_trigger"
        ] = []
        malformed_binding["journeys"][0]["identity_bindings"][0]["consumers"][0][  # type: ignore[index]
            "contract_pointer"
        ] = []
        malformed_binding["contract_sha256"] = full_stack_qa_contract_sha256(
            malformed_binding
        )
        self.assertIsInstance(self._issues(malformed_binding), list)

    def test_manifest_schema_and_scaffold_accept_optional_canonical_plan(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            repository = Path(temporary)
            pack = initialize_v2(
                skill_root=ROOT,
                product_name="QA Fixture",
                product_type="web-app-saas",
                playbooks=[],
                source_description="authorized local fixture",
                repo_root=repository,
                output_dir=Path("docs/clone"),
                timestamp="2026-07-19T12:00:00+00:00",
            )
            manifest_path = pack / "clone_pack.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["plans"]["full_stack_qa"] = "full_stack_qa_plan.json"
            manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
            (pack / "full_stack_qa_plan.json").write_text(
                json.dumps({"pack_id": manifest["pack_id"], "pack_revision": 1}) + "\n",
                encoding="utf-8",
            )

            self.assertEqual(validate_schema_file(manifest, MANIFEST_SCHEMA), [])
            diagnostics = validate_v2(pack, "scaffold").sorted_all()
            self.assertNotIn("PLAN_MANIFEST_INVALID", [item.code for item in diagnostics])

    def test_legacy_manifest_without_optional_plan_remains_valid(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            repository = Path(temporary)
            pack = initialize_v2(
                skill_root=ROOT,
                product_name="Legacy Fixture",
                product_type="website",
                playbooks=[],
                source_description="authorized local fixture",
                repo_root=repository,
                output_dir=Path("docs/clone"),
                timestamp="2026-07-19T12:00:00+00:00",
            )
            diagnostics = validate_v2(pack, "scaffold").sorted_all()
            self.assertNotIn("PLAN_MANIFEST_INVALID", [item.code for item in diagnostics])

    def test_build_ready_routes_optional_plan_errors_and_holds(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            repository = Path(temporary)
            pack = initialize_v2(
                skill_root=ROOT,
                product_name="QA Profile Fixture",
                product_type="web-app-saas",
                playbooks=[],
                source_description="authorized local fixture",
                repo_root=repository,
                output_dir=Path("docs/clone"),
                timestamp="2026-07-19T12:00:00+00:00",
            )
            manifest_path = pack / "clone_pack.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["plans"]["full_stack_qa"] = "full_stack_qa_plan.json"
            manifest_path.write_text(json.dumps(manifest, sort_keys=True) + "\n", encoding="utf-8")
            (pack / "full_stack_qa_plan.json").write_text(
                json.dumps({"pack_id": manifest["pack_id"], "pack_revision": 1}) + "\n",
                encoding="utf-8",
            )
            injected = [
                FullStackQaIssue("full_stack_qa_plan.json", "QA_READY_TEST", "ready failure"),
                FullStackQaIssue(
                    "full_stack_qa_plan.json",
                    "QA_HOLD_TEST",
                    "verified hold",
                    hold=True,
                ),
            ]

            with mock.patch(
                "scripts.clonepack.pack.validate_full_stack_qa_plan",
                return_value=injected,
            ) as validator:
                diagnostics = validate_v2(pack, "build-ready")

            validator.assert_called_once()
            self.assertTrue(validator.call_args.kwargs["require_ready"])
            self.assertFalse(validator.call_args.kwargs["require_verified"])
            self.assertIn("QA_READY_TEST", {item.code for item in diagnostics.diagnostics})
            self.assertIn("QA_HOLD_TEST", {item.code for item in diagnostics.hold_reasons})

            with mock.patch(
                "scripts.clonepack.pack.validate_full_stack_qa_plan",
                return_value=[],
            ) as planning_validator:
                validate_v2(pack, "gap-plan")

            planning_validator.assert_called_once()
            self.assertFalse(planning_validator.call_args.kwargs["require_verified"])

            with mock.patch(
                "scripts.clonepack.pack.validate_full_stack_qa_plan",
                return_value=[],
            ) as later_validator:
                validate_v2(pack, "gap-closure")

            later_validator.assert_called_once()
            self.assertTrue(later_validator.call_args.kwargs["require_verified"])


if __name__ == "__main__":
    unittest.main()
