from __future__ import annotations

import hashlib
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any

from tests.test_v2_regression import PINNED_TIMESTAMP, canonical_json, read_json, run_cli, write_json


class GapEvidenceIntegrityTests(unittest.TestCase):
    maxDiff = None

    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)
        self.temp_root = Path(self.temporary_directory.name)
        self.repository = self.temp_root / "repository"
        self.repository.mkdir()

    def _init(self, name: str) -> Path:
        result = run_cli(
            "init",
            "--product-name",
            f"Gap Evidence {name}",
            "--product-type",
            "cli",
            "--source-description",
            "Authorized synthetic reference",
            "--repo-root",
            self.repository,
            "--output-dir",
            name,
            "--timestamp",
            PINNED_TIMESTAMP,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        return self.repository / name

    def _add_records(self, pack: Path, specifications: list[dict[str, Any]]) -> None:
        document = pack / "clone_brief.md"
        text = document.read_text(encoding="utf-8").rstrip("\n") + "\n"
        records: list[dict[str, Any]] = []
        lines: list[str] = []
        for position, specification in enumerate(specifications, 1):
            identifier = str(specification["id"])
            anchor = f"{identifier} lifecycle fixture {position}"
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
                    "applicability": "MVP",
                    "state": specification.get("state", "READY"),
                    "attributes": specification.get("attributes", {}),
                }
            )
        document.write_text(text + "".join(lines), encoding="utf-8", newline="\n")
        index_path = pack / "clone_index.json"
        index = read_json(index_path)
        index["records"] = records
        write_json(index_path, index)

    def _prepare(self, name: str, *, implement: bool = True) -> tuple[Path, str]:
        pack = self._init(name)
        manifest_path = pack / "clone_pack.json"
        manifest = read_json(manifest_path)
        manifest["reference_baseline_id"] = "BASELINE-GAP-001"
        manifest["repository_state"] = {
            "kind": "working-tree",
            "revision": "repository-revision-001",
            "diff_sha256": "0" * 64,
        }
        write_json(manifest_path, manifest)

        self._add_records(
            pack,
            [
                {"id": "ENV-001", "kind": "ENV"},
                {"id": "E-001", "kind": "E"},
                {"id": "DEC-001", "kind": "DEC"},
                {"id": "AC-001", "kind": "AC"},
                {
                    "id": "GATE-001",
                    "kind": "GATE",
                    "attributes": {
                        "argv": [sys.executable, "-c", "print('gate-pass')"],
                        "cwd": ".",
                        "environment": {},
                        "timeout_seconds": 30,
                        "expected_exit": 0,
                        "covered_ids": ["AC-001"],
                        "oracle_ids": ["E-001"],
                        "normalizations": [],
                        "redactions": [],
                    },
                },
                {"id": "CAP-001", "kind": "CAP"},
                {"id": "CAP-002", "kind": "CAP"},
                {"id": "PAR-001", "kind": "PAR"},
                {"id": "ASSURE-001", "kind": "ASSURE"},
                {
                    "id": "GAP-001",
                    "kind": "GAP",
                    "links": {
                        "dependencies": [],
                        "acceptance": ["AC-001"],
                        "parity": ["PAR-001"],
                        "assurance": ["ASSURE-001"],
                    },
                    "attributes": {"status": "OPEN", "readiness": "READY"},
                },
            ],
        )

        reference = pack / "reference.bin"
        clone = pack / "clone.bin"
        reference.write_bytes(b"same-observable\n")
        clone.write_bytes(b"same-observable\n")
        capture = read_json(pack / "capture_plan.json")
        capture["cases"] = [
            {
                "id": case_id,
                "adapter": "manual",
                "side": side,
                "environment_id": "ENV-001",
                "required": True,
                "authorization_decision_ids": ["DEC-001"],
                "safe_test_environment": True,
                "timeout_seconds": 30,
                "input": {"source_path": source},
                "lifecycle": {"setup": None, "teardown": None},
                "redactions": [],
                "result": None,
            }
            for case_id, side, source in (
                ("CAP-001", "reference", "reference.bin"),
                ("CAP-002", "clone", "clone.bin"),
            )
        ]
        write_json(pack / "capture_plan.json", capture)
        parity = read_json(pack / "parity_plan.json")
        parity["cases"] = [
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
        write_json(pack / "parity_plan.json", parity)
        assurance = read_json(pack / "assurance_plan.json")
        assurance["risk_profile"] = "local-evaluation"
        assurance["cases"] = [
            {
                "id": "ASSURE-001",
                "kind": "threat-model",
                "required": True,
                "argv": [sys.executable, "-c", "print('assurance-pass')"],
                "cwd": ".",
                "timeout_seconds": 30,
                "expected_exit": 0,
                "artifact_paths": [],
                "result": None,
            }
        ]
        write_json(pack / "assurance_plan.json", assurance)

        index = read_json(pack / "clone_index.json")
        records = {record["id"]: record for record in index["records"]}
        for case in capture["cases"]:
            record = records[case["id"]]
            record["links"] = {
                "environments": [case["environment_id"]],
                "decisions": sorted(case["authorization_decision_ids"]),
            }
            record["attributes"]["case_sha256"] = hashlib.sha256(
                canonical_json({key: value for key, value in case.items() if key != "result"}).encode("utf-8")
            ).hexdigest()
        parity_record = records["PAR-001"]
        parity_record["links"] = {"captures": ["CAP-001", "CAP-002"]}
        parity_record["attributes"]["case_sha256"] = hashlib.sha256(
            canonical_json({key: value for key, value in parity["cases"][0].items() if key != "result"}).encode("utf-8")
        ).hexdigest()
        assurance_record = records["ASSURE-001"]
        assurance_record["attributes"]["case_sha256"] = hashlib.sha256(
            canonical_json({key: value for key, value in assurance["cases"][0].items() if key != "result"}).encode("utf-8")
        ).hexdigest()
        write_json(pack / "clone_index.json", index)

        started = self._transition(pack, "IN_PROGRESS")
        self.assertEqual(started.returncode, 0, started.stderr)
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
        run_id = json.loads(recorded.stdout)["run_id"]
        for case_id in ("CAP-001", "CAP-002"):
            captured = run_cli("capture", pack, "--case", case_id)
            self.assertEqual(captured.returncode, 0, captured.stderr)
        compared = run_cli("parity", pack, "--case", "PAR-001")
        self.assertEqual(compared.returncode, 0, compared.stderr)
        assured = run_cli("assure", pack, "--case", "ASSURE-001")
        self.assertEqual(assured.returncode, 0, assured.stderr)
        if implement:
            implemented = self._transition(pack, "IMPLEMENTED", evidence=[run_id])
            self.assertEqual(implemented.returncode, 0, implemented.stderr)
        return pack, run_id

    def _transition(
        self,
        pack: Path,
        status: str,
        *,
        evidence: list[str] | None = None,
        decisions: list[str] | None = None,
        timestamp: str = PINNED_TIMESTAMP,
    ) -> Any:
        arguments: list[object] = [
            "gap-transition",
            pack,
            "GAP-001",
            "--to",
            status,
            "--actor",
            "integrity-test",
            "--reason",
            f"exercise {status} evidence boundary",
            "--timestamp",
            timestamp,
        ]
        for identifier in evidence or []:
            arguments.extend(("--evidence", identifier))
        for identifier in decisions or []:
            arguments.extend(("--decision", identifier))
        return run_cli(*arguments)

    def _transition_state(self, pack: Path) -> tuple[bytes, bytes, bytes]:
        return tuple(
            (pack / relative).read_bytes()
            for relative in ("clone_index.json", "history/gap_events.jsonl", "gaps_analysis.md")
        )

    def _copy(self, source: Path, name: str) -> Path:
        destination = self.repository / name
        shutil.copytree(source, destination)
        return destination

    def _verify(self, pack: Path, run_id: str, *, include_parity: bool = True, include_assurance: bool = True) -> Any:
        evidence = [run_id]
        if include_parity:
            evidence.append("PAR-001")
        if include_assurance:
            evidence.append("ASSURE-001")
        return self._transition(pack, "VERIFIED", evidence=evidence)

    def test_current_run_parity_and_assurance_complete_verification(self) -> None:
        pack, run_id = self._prepare("happy")
        verified = self._verify(pack, run_id)

        self.assertEqual(verified.returncode, 0, verified.stderr)
        event = json.loads(verified.stdout)
        self.assertEqual((event["from"], event["to"]), ("IMPLEMENTED", "VERIFIED"))
        gaps_text = (pack / "gaps_analysis.md").read_text(encoding="utf-8")
        self.assertIn("- `NO-OPEN-GAPS`: true", gaps_text)

    def test_supplied_ids_must_exist_have_legal_kinds_and_be_unique(self) -> None:
        pack, run_id = self._prepare("references")
        cases = (
            ([run_id, "PAR-001", "ASSURE-001", "AC-001"], [], "GAP_EVIDENCE_KIND_INVALID", 1),
            ([run_id, "PAR-001", "ASSURE-999"], [], "REF_UNDEFINED", 1),
            ([run_id, run_id, "PAR-001", "ASSURE-001"], [], "ARG_INVALID", 2),
            ([run_id, "PAR-001", "ASSURE-001"], ["AC-001"], "GAP_DECISION_KIND_INVALID", 1),
            ([run_id, "PAR-001", "ASSURE-001"], ["DEC-999"], "REF_UNDEFINED", 1),
        )
        for number, (evidence, decisions, diagnostic, returncode) in enumerate(cases, 1):
            with self.subTest(diagnostic=diagnostic, evidence=evidence, decisions=decisions):
                candidate = self._copy(pack, f"references-{number}")
                before = self._transition_state(candidate)
                result = self._transition(candidate, "VERIFIED", evidence=evidence, decisions=decisions)
                self.assertEqual(result.returncode, returncode)
                self.assertIn(f"{diagnostic}:", result.stderr)
                self.assertEqual(self._transition_state(candidate), before)

    def test_implemented_rejects_stale_run_identity_and_tampered_artifacts(self) -> None:
        base, run_id = self._prepare("run-base", implement=False)
        stale = self._copy(base, "run-stale")
        run_path = stale / "runs" / f"{run_id}.json"
        run = read_json(run_path)
        run["clone_revision"] = "old-repository-revision"
        write_json(run_path, run)
        stale_before = self._transition_state(stale)
        stale_result = self._transition(stale, "IMPLEMENTED", evidence=[run_id])
        self.assertEqual(stale_result.returncode, 1)
        self.assertIn("RUN_STALE_REVISION:", stale_result.stderr)
        self.assertEqual(self._transition_state(stale), stale_before)

        tampered = self._copy(base, "run-tampered")
        artifact = read_json(tampered / "runs" / f"{run_id}.json")["artifacts"][0]
        (tampered / artifact["path"]).write_bytes(b"tampered-run-output\n")
        tampered_before = self._transition_state(tampered)
        tampered_result = self._transition(tampered, "IMPLEMENTED", evidence=[run_id])
        self.assertEqual(tampered_result.returncode, 4)
        self.assertIn("ARTIFACT_HASH_MISMATCH:", tampered_result.stderr)
        self.assertEqual(self._transition_state(tampered), tampered_before)

    def test_verified_rejects_missing_failed_stale_or_mismatched_parity(self) -> None:
        base, run_id = self._prepare("parity-base")
        missing = self._verify(base, run_id, include_parity=False)
        self.assertEqual(missing.returncode, 1)
        self.assertIn("GAP_EVIDENCE_MISSING:", missing.stderr)

        failed = self._copy(base, "parity-failed")
        failed_plan = read_json(failed / "parity_plan.json")
        failed_result_path = failed / failed_plan["cases"][0]["result"]["path"]
        failed_result = read_json(failed_result_path)
        failed_result["status"] = "FAIL"
        write_json(failed_result_path, failed_result)
        failed_plan["cases"][0]["result"].update(
            status="FAIL", sha256=hashlib.sha256(failed_result_path.read_bytes()).hexdigest()
        )
        write_json(failed / "parity_plan.json", failed_plan)
        rejected = self._verify(failed, run_id)
        self.assertEqual(rejected.returncode, 1)
        self.assertIn("PARITY_NOT_PASS:", rejected.stderr)

        stale_contract = self._copy(base, "parity-contract-stale")
        stale_plan = read_json(stale_contract / "parity_plan.json")
        stale_plan["cases"][0]["comparator"] = "text"
        write_json(stale_contract / "parity_plan.json", stale_plan)
        rejected = self._verify(stale_contract, run_id)
        self.assertEqual(rejected.returncode, 1)
        self.assertIn("PARITY_CONTRACT_STALE:", rejected.stderr)

        stale_identity = self._copy(base, "parity-identity-stale")
        identity_plan = read_json(stale_identity / "parity_plan.json")
        identity_result_path = stale_identity / identity_plan["cases"][0]["result"]["path"]
        identity_result = read_json(identity_result_path)
        identity_result["reference_baseline_id"] = "BASELINE-OLD-001"
        write_json(identity_result_path, identity_result)
        identity_plan["cases"][0]["result"]["sha256"] = hashlib.sha256(identity_result_path.read_bytes()).hexdigest()
        write_json(stale_identity / "parity_plan.json", identity_plan)
        rejected = self._verify(stale_identity, run_id)
        self.assertEqual(rejected.returncode, 1)
        self.assertIn("PARITY_STALE_REFERENCE:", rejected.stderr)

    def test_verified_rejects_missing_failed_stale_or_tampered_assurance(self) -> None:
        base, run_id = self._prepare("assurance-base")
        missing = self._verify(base, run_id, include_assurance=False)
        self.assertEqual(missing.returncode, 1)
        self.assertIn("GAP_EVIDENCE_MISSING:", missing.stderr)

        failed = self._copy(base, "assurance-failed")
        failed_plan = read_json(failed / "assurance_plan.json")
        failed_result_path = failed / failed_plan["cases"][0]["result"]["path"]
        failed_result = read_json(failed_result_path)
        failed_result["status"] = "FAIL"
        write_json(failed_result_path, failed_result)
        failed_plan["cases"][0]["result"].update(
            status="FAIL", sha256=hashlib.sha256(failed_result_path.read_bytes()).hexdigest()
        )
        write_json(failed / "assurance_plan.json", failed_plan)
        rejected = self._verify(failed, run_id)
        self.assertEqual(rejected.returncode, 1)
        self.assertIn("ASSURANCE_NOT_PASS:", rejected.stderr)

        stale_contract = self._copy(base, "assurance-contract-stale")
        stale_plan = read_json(stale_contract / "assurance_plan.json")
        stale_plan["cases"][0]["expected_exit"] = 7
        write_json(stale_contract / "assurance_plan.json", stale_plan)
        rejected = self._verify(stale_contract, run_id)
        self.assertEqual(rejected.returncode, 1)
        self.assertIn("ASSURANCE_CONTRACT_STALE:", rejected.stderr)

        tampered = self._copy(base, "assurance-artifact-tampered")
        tampered_plan = read_json(tampered / "assurance_plan.json")
        result_path = tampered / tampered_plan["cases"][0]["result"]["path"]
        nested_artifact = read_json(result_path)["artifacts"][0]
        (tampered / nested_artifact["path"]).write_bytes(b"tampered-assurance-output\n")
        rejected = self._verify(tampered, run_id)
        self.assertEqual(rejected.returncode, 4)
        self.assertIn("ARTIFACT_HASH_MISMATCH:", rejected.stderr)

    def test_event_timestamp_cannot_regress_and_failed_append_is_atomic(self) -> None:
        pack, run_id = self._prepare("chronology")
        before = self._transition_state(pack)
        regressed = self._transition(
            pack,
            "VERIFIED",
            evidence=[run_id, "PAR-001", "ASSURE-001"],
            timestamp="2026-07-18T12:34:55+00:00",
        )

        self.assertEqual(regressed.returncode, 1)
        self.assertIn("GAP_EVENT_TIME_REGRESSION:", regressed.stderr)
        self.assertEqual(self._transition_state(pack), before)


if __name__ == "__main__":
    unittest.main()
