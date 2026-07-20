from __future__ import annotations

import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any

from scripts.clonepack.schema import validate_schema_file
from tests.test_v2_regression import PINNED_TIMESTAMP, canonical_json, read_json, run_cli, tree_bytes, write_json


ROOT = Path(__file__).resolve().parents[1]
RUN_SCHEMA = ROOT / "assets" / "schemas" / "clone-run-v2.schema.json"


class RunAssuranceFreshnessTests(unittest.TestCase):
    maxDiff = None

    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)
        self.temp_root = Path(self.temporary_directory.name)
        self.repository = self.temp_root / "repository"
        self.repository.mkdir()

    def init_pack(self, name: str) -> Path:
        initialized = run_cli(
            "init",
            "--product-name",
            f"Freshness {name}",
            "--product-type",
            "cli",
            "--source-description",
            "Authorized local fixture",
            "--repo-root",
            self.repository,
            "--output-dir",
            name,
            "--timestamp",
            PINNED_TIMESTAMP,
        )
        self.assertEqual(initialized.returncode, 0, initialized.stderr)
        pack = self.repository / name
        manifest = read_json(pack / "clone_pack.json")
        manifest["reference_baseline_id"] = "BASELINE-FRESH-001"
        manifest["repository_state"] = {
            "kind": "working-tree",
            "revision": "fresh-revision-001",
            "diff_sha256": "1" * 64,
        }
        write_json(pack / "clone_pack.json", manifest)
        return pack

    def set_records(self, pack: Path, specifications: list[dict[str, Any]]) -> None:
        document = pack / "clone_brief.md"
        text = document.read_text(encoding="utf-8").rstrip("\n") + "\n"
        records: list[dict[str, Any]] = []
        lines: list[str] = []
        for number, specification in enumerate(specifications, 1):
            identifier = str(specification["id"])
            anchor = f"{identifier} freshness contract {number}"
            line = f"- {anchor}\n"
            lines.append(line)
            records.append(
                {
                    "id": identifier,
                    "kind": specification["kind"],
                    "locator": {
                        "path": "clone_brief.md",
                        "anchor": anchor,
                        "sha256": hashlib.sha256(line.encode("utf-8")).hexdigest(),
                    },
                    "links": specification.get("links", {}),
                    "applicability": specification.get("applicability", "MVP"),
                    "state": specification.get("state", "READY"),
                    "attributes": specification.get("attributes", {}),
                }
            )
        document.write_text(text + "".join(lines), encoding="utf-8", newline="\n")
        index = read_json(pack / "clone_index.json")
        index["records"] = records
        write_json(pack / "clone_index.json", index)

    def base_records(self, *, procedure_sha256: str | None = None, marker: Path | None = None) -> list[dict[str, Any]]:
        command = "print('gate-pass')"
        if marker is not None:
            command = f"from pathlib import Path; Path({str(marker)!r}).write_text('executed', encoding='utf-8')"
        test_attributes: dict[str, Any] = {"environment_id": "ENV-001"}
        if procedure_sha256 is not None:
            test_attributes["manual_procedure_sha256"] = procedure_sha256
        return [
            {"id": "ENV-001", "kind": "ENV"},
            {"id": "E-001", "kind": "E"},
            {"id": "REQ-001", "kind": "REQ"},
            {"id": "AC-001", "kind": "AC"},
            {
                "id": "TEST-001",
                "kind": "TEST",
                "links": {"requirements": ["REQ-001"], "acceptance": ["AC-001"], "oracles": ["E-001"]},
                "attributes": test_attributes,
            },
            {
                "id": "GATE-001",
                "kind": "GATE",
                "attributes": {
                    "argv": [sys.executable, "-c", command],
                    "cwd": ".",
                    "environment": {},
                    "timeout_seconds": 30,
                    "expected_exit": 0,
                    "blocked_exit_codes": [7],
                    "artifact_paths": [],
                    "fresh_artifact_paths": [],
                    "covered_ids": ["REQ-001", "AC-001", "TEST-001"],
                    "oracle_ids": ["E-001"],
                    "normalizations": ["exact-exit"],
                    "redactions": [],
                },
            },
        ]

    def diagnostics(self, pack: Path, profile: str = "scaffold") -> list[dict[str, Any]]:
        validated = run_cli("validate", pack, "--profile", profile, "--format", "json")
        self.assertNotEqual(validated.returncode, 70, validated.stderr)
        return json.loads(validated.stdout)["diagnostics"]

    def test_record_run_binds_every_contract_and_validator_detects_staleness(self) -> None:
        pack = self.init_pack("automatic")
        self.set_records(pack, self.base_records())

        recorded = run_cli(
            "record-run",
            pack,
            "--gate",
            "GATE-001",
            "--environment",
            "ENV-001",
            "--timestamp",
            PINNED_TIMESTAMP,
        )
        self.assertEqual(recorded.returncode, 0, recorded.stderr)
        run = json.loads(recorded.stdout)
        self.assertEqual(
            list(run["contract_hashes"]),
            ["AC-001", "E-001", "ENV-001", "GATE-001", "REQ-001", "TEST-001"],
        )
        self.assertEqual(run["clone_diff_sha256"], "1" * 64)
        self.assertEqual(
            run["execution_contract"],
            {
                "argv": [sys.executable, "-c", "print('gate-pass')"],
                "cwd": ".",
                "environment": {},
                "timeout_seconds": 30,
                "expected_exit": 0,
                "blocked_exit_codes": [7],
                "artifact_paths": [],
                "fresh_artifact_paths": [],
                "covered_ids": ["AC-001", "REQ-001", "TEST-001"],
                "oracle_ids": ["E-001"],
                "normalizations": ["exact-exit"],
                "redactions": [],
            },
        )
        current_without_contract = dict(run)
        current_without_contract.pop("execution_contract")
        self.assertTrue(validate_schema_file(current_without_contract, RUN_SCHEMA))
        legacy_without_contract = dict(current_without_contract)
        legacy_without_contract["runner_version"] = "2.1.0"
        self.assertEqual(validate_schema_file(legacy_without_contract, RUN_SCHEMA), [])
        current = self.diagnostics(pack)
        self.assertNotIn("RUN_CONTRACT_STALE", {item["code"] for item in current})
        self.assertNotIn("RUN_INDEX_INVALID", {item["code"] for item in current})

        index = read_json(pack / "clone_index.json")
        gate = next(record for record in index["records"] if record["id"] == "GATE-001")
        gate["attributes"]["artifact_paths"] = ["artifacts/current.json"]
        gate["attributes"]["fresh_artifact_paths"] = ["artifacts/current.json"]
        write_json(pack / "clone_index.json", index)
        self.assertIn(
            "RUN_CONTRACT_STALE",
            {item["code"] for item in self.diagnostics(pack)},
        )
        gate["attributes"]["artifact_paths"] = []
        gate["attributes"]["fresh_artifact_paths"] = []
        old_anchor = gate["locator"]["anchor"]
        new_anchor = old_anchor + " changed"
        document = pack / gate["locator"]["path"]
        text = document.read_text(encoding="utf-8").replace(f"- {old_anchor}\n", f"- {new_anchor}\n")
        document.write_text(text, encoding="utf-8", newline="\n")
        gate["locator"]["anchor"] = new_anchor
        gate["locator"]["sha256"] = hashlib.sha256(f"- {new_anchor}\n".encode("utf-8")).hexdigest()
        counterpart = next(record for record in index["records"] if record["id"] == run["run_id"])
        counterpart["links"].pop("gates")
        write_json(pack / "clone_index.json", index)
        manifest = read_json(pack / "clone_pack.json")
        manifest["repository_state"]["diff_sha256"] = "2" * 64
        write_json(pack / "clone_pack.json", manifest)

        codes = {item["code"] for item in self.diagnostics(pack)}
        self.assertIn("RUN_CONTRACT_STALE", codes)
        self.assertIn("RUN_INDEX_INVALID", codes)
        self.assertIn("RUN_STALE_REVISION", codes)

        (pack / "runs" / f"{run['run_id']}.json").unlink()
        self.assertIn("RUN_FILE_MISSING", {item["code"] for item in self.diagnostics(pack)})

    def test_stale_timeout_recovery_preserves_active_pack_and_uses_independent_revision_one(self) -> None:
        source = self.init_pack("docs-clone")
        records = self.base_records()
        gate = next(record for record in records if record["id"] == "GATE-001")
        gate["attributes"]["timeout_seconds"] = 60
        self.set_records(source, records)
        source_manifest = read_json(source / "clone_pack.json")
        source_manifest["state"] = "active"
        write_json(source / "clone_pack.json", source_manifest)

        recorded = run_cli(
            "record-run",
            source,
            "--gate",
            "GATE-001",
            "--environment",
            "ENV-001",
            "--timestamp",
            PINNED_TIMESTAMP,
        )
        self.assertEqual(0, recorded.returncode, recorded.stderr)
        source_run = json.loads(recorded.stdout)
        self.assertEqual(60, source_run["execution_contract"]["timeout_seconds"])

        source_index = read_json(source / "clone_index.json")
        source_gate = next(record for record in source_index["records"] if record["id"] == "GATE-001")
        source_gate["attributes"]["timeout_seconds"] = 300
        write_json(source / "clone_index.json", source_index)
        self.assertIn("RUN_CONTRACT_STALE", {item["code"] for item in self.diagnostics(source)})
        self.assertEqual("active", read_json(source / "clone_pack.json")["state"])
        self.assertFalse((source / "seal.json").exists())
        frozen_source = tree_bytes(source)

        recovery = self.init_pack("docs-clone-recovery")
        recovery_manifest = read_json(recovery / "clone_pack.json")
        source_manifest = read_json(source / "clone_pack.json")

        self.assertEqual(frozen_source, tree_bytes(source))
        self.assertNotEqual(source_manifest["pack_id"], recovery_manifest["pack_id"])
        self.assertEqual(1, recovery_manifest["pack_revision"])
        self.assertIsNone(recovery_manifest["supersedes"])
        self.assertEqual([], list((recovery / "runs").glob("RUN-*.json")))
        self.assertTrue((source / "runs" / f"{source_run['run_id']}.json").is_file())

    def test_record_run_rejects_bad_references_before_execution_and_preserves_collisions(self) -> None:
        pack = self.init_pack("preflight")
        marker = self.repository / "executed.txt"
        self.set_records(pack, self.base_records(marker=marker))
        index = read_json(pack / "clone_index.json")
        gate = next(record for record in index["records"] if record["id"] == "GATE-001")
        gate["attributes"]["covered_ids"].append("REQ-999")
        write_json(pack / "clone_index.json", index)

        rejected = run_cli("record-run", pack, "--gate", "GATE-001", "--environment", "ENV-001")
        self.assertEqual(rejected.returncode, 1)
        self.assertIn("REF_UNDEFINED:", rejected.stderr)
        self.assertFalse(marker.exists())
        self.assertEqual(list((pack / "runs").glob("RUN-*.json")), [])

        wrong_kind = run_cli("record-run", pack, "--gate", "ENV-001", "--environment", "E-001")
        self.assertEqual(wrong_kind.returncode, 1)
        self.assertIn("REF_WRONG_KIND:", wrong_kind.stderr)
        self.assertFalse(marker.exists())

        gate["attributes"]["covered_ids"].remove("REQ-999")
        write_json(pack / "clone_index.json", index)
        collision = pack / "runs" / "artifacts" / "RUN-001"
        collision.mkdir(parents=True)
        sentinel = collision / "owned.txt"
        sentinel.write_text("owned\n", encoding="utf-8")
        recorded = run_cli("record-run", pack, "--gate", "GATE-001", "--environment", "ENV-001")
        self.assertEqual(recorded.returncode, 0, recorded.stderr)
        self.assertEqual(json.loads(recorded.stdout)["run_id"], "RUN-002")
        self.assertEqual(sentinel.read_text(encoding="utf-8"), "owned\n")

    def test_record_run_rejects_invalid_execution_contract_before_execution(self) -> None:
        pack = self.init_pack("execution-contract-preflight")
        marker = self.repository / "invalid-contract-executed.txt"
        self.set_records(pack, self.base_records(marker=marker))
        index = read_json(pack / "clone_index.json")
        gate = next(record for record in index["records"] if record["id"] == "GATE-001")
        gate["attributes"]["environment"] = {"BAD-NAME": "value"}
        write_json(pack / "clone_index.json", index)

        rejected = run_cli(
            "record-run",
            pack,
            "--gate",
            "GATE-001",
            "--environment",
            "ENV-001",
        )

        self.assertEqual(rejected.returncode, 1, rejected.stderr)
        self.assertFalse(marker.exists())
        self.assertIn("RUN_CONTRACT_INVALID:", rejected.stderr)
        self.assertEqual(list((pack / "runs").glob("RUN-*.json")), [])

    def test_manual_run_requires_the_pinned_procedure_and_binds_test_contract(self) -> None:
        pack = self.init_pack("manual")
        procedure = self.temp_root / "procedure.md"
        procedure.write_text("# Observe\n\n1. Verify output.\n", encoding="utf-8")
        procedure_sha256 = hashlib.sha256(procedure.read_bytes()).hexdigest()
        self.set_records(pack, self.base_records(procedure_sha256=procedure_sha256))
        evidence = pack / "manual-evidence.txt"
        evidence.write_text("observed pass\n", encoding="utf-8")
        wrong = self.temp_root / "wrong.md"
        wrong.write_text("different steps\n", encoding="utf-8")

        rejected = run_cli(
            "record-manual",
            pack,
            "--test",
            "TEST-001",
            "--procedure",
            wrong,
            "--observer",
            "observer-1",
            "--authority",
            "DEC-001",
            "--artifact",
            "manual-evidence.txt",
        )
        self.assertEqual(rejected.returncode, 1)
        self.assertIn("MANUAL_PROCEDURE_MISMATCH:", rejected.stderr)
        self.assertEqual(list((pack / "runs").glob("RUN-*.json")), [])

        recorded = run_cli(
            "record-manual",
            pack,
            "--test",
            "TEST-001",
            "--procedure",
            procedure,
            "--observer",
            "observer-1",
            "--authority",
            "DEC-001",
            "--artifact",
            "manual-evidence.txt",
            "--timestamp",
            PINNED_TIMESTAMP,
        )
        self.assertEqual(recorded.returncode, 0, recorded.stderr)
        run = json.loads(recorded.stdout)
        self.assertEqual(run["manual_attestation"]["procedure_sha256"], procedure_sha256)
        self.assertEqual(
            list(run["contract_hashes"]),
            ["AC-001", "E-001", "ENV-001", "REQ-001", "TEST-001"],
        )
        self.assertNotIn("RUN_CONTRACT_STALE", {item["code"] for item in self.diagnostics(pack)})

        index = read_json(pack / "clone_index.json")
        test = next(record for record in index["records"] if record["id"] == "TEST-001")
        test["attributes"]["manual_procedure_sha256"] = "f" * 64
        write_json(pack / "clone_index.json", index)
        self.assertIn("RUN_CONTRACT_STALE", {item["code"] for item in self.diagnostics(pack)})

    def test_assurance_binds_case_and_repository_and_preflights_all_collisions(self) -> None:
        pack = self.init_pack("assurance")
        plan = read_json(pack / "assurance_plan.json")
        marker = self.repository / "second-assurance-executed.txt"
        plan["risk_profile"] = "local-evaluation"
        plan["cases"] = [
            {
                "id": "ASSURE-001",
                "kind": "threat-model",
                "required": True,
                "argv": [sys.executable, "-c", "print('first')"],
                "cwd": ".",
                "timeout_seconds": 30,
                "expected_exit": 0,
                "artifact_paths": [],
                "result": None,
            },
            {
                "id": "ASSURE-002",
                "kind": "provenance",
                "required": False,
                "argv": [
                    sys.executable,
                    "-c",
                    f"from pathlib import Path; Path({str(marker)!r}).write_text('executed', encoding='utf-8')",
                ],
                "cwd": ".",
                "timeout_seconds": 30,
                "expected_exit": 0,
                "artifact_paths": [],
                "result": None,
            },
        ]
        write_json(pack / "assurance_plan.json", plan)
        self.set_records(
            pack,
            [
                {
                    "id": str(case["id"]),
                    "kind": "ASSURE",
                    "attributes": {
                        "case_sha256": hashlib.sha256(
                            canonical_json({key: value for key, value in case.items() if key != "result"}).encode("utf-8")
                        ).hexdigest()
                    },
                }
                for case in plan["cases"]
            ],
        )

        assured = run_cli("assure", pack, "--case", "ASSURE-001")
        self.assertEqual(assured.returncode, 0, assured.stderr)
        updated = read_json(pack / "assurance_plan.json")
        result_path = pack / updated["cases"][0]["result"]["path"]
        result = read_json(result_path)
        self.assertEqual(result["reference_baseline_id"], "BASELINE-FRESH-001")
        self.assertEqual(result["clone_revision"], "fresh-revision-001")
        self.assertEqual(result["clone_diff_sha256"], "1" * 64)
        expected_case_hash = hashlib.sha256(
            canonical_json({key: value for key, value in updated["cases"][0].items() if key != "result"}).encode("utf-8")
        ).hexdigest()
        self.assertEqual(result["case_sha256"], expected_case_hash)
        optional_null_diagnostics = self.diagnostics(pack, "verified-mvp")
        self.assertFalse(
            any(item["code"] == "ASSURANCE_BLOCKED" and item["record_id"] == "ASSURE-002" for item in optional_null_diagnostics),
            optional_null_diagnostics,
        )

        collision = run_cli("assure", pack)
        self.assertEqual(collision.returncode, 1)
        self.assertIn("OUTPUT_EXISTS:", collision.stderr)
        self.assertFalse(marker.exists())

        updated["cases"][1]["expected_exit"] = 7
        write_json(pack / "assurance_plan.json", updated)
        index = read_json(pack / "clone_index.json")
        optional_record = next(record for record in index["records"] if record["id"] == "ASSURE-002")
        optional_record["attributes"]["case_sha256"] = hashlib.sha256(
            canonical_json(
                {key: value for key, value in updated["cases"][1].items() if key != "result"}
            ).encode("utf-8")
        ).hexdigest()
        write_json(pack / "clone_index.json", index)
        optional_failed = run_cli("assure", pack, "--case", "ASSURE-002")
        self.assertEqual(optional_failed.returncode, 5, optional_failed.stderr)
        self.assertTrue(marker.exists())
        optional_failed_diagnostics = self.diagnostics(pack, "verified-mvp")
        self.assertFalse(
            any(item["code"] == "ASSURANCE_BLOCKED" and item["record_id"] == "ASSURE-002" for item in optional_failed_diagnostics),
            optional_failed_diagnostics,
        )
        self.assertFalse(
            any(
                item["record_id"] == "ASSURE-002"
                and item["code"] in {"RESULT_INVALID", "RESULT_STATUS_MISMATCH", "RESULT_IDENTITY_MISMATCH", "ASSURANCE_CONTRACT_STALE"}
                for item in optional_failed_diagnostics
            ),
            optional_failed_diagnostics,
        )

        updated = read_json(pack / "assurance_plan.json")
        updated["cases"][0]["expected_exit"] = 7
        write_json(pack / "assurance_plan.json", updated)
        diagnostics = self.diagnostics(pack, "verified-mvp")
        self.assertTrue(
            any(item["code"] == "ASSURANCE_CONTRACT_STALE" and item["record_id"] == "ASSURE-001" for item in diagnostics),
            diagnostics,
        )


if __name__ == "__main__":
    unittest.main()
