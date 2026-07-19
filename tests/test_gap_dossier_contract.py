from __future__ import annotations

import copy
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from typing import Any

from scripts.clonepack.dossier import validate_gap_plan_record
from tests.test_v2_regression import PINNED_TIMESTAMP, read_json, run_cli, write_json


def record(identifier: str, kind: str) -> dict[str, Any]:
    return {
        "id": identifier,
        "kind": kind,
        "locator": {"path": "definitions.md", "anchor": identifier, "sha256": "0" * 64},
        "links": {},
        "applicability": "MVP",
        "state": "READY",
        "attributes": {},
    }


class GapDossierContractTests(unittest.TestCase):
    maxDiff = None

    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.pack = Path(temporary.name) / "pack"
        self.repository = Path(temporary.name) / "repository"
        (self.pack / "evidence").mkdir(parents=True)
        (self.repository / "src").mkdir(parents=True)
        (self.repository / "tests").mkdir(parents=True)
        (self.pack / "evidence" / "reference.txt").write_text("reference observation\n", encoding="utf-8")
        (self.repository / "src" / "app.py").write_text("def target():\n    return 'old'\n", encoding="utf-8")
        self.manifest = {"repository_root": str(self.repository)}
        kinds = {
            "E-001": "E",
            "E-002": "E",
            "REQ-GAP-001-01": "REQ",
            "ACT-001": "ACT",
            "WF-001": "WF",
            "CHANGE-GAP-001-01": "CHANGE",
            "CHANGE-GAP-001-02": "CHANGE",
            "CHANGE-GAP-001-03": "CHANGE",
            "STEP-GAP-001-01": "STEP",
            "ART-001": "ART",
            "TEST-GAP-001-01": "TEST",
            "GATE-001": "GATE",
            "AC-GAP-001-01": "AC",
            "GAPDEC-001": "GAPDEC",
            "GAPDEC-002": "GAPDEC",
            "HALT-001": "HALT",
            "GAP-001": "GAP",
        }
        self.records = {identifier: record(identifier, kind) for identifier, kind in kinds.items()}
        for identifier in ("E-001", "E-002", "REQ-GAP-001-01", "ACT-001", "WF-001", "ART-001", "AC-GAP-001-01", "GAPDEC-001", "GAPDEC-002", "HALT-001"):
            self.records[identifier]["links"] = {"gaps": ["GAP-001"]}
        for identifier in ("CHANGE-GAP-001-01", "CHANGE-GAP-001-02", "CHANGE-GAP-001-03"):
            self.records[identifier]["links"] = {
                "gaps": ["GAP-001"],
                "requirements": ["REQ-GAP-001-01"],
            }
        self.records["STEP-GAP-001-01"]["links"] = {
            "gaps": ["GAP-001"],
            "changes": ["CHANGE-GAP-001-01", "CHANGE-GAP-001-02", "CHANGE-GAP-001-03"],
        }
        self.records["ART-001"]["links"]["evidence"] = ["E-001"]
        self.records["TEST-GAP-001-01"]["links"] = {
            "gaps": ["GAP-001"],
            "requirements": ["REQ-GAP-001-01"],
            "acceptance": ["AC-GAP-001-01"],
            "artifacts": ["ART-001"],
            "gates": ["GATE-001"],
        }
        self.records["GATE-001"]["links"] = {
            "gaps": ["GAP-001"],
            "requirements": ["REQ-GAP-001-01"],
            "acceptance": ["AC-GAP-001-01"],
            "tests": ["TEST-GAP-001-01"],
        }
        self.dossier = {
            "schema_version": "clone-gap-dossier/v2",
            "gap_id": "GAP-001",
            "source_ids": ["E-001", "REQ-GAP-001-01"],
            "current_behavior": {
                "reference": {
                    "preconditions": "Authorized local fixture with empty state",
                    "observable": "The command emits one deterministic JSON object",
                    "state_effects": "The reference fixture remains unchanged",
                    "errors": "No error occurs for this input",
                    "locators": [
                        {
                            "scope": "pack",
                            "path": "evidence/reference.txt",
                            "symbol": None,
                            "evidence_ids": ["E-001"],
                            "existence": "existing",
                        }
                    ],
                },
                "clone": {
                    "preconditions": "Local clone repository at the pinned revision",
                    "observable": "The existing function returns the old value",
                    "state_effects": "No persisted state changes",
                    "errors": "No error occurs for this input",
                    "locators": [
                        {
                            "scope": "repository",
                            "path": "src/app.py",
                            "symbol": "def target():",
                            "evidence_ids": ["E-002"],
                            "existence": "existing",
                        }
                    ],
                },
            },
            "target_behavior": {
                "preconditions": "Local clone repository at the pinned revision",
                "observable": "The function returns the exact reference value",
                "state_effects": "No persisted state changes",
                "errors": "Invalid inputs raise ValueError with exact arguments",
                "prohibited_effects": "The implementation performs no network or filesystem writes",
            },
            "observable_delta": "The clone returns old while the reference returns new",
            "impact": {
                "actor_ids": ["ACT-001"],
                "workflow_ids": ["WF-001"],
                "priority": "P1",
                "effect": "The primary actor receives the wrong value",
                "reason_deferred": "The behavior is outside the pinned MVP slice",
            },
            "allowed_fence": {
                "paths": ["src", "tests"],
                "forbidden_paths": ["deployment"],
                "dirty_state_rule": "Preserve unrelated changes and halt on overlap",
            },
            "change_map": [
                {
                    "id": "CHANGE-GAP-001-01",
                    "order": 1,
                    "operation": "modify",
                    "path": "src/app.py",
                    "destination_path": None,
                    "symbol": "def target():",
                    "existence": "existing",
                    "contract": "Return the exact reference value for the governed input",
                    "requirement_ids": ["REQ-GAP-001-01"],
                },
                {
                    "id": "CHANGE-GAP-001-02",
                    "order": 2,
                    "operation": "create",
                    "path": "tests/test_app.py",
                    "destination_path": None,
                    "symbol": None,
                    "existence": "new",
                    "contract": "Add independent normal boundary negative and recovery assertions",
                    "requirement_ids": ["REQ-GAP-001-01"],
                },
                {
                    "id": "CHANGE-GAP-001-03",
                    "order": 3,
                    "operation": "create",
                    "path": "tests/fixtures/case.json",
                    "destination_path": None,
                    "symbol": None,
                    "existence": "new",
                    "contract": "Add one independently derived immutable fixture",
                    "requirement_ids": ["REQ-GAP-001-01"],
                },
            ],
            "contracts": {
                name: {"status": "APPLICABLE", "contract": f"Exact {name} contract"}
                for name in ("interface", "state", "data", "migration", "algorithm", "error", "security", "telemetry", "compatibility")
            },
            "steps": [
                {
                    "id": "STEP-GAP-001-01",
                    "order": 1,
                    "preconditions": "Pinned revision and clean allowed fence",
                    "action": "Add the fixture and failing test before changing the function",
                    "change_ids": ["CHANGE-GAP-001-01", "CHANGE-GAP-001-02", "CHANGE-GAP-001-03"],
                    "paths": ["src/app.py", "tests/test_app.py", "tests/fixtures/case.json"],
                    "expected_checkpoint": "The focused test fails for the governed value before the implementation edit",
                }
            ],
            "fixtures": [
                {
                    "id": "ART-001",
                    "path": "tests/fixtures/case.json",
                    "existence": "new",
                    "origin": "Hand-computed from E-001 without clone execution",
                    "evidence_ids": ["E-001"],
                }
            ],
            "tests": [
                {
                    "id": "TEST-GAP-001-01",
                    "path": "tests/test_app.py",
                    "existence": "new",
                    "fixture_ids": ["ART-001"],
                    "categories": ["normal", "boundary", "negative", "recovery"],
                    "cwd": ".",
                    "argv": ["python3", "-m", "unittest", "tests.test_app"],
                    "environment": {},
                    "timeout_seconds": 300,
                    "expected_exit": 0,
                    "expected_result": "Four named cases pass and no prohibited write occurs",
                }
            ],
            "test_dimensions": {
                name: {"status": "REQUIRED", "test_ids": ["TEST-GAP-001-01"]}
                for name in ("normal", "boundary", "negative", "recovery")
            }
            | {
                "authorization": {
                    "status": "NOT_APPLICABLE",
                    "decision_id": "GAPDEC-001",
                    "reason": "The function has no identity or privilege input",
                },
                "concurrency": {
                    "status": "NOT_APPLICABLE",
                    "decision_id": "GAPDEC-002",
                    "reason": "The pure function has no shared state",
                },
            },
            "gates": [
                {
                    "id": "GATE-001",
                    "cwd": ".",
                    "argv": ["python3", "-m", "unittest", "tests.test_app"],
                    "environment": {},
                    "timeout_seconds": 300,
                    "expected_exit": 0,
                    "expected_result": "All governed test cases pass",
                    "covered_ids": ["REQ-GAP-001-01", "AC-GAP-001-01", "TEST-GAP-001-01"],
                }
            ],
            "acceptance_ids": ["AC-GAP-001-01"],
            "rollout": {
                name: {"status": "APPLICABLE", "contract": f"Exact {name} procedure and proof"}
                for name in ("activation", "rollback", "recovery", "data_repair", "backward_compatibility")
            },
            "non_goals": ["No unrelated public interface changes"],
            "prohibited_shortcuts": ["Do not hard-code the fixture output"],
            "risks": [
                {
                    "risk": "The change alters invalid-input behavior",
                    "trigger": "A negative assertion differs",
                    "mitigation": "Retain the existing error branch and add an exact assertion",
                    "proof": "GATE-001 records the negative case",
                }
            ],
            "halts": [
                {
                    "id": "HALT-001",
                    "trigger": "The existing symbol differs from the pinned locator",
                    "question": "Which current symbol owns the governed behavior?",
                    "authority": "Repository maintainer",
                }
            ],
            "closure": {
                "state": "NOT_STARTED",
                "implemented_revision": None,
                "run_ids": [],
                "parity_ids": [],
                "assurance_ids": [],
                "residual_gap_ids": [],
            },
        }
        self.gap = self.records["GAP-001"]
        self.gap["links"] = {
            "evidence": ["E-001", "E-002"],
            "requirements": ["REQ-GAP-001-01"],
            "actors": ["ACT-001"],
            "workflows": ["WF-001"],
            "artifacts": ["ART-001"],
            "acceptance": ["AC-GAP-001-01"],
            "tests": ["TEST-GAP-001-01"],
            "gates": ["GATE-001"],
            "changes": ["CHANGE-GAP-001-01", "CHANGE-GAP-001-02", "CHANGE-GAP-001-03"],
            "steps": ["STEP-GAP-001-01"],
            "halts": ["HALT-001"],
        }
        self.gap["attributes"] = {
            "class": "QUALITY_GAP",
            "status": "OPEN",
            "readiness": "READY",
            "dossier": self.dossier,
        }

    def problems(self, gap: dict[str, Any] | None = None) -> set[str]:
        return {
            problem.code
            for problem in validate_gap_plan_record(
                self.pack,
                self.manifest,
                self.records,
                "GAP-001",
                gap or self.gap,
            )
        }

    def test_complete_dossier_is_cold_executable(self) -> None:
        self.assertEqual(self.problems(), set())

    def test_schema_trace_path_and_language_defects_are_discriminated(self) -> None:
        missing = copy.deepcopy(self.gap)
        del missing["attributes"]["dossier"]["rollout"]
        self.assertIn("GAP_DOSSIER_SCHEMA", self.problems(missing))

        untraced = copy.deepcopy(self.gap)
        untraced["links"]["tests"] = []
        self.assertIn("GAP_DOSSIER_TRACE_INVALID", self.problems(untraced))

        invented = copy.deepcopy(self.gap)
        invented["attributes"]["dossier"]["change_map"][0]["symbol"] = "def invented():"
        self.assertIn("GAP_DOSSIER_SYMBOL_INVALID", self.problems(invented))

        ambiguous = copy.deepcopy(self.gap)
        ambiguous["attributes"]["dossier"]["observable_delta"] = "This should be fixed later"
        self.assertIn("GAP_DOSSIER_AMBIGUOUS", self.problems(ambiguous))

        forbidden = copy.deepcopy(self.gap)
        forbidden["attributes"]["dossier"]["allowed_fence"]["forbidden_paths"] = ["tests/fixtures"]
        self.assertIn("GAP_DOSSIER_FENCE_VIOLATION", self.problems(forbidden))

        raw_secret = copy.deepcopy(self.gap)
        raw_secret["attributes"]["dossier"]["gates"][0]["environment"] = {"API_TOKEN": "raw-secret"}
        self.assertIn("GAP_DOSSIER_SECRET_INVALID", self.problems(raw_secret))

        incomplete_rename = copy.deepcopy(self.gap)
        change = incomplete_rename["attributes"]["dossier"]["change_map"][0]
        change["operation"] = "rename"
        self.assertIn("GAP_DOSSIER_PATH_STATE", self.problems(incomplete_rename))

        missing_backlink = copy.deepcopy(self.gap)
        records = copy.deepcopy(self.records)
        records["GATE-001"]["links"]["tests"] = []
        codes = {
            problem.code
            for problem in validate_gap_plan_record(
                self.pack,
                self.manifest,
                records,
                "GAP-001",
                missing_backlink,
            )
        }
        self.assertIn("GAP_DOSSIER_TRACE_INVALID", codes)

    def test_evidence_gap_requires_a_complete_blocker_contract(self) -> None:
        blocked = copy.deepcopy(self.gap)
        blocked["attributes"] = {
            "class": "EVIDENCE_GAP",
            "status": "BLOCKED",
            "readiness": "BLOCKED",
            "blocker": {
                "missing_evidence": "Reference invalid-input bytes",
                "investigations": ["Executed the authorized documented cases"],
                "resolution_question": "What exact bytes are emitted for invalid UTF-8?",
                "authority": "Reference owner",
            },
        }
        self.assertEqual(self.problems(blocked), set())
        del blocked["attributes"]["blocker"]["resolution_question"]
        self.assertIn("GAP_BLOCKER_INCOMPLETE", self.problems(blocked))

    def test_gap_plan_profile_invokes_machine_dossier_validation(self) -> None:
        created = run_cli(
            "init",
            "--product-name",
            "Dossier Integration",
            "--product-type",
            "cli",
            "--source-description",
            "Authorized synthetic source",
            "--repo-root",
            self.repository,
            "--output-dir",
            "integration-pack",
            "--timestamp",
            PINNED_TIMESTAMP,
        )
        self.assertEqual(created.returncode, 0, created.stderr)
        pack = self.repository / "integration-pack"
        brief = pack / "clone_brief.md"
        anchor = "GAP-001 dossier integration definition"
        line = f"- {anchor}\n"
        brief.write_text(brief.read_text(encoding="utf-8") + line, encoding="utf-8", newline="\n")
        index = read_json(pack / "clone_index.json")
        index["records"] = [
            {
                "id": "GAP-001",
                "kind": "GAP",
                "locator": {
                    "path": "clone_brief.md",
                    "anchor": anchor,
                    "sha256": hashlib.sha256(line.encode("utf-8")).hexdigest(),
                },
                "links": {"dependencies": []},
                "applicability": "MVP",
                "state": "OPEN",
                "attributes": {
                    "class": "QUALITY_GAP",
                    "status": "OPEN",
                    "readiness": "READY",
                    "selected": True,
                    "plan_order": 1,
                },
            }
        ]
        write_json(pack / "clone_index.json", index)

        validated = run_cli("validate", pack, "--profile", "gap-plan", "--format", "json")
        payload = json.loads(validated.stdout)
        diagnostics = {
            (item["code"], item["record_id"])
            for item in payload["diagnostics"]
        }

        self.assertEqual(validated.returncode, 1)
        self.assertIn(("GAP_DOSSIER_MISSING", "GAP-001"), diagnostics)


if __name__ == "__main__":
    unittest.main()
