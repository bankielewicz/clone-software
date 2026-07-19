from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any

from scripts.clonepack import TOOL_VERSION


SKILL_ROOT = Path(__file__).resolve().parents[1]
CLONE_PACK = SKILL_ROOT / "scripts" / "clone_pack.py"
PINNED_TIMESTAMP = "2026-07-18T12:34:56+00:00"


def canonical_json(value: Any) -> str:
    return json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


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


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise AssertionError(f"expected a JSON object in {path}")
    return value


def write_json(path: Path, value: Any) -> None:
    path.write_text(canonical_json(value), encoding="utf-8", newline="\n")


def tree_bytes(root: Path) -> dict[str, bytes | None]:
    return {
        path.relative_to(root).as_posix(): path.read_bytes() if path.is_file() else None
        for path in sorted(root.rglob("*"))
    }


class V2RegressionTests(unittest.TestCase):
    maxDiff = None

    def setUp(self) -> None:
        self.assertTrue(CLONE_PACK.is_file(), f"missing unified CLI: {CLONE_PACK}")
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)
        self.temp_root = Path(self.temporary_directory.name)
        self.repo_root = self.temp_root / "repository"
        self.repo_root.mkdir()

    def init_pack(
        self,
        output_dir: str = "clone-pack",
        *,
        repo_root: Path | None = None,
        product_name: str = "Regression Product",
    ) -> tuple[Path, subprocess.CompletedProcess[str]]:
        repository = repo_root or self.repo_root
        result = run_cli(
            "init",
            "--product-name",
            product_name,
            "--product-type",
            "cli",
            "--source-description",
            "Pinned local reference",
            "--repo-root",
            repository,
            "--output-dir",
            output_dir,
            "--timestamp",
            PINNED_TIMESTAMP,
        )
        output = Path(output_dir)
        pack = output if output.is_absolute() else repository / output
        return pack.resolve(), result

    def assert_init_ok(self, output_dir: str = "clone-pack") -> Path:
        pack, result = self.init_pack(output_dir)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stderr, "")
        self.assertTrue(pack.is_dir())
        return pack

    def add_records(self, pack: Path, specifications: list[dict[str, Any]]) -> None:
        document = pack / "clone_brief.md"
        original = document.read_text(encoding="utf-8").rstrip("\n") + "\n"
        lines: list[str] = []
        records: list[dict[str, Any]] = []
        for position, specification in enumerate(specifications, 1):
            identifier = str(specification["id"])
            anchor = str(specification.get("anchor", f"{identifier} definition {position}"))
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
        document.write_text(original + "".join(lines), encoding="utf-8", newline="\n")
        index_path = pack / "clone_index.json"
        index = read_json(index_path)
        index["records"] = records
        write_json(index_path, index)

    def plan_case_records(self, pack: Path, *plan_names: str) -> list[dict[str, Any]]:
        manifest = read_json(pack / "clone_pack.json")
        specifications: list[dict[str, Any]] = []
        seen: set[str] = set()

        def append(specification: dict[str, Any]) -> None:
            identifier = str(specification["id"])
            if identifier not in seen:
                specifications.append(specification)
                seen.add(identifier)

        for plan_name in plan_names:
            plan = read_json(pack / manifest["plans"][plan_name])
            for case in plan.get("cases", []):
                contract_hash = hashlib.sha256(
                    canonical_json({key: value for key, value in case.items() if key != "result"}).encode("utf-8")
                ).hexdigest()
                if plan_name == "capture":
                    append({"id": str(case["environment_id"]), "kind": "ENV"})
                    authorities = sorted(str(item) for item in case.get("authorization_decision_ids", []))
                    for authority_id in authorities:
                        append({"id": authority_id, "kind": "DEC"})
                    append(
                        {
                            "id": str(case["id"]),
                            "kind": "CAP",
                            "links": {
                                "environments": [str(case["environment_id"])],
                                "decisions": authorities,
                            },
                            "attributes": {"case_sha256": contract_hash},
                        }
                    )
                elif plan_name == "parity":
                    append(
                        {
                            "id": str(case["id"]),
                            "kind": "PAR",
                            "links": {
                                "captures": sorted(
                                    [str(case["reference_capture_id"]), str(case["clone_capture_id"])]
                                )
                            },
                            "attributes": {"case_sha256": contract_hash},
                        }
                    )
                elif plan_name == "assurance":
                    append(
                        {
                            "id": str(case["id"]),
                            "kind": "ASSURE",
                            "attributes": {"case_sha256": contract_hash},
                        }
                    )
        return specifications

    def resolve_required_markers(self, pack: Path) -> None:
        marker = re.compile(r"\[\[(?:REQUIRED|MIGRATION_REQUIRED):[^\]]*\]\]")
        cited_id = re.compile(
            r"\b(?:REQ-GAP-\d{3,}-\d{2,}|AC-GAP-\d{3,}-\d{2,}|"
            r"TEST-GAP-\d{3,}-\d{2,}|STEP-GAP-\d{3,}-\d{2,}|CHANGE-GAP-\d{3,}-\d{2,}|"
            r"[A-Z]+(?:-[A-Z]+)*-\d{3,})\b"
        )
        manifest = read_json(pack / "clone_pack.json")
        for entry in manifest["documents"]:
            path = pack / entry["path"]
            text = path.read_text(encoding="utf-8")
            text = marker.sub("RESOLVED", text)
            path.write_text(cited_id.sub("RESOLVED-ID", text), encoding="utf-8", newline="\n")

    def make_verification_fixture(self, pack: Path, records: list[dict[str, Any]]) -> None:
        self.resolve_required_markers(pack)
        manifest = read_json(pack / "clone_pack.json")
        manifest["reference_baseline_id"] = "BASELINE-REGRESSION-001"
        manifest["repository_state"] = {
            "kind": "working-tree",
            "revision": "fixture-revision-001",
            "diff_sha256": "0" * 64,
        }
        write_json(pack / "clone_pack.json", manifest)
        (pack / "fixture-reference.bin").write_bytes(b"verified-observable\n")
        (pack / "fixture-clone.bin").write_bytes(b"verified-observable\n")
        capture_path = pack / manifest["plans"]["capture"]
        capture = read_json(capture_path)
        capture["cases"] = [
            {
                "id": case_id,
                "adapter": "manual",
                "side": side,
                "environment_id": "ENV-001",
                "required": True,
                "authorization_decision_ids": [],
                "safe_test_environment": True,
                "timeout_seconds": 30,
                "input": {"source_path": source_path},
                "lifecycle": {"setup": None, "teardown": None},
                "redactions": [],
                "result": None,
            }
            for case_id, side, source_path in (
                ("CAP-900", "reference", "fixture-reference.bin"),
                ("CAP-901", "clone", "fixture-clone.bin"),
            )
        ]
        write_json(capture_path, capture)
        parity_path = pack / manifest["plans"]["parity"]
        parity = read_json(parity_path)
        parity["cases"] = [
            {
                "id": "PAR-900",
                "comparator": "exact",
                "required": True,
                "reference_capture_id": "CAP-900",
                "clone_capture_id": "CAP-901",
                "normalizations": [],
                "options": {},
                "result": None,
            }
        ]
        write_json(parity_path, parity)
        scaffold_path = pack / manifest["plans"]["scaffold"]
        scaffold = read_json(scaffold_path)
        scaffold.update(
            {
                "stack_decision_id": "STACK-001",
                "profile_id": "not-applicable",
                "template": "not-applicable",
                "output_root": ".",
                "required_paths": [],
                "commands": {"setup": None, "test": None, "build": None, "run": None},
                "applied": False,
            }
        )
        write_json(scaffold_path, scaffold)
        assurance_path = pack / manifest["plans"]["assurance"]
        assurance = read_json(assurance_path)
        assurance["risk_profile"] = "local-evaluation"
        assurance["cases"] = []
        for number, kind in enumerate(("threat-model", "provenance"), 1):
            case = {
                "id": f"ASSURE-{number:03d}",
                "kind": kind,
                "required": True,
                "argv": [sys.executable, "-c", "raise SystemExit(0)"],
                "cwd": ".",
                "expected_exit": 0,
                "result": None,
            }
            evidence_path = pack / "evidence" / "assurance" / f"fixture-{kind}.json"
            write_json(
                evidence_path,
                {
                    "schema_version": "clone-assurance-result/v2",
                    "assurance_id": case["id"],
                    "pack_id": manifest["pack_id"],
                    "pack_revision": manifest["pack_revision"],
                    "reference_baseline_id": manifest["reference_baseline_id"],
                    "clone_revision": manifest["repository_state"]["revision"],
                    "clone_diff_sha256": manifest["repository_state"]["diff_sha256"],
                    "case_sha256": hashlib.sha256(
                        canonical_json({key: value for key, value in case.items() if key != "result"}).encode("utf-8")
                    ).hexdigest(),
                    "kind": kind,
                    "status": "PASS",
                    "diagnostic": None,
                    "artifacts": [],
                    "runner_version": "fixture",
                },
            )
            case["result"] = {
                "status": "PASS",
                "path": evidence_path.relative_to(pack).as_posix(),
                "sha256": hashlib.sha256(evidence_path.read_bytes()).hexdigest(),
            }
            assurance["cases"].append(case)
        write_json(assurance_path, assurance)
        required_records = [
            {
                "id": "ENV-001",
                "kind": "ENV",
                "attributes": {"fixture": True},
            },
            {
                "id": "PROV-001",
                "kind": "PROV",
                "attributes": {
                    "origin": "synthetic local fixture",
                    "version": "1",
                    "sha256": "0" * 64,
                    "license": "test-only",
                    "rights_basis": "generated test fixture",
                    "disposition": "retain",
                    "separation_profile": "non-separated",
                },
            },
            *self.plan_case_records(pack, "capture", "parity", "assurance"),
            {"id": "E-900", "kind": "E", "links": {"requirements": ["REQ-900"]}},
            {
                "id": "REQ-900",
                "kind": "REQ",
                "links": {
                    "evidence": ["E-900"],
                    "acceptance": ["AC-900"],
                    "tests": ["TEST-900"],
                },
                "attributes": {"mvp": True, "implementation_locator": "fixture-product:verified"},
            },
            {
                "id": "AC-900",
                "kind": "AC",
                "links": {"requirements": ["REQ-900"], "tests": ["TEST-900"]},
            },
            {
                "id": "TEST-900",
                "kind": "TEST",
                "links": {
                    "requirements": ["REQ-900"],
                    "acceptance": ["AC-900"],
                    "oracles": ["E-900"],
                    "gates": ["GATE-900"],
                },
            },
            {
                "id": "GATE-900",
                "kind": "GATE",
                "links": {"tests": ["TEST-900"]},
                "attributes": {
                    "argv": [sys.executable, "-c", "raise SystemExit(0)"],
                    "cwd": ".",
                    "environment": {},
                    "timeout_seconds": 30,
                    "expected_exit": 0,
                    "covered_ids": ["REQ-900", "AC-900", "TEST-900"],
                    "oracle_ids": ["E-900"],
                    "normalizations": [],
                    "redactions": [],
                },
            },
        ]
        existing_ids = {str(record["id"]) for record in records}
        injected: list[dict[str, Any]] = []
        injected_ids: set[str] = set()
        for record in required_records:
            identifier = str(record["id"])
            if identifier not in existing_ids and identifier not in injected_ids:
                injected.append(record)
                injected_ids.add(identifier)
        self.add_records(pack, injected + records)
        for case_id in ("CAP-900", "CAP-901"):
            captured = run_cli("capture", pack, "--case", case_id)
            self.assertEqual(captured.returncode, 0, captured.stderr)
        compared = run_cli("parity", pack, "--case", "PAR-900")
        self.assertEqual(compared.returncode, 0, compared.stderr)
        recorded = run_cli(
            "record-run",
            pack,
            "--gate",
            "GATE-900",
            "--environment",
            "ENV-001",
            "--timestamp",
            PINNED_TIMESTAMP,
        )
        self.assertEqual(recorded.returncode, 0, recorded.stderr)

    def test_init_is_deterministic_non_overwriting_and_path_safe(self) -> None:
        first, first_result = self.init_pack("pack-a", product_name="Deterministic Product")
        second, second_result = self.init_pack("pack-b", product_name="Deterministic Product")

        self.assertEqual(first_result.returncode, 0, first_result.stderr)
        self.assertEqual(second_result.returncode, 0, second_result.stderr)
        self.assertEqual(tree_bytes(first), tree_bytes(second))

        collision, collision_result = self.init_pack("pack-a", product_name="Deterministic Product")
        self.assertEqual(collision, first)
        self.assertEqual(collision_result.returncode, 2)
        self.assertEqual(collision_result.stdout, "")
        self.assertIn("OUTPUT_EXISTS: refusing to overwrite existing destination", collision_result.stderr)

        outside = self.temp_root / "outside"
        _, outside_result = self.init_pack("../outside")
        _, root_result = self.init_pack(".")
        self.assertEqual(outside_result.returncode, 2)
        self.assertIn("PATH_ESCAPE:", outside_result.stderr)
        self.assertFalse(outside.exists())
        self.assertEqual(root_result.returncode, 2)
        self.assertIn("PATH_UNSAFE:", root_result.stderr)

    def test_untouched_v2_pack_passes_scaffold_profile(self) -> None:
        pack = self.assert_init_ok()

        first = run_cli("validate", pack, "--profile", "scaffold", "--format", "json")
        second = run_cli("validate", pack, "--profile", "scaffold", "--format", "json")

        self.assertEqual(first.returncode, 0, first.stderr)
        self.assertEqual(first.stderr, "")
        self.assertEqual(first.stdout, second.stdout)
        self.assertEqual(
            json.loads(first.stdout),
            {
                "schema_version": "clone-pack/v2",
                "profile": "scaffold",
                "status": "PASS",
                "diagnostics": [],
            },
        )

    def test_manifest_and_index_schemas_are_always_enforced(self) -> None:
        pack = self.assert_init_ok()
        manifest = read_json(pack / "clone_pack.json")
        manifest["product_name"] = ""
        write_json(pack / "clone_pack.json", manifest)
        index = read_json(pack / "clone_index.json")
        index["pack_revision"] = True
        write_json(pack / "clone_index.json", index)

        first = run_cli("validate", pack, "--profile", "scaffold", "--format", "json")
        second = run_cli("validate", pack, "--profile", "scaffold", "--format", "json")
        payload = json.loads(first.stdout)
        schema_paths = {
            diagnostic["path"]
            for diagnostic in payload["diagnostics"]
            if diagnostic["code"] == "SCHEMA_INVALID"
        }

        self.assertEqual(first.returncode, 1)
        self.assertEqual(first.stdout, second.stdout)
        self.assertIn("clone_pack.json#/product_name", schema_paths)
        self.assertIn("clone_index.json#/pack_revision", schema_paths)

    def test_plan_schema_validation_enters_at_the_declared_readiness_phase(self) -> None:
        pack = self.assert_init_ok()
        for name in ("capture", "parity", "scaffold", "assurance"):
            path = pack / f"{name}_plan.json"
            plan = read_json(path)
            plan["schema_version"] = "wrong"
            write_json(path, plan)

        expected = {
            "scaffold": set(),
            "baseline-ready": {"capture_plan.json"},
            "spec-ready": {"capture_plan.json", "parity_plan.json"},
            "build-ready": {
                "capture_plan.json",
                "parity_plan.json",
                "scaffold_plan.json",
                "assurance_plan.json",
            },
        }
        for profile, expected_artifacts in expected.items():
            with self.subTest(profile=profile):
                validated = run_cli("validate", pack, "--profile", profile, "--format", "json")
                payload = json.loads(validated.stdout)
                artifacts = {
                    diagnostic["path"].split("#", 1)[0]
                    for diagnostic in payload["diagnostics"]
                    if diagnostic["code"] == "SCHEMA_INVALID"
                }
                self.assertEqual(artifacts, expected_artifacts)

    def test_existing_runs_gap_events_and_seals_are_schema_validated(self) -> None:
        pack = self.assert_init_ok()
        write_json(pack / "runs" / "RUN-001.json", {"schema_version": "clone-run/v2", "run_id": "RUN-001"})

        event = {
            "schema_version": "clone-gap-event/v2",
            "event_id": "GAPEVT-001-001",
            "gap_id": "GAP-001",
            "sequence": True,
            "from": "OPEN",
            "to": "BLOCKED",
            "timestamp": PINNED_TIMESTAMP,
            "actor": "schema-regression",
            "evidence_ids": [],
            "decision_ids": [],
            "reason": "exercise integer versus boolean validation",
            "previous_event_sha256": "",
        }
        event["event_sha256"] = hashlib.sha256(canonical_json(event).encode("utf-8")).hexdigest()
        (pack / "history" / "gap_events.jsonl").write_text(
            json.dumps(event, sort_keys=True) + "\n",
            encoding="utf-8",
            newline="\n",
        )

        manifest_hash = hashlib.sha256((pack / "clone_pack.json").read_bytes()).hexdigest()
        write_json(
            pack / "seal.json",
            {
                "schema_version": "clone-seal/v2",
                "pack_id": read_json(pack / "clone_pack.json")["pack_id"],
                "pack_revision": True,
                "profile": "scaffold",
                "created_at": PINNED_TIMESTAMP,
                "verdict": "PASS",
                "files": {"clone_pack.json": manifest_hash},
                "manifest_sha256": manifest_hash,
            },
        )

        validated = run_cli("validate", pack, "--profile", "scaffold", "--format", "json")
        payload = json.loads(validated.stdout)
        schema_paths = {
            diagnostic["path"]
            for diagnostic in payload["diagnostics"]
            if diagnostic["code"] == "SCHEMA_INVALID"
        }

        self.assertEqual(validated.returncode, 1)
        self.assertIn("runs/RUN-001.json#/pack_id", schema_paths)
        self.assertIn("history/gap_events.jsonl:1#/sequence", schema_paths)
        self.assertIn("seal.json#/pack_revision", schema_paths)

    def test_index_rejects_duplicate_undefined_and_wrong_kind_ids(self) -> None:
        pack = self.assert_init_ok()
        self.add_records(
            pack,
            [
                {"id": "E-001", "kind": "E", "anchor": "E-001 primary definition"},
                {"id": "E-001", "kind": "E", "anchor": "E-001 duplicate definition"},
                {
                    "id": "REQ-001",
                    "kind": "REQ",
                    "links": {
                        "evidence": ["REQ-001"],
                        "tests": ["TEST-999"],
                    },
                },
            ],
        )

        result = run_cli("validate", pack, "--profile", "scaffold", "--format", "json")
        payload = json.loads(result.stdout)
        diagnostics = {(item["code"], item["record_id"], item["message"]) for item in payload["diagnostics"]}

        self.assertEqual(result.returncode, 1)
        self.assertIn(("ID_DUPLICATE", "E-001", "duplicate record ID: E-001"), diagnostics)
        self.assertIn(("REF_UNDEFINED", "REQ-001", "undefined reference: TEST-999"), diagnostics)
        self.assertIn(("REF_WRONG_KIND", "REQ-001", "evidence cannot target REQ"), diagnostics)

    def test_verified_text_claim_cannot_replace_current_run_evidence(self) -> None:
        pack = self.assert_init_ok()
        self.make_verification_fixture(
            pack,
            [
                {"id": "E-001", "kind": "E", "links": {"requirements": ["REQ-001"]}},
                {
                    "id": "REQ-001",
                    "kind": "REQ",
                    "links": {
                        "evidence": ["E-001"],
                        "acceptance": ["AC-001"],
                        "tests": ["TEST-001"],
                    },
                    "attributes": {
                        "mvp": True,
                        "implementation_locator": "src/regression.py:1",
                        "verification_status": "VERIFIED",
                    },
                },
                {
                    "id": "AC-001",
                    "kind": "AC",
                    "links": {"requirements": ["REQ-001"], "tests": ["TEST-001"]},
                },
                {
                    "id": "TEST-001",
                    "kind": "TEST",
                    "links": {
                        "requirements": ["REQ-001"],
                        "acceptance": ["AC-001"],
                        "oracles": ["E-001"],
                        "gates": ["GATE-001"],
                    },
                },
                {"id": "GATE-001", "kind": "GATE", "links": {"tests": ["TEST-001"]}},
            ],
        )

        result = run_cli("seal", pack, "--profile", "verified-mvp", "--timestamp", PINNED_TIMESTAMP)

        self.assertEqual(result.returncode, 5)
        self.assertEqual(result.stdout, "")
        self.assertIn("SEAL_PRECONDITION:", result.stderr)
        self.assertIn("current passing runs do not cover: AC-001", result.stderr)
        self.assertFalse((pack / "seal.json").exists())

    def test_seal_detects_one_byte_equivalent_plan_tamper(self) -> None:
        pack = self.assert_init_ok()
        self.make_verification_fixture(
            pack,
            [{"id": "E-001", "kind": "E", "attributes": {"investigation_only": True}}],
        )

        sealed = run_cli("seal", pack, "--profile", "verified-mvp", "--timestamp", PINNED_TIMESTAMP)
        self.assertEqual(sealed.returncode, 0, sealed.stderr)
        self.assertTrue((pack / "seal.json").is_file())

        capture_plan = pack / "capture_plan.json"
        capture_plan.write_bytes(capture_plan.read_bytes() + b" ")
        validated = run_cli("validate", pack, "--profile", "verified-mvp", "--format", "json")
        payload = json.loads(validated.stdout)

        self.assertEqual(validated.returncode, 4)
        self.assertIn("SEAL_TAMPERED", {item["code"] for item in payload["diagnostics"]})
        self.assertTrue(
            any("sealed file changed: capture_plan.json" in item["message"] for item in payload["diagnostics"])
        )

    def test_verified_mvp_rejects_vacuous_plans_and_missing_mvp_requirement(self) -> None:
        pack = self.assert_init_ok()
        self.make_verification_fixture(pack, [])
        capture = read_json(pack / "capture_plan.json")
        capture["cases"] = []
        write_json(pack / "capture_plan.json", capture)
        parity = read_json(pack / "parity_plan.json")
        parity["cases"] = []
        write_json(pack / "parity_plan.json", parity)
        index = read_json(pack / "clone_index.json")
        next(record for record in index["records"] if record["id"] == "REQ-900")["attributes"]["mvp"] = False
        write_json(pack / "clone_index.json", index)

        rejected = run_cli("seal", pack, "--profile", "verified-mvp", "--timestamp", PINNED_TIMESTAMP)

        self.assertEqual(rejected.returncode, 5, rejected.stderr)
        for message in (
            "required reference capture",
            "required clone capture",
            "at least one attributes.mvp=true REQ",
            "REQ -> AC -> TEST -> GATE -> RUN chain",
            "required parity case",
        ):
            self.assertIn(message, rejected.stderr)
        self.assertFalse((pack / "seal.json").exists())

    def test_run_creation_adds_all_reciprocal_links_and_validator_rejects_a_missing_backlink(self) -> None:
        pack = self.assert_init_ok()
        self.make_verification_fixture(pack, [])
        index = read_json(pack / "clone_index.json")
        run = next(record for record in index["records"] if record["kind"] == "RUN")
        run_id = run["id"]
        for target_id in ("REQ-900", "AC-900", "TEST-900", "GATE-900", "E-900"):
            target = next(record for record in index["records"] if record["id"] == target_id)
            self.assertIn(run_id, target["links"]["runs"])

        test = next(record for record in index["records"] if record["id"] == "TEST-900")
        test["links"]["runs"].remove(run_id)
        write_json(pack / "clone_index.json", index)
        rejected = run_cli("seal", pack, "--profile", "verified-mvp", "--timestamp", PINNED_TIMESTAMP)
        self.assertEqual(rejected.returncode, 1)
        self.assertIn("TEST-900.runs does not link back to RUN-001", rejected.stderr)

    def test_surface_requires_typed_disposition(self) -> None:
        pack = self.assert_init_ok()
        self.make_verification_fixture(pack, [{"id": "SURF-001", "kind": "SURF"}])
        rejected = run_cli("seal", pack, "--profile", "verified-mvp", "--timestamp", PINNED_TIMESTAMP)
        self.assertEqual(rejected.returncode, 1)
        self.assertIn("attributes.disposition must use the controlled capability vocabulary", rejected.stderr)

    def test_gap_transitions_are_atomic_legal_and_dependency_gated(self) -> None:
        pack = self.assert_init_ok("legal-gap-pack")
        self.add_records(
            pack,
            [
                {
                    "id": "GAP-001",
                    "kind": "GAP",
                    "links": {"dependencies": []},
                    "attributes": {"status": "OPEN", "readiness": "READY"},
                }
            ],
        )

        legal = run_cli(
            "gap-transition",
            pack,
            "GAP-001",
            "--to",
            "IN_PROGRESS",
            "--actor",
            "regression-test",
            "--reason",
            "ready to implement",
            "--timestamp",
            PINNED_TIMESTAMP,
        )
        self.assertEqual(legal.returncode, 0, legal.stderr)
        event = json.loads(legal.stdout)
        self.assertEqual((event["from"], event["to"], event["sequence"]), ("OPEN", "IN_PROGRESS", 1))

        illegal = run_cli(
            "gap-transition",
            pack,
            "GAP-001",
            "--to",
            "BLOCKED",
            "--actor",
            "regression-test",
            "--reason",
            "illegal edge",
            "--timestamp",
            PINNED_TIMESTAMP,
        )
        self.assertEqual(illegal.returncode, 1)
        self.assertIn("GAP_ILLEGAL_TRANSITION: illegal gap transition: IN_PROGRESS -> BLOCKED", illegal.stderr)
        index = read_json(pack / "clone_index.json")
        self.assertEqual(index["records"][0]["attributes"]["status"], "IN_PROGRESS")
        history = [json.loads(line) for line in (pack / "history" / "gap_events.jsonl").read_text(encoding="utf-8").splitlines()]
        self.assertEqual(len(history), 1)

        dependency_pack = self.assert_init_ok("dependency-gap-pack")
        self.add_records(
            dependency_pack,
            [
                {
                    "id": "GAP-001",
                    "kind": "GAP",
                    "links": {"dependencies": ["GAP-002"]},
                    "attributes": {"status": "OPEN", "readiness": "READY"},
                },
                {
                    "id": "GAP-002",
                    "kind": "GAP",
                    "links": {"dependencies": []},
                    "attributes": {"status": "OPEN", "readiness": "READY"},
                },
            ],
        )
        blocked = run_cli(
            "gap-transition",
            dependency_pack,
            "GAP-001",
            "--to",
            "IN_PROGRESS",
            "--actor",
            "regression-test",
            "--reason",
            "dependency is still open",
            "--timestamp",
            PINNED_TIMESTAMP,
        )
        self.assertEqual(blocked.returncode, 1)
        self.assertIn("GAP_DEP_UNSATISFIED: unverified gap dependencies: GAP-002", blocked.stderr)
        blocked_index = read_json(dependency_pack / "clone_index.json")
        self.assertEqual(blocked_index["records"][0]["attributes"]["status"], "OPEN")
        self.assertEqual((dependency_pack / "history" / "gap_events.jsonl").read_text(encoding="utf-8"), "")

    def test_process_filesystem_and_manual_capture_are_local_and_separated(self) -> None:
        pack = self.assert_init_ok()
        fixture_dir = self.repo_root / "fixture-tree"
        fixture_dir.mkdir()
        fixture_bytes = b"filesystem fixture\n"
        (fixture_dir / "sample.txt").write_bytes(fixture_bytes)
        manual_bytes = b"manual evidence\x00\n"
        (pack / "manual-source.bin").write_bytes(manual_bytes)
        plan_path = pack / "capture_plan.json"
        plan = read_json(plan_path)
        plan["cases"] = [
            {
                "id": "CAP-001",
                "adapter": "process",
                "side": "clone",
                "environment_id": "ENV-001",
                "required": True,
                "authorization_decision_ids": [],
                "safe_test_environment": True,
                "timeout_seconds": 10,
                "input": {
                    "argv": [
                        sys.executable,
                        "-c",
                        "import sys;sys.stdout.buffer.write(b'OUT\\x00');sys.stderr.buffer.write(b'ERR\\n')",
                    ],
                    "cwd": ".",
                    "environment": {},
                },
                "lifecycle": {"setup": None, "teardown": None},
                "redactions": [],
                "result": None,
            },
            {
                "id": "CAP-002",
                "adapter": "filesystem",
                "side": "clone",
                "environment_id": "ENV-001",
                "required": True,
                "authorization_decision_ids": [],
                "safe_test_environment": True,
                "timeout_seconds": 10,
                "input": {"path": "fixture-tree"},
                "lifecycle": {"setup": None, "teardown": None},
                "redactions": [],
                "result": None,
            },
            {
                "id": "CAP-003",
                "adapter": "manual",
                "side": "reference",
                "environment_id": "ENV-001",
                "required": True,
                "authorization_decision_ids": [],
                "safe_test_environment": True,
                "timeout_seconds": 10,
                "input": {"source_path": "manual-source.bin"},
                "lifecycle": {"setup": None, "teardown": None},
                "redactions": [],
                "result": None,
            },
        ]
        write_json(plan_path, plan)
        self.add_records(pack, self.plan_case_records(pack, "capture"))

        results = [run_cli("capture", pack, "--case", case_id) for case_id in ("CAP-001", "CAP-002", "CAP-003")]
        self.assertEqual([result.returncode for result in results], [0, 0, 0], [result.stderr for result in results])
        self.assertEqual((pack / "evidence" / "captures" / "CAP-001" / "stdout.bin").read_bytes(), b"OUT\x00")
        self.assertEqual((pack / "evidence" / "captures" / "CAP-001" / "stderr.bin").read_bytes(), b"ERR\n")
        process_metadata = read_json(pack / "evidence" / "captures" / "CAP-001" / "process.json")
        self.assertEqual(process_metadata["exit_code"], 0)
        snapshot = read_json(pack / "evidence" / "captures" / "CAP-002" / "filesystem.json")
        file_entry = next(entry for entry in snapshot["entries"] if entry["path"] == "sample.txt")
        self.assertEqual(file_entry["sha256"], hashlib.sha256(fixture_bytes).hexdigest())
        self.assertEqual(
            (pack / "evidence" / "captures" / "CAP-003" / "manual" / "manual-source.bin").read_bytes(),
            manual_bytes,
        )
        updated = read_json(plan_path)
        self.assertEqual([case["result"]["status"] for case in updated["cases"]], ["PASS", "PASS", "PASS"])

    def test_parity_records_pass_and_fail_without_normalizing_differences(self) -> None:
        pack = self.assert_init_ok()
        sources = {
            "reference-pass.bin": b"same\n",
            "clone-pass.bin": b"same\n",
            "reference-fail.bin": b"expected\n",
            "clone-fail.bin": b"actual\n",
        }
        for name, content in sources.items():
            (pack / name).write_bytes(content)
        capture_plan = read_json(pack / "capture_plan.json")
        capture_plan["cases"] = [
            {
                "id": case_id,
                "adapter": "manual",
                "side": side,
                "environment_id": "ENV-001",
                "required": True,
                "authorization_decision_ids": [],
                "safe_test_environment": True,
                "timeout_seconds": 10,
                "input": {"source_path": source_path},
                "lifecycle": {"setup": None, "teardown": None},
                "redactions": [],
                "result": None,
            }
            for case_id, side, source_path in (
                ("CAP-101", "reference", "reference-pass.bin"),
                ("CAP-102", "clone", "clone-pass.bin"),
                ("CAP-103", "reference", "reference-fail.bin"),
                ("CAP-104", "clone", "clone-fail.bin"),
            )
        ]
        write_json(pack / "capture_plan.json", capture_plan)
        parity_plan = read_json(pack / "parity_plan.json")
        parity_plan["cases"] = [
            {
                "id": "PAR-001",
                "comparator": "exact",
                "required": True,
                "reference_capture_id": "CAP-101",
                "clone_capture_id": "CAP-102",
                "normalizations": [],
                "result": None,
            },
            {
                "id": "PAR-002",
                "comparator": "exact",
                "required": True,
                "reference_capture_id": "CAP-103",
                "clone_capture_id": "CAP-104",
                "normalizations": [],
                "result": None,
            },
        ]
        write_json(pack / "parity_plan.json", parity_plan)
        self.add_records(pack, self.plan_case_records(pack, "capture", "parity"))
        for capture_id in ("CAP-101", "CAP-102", "CAP-103", "CAP-104"):
            captured = run_cli("capture", pack, "--case", capture_id)
            self.assertEqual(captured.returncode, 0, captured.stderr)

        passing = run_cli("parity", pack, "--case", "PAR-001")
        failing = run_cli("parity", pack, "--case", "PAR-002")

        self.assertEqual(passing.returncode, 0, passing.stderr)
        self.assertEqual(json.loads(passing.stdout)["status"], "PASS")
        self.assertEqual(failing.returncode, 5)
        failed_result = json.loads(failing.stdout)
        self.assertEqual(failed_result["status"], "FAIL")
        self.assertEqual(failed_result["details"], ["artifact pair 1 differs"])

    def test_scaffold_dry_run_writes_nothing_and_collision_halts(self) -> None:
        pack = self.assert_init_ok()
        plan_path = pack / "scaffold_plan.json"
        plan = read_json(plan_path)
        catalog = read_json(SKILL_ROOT / "assets" / "scaffolds" / "catalog.json")
        profile = next(item for item in catalog["profiles"] if item["id"] == "python-src")
        plan.update(
            {
                "stack_decision_id": "STACK-001",
                "profile_id": "python-src",
                "template": profile["template"],
                "output_root": "generated",
                "required_paths": profile["required_paths"],
                "commands": profile["commands"],
            }
        )
        write_json(plan_path, plan)

        preview = run_cli("scaffold", pack)
        self.assertEqual(preview.returncode, 0, preview.stderr)
        payload = json.loads(preview.stdout)
        self.assertFalse(payload["applied"])
        self.assertIn("generated/README.md", payload["files"])
        self.assertFalse((self.repo_root / "generated").exists())

        collision_path = self.repo_root / "generated" / "README.md"
        collision_path.parent.mkdir()
        collision_path.write_text("owned by the caller\n", encoding="utf-8", newline="\n")
        collision = run_cli("scaffold", pack)
        self.assertEqual(collision.returncode, 1)
        self.assertEqual(collision.stdout, "")
        self.assertIn("SCAFFOLD_COLLISION: scaffold collisions: generated/README.md", collision.stderr)
        self.assertEqual(collision_path.read_text(encoding="utf-8"), "owned by the caller\n")

    def test_missing_assurance_executable_is_recorded_as_blocked(self) -> None:
        pack = self.assert_init_ok()
        plan_path = pack / "assurance_plan.json"
        plan = read_json(plan_path)
        plan["risk_profile"] = "local-evaluation"
        plan["cases"] = [
            {
                "id": "ASSURE-001",
                "kind": "static",
                "required": True,
                "argv": ["clone-pack-executable-that-does-not-exist-7c55a6f5"],
                "cwd": ".",
                "timeout_seconds": 10,
                "expected_exit": 0,
                "result": None,
            }
        ]
        write_json(plan_path, plan)
        self.add_records(pack, self.plan_case_records(pack, "assurance"))

        result = run_cli("assure", pack, "--case", "ASSURE-001")
        evidence = read_json(pack / "evidence" / "assurance" / "ASSURE-001" / "result.json")
        updated = read_json(plan_path)

        self.assertEqual(result.returncode, 7)
        self.assertEqual(result.stdout, "")
        self.assertEqual(result.stderr, "")
        self.assertEqual(evidence["status"], "BLOCKED")
        self.assertEqual(evidence["diagnostic"]["code"], "CAPABILITY_MISSING")
        self.assertEqual(updated["cases"][0]["result"]["status"], "BLOCKED")

    def test_v1_migration_is_non_overwriting_and_downgrades_verified_claims(self) -> None:
        source = self.temp_root / "legacy-v1"
        source.mkdir()
        legacy_documents = [
            "clone_brief.md",
            "evidence_ledger.md",
            "clone_specification.md",
            "mvp_build_plan.md",
            "acceptance_matrix.md",
            "gaps_analysis.md",
            "gap_implementation_plan.md",
        ]
        manifest = {
            "schema_version": "clone-pack/v1",
            "pack_id": "clone-legacy-regression-2024-01-02",
            "product_name": "Legacy Regression",
            "product_type": "cli",
            "reference_source": "Pinned legacy fixture",
            "created_at": "2024-01-02T03:04:05+00:00",
            "repository_root": self.repo_root.as_posix(),
            "documents": legacy_documents,
        }
        write_json(source / "clone_pack.json", manifest)
        for document in legacy_documents:
            (source / document).write_text(f"# Legacy {document}\n", encoding="utf-8", newline="\n")
        (source / "clone_specification.md").write_text(
            "# Legacy specification\n\n### REQ-001 - VERIFIED implementation\n",
            encoding="utf-8",
            newline="\n",
        )
        (source / "gaps_analysis.md").write_text(
            "# Legacy gaps\n\n### GAP-001 - VERIFIED gap\n",
            encoding="utf-8",
            newline="\n",
        )
        source_before = tree_bytes(source)
        destination = self.temp_root / "migrated-v2"

        migrated = run_cli(
            "migrate",
            source,
            "--output",
            destination,
            "--timestamp",
            PINNED_TIMESTAMP,
        )
        self.assertEqual(migrated.returncode, 0, migrated.stderr)
        self.assertEqual(tree_bytes(source), source_before)
        index = read_json(destination / "clone_index.json")
        records = {record["id"]: record for record in index["records"]}
        self.assertEqual(records["REQ-001"]["attributes"]["verification_status"], "IMPLEMENTED_UNVERIFIED")
        self.assertEqual(records["GAP-001"]["attributes"]["status"], "IMPLEMENTED")
        report = read_json(
            destination
            / "history"
            / "migrations"
            / "MIG-001"
            / "migration_report.json"
        )
        self.assertEqual(report["tool_version"], TOOL_VERSION)
        downgrades = {
            item["record_id"]: item for item in report["status_downgrades"]
        }
        self.assertEqual(set(downgrades), {"REQ-001", "GAP-001"})
        self.assertEqual(
            (downgrades["REQ-001"]["kind"], downgrades["REQ-001"]["migrated_status"]),
            ("REQ", "IMPLEMENTED_UNVERIFIED"),
        )
        self.assertEqual(
            (downgrades["GAP-001"]["kind"], downgrades["GAP-001"]["migrated_status"]),
            ("GAP", "IMPLEMENTED"),
        )
        verification_loss = report["unresolved_losses"][2]
        self.assertEqual(
            (
                verification_loss["sequence"],
                verification_loss["loss_id"],
                verification_loss["category"],
            ),
            (3, "LOSS-003", "verification-evidence-reconciliation"),
        )
        self.assertEqual(
            verification_loss["affected_record_ids"],
            ["GAP-001", "REQ-001"],
        )
        self.assertEqual(
            verification_loss["source_paths"],
            ["clone_specification.md", "gaps_analysis.md"],
        )
        self.assertEqual(
            (
                destination
                / "history"
                / "migrations"
                / "MIG-001"
                / "source"
                / "clone_specification.md"
            ).read_bytes(),
            (source / "clone_specification.md").read_bytes(),
        )
        destination_before = tree_bytes(destination)

        repeated = run_cli("migrate", source, "--output", destination, "--timestamp", PINNED_TIMESTAMP)
        self.assertEqual(repeated.returncode, 6)
        self.assertIn("MIGRATION_DESTINATION_EXISTS:", repeated.stderr)
        self.assertEqual(tree_bytes(destination), destination_before)
        self.assertEqual(tree_bytes(source), source_before)


if __name__ == "__main__":
    unittest.main()
