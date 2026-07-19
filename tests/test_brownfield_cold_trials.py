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

from scripts.clonepack.common import ClonePackError, canonical_json, case_contract_sha256
from scripts.clonepack.enhancement import (
    initialize_enhancement_v2,
    run_preservation_baseline,
    run_preservation_regression,
)
from scripts.clonepack.repository import repository_snapshot


ROOT = Path(__file__).resolve().parents[1]
CLONE_PACK = ROOT / "scripts" / "clone_pack.py"
PINNED_TIMESTAMP = "2026-07-19T16:00:00+00:00"


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
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
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


class BrownfieldColdForwardTrials(unittest.TestCase):
    """Cold, executable acceptance trials for the complete brownfield workflow."""

    maxDiff = None

    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.temporary_root = Path(temporary.name)

    def _write_repository(self, name: str, files: dict[str, str], *, git: bool) -> tuple[Path, str | None]:
        repository = self.temporary_root / name
        repository.mkdir()
        for relative, content in files.items():
            path = repository / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8", newline="\n")
        if not git:
            return repository, None

        initialized = run_git(repository, "init", "-q", "-b", "main")
        self.assertEqual(initialized.returncode, 0, initialized.stderr)
        for key, value in (
            ("user.name", "Cold Trial Fixture"),
            ("user.email", "cold-trial@example.invalid"),
        ):
            configured = run_git(repository, "config", key, value)
            self.assertEqual(configured.returncode, 0, configured.stderr)
        added = run_git(repository, "add", ".")
        self.assertEqual(added.returncode, 0, added.stderr)
        committed = run_git(repository, "commit", "-q", "-m", "adopted fixture")
        self.assertEqual(committed.returncode, 0, committed.stderr)
        head = run_git(repository, "rev-parse", "HEAD")
        self.assertEqual(head.returncode, 0, head.stderr)
        return repository, head.stdout.strip()

    def _initialize_api(
        self,
        repository: Path,
        *,
        product_name: str,
        product_type: str,
        playbooks: list[str],
        title: str,
        change_types: list[str],
    ) -> Path:
        result = initialize_enhancement_v2(
            skill_root=ROOT,
            product_name=product_name,
            product_type=product_type,
            playbooks=playbooks,
            enhancement_id="ENH-001",
            title=title,
            change_types=change_types,
            request_file=repository / "request.md",
            repo_root=repository,
            output_dir=Path("clone-pack"),
            timestamp=PINNED_TIMESTAMP,
        )
        pack = repository / "clone-pack"
        self.assertEqual(
            result,
            {
                "schema_version": "clone-enhancement-init-result/v2",
                "enhancement_id": "ENH-001",
                "pack_path": pack.resolve().as_posix(),
                "status": "DRAFT",
                "workstream": "brownfield-enhancement",
            },
        )
        return pack

    def _initialize_cli(
        self,
        repository: Path,
        *,
        product_name: str,
        product_type: str,
        playbooks: list[str],
        title: str,
        change_types: list[str],
    ) -> Path:
        arguments: list[object] = [
            "enhancement-init",
            "--product-name",
            product_name,
            "--product-type",
            product_type,
        ]
        for playbook in playbooks:
            arguments.extend(("--playbook", playbook))
        arguments.extend(
            (
                "--enhancement-id",
                "ENH-001",
                "--title",
                title,
            )
        )
        for change_type in change_types:
            arguments.extend(("--change-type", change_type))
        arguments.extend(
            (
                "--request-file",
                repository / "request.md",
                "--repo-root",
                repository,
                "--output-dir",
                "clone-pack",
                "--timestamp",
                PINNED_TIMESTAMP,
            )
        )
        initialized = run_cli(*arguments)
        self.assertEqual(initialized.returncode, 0, initialized.stderr)
        payload = self._canonical_payload(initialized)
        pack = repository / "clone-pack"
        self.assertEqual(
            {key: payload[key] for key in ("enhancement_id", "pack_path", "status")},
            {
                "enhancement_id": "ENH-001",
                "pack_path": pack.resolve().as_posix(),
                "status": "DRAFT",
            },
        )
        return pack

    def _canonical_payload(self, completed: subprocess.CompletedProcess[str]) -> dict[str, Any]:
        self.assertNotEqual(completed.stdout, "", completed.stderr)
        value = json.loads(completed.stdout)
        self.assertIsInstance(value, dict)
        self.assertEqual(completed.stdout, canonical_json(value))
        return value

    @staticmethod
    def _case(
        argv: list[str],
        *,
        known_failure: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return {
            "id": "PRES-001",
            "required": True,
            "argv": argv,
            "cwd": ".",
            "environment": {},
            "timeout_seconds": 30,
            "expected_exit": 0,
            "artifact_paths": [],
            "comparator": "exact",
            "normalizations": [],
            "options": {},
            "redactions": [],
            "known_failure": known_failure,
            "result": {"baseline": None, "regression": None},
        }

    def _add_index_records(
        self,
        pack: Path,
        specifications: list[dict[str, Any]],
        *,
        link_updates: dict[str, dict[str, list[str]]] | None = None,
    ) -> None:
        index_path = pack / "clone_index.json"
        index = read_json(index_path)
        records = {str(record["id"]): record for record in index["records"]}
        for identifier, relations in (link_updates or {}).items():
            self.assertIn(identifier, records)
            links = records[identifier].setdefault("links", {})
            for relation, targets in relations.items():
                links[relation] = sorted(targets)

        document = pack / "clone_brief.md"
        text = document.read_text(encoding="utf-8").rstrip("\n") + "\n"
        starting_position = len(records) + 1
        for offset, specification in enumerate(specifications):
            identifier = str(specification["id"])
            self.assertNotIn(identifier, records)
            anchor = f"{identifier} cold-forward definition {starting_position + offset}"
            line = f"- {anchor}\n"
            text += line
            record = {
                "id": identifier,
                "kind": specification["kind"],
                "locator": {
                    "path": "clone_brief.md",
                    "anchor": anchor,
                    "sha256": hashlib.sha256(line.encode("utf-8")).hexdigest(),
                },
                "links": specification.get("links", {}),
                "applicability": specification.get("applicability", "REQUIRED"),
                "state": specification.get("state", "READY"),
                "attributes": specification.get("attributes", {}),
            }
            index["records"].append(record)
            records[identifier] = record
        document.write_text(text, encoding="utf-8", newline="\n")
        write_json(index_path, index)

        manifest_path = pack / "clone_pack.json"
        manifest = read_json(manifest_path)
        document_entry = next(entry for entry in manifest["documents"] if entry["path"] == "clone_brief.md")
        document_entry["sha256"] = hashlib.sha256(document.read_bytes()).hexdigest()
        write_json(manifest_path, manifest)

    def _configure_baseline_contract(
        self,
        pack: Path,
        *,
        case: dict[str, Any],
        decision_records: list[dict[str, Any]],
    ) -> None:
        decision_ids = [str(record["id"]) for record in decision_records]
        plan_path = pack / "enhancement_plan.json"
        plan = read_json(plan_path)
        plan["authority_ids"] = decision_ids
        plan["preservation_cases"] = [case]
        write_json(plan_path, plan)

        self._add_index_records(
            pack,
            [
                *decision_records,
                {
                    "id": str(case["id"]),
                    "kind": "PRES",
                    "state": "READY",
                    "links": {
                        "enhancements": ["ENH-001"],
                        "decisions": list((case.get("known_failure") or {}).get("decision_ids", [])),
                    },
                    "attributes": {"case_sha256": case_contract_sha256(case)},
                },
            ],
            link_updates={
                "ENH-001": {
                    "decisions": decision_ids,
                    "preservations": [str(case["id"])],
                }
            },
        )

    @staticmethod
    def _ordered_step(order: int, action: str, preconditions: str) -> dict[str, Any]:
        return {
            "order": order,
            "action": action,
            "preconditions": preconditions,
            "verification_ids": ["GATE-001"],
        }

    def _configure_full_plan(
        self,
        pack: Path,
        *,
        allowed_paths: list[str],
        change_map: list[dict[str, Any]],
        affected_surfaces: list[str],
        compatibility: list[dict[str, Any]],
        gate_argv: list[str],
        requirement_statement: str,
        acceptance_statement: str,
        invariant_statement: str,
        extra_records: list[dict[str, Any]] | None = None,
        plan_updates: dict[str, Any] | None = None,
    ) -> None:
        plan_path = pack / "enhancement_plan.json"
        plan = read_json(plan_path)
        self.assertEqual(plan["status"], "READY")
        decision_ids = [str(identifier) for identifier in plan["authority_ids"]]
        gate = {
            "id": "GATE-001",
            "required": True,
            "argv": gate_argv,
            "cwd": ".",
            "environment": {},
            "timeout_seconds": 30,
            "expected_exit": 0,
            "result_id": None,
        }
        plan.update(
            {
                "target_requirements": ["REQ-001"],
                "invariants": [
                    {
                        "id": "INV-001",
                        "statement": invariant_statement,
                        "verification_ids": ["TEST-001", "GATE-001"],
                    }
                ],
                "impact_edges": [
                    {
                        "id": f"IMPACT-{position:03d}",
                        "source_id": surface_id,
                        "target_id": "REQ-001",
                        "kind": "depends-on",
                        "reason": f"{surface_id} is changed only through REQ-001.",
                        "evidence_ids": ["E-001"],
                    }
                    for position, surface_id in enumerate(affected_surfaces, 1)
                ],
                "affected_surfaces": affected_surfaces,
                "compatibility": compatibility,
                "delivery_strategy": "in-place",
                "feature_flag": None,
                "expand_contract": None,
                "scope": {
                    "allowed_paths": allowed_paths,
                    "forbidden_paths": [".github", "deploy", "production"],
                    "generated_paths": [
                        path
                        for change in change_map
                        if change["generated"] is True
                        for path in change["paths"]
                    ],
                    "rename_policy": "forbid",
                    "declared_renames": [],
                    "protected_dirty_paths": [],
                },
                "change_map": change_map,
                "slices": [
                    {
                        "id": "SLICE-001",
                        "order": 1,
                        "title": "Implement and verify the complete bounded enhancement delta.",
                        "change_ids": [str(change["id"]) for change in change_map],
                        "depends_on": [],
                        "test_ids": ["TEST-001"],
                        "gate_ids": ["GATE-001"],
                        "acceptance": acceptance_statement,
                    }
                ],
                "gates": [gate],
                "assurance": {"required_ids": [], "result_ids": []},
                "rollout": {
                    "strategy": "verified-code-handoff",
                    "steps": [
                        self._ordered_step(
                            1,
                            "Hand off the verified working tree without deploying or merging it.",
                            "The current candidate snapshot, preservation regression, gate run, and scope result all pass.",
                        )
                    ],
                    "deployment_permitted": False,
                },
                "rollback": {
                    "application": [
                        self._ordered_step(
                            1,
                            "Restore every changed application path from the adopted SNAP-001 bytes.",
                            "A candidate verification result fails before any deployment or merge.",
                        )
                    ],
                    "data": [],
                },
                "recovery": {
                    "steps": [
                        self._ordered_step(
                            1,
                            "Run GATE-001 against the restored working tree and retain its result.",
                            "The application rollback step completed without modifying repository history.",
                        )
                    ],
                    "verification_commands": [
                        {
                            "id": "GATE-001",
                            "argv": gate_argv,
                            "cwd": ".",
                            "expected_exit": 0,
                            "timeout_seconds": 30,
                        }
                    ],
                },
            }
        )
        if plan_updates:
            plan.update(plan_updates)
        write_json(plan_path, plan)

        kind_by_prefix = {"SURF": "SURF", "IF": "IF", "DATA": "DATA", "COMP": "COMP"}
        surface_records = []
        for identifier in affected_surfaces:
            kind = kind_by_prefix[identifier.split("-", 1)[0]]
            attributes = {"contract": f"{identifier} is governed by REQ-001."}
            if kind == "SURF":
                attributes["disposition"] = "EQUIVALENT"
            surface_records.append(
                {
                    "id": identifier,
                    "kind": kind,
                    "state": "READY",
                    "links": {"enhancements": ["ENH-001"], "requirements": ["REQ-001"]},
                    "attributes": attributes,
                }
            )

        trace_records = [
            {
                "id": "E-001",
                "kind": "E",
                "state": "READY",
                "links": {"requirements": ["REQ-001"]},
                "attributes": {
                    "source": "The adopted repository and authorized request define the cold-forward oracle.",
                    "investigation_only": False,
                },
            },
            {
                "id": "REQ-001",
                "kind": "REQ",
                "state": "READY",
                "links": {
                    "evidence": ["E-001"],
                    "decisions": decision_ids,
                    "acceptance": ["AC-001"],
                    "tests": ["TEST-001"],
                    "enhancements": ["ENH-001"],
                },
                "attributes": {
                    "statement": requirement_statement,
                    "implementation_locator": ", ".join(allowed_paths),
                    "mvp": True,
                },
            },
            {
                "id": "AC-001",
                "kind": "AC",
                "state": "READY",
                "links": {"requirements": ["REQ-001"], "tests": ["TEST-001"]},
                "attributes": {"criterion": acceptance_statement},
            },
            {
                "id": "TEST-001",
                "kind": "TEST",
                "state": "READY",
                "links": {
                    "requirements": ["REQ-001"],
                    "acceptance": ["AC-001"],
                    "oracles": ["E-001"],
                    "gates": ["GATE-001"],
                },
                "attributes": {
                    "discriminating": True,
                    "procedure": "Execute GATE-001 in ENV-001 and require its exact exit-zero contract.",
                },
            },
            {
                "id": "ENV-001",
                "kind": "ENV",
                "state": "READY",
                "links": {},
                "attributes": {"name": "isolated cold-forward local process environment"},
            },
            {
                "id": "GATE-001",
                "kind": "GATE",
                "state": "READY",
                "links": {"tests": ["TEST-001"], "enhancements": ["ENH-001"]},
                "attributes": {
                    "argv": gate_argv,
                    "cwd": ".",
                    "environment": {},
                    "timeout_seconds": 30,
                    "expected_exit": 0,
                    "covered_ids": ["REQ-001", "AC-001", "TEST-001"],
                    "oracle_ids": ["E-001"],
                    "artifact_paths": [],
                    "normalizations": [],
                    "redactions": [],
                },
            },
            {
                "id": "INV-001",
                "kind": "INV",
                "state": "READY",
                "links": {"enhancements": ["ENH-001"]},
                "attributes": {
                    "statement": invariant_statement,
                    "verification_ids": ["TEST-001", "GATE-001"],
                },
            },
            *[
                {
                    "id": str(change["id"]),
                    "kind": "CHANGE",
                    "state": "READY",
                    "links": {"enhancements": ["ENH-001"], "requirements": ["REQ-001"]},
                    "attributes": dict(change),
                }
                for change in change_map
            ],
            *(extra_records or []),
        ]
        extra_ids_by_kind: dict[str, list[str]] = {}
        for record in extra_records or []:
            extra_ids_by_kind.setdefault(str(record["kind"]), []).append(str(record["id"]))
        enhancement_links = {
            "requirements": ["REQ-001"],
            "invariants": ["INV-001"],
            "changes": [str(change["id"]) for change in change_map],
            "gates": ["GATE-001"],
            "surfaces": [identifier for identifier in affected_surfaces if identifier.startswith("SURF-")],
            "interfaces": [identifier for identifier in affected_surfaces if identifier.startswith("IF-")],
        }
        if extra_ids_by_kind.get("GAP"):
            enhancement_links["gaps"] = extra_ids_by_kind["GAP"]
        if extra_ids_by_kind.get("HALT"):
            enhancement_links["halts"] = extra_ids_by_kind["HALT"]
        link_updates = {"ENH-001": enhancement_links}
        for decision_id in decision_ids:
            link_updates[decision_id] = {
                "enhancements": ["ENH-001"],
                "requirements": ["REQ-001"],
            }
        self._add_index_records(pack, [*surface_records, *trace_records], link_updates=link_updates)

    def _record_snapshot_api(self, pack: Path, role: str) -> dict[str, Any]:
        result, exit_code = repository_snapshot(
            pack,
            role,
            record=True,
            check=False,
            timestamp=PINNED_TIMESTAMP,
        )
        self.assertEqual(exit_code, 0, result)
        self.assertEqual(result["status"], "RECORDED")
        self.assertEqual(result["role"], role)
        return result

    def _check_snapshot_api(self, pack: Path, role: str) -> dict[str, Any]:
        result, exit_code = repository_snapshot(pack, role, record=False, check=True)
        self.assertEqual(exit_code, 0, result)
        self.assertEqual(result["status"], "MATCH")
        return result

    def _transition_cli(
        self,
        pack: Path,
        *,
        from_status: str,
        to_status: str,
        sequence: int,
        evidence_ids: list[str],
        decision_ids: list[str],
        reason: str,
    ) -> dict[str, Any]:
        arguments: list[object] = [
            "enhancement-transition",
            pack,
            "ENH-001",
            "--to",
            to_status,
            "--actor",
            "cold-trial-owner",
            "--reason",
            reason,
        ]
        for evidence_id in evidence_ids:
            arguments.extend(("--evidence", evidence_id))
        for decision_id in decision_ids:
            arguments.extend(("--decision", decision_id))
        arguments.extend(("--timestamp", PINNED_TIMESTAMP))
        completed = run_cli(*arguments)
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(completed.stderr, "")
        event = self._canonical_payload(completed)
        self.assertEqual(
            {
                key: event[key]
                for key in (
                    "enhancement_id",
                    "sequence",
                    "from",
                    "to",
                    "actor",
                    "evidence_ids",
                    "decision_ids",
                    "reason",
                )
            },
            {
                "enhancement_id": "ENH-001",
                "sequence": sequence,
                "from": from_status,
                "to": to_status,
                "actor": "cold-trial-owner",
                "evidence_ids": evidence_ids,
                "decision_ids": decision_ids,
                "reason": reason,
            },
        )
        self.assertEqual(event["previous_event_sha256"] == "", sequence == 1)
        if sequence > 1:
            self.assertEqual(len(event["previous_event_sha256"]), 64)
        self.assertEqual(len(event["event_sha256"]), 64)
        return event

    def _record_gate_cli(self, pack: Path, candidate_id: str) -> dict[str, Any]:
        completed = run_cli(
            "record-run",
            pack,
            "--gate",
            "GATE-001",
            "--environment",
            "ENV-001",
            "--timestamp",
            PINNED_TIMESTAMP,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(completed.stderr, "")
        run = self._canonical_payload(completed)
        self.assertEqual(
            {
                key: run[key]
                for key in (
                    "run_id",
                    "result",
                    "gate_id",
                    "environment_id",
                    "covered_ids",
                    "oracle_ids",
                    "clone_revision",
                )
            },
            {
                "run_id": "RUN-001",
                "result": "PASS",
                "gate_id": "GATE-001",
                "environment_id": "ENV-001",
                "covered_ids": ["AC-001", "REQ-001", "TEST-001"],
                "oracle_ids": ["E-001"],
                "clone_revision": candidate_id,
            },
        )
        self.assertEqual(len(run["clone_diff_sha256"]), 64)
        return run

    def _configure_required_assurance(self, pack: Path) -> None:
        case = {
            "id": "ASSURE-001",
            "kind": "threat-model",
            "required": True,
            "argv": [sys.executable, "-c", "print('threat-model-pass')"],
            "cwd": ".",
            "timeout_seconds": 30,
            "expected_exit": 0,
            "artifact_paths": [],
            "result": None,
        }
        assurance_path = pack / "assurance_plan.json"
        assurance_plan = read_json(assurance_path)
        assurance_plan["risk_profile"] = "local-evaluation"
        assurance_plan["cases"] = [case]
        write_json(assurance_path, assurance_plan)

        enhancement_path = pack / "enhancement_plan.json"
        enhancement_plan = read_json(enhancement_path)
        enhancement_plan["assurance"] = {
            "required_ids": ["ASSURE-001"],
            "result_ids": [],
        }
        write_json(enhancement_path, enhancement_plan)
        self._add_index_records(
            pack,
            [
                {
                    "id": "ASSURE-001",
                    "kind": "ASSURE",
                    "state": "READY",
                    "links": {"enhancements": ["ENH-001"]},
                    "attributes": {"case_sha256": case_contract_sha256(case)},
                }
            ],
            link_updates={"ENH-001": {"assurance": ["ASSURE-001"]}},
        )

    def _seal_and_validate_cli(self, pack: Path) -> dict[str, Any]:
        sealed = run_cli(
            "seal",
            pack,
            "--profile",
            "verified-enhancement",
            "--timestamp",
            PINNED_TIMESTAMP,
        )
        self.assertEqual(sealed.returncode, 0, sealed.stderr)
        self.assertEqual(sealed.stderr, "")
        seal = self._canonical_payload(sealed)
        self.assertEqual(seal["profile"], "verified-enhancement")
        self.assertEqual(seal["verdict"], "PASS")
        self.assertEqual(seal["pack_revision"], 1)
        self.assertIn("enhancement_bindings", seal)

        validated = run_cli(
            "validate",
            pack,
            "--profile",
            "verified-enhancement",
            "--format",
            "json",
            "--max-problems",
            "0",
        )
        self.assertEqual(validated.returncode, 0, validated.stderr)
        self.assertEqual(validated.stderr, "")
        validation = self._canonical_payload(validated)
        self.assertEqual(validation["status"], "PASS")
        self.assertEqual(validation["diagnostics"], [])
        return seal

    def _assert_baseline_immutable(self, pack: Path, result_path: str) -> None:
        retained = pack / result_path
        before = retained.read_bytes()
        with self.assertRaises(ClonePackError) as raised:
            run_preservation_baseline(
                pack,
                ["PRES-001"],
                timestamp=PINNED_TIMESTAMP,
            )
        self.assertEqual(raised.exception.diagnostic, "BASELINE_IMMUTABLE")
        self.assertEqual(retained.read_bytes(), before)

    def _assert_adopted_snapshot_immutable(self, pack: Path, snapshot_path: str) -> None:
        retained = pack / snapshot_path
        before = retained.read_bytes()
        with self.assertRaises(ClonePackError) as raised:
            repository_snapshot(
                pack,
                "adopted",
                record=True,
                check=False,
                timestamp=PINNED_TIMESTAMP,
            )
        self.assertEqual(raised.exception.diagnostic, "ADOPTED_SNAPSHOT_IMMUTABLE")
        self.assertEqual(retained.read_bytes(), before)

    def _assert_git_has_no_delivery_side_effects(self, repository: Path, adopted_head: str) -> None:
        head = run_git(repository, "rev-parse", "HEAD")
        self.assertEqual(head.returncode, 0, head.stderr)
        self.assertEqual(head.stdout.strip(), adopted_head)
        count = run_git(repository, "rev-list", "--count", "HEAD")
        self.assertEqual(count.returncode, 0, count.stderr)
        self.assertEqual(count.stdout.strip(), "1")
        staged = run_git(repository, "diff", "--cached", "--name-only")
        self.assertEqual(staged.returncode, 0, staged.stderr)
        self.assertEqual(staged.stdout, "")
        remotes = run_git(repository, "remote")
        self.assertEqual(remotes.returncode, 0, remotes.stderr)
        self.assertEqual(remotes.stdout, "")
        self.assertFalse((repository / ".git" / "MERGE_HEAD").exists())
        self.assertFalse((repository / "deployed.marker").exists())

    def _assert_non_git_has_no_delivery_side_effects(self, repository: Path) -> None:
        self.assertFalse((repository / ".git").exists())
        self.assertFalse((repository / "deployed.marker").exists())
        self.assertFalse((repository / "merged.marker").exists())

    def test_git_web_api_additive_feature_preserves_existing_health_contract(self) -> None:
        repository, adopted_head = self._write_repository(
            "git-web-api",
            {
                "api.py": (
                    "import sys\n"
                    "if sys.argv[1:] == ['health']:\n"
                    "    print('{\"status\":\"ok\"}')\n"
                    "else:\n"
                    "    raise SystemExit(2)\n"
                ),
                "web/index.html": "<!doctype html><title>Inventory</title>\n",
                "request.md": "# Add export\n\nAdd an export page and API without changing health behavior.\n",
            },
            git=True,
        )
        self.assertIsNotNone(adopted_head)
        pack = self._initialize_api(
            repository,
            product_name="Cold Web API",
            product_type="hybrid",
            playbooks=["web-app-saas", "api-service-server"],
            title="Add export page and API",
            change_types=["feature"],
        )
        case = self._case([sys.executable, "api.py", "health"])
        decisions = [
            {
                "id": "DEC-001",
                "kind": "DEC",
                "state": "READY",
                "links": {"enhancements": ["ENH-001"]},
                "attributes": {"decision": "Authorize only the additive export page and API paths."},
            }
        ]
        self._configure_baseline_contract(
            pack,
            case=case,
            decision_records=decisions,
        )

        adopted = self._record_snapshot_api(pack, "adopted")
        self.assertEqual(adopted["snapshot_id"], "SNAP-001")
        self.assertEqual(adopted["snapshot_path"], "evidence/snapshots/SNAP-001.json")
        self.assertEqual(adopted["repository_kind"], "git")
        self._transition_cli(
            pack,
            from_status="DRAFT",
            to_status="READY",
            sequence=1,
            evidence_ids=["SNAP-001"],
            decision_ids=["DEC-001"],
            reason="The adopted Git tree is immutable and the preservation command is exact.",
        )
        baseline, baseline_exit = run_preservation_baseline(
            pack,
            ["PRES-001"],
            timestamp=PINNED_TIMESTAMP,
        )
        self.assertEqual(baseline_exit, 0, baseline)
        self.assertEqual(
            baseline,
            {
                "case_id": "PRES-001",
                "status": "PASS",
                "adopted_snapshot_id": "SNAP-001",
                "result_path": "evidence/preservation/PRES-001/baseline/result.json",
            },
        )
        baseline_bytes = (pack / baseline["result_path"]).read_bytes()
        self._assert_baseline_immutable(pack, baseline["result_path"])

        gate_argv = [
            sys.executable,
            "-c",
            (
                "from pathlib import Path; namespace = {}; "
                "exec(compile(Path('export_api.py').read_text(encoding='utf-8'), "
                "'export_api.py', 'exec'), namespace); "
                "assert namespace['export_rows']([1, 2]) == {'rows': [1, 2]}; "
                "assert Path('web/export.html').read_text(encoding='utf-8') == "
                "'<!doctype html><title>Export</title>\\n'"
            ),
        ]
        self._configure_full_plan(
            pack,
            allowed_paths=["export_api.py", "web/export.html"],
            change_map=[
                {
                    "id": "CHANGE-001",
                    "operation": "create",
                    "paths": ["export_api.py"],
                    "generated": False,
                    "requirement_ids": ["REQ-001"],
                    "slice_ids": ["SLICE-001"],
                },
                {
                    "id": "CHANGE-002",
                    "operation": "create",
                    "paths": ["web/export.html"],
                    "generated": False,
                    "requirement_ids": ["REQ-001"],
                    "slice_ids": ["SLICE-001"],
                },
            ],
            affected_surfaces=["SURF-001", "IF-001"],
            compatibility=[
                {
                    "surface_id": "SURF-001",
                    "disposition": "ADDITIVE",
                    "decision_ids": ["DEC-001"],
                    "reason": "web/export.html is additive and web/index.html remains byte-identical.",
                },
                {
                    "surface_id": "IF-001",
                    "disposition": "ADDITIVE",
                    "decision_ids": ["DEC-001"],
                    "reason": "export_api.py is additive and api.py health remains byte-identical.",
                }
            ],
            gate_argv=gate_argv,
            requirement_statement=(
                "Create export_api.py and web/export.html while preserving the exact api.py health output and exit code."
            ),
            acceptance_statement=(
                "GATE-001 returns exit 0, export_rows([1, 2]) returns {'rows': [1, 2]}, and the export page bytes are exact."
            ),
            invariant_statement="api.py health continues to emit exactly {\"status\":\"ok\"} followed by one newline and exits 0.",
        )
        self._configure_required_assurance(pack)
        full_plan = read_json(pack / "enhancement_plan.json")
        self.assertEqual(full_plan["target_requirements"], ["REQ-001"])
        self.assertEqual(full_plan["change_map"][0]["generated"], False)
        self.assertEqual(full_plan["change_map"][0]["requirement_ids"], ["REQ-001"])
        self.assertEqual(full_plan["change_map"][0]["slice_ids"], ["SLICE-001"])
        self._transition_cli(
            pack,
            from_status="READY",
            to_status="IN_PROGRESS",
            sequence=2,
            evidence_ids=["PRES-001"],
            decision_ids=["DEC-001"],
            reason="The complete requirement, invariant, impact, compatibility, change, slice, and gate contracts pass enhancement-ready.",
        )

        (repository / "export_api.py").write_text(
            "def export_rows(rows):\n    return {'rows': list(rows)}\n",
            encoding="utf-8",
            newline="\n",
        )
        (repository / "web" / "export.html").write_text(
            "<!doctype html><title>Export</title>\n",
            encoding="utf-8",
            newline="\n",
        )
        candidate = self._record_snapshot_api(pack, "candidate")
        self.assertEqual(candidate["snapshot_id"], "SNAP-002")
        self.assertEqual(candidate["snapshot_path"], "evidence/snapshots/SNAP-002.json")
        self._check_snapshot_api(pack, "candidate")
        run = self._record_gate_cli(pack, "SNAP-002")
        self.assertEqual(run["argv"], gate_argv)
        self._transition_cli(
            pack,
            from_status="IN_PROGRESS",
            to_status="IMPLEMENTED",
            sequence=3,
            evidence_ids=["SNAP-002"],
            decision_ids=[],
            reason="The bounded product edit exactly matches the retained candidate snapshot.",
        )
        regression, regression_exit = run_preservation_regression(
            pack,
            ["PRES-001"],
            timestamp=PINNED_TIMESTAMP,
        )
        self.assertEqual(regression_exit, 0, regression)
        self.assertEqual(
            regression,
            {
                "case_id": "PRES-001",
                "status": "PASS",
                "candidate_snapshot_id": "SNAP-002",
                "baseline_result_path": baseline["result_path"],
                "result_path": "evidence/preservation/PRES-001/regression/SNAP-002/result.json",
            },
        )
        scope = run_cli("verify-scope", pack, "--enhancement", "ENH-001")
        self.assertEqual(scope.returncode, 0, scope.stderr)
        scope_payload = self._canonical_payload(scope)
        self.assertEqual(
            {key: scope_payload[key] for key in (
                "status",
                "changed_paths",
                "added_paths",
                "removed_paths",
                "modified_paths",
                "renames",
                "unauthorized_paths",
            )},
            {
                "status": "PASS",
                "changed_paths": ["export_api.py", "web/export.html"],
                "added_paths": ["export_api.py", "web/export.html"],
                "removed_paths": [],
                "modified_paths": [],
                "renames": [],
                "unauthorized_paths": [],
            },
        )
        self.assertEqual(scope_payload["scope_id"], "SCOPE-001")
        assured = run_cli("assure", pack)
        self.assertEqual(assured.returncode, 0, assured.stderr)
        assurance_payload = self._canonical_payload(assured)
        self.assertEqual(assurance_payload["status"], "PASS")
        self.assertEqual(assurance_payload["selected_case_ids"], ["ASSURE-001"])
        enhanced = read_json(pack / "enhancement_plan.json")
        self.assertEqual(enhanced["assurance"]["result_ids"], ["ASSURE-001"])
        self.assertEqual(enhanced["result_references"]["assurance_ids"], ["ASSURE-001"])
        self._transition_cli(
            pack,
            from_status="IMPLEMENTED",
            to_status="VERIFIED",
            sequence=4,
            evidence_ids=["RUN-001", "PRES-001", "SCOPE-001", "ASSURE-001"],
            decision_ids=["DEC-001"],
            reason="The current gate, preservation, scope, and assurance results all pass for SNAP-002.",
        )
        seal = self._seal_and_validate_cli(pack)
        bindings = seal["enhancement_bindings"]
        self.assertEqual(
            [item["id"] for item in bindings["preservation_results"]],
            ["PRES-001:baseline", "PRES-001:regression"],
        )
        self.assertEqual(
            [item["id"] for item in bindings["assurance_results"]],
            ["ASSURE-001"],
        )
        self.assertEqual((pack / baseline["result_path"]).read_bytes(), baseline_bytes)
        self._assert_adopted_snapshot_immutable(pack, adopted["snapshot_path"])
        self._assert_git_has_no_delivery_side_effects(repository, str(adopted_head))

    def test_dependency_upgrade_preserves_authority_approved_known_baseline_failure(self) -> None:
        known_stderr = b"known resolver fixture failure\n"
        repository, adopted_head = self._write_repository(
            "git-dependency-upgrade",
            {
                "requirements.txt": "example-lib==1.0.0\n",
                "resolver_check.py": (
                    "import sys\n"
                    "sys.stderr.write('known resolver fixture failure\\n')\n"
                    "raise SystemExit(3)\n"
                ),
                "request.md": "# Dependency upgrade\n\nUpgrade example-lib without changing the accepted resolver failure.\n",
            },
            git=True,
        )
        self.assertIsNotNone(adopted_head)
        pack = self._initialize_api(
            repository,
            product_name="Cold Dependency Upgrade",
            product_type="cli",
            playbooks=["cli"],
            title="Upgrade example-lib",
            change_types=["dependency-upgrade"],
        )
        known_failure = {
            "expected_exit": 3,
            "expected_stdout_sha256": hashlib.sha256(b"").hexdigest(),
            "expected_stderr_sha256": hashlib.sha256(known_stderr).hexdigest(),
            "reason": "DEC-001 accepts this exact pre-existing local resolver failure.",
            "decision_ids": ["DEC-001"],
        }
        case = self._case(
            [sys.executable, "resolver_check.py"],
            known_failure=known_failure,
        )
        decisions = [
            {
                "id": "DEC-001",
                "kind": "DEC",
                "state": "READY",
                "links": {"enhancements": ["ENH-001"]},
                "attributes": {
                    "decision": "Accept exit 3 and the exact retained stderr as the known baseline failure.",
                    "decision_status": "APPROVED",
                },
            }
        ]
        self._configure_baseline_contract(
            pack,
            case=case,
            decision_records=decisions,
        )

        adopted = self._record_snapshot_api(pack, "adopted")
        self.assertEqual(adopted["snapshot_id"], "SNAP-001")
        self._transition_cli(
            pack,
            from_status="DRAFT",
            to_status="READY",
            sequence=1,
            evidence_ids=["SNAP-001"],
            decision_ids=["DEC-001"],
            reason="The adopted dependency baseline and its authority-approved failure oracle are exact.",
        )
        baseline, baseline_exit = run_preservation_baseline(
            pack,
            ["PRES-001"],
            timestamp=PINNED_TIMESTAMP,
        )
        self.assertEqual(baseline_exit, 0, baseline)
        self.assertEqual(
            baseline,
            {
                "case_id": "PRES-001",
                "status": "PASS",
                "adopted_snapshot_id": "SNAP-001",
                "result_path": "evidence/preservation/PRES-001/baseline/result.json",
            },
        )
        baseline_result = read_json(pack / baseline["result_path"])
        self.assertEqual(
            {
                "status": baseline_result["status"],
                "expected_exit": baseline_result["expected_exit"],
                "observed_exit": baseline_result["observed_exit"],
                "known_failure": baseline_result["known_failure"],
                "diagnostic": baseline_result["diagnostic"],
                "details": baseline_result["details"],
            },
            {
                "status": "PASS",
                "expected_exit": 0,
                "observed_exit": 3,
                "known_failure": known_failure,
                "diagnostic": None,
                "details": ["authority-approved known failure matched exactly"],
            },
        )
        baseline_bytes = (pack / baseline["result_path"]).read_bytes()
        self._assert_baseline_immutable(pack, baseline["result_path"])

        gate_argv = [
            sys.executable,
            "-c",
            (
                "from pathlib import Path; import subprocess, sys; "
                "assert Path('requirements.txt').read_text(encoding='utf-8') == 'example-lib==1.1.0\\n'; "
                "completed = subprocess.run([sys.executable, 'resolver_check.py'], capture_output=True); "
                "assert completed.returncode == 3; assert completed.stdout == b''; "
                "assert completed.stderr == b'known resolver fixture failure\\n'"
            ),
        ]
        accepted_finding = {
            "id": "FIND-001",
            "tool": "resolver_check.py",
            "severity": "informational",
            "status": "accepted",
            "summary": "The local resolver fixture exits 3 with the authority-approved exact stderr.",
            "path": "requirements.txt",
            "evidence_ids": ["PRES-001"],
            "decision_ids": ["DEC-001"],
        }
        self._configure_full_plan(
            pack,
            allowed_paths=["requirements.txt"],
            change_map=[
                {
                    "id": "CHANGE-001",
                    "operation": "modify",
                    "paths": ["requirements.txt"],
                    "generated": False,
                    "requirement_ids": ["REQ-001"],
                    "slice_ids": ["SLICE-001"],
                }
            ],
            affected_surfaces=["SURF-001"],
            compatibility=[
                {
                    "surface_id": "SURF-001",
                    "disposition": "PRESERVE",
                    "decision_ids": ["DEC-001"],
                    "reason": "The exact known baseline failure remains the preservation oracle.",
                }
            ],
            gate_argv=gate_argv,
            requirement_statement=(
                "Change requirements.txt from example-lib==1.0.0 to example-lib==1.1.0 and preserve the exact accepted resolver failure."
            ),
            acceptance_statement=(
                "GATE-001 requires the 1.1.0 pin and the resolver process to return exit 3, empty stdout, and the exact approved stderr bytes."
            ),
            invariant_statement=(
                "resolver_check.py continues to return exit 3, empty stdout, and exactly known resolver fixture failure followed by one newline."
            ),
            plan_updates={
                "dependency": {
                    "baseline_findings": [accepted_finding],
                    "candidate_findings": [accepted_finding],
                    "unavailable_data": [],
                },
                "rollback": {
                    "application": [
                        self._ordered_step(
                            1,
                            "Restore requirements.txt to the adopted exact bytes example-lib==1.0.0 followed by one newline.",
                            "The candidate gate or preservation regression fails before deployment or merge.",
                        )
                    ],
                    "data": [],
                },
            },
        )
        self._transition_cli(
            pack,
            from_status="READY",
            to_status="IN_PROGRESS",
            sequence=2,
            evidence_ids=["PRES-001"],
            decision_ids=["DEC-001"],
            reason="The dependency change, exact failure invariant, discriminating test, and rollback are fully specified.",
        )

        (repository / "requirements.txt").write_text(
            "example-lib==1.1.0\n",
            encoding="utf-8",
            newline="\n",
        )
        candidate = self._record_snapshot_api(pack, "candidate")
        self.assertEqual(candidate["snapshot_id"], "SNAP-002")
        self._transition_cli(
            pack,
            from_status="IN_PROGRESS",
            to_status="IMPLEMENTED",
            sequence=3,
            evidence_ids=["SNAP-002"],
            decision_ids=[],
            reason="The dependency pin is the only product delta in the current candidate snapshot.",
        )
        regression, regression_exit = run_preservation_regression(
            pack,
            ["PRES-001"],
            timestamp=PINNED_TIMESTAMP,
        )
        self.assertEqual(regression_exit, 0, regression)
        self.assertEqual(
            regression,
            {
                "case_id": "PRES-001",
                "status": "PASS",
                "candidate_snapshot_id": "SNAP-002",
                "baseline_result_path": baseline["result_path"],
                "result_path": "evidence/preservation/PRES-001/regression/SNAP-002/result.json",
            },
        )
        regression_result = read_json(pack / regression["result_path"])
        self.assertEqual(regression_result["observed_exit"], 3)
        self.assertEqual(regression_result["known_failure"], known_failure)

        run = self._record_gate_cli(pack, "SNAP-002")
        self.assertEqual(run["argv"], gate_argv)
        scope = run_cli("verify-scope", pack, "--enhancement", "ENH-001")
        self.assertEqual(scope.returncode, 0, scope.stderr)
        scope_payload = self._canonical_payload(scope)
        self.assertEqual(scope_payload["status"], "PASS")
        self.assertEqual(scope_payload["changed_paths"], ["requirements.txt"])
        self.assertEqual(scope_payload["modified_paths"], ["requirements.txt"])
        self.assertEqual(scope_payload["unauthorized_paths"], [])
        self.assertEqual(scope_payload["scope_id"], "SCOPE-001")
        self._transition_cli(
            pack,
            from_status="IMPLEMENTED",
            to_status="VERIFIED",
            sequence=4,
            evidence_ids=["RUN-001", "PRES-001", "SCOPE-001"],
            decision_ids=["DEC-001"],
            reason="The current gate, authority-approved preservation result, and exact scope result pass for SNAP-002.",
        )
        self._seal_and_validate_cli(pack)
        self.assertEqual((pack / baseline["result_path"]).read_bytes(), baseline_bytes)
        self._assert_adopted_snapshot_immutable(pack, adopted["snapshot_path"])
        self._assert_git_has_no_delivery_side_effects(repository, str(adopted_head))

    def test_expand_contract_plan_defers_destructive_contract_phase_behind_halt_and_gap(self) -> None:
        repository, _ = self._write_repository(
            "expand-contract-plan",
            {
                "schema.sql": "CREATE TABLE customer (id INTEGER PRIMARY KEY, legacy_tier TEXT NOT NULL);\n",
                "reader.py": "print('legacy_tier-readable')\n",
                "request.md": (
                    "# Customer tier migration\n\n"
                    "Plan expand, backfill, and reader switch; defer the destructive contract phase.\n"
                ),
            },
            git=False,
        )
        schema_before = (repository / "schema.sql").read_bytes()
        pack = self._initialize_api(
            repository,
            product_name="Cold Expand Contract",
            product_type="data-pipeline",
            playbooks=["data-pipeline"],
            title="Migrate customer tier with expand-contract",
            change_types=["data-migration"],
        )
        case = self._case([sys.executable, "reader.py"])
        decisions = [
            {
                "id": "DEC-001",
                "kind": "DEC",
                "state": "READY",
                "links": {"enhancements": ["ENH-001"]},
                "attributes": {
                    "decision": "Authorize an exact non-destructive expand, backfill, and switch plan; prohibit contract execution.",
                    "decision_status": "APPROVED",
                },
            }
        ]
        self._configure_baseline_contract(pack, case=case, decision_records=decisions)
        adopted = self._record_snapshot_api(pack, "adopted")
        self.assertEqual(adopted["snapshot_id"], "SNAP-001")
        self._transition_cli(
            pack,
            from_status="DRAFT",
            to_status="READY",
            sequence=1,
            evidence_ids=["SNAP-001"],
            decision_ids=["DEC-001"],
            reason="The adopted schema and legacy reader preservation contract are exact.",
        )
        baseline, baseline_exit = run_preservation_baseline(
            pack,
            ["PRES-001"],
            timestamp=PINNED_TIMESTAMP,
        )
        self.assertEqual(baseline_exit, 0, baseline)
        self.assertEqual(baseline["status"], "PASS")
        baseline_bytes = (pack / baseline["result_path"]).read_bytes()
        self._assert_baseline_immutable(pack, baseline["result_path"])

        def migration_step(
            identifier: str,
            order: int,
            action: str,
            paths: list[str],
            change_ids: list[str],
            completion_condition: str,
            *,
            destructive: bool = False,
            status: str = "PLANNED",
            halt_id: str | None = None,
            residual_gap_id: str | None = None,
        ) -> dict[str, Any]:
            return {
                "id": identifier,
                "order": order,
                "action": action,
                "paths": paths,
                "destructive": destructive,
                "status": status,
                "change_ids": change_ids,
                "verification_ids": ["GATE-001"],
                "completion_condition": completion_condition,
                "halt_id": halt_id,
                "residual_gap_id": residual_gap_id,
            }

        expand_contract = {
            "expand": [
                migration_step(
                    "MIGSTEP-001",
                    1,
                    "Create migrations/001_expand.sql to add nullable customer_tier while retaining legacy_tier.",
                    ["migrations/001_expand.sql"],
                    ["CHANGE-001"],
                    "The migration adds customer_tier and leaves legacy_tier readable and writable.",
                )
            ],
            "backfill": [
                migration_step(
                    "MIGSTEP-002",
                    2,
                    "Create migrations/002_backfill.py to copy legacy_tier into customer_tier in ascending customer.id batches.",
                    ["migrations/002_backfill.py"],
                    ["CHANGE-002"],
                    "Every row with non-null legacy_tier has the identical customer_tier value and rerunning the batch changes zero rows.",
                )
            ],
            "switch": [
                migration_step(
                    "MIGSTEP-003",
                    3,
                    "Modify reader.py to read customer_tier and fall back to legacy_tier during the mixed-version window.",
                    ["reader.py"],
                    ["CHANGE-003"],
                    "Old-schema and expanded-schema fixtures both emit legacy_tier-readable and exit 0.",
                )
            ],
            "contract": [
                migration_step(
                    "MIGSTEP-004",
                    4,
                    "Drop legacy_tier only after mixed-version evidence and separate destructive-migration authority exist.",
                    ["migrations/004_contract.sql"],
                    [],
                    "GAP-001 is closed, DEC-002 is approved, and the named contract verification run passes.",
                    destructive=True,
                    status="DEFERRED",
                    halt_id="HALT-001",
                    residual_gap_id="GAP-001",
                )
            ],
            "schema_and_data_invariants": ["INV-001"],
            "mixed_version_compatibility": (
                "Readers accepting only legacy_tier and readers preferring customer_tier with legacy_tier fallback both operate while both columns exist."
            ),
            "forward_boundary": (
                "Proceed from backfill to switch only after every existing row has equal non-null legacy_tier and customer_tier values."
            ),
            "rollback_boundary": (
                "Application rollback is permitted while legacy_tier exists; data rollback requires the retained pre-batch checkpoint before any contract step."
            ),
            "application_rollback": [
                migration_step(
                    "MIGSTEP-005",
                    5,
                    "Restore reader.py to read legacy_tier while both columns remain present.",
                    ["reader.py"],
                    ["CHANGE-003"],
                    "reader.py emits legacy_tier-readable against the adopted fixture and exits 0.",
                )
            ],
            "data_rollback": [
                migration_step(
                    "MIGSTEP-006",
                    6,
                    "Stop the backfill and restore customer_tier values from the retained pre-batch checkpoint.",
                    ["migrations/002_backfill.py"],
                    ["CHANGE-002"],
                    "A row-count and value hash comparison equals the retained pre-batch checkpoint.",
                )
            ],
            "backup_restore_prerequisites": (
                "Retain a checksum-verified pre-batch snapshot containing customer.id, legacy_tier, and customer_tier before each backfill batch."
            ),
            "idempotency_contract": (
                "Reapplying expand is a no-op after the column exists, and rerunning backfill updates only rows whose customer_tier differs from legacy_tier."
            ),
            "exit_condition": (
                "The contract phase remains deferred until GAP-001 is closed, DEC-002 is approved, and all mixed-version evidence passes."
            ),
            "validation_command_ids": ["GATE-001"],
            "decision_ids": ["DEC-001"],
        }
        rollback = {
            "application": [
                self._ordered_step(
                    1,
                    "Restore reader.py to the adopted legacy_tier reader bytes while both columns remain present.",
                    "A switch-phase verification fails and migrations/004_contract.sql has not been created or executed.",
                )
            ],
            "data": [
                self._ordered_step(
                    1,
                    "Stop backfill execution and restore customer_tier values from the checksum-verified pre-batch checkpoint.",
                    "A backfill verification fails before the switch phase begins.",
                )
            ],
        }
        gate_argv = [sys.executable, "reader.py"]
        expand_sql = "ALTER TABLE customer ADD COLUMN customer_tier TEXT NULL;\n"
        backfill_program = "# update customer_tier from legacy_tier in ascending customer.id batches\n"
        switched_reader = "print('legacy_tier-readable')\n"
        self._configure_full_plan(
            pack,
            allowed_paths=[
                "migrations/001_expand.sql",
                "migrations/002_backfill.py",
                "reader.py",
            ],
            change_map=[
                {
                    "id": "CHANGE-001",
                    "operation": "create",
                    "paths": ["migrations/001_expand.sql"],
                    "generated": False,
                    "requirement_ids": ["REQ-001"],
                    "slice_ids": ["SLICE-001"],
                },
                {
                    "id": "CHANGE-002",
                    "operation": "create",
                    "paths": ["migrations/002_backfill.py"],
                    "generated": False,
                    "requirement_ids": ["REQ-001"],
                    "slice_ids": ["SLICE-001"],
                },
                {
                    "id": "CHANGE-003",
                    "operation": "modify",
                    "paths": ["reader.py"],
                    "generated": False,
                    "requirement_ids": ["REQ-001"],
                    "slice_ids": ["SLICE-001"],
                },
            ],
            affected_surfaces=["SURF-001"],
            compatibility=[
                {
                    "surface_id": "SURF-001",
                    "disposition": "PRESERVE",
                    "decision_ids": ["DEC-001"],
                    "reason": "legacy_tier remains present and readable throughout expand, backfill, and switch.",
                }
            ],
            gate_argv=gate_argv,
            requirement_statement=(
                "Specify exact expand, backfill, and reader-switch changes while deferring legacy_tier removal behind HALT-001 and GAP-001."
            ),
            acceptance_statement=(
                "The READY plan contains ordered non-destructive expand, backfill, and switch steps plus one destructive DEFERRED contract step bound to HALT-001 and GAP-001."
            ),
            invariant_statement="legacy_tier remains present, readable, and unchanged until the separately authorized contract phase completes.",
            extra_records=[
                {
                    "id": "GAP-001",
                    "kind": "GAP",
                    "state": "OPEN",
                    "links": {"enhancements": ["ENH-001"], "halts": ["HALT-001"], "dependencies": []},
                    "attributes": {
                        "class": "MIGRATION_GAP",
                        "status": "OPEN",
                        "readiness": "BLOCKED",
                        "delta": "Destructive legacy_tier removal lacks mixed-version evidence and separate authority.",
                    },
                },
                {
                    "id": "HALT-001",
                    "kind": "HALT",
                    "state": "OPEN",
                    "links": {
                        "enhancements": ["ENH-001"],
                        "gaps": ["GAP-001"],
                        "decisions": ["DEC-002"],
                    },
                    "attributes": {
                        "code": "DESTRUCTIVE_CONTRACT_DEFERRED",
                        "condition": "Any attempt to create or execute migrations/004_contract.sql before GAP-001 closes.",
                        "owner": "migration-owner",
                        "resolution_question": "Does current mixed-version evidence justify approving DEC-002 and closing GAP-001?",
                    },
                },
                {
                    "id": "DEC-002",
                    "kind": "DEC",
                    "state": "DRAFT",
                    "links": {"halts": ["HALT-001"]},
                    "attributes": {
                        "decision": "Approve or reject destructive removal of legacy_tier after the required evidence exists.",
                        "decision_status": "PENDING",
                    },
                },
            ],
            plan_updates={
                "delivery_strategy": "expand-contract",
                "expand_contract": expand_contract,
                "migration": {
                    "framework": "ordered-sql-and-python",
                    "applied_history": [],
                    "planned": [
                        {
                            "id": "MIG-001",
                            "path": "migrations/001_expand.sql",
                            "checksum": hashlib.sha256(expand_sql.encode("utf-8")).hexdigest(),
                            "state": "planned",
                            "decision_ids": ["DEC-001"],
                        },
                        {
                            "id": "MIG-002",
                            "path": "migrations/002_backfill.py",
                            "checksum": hashlib.sha256(backfill_program.encode("utf-8")).hexdigest(),
                            "state": "planned",
                            "decision_ids": ["DEC-001"],
                        },
                        {
                            "id": "MIG-003",
                            "path": "reader.py",
                            "checksum": hashlib.sha256(switched_reader.encode("utf-8")).hexdigest(),
                            "state": "planned",
                            "decision_ids": ["DEC-001"],
                        },
                    ],
                    "validation_commands": [
                        {
                            "id": "GATE-001",
                            "argv": gate_argv,
                            "cwd": ".",
                            "expected_exit": 0,
                            "timeout_seconds": 30,
                        }
                    ],
                },
                "halts": [
                    {
                        "id": "HALT-001",
                        "code": "DESTRUCTIVE_CONTRACT_DEFERRED",
                        "condition": "Contract phase requested before GAP-001 is closed.",
                        "owner": "migration-owner",
                        "resolution_question": "Does current mixed-version evidence justify approving DEC-002 and closing GAP-001?",
                        "required_evidence_ids": ["PRES-001", "GATE-001"],
                        "required_decision_ids": ["DEC-002"],
                    }
                ],
                "residual_gap_ids": ["GAP-001"],
                "rollback": rollback,
                "recovery": {
                    "steps": [
                        self._ordered_step(
                            1,
                            "Run GATE-001 after application and data rollback and retain its exact output.",
                            "Both rollback branches completed and schema.sql still contains legacy_tier.",
                        )
                    ],
                    "verification_commands": [
                        {
                            "id": "GATE-001",
                            "argv": gate_argv,
                            "cwd": ".",
                            "expected_exit": 0,
                            "timeout_seconds": 30,
                        }
                    ],
                },
                "rollout": {
                    "strategy": "verified-code-handoff",
                    "steps": [
                        self._ordered_step(
                            1,
                            "Hand off only the READY migration plan; do not create migration files, deploy, merge, backfill, switch, or contract.",
                            "The enhancement-ready validation profile passes with the contract step DEFERRED.",
                        )
                    ],
                    "deployment_permitted": False,
                },
            },
        )

        validated = run_cli(
            "validate",
            pack,
            "--profile",
            "enhancement-ready",
            "--format",
            "json",
            "--max-problems",
            "0",
        )
        self.assertEqual(validated.returncode, 0, validated.stderr)
        validation_payload = self._canonical_payload(validated)
        self.assertEqual(validation_payload["status"], "PASS")
        self.assertEqual(validation_payload["diagnostics"], [])

        terminal_plan = read_json(pack / "enhancement_plan.json")
        self.assertEqual(terminal_plan["status"], "READY")
        self.assertEqual(terminal_plan["delivery_strategy"], "expand-contract")
        self.assertEqual(terminal_plan["expand_contract"], expand_contract)
        contract_step = terminal_plan["expand_contract"]["contract"][0]
        self.assertEqual(contract_step["id"], "MIGSTEP-004")
        self.assertEqual(contract_step["status"], "DEFERRED")
        self.assertTrue(contract_step["destructive"])
        self.assertEqual(contract_step["change_ids"], [])
        self.assertEqual(contract_step["halt_id"], "HALT-001")
        self.assertEqual(contract_step["residual_gap_id"], "GAP-001")
        self.assertEqual(terminal_plan["residual_gap_ids"], ["GAP-001"])
        self.assertEqual(terminal_plan["rollback"], rollback)
        self.assertEqual(len(terminal_plan["expand_contract"]["application_rollback"]), 1)
        self.assertEqual(len(terminal_plan["expand_contract"]["data_rollback"]), 1)
        self.assertIsNone(terminal_plan["snapshots"]["candidate"])
        self.assertIsNone(terminal_plan["scope_result"])
        self.assertEqual(terminal_plan["result_references"]["run_ids"], [])
        self.assertFalse(terminal_plan["rollout"]["deployment_permitted"])
        self.assertFalse((repository / "migrations").exists())
        self.assertEqual((repository / "schema.sql").read_bytes(), schema_before)
        self.assertEqual((pack / baseline["result_path"]).read_bytes(), baseline_bytes)
        self._assert_adopted_snapshot_immutable(pack, adopted["snapshot_path"])
        self._assert_non_git_has_no_delivery_side_effects(repository)

    def test_non_git_cli_uses_full_tree_snapshots_through_verified_scope(self) -> None:
        repository, _ = self._write_repository(
            "non-git-cli",
            {
                "cli_app.py": (
                    "import sys\n"
                    "if sys.argv[1:] == ['version']:\n"
                    "    print('1.0.0')\n"
                    "else:\n"
                    "    raise SystemExit(2)\n"
                ),
                "config/default.json": "{\"color\": false}\n",
                "docs/usage.txt": "cli_app.py version\n",
                "request.md": "# Add status command\n\nAdd status while preserving version output.\n",
            },
            git=False,
        )
        pack = self._initialize_cli(
            repository,
            product_name="Cold Non-Git CLI",
            product_type="cli",
            playbooks=["cli"],
            title="Add status command",
            change_types=["feature"],
        )
        case = self._case([sys.executable, "cli_app.py", "version"])
        decisions = [
            {
                "id": "DEC-001",
                "kind": "DEC",
                "state": "READY",
                "links": {"enhancements": ["ENH-001"]},
                "attributes": {
                    "decision": "Authorize only the additive status command while preserving version output.",
                    "decision_status": "APPROVED",
                },
            }
        ]
        self._configure_baseline_contract(
            pack,
            case=case,
            decision_records=decisions,
        )

        adopted = run_cli(
            "repo-snapshot",
            pack,
            "--role",
            "adopted",
            "--record",
        )
        self.assertEqual(adopted.returncode, 0, adopted.stderr)
        adopted_payload = self._canonical_payload(adopted)
        self.assertEqual(adopted_payload["repository_kind"], "filesystem")
        self.assertEqual(adopted_payload["snapshot_id"], "SNAP-001")
        adopted_snapshot = read_json(pack / adopted_payload["snapshot_path"])
        self.assertEqual(adopted_snapshot["includes"], [])
        self.assertEqual(
            [entry["path"] for entry in adopted_snapshot["entries"]],
            ["cli_app.py", "config/default.json", "docs/usage.txt", "request.md"],
        )
        adopted_bytes = (pack / adopted_payload["snapshot_path"]).read_bytes()

        self._transition_cli(
            pack,
            from_status="DRAFT",
            to_status="READY",
            sequence=1,
            evidence_ids=["SNAP-001"],
            decision_ids=["DEC-001"],
            reason="The non-Git full-tree adopted snapshot and exact version oracle are retained.",
        )

        baseline = run_cli("baseline-run", pack, "--case", "PRES-001")
        self.assertEqual(baseline.returncode, 0, baseline.stderr)
        baseline_payload = self._canonical_payload(baseline)
        self.assertEqual(
            baseline_payload,
            {
                "case_id": "PRES-001",
                "status": "PASS",
                "adopted_snapshot_id": "SNAP-001",
                "result_path": "evidence/preservation/PRES-001/baseline/result.json",
            },
        )
        baseline_bytes = (pack / baseline_payload["result_path"]).read_bytes()
        repeated_baseline = run_cli("baseline-run", pack, "--case", "PRES-001")
        self.assertEqual(repeated_baseline.returncode, 1)
        self.assertEqual(repeated_baseline.stdout, "")
        self.assertIn("BASELINE_IMMUTABLE:", repeated_baseline.stderr)
        self.assertEqual((pack / baseline_payload["result_path"]).read_bytes(), baseline_bytes)

        gate_argv = [
            sys.executable,
            "-c",
            (
                "import subprocess, sys; "
                "version = subprocess.run([sys.executable, 'cli_app.py', 'version'], capture_output=True); "
                "status = subprocess.run([sys.executable, 'cli_app.py', 'status'], capture_output=True); "
                "assert (version.returncode, version.stdout, version.stderr) == (0, b'1.0.0\\n', b''); "
                "assert (status.returncode, status.stdout, status.stderr) == (0, b'ready\\n', b'')"
            ),
        ]
        self._configure_full_plan(
            pack,
            allowed_paths=["cli_app.py"],
            change_map=[
                {
                    "id": "CHANGE-001",
                    "operation": "modify",
                    "paths": ["cli_app.py"],
                    "generated": False,
                    "requirement_ids": ["REQ-001"],
                    "slice_ids": ["SLICE-001"],
                }
            ],
            affected_surfaces=["SURF-001"],
            compatibility=[
                {
                    "surface_id": "SURF-001",
                    "disposition": "ADDITIVE",
                    "decision_ids": ["DEC-001"],
                    "reason": "status is additive and version remains byte-identical.",
                }
            ],
            gate_argv=gate_argv,
            requirement_statement=(
                "Add cli_app.py status output ready followed by one newline while preserving exact version output and exits."
            ),
            acceptance_statement=(
                "GATE-001 requires version to emit 1.0.0 and status to emit ready, each with one newline, empty stderr, and exit 0."
            ),
            invariant_statement="cli_app.py version continues to emit exactly 1.0.0 followed by one newline, empty stderr, and exit 0.",
        )
        self._transition_cli(
            pack,
            from_status="READY",
            to_status="IN_PROGRESS",
            sequence=2,
            evidence_ids=["PRES-001"],
            decision_ids=["DEC-001"],
            reason="The additive CLI change has a complete requirement chain, exact scope, preservation baseline, and rollback.",
        )
        (repository / "cli_app.py").write_text(
            (
                "import sys\n"
                "if sys.argv[1:] == ['version']:\n"
                "    print('1.0.0')\n"
                "elif sys.argv[1:] == ['status']:\n"
                "    print('ready')\n"
                "else:\n"
                "    raise SystemExit(2)\n"
            ),
            encoding="utf-8",
            newline="\n",
        )

        candidate = run_cli(
            "repo-snapshot",
            pack,
            "--role",
            "candidate",
            "--record",
        )
        self.assertEqual(candidate.returncode, 0, candidate.stderr)
        candidate_payload = self._canonical_payload(candidate)
        self.assertEqual(candidate_payload["snapshot_id"], "SNAP-002")
        candidate_snapshot = read_json(pack / candidate_payload["snapshot_path"])
        self.assertEqual(candidate_snapshot["includes"], [])
        self.assertEqual(
            [entry["path"] for entry in candidate_snapshot["entries"]],
            ["cli_app.py", "config/default.json", "docs/usage.txt", "request.md"],
        )
        checked = run_cli(
            "repo-snapshot",
            pack,
            "--role",
            "candidate",
            "--check",
        )
        self.assertEqual(checked.returncode, 0, checked.stderr)
        self.assertEqual(self._canonical_payload(checked)["status"], "MATCH")
        self._transition_cli(
            pack,
            from_status="IN_PROGRESS",
            to_status="IMPLEMENTED",
            sequence=3,
            evidence_ids=["SNAP-002"],
            decision_ids=[],
            reason="The full-tree candidate snapshot contains exactly the declared cli_app.py modification.",
        )
        regression = run_cli("regression", pack, "--case", "PRES-001")
        self.assertEqual(regression.returncode, 0, regression.stderr)
        regression_payload = self._canonical_payload(regression)
        self.assertEqual(
            regression_payload,
            {
                "case_id": "PRES-001",
                "status": "PASS",
                "candidate_snapshot_id": "SNAP-002",
                "baseline_result_path": baseline_payload["result_path"],
                "result_path": "evidence/preservation/PRES-001/regression/SNAP-002/result.json",
            },
        )
        run = self._record_gate_cli(pack, "SNAP-002")
        self.assertEqual(run["argv"], gate_argv)
        scope = run_cli("verify-scope", pack, "--enhancement", "ENH-001")
        self.assertEqual(scope.returncode, 0, scope.stderr)
        scope_payload = self._canonical_payload(scope)
        self.assertEqual(
            {
                "status": scope_payload["status"],
                "changed_paths": scope_payload["changed_paths"],
                "added_paths": scope_payload["added_paths"],
                "removed_paths": scope_payload["removed_paths"],
                "modified_paths": scope_payload["modified_paths"],
                "unauthorized_paths": scope_payload["unauthorized_paths"],
            },
            {
                "status": "PASS",
                "changed_paths": ["cli_app.py"],
                "added_paths": [],
                "removed_paths": [],
                "modified_paths": ["cli_app.py"],
                "unauthorized_paths": [],
            },
        )
        self.assertEqual(scope_payload["scope_id"], "SCOPE-001")
        self._transition_cli(
            pack,
            from_status="IMPLEMENTED",
            to_status="VERIFIED",
            sequence=4,
            evidence_ids=["RUN-001", "PRES-001", "SCOPE-001"],
            decision_ids=["DEC-001"],
            reason="The current non-Git candidate has passing gate, preservation, and exact full-tree scope evidence.",
        )
        self._seal_and_validate_cli(pack)

        repeated_adopted = run_cli(
            "repo-snapshot",
            pack,
            "--role",
            "adopted",
            "--record",
        )
        self.assertEqual(repeated_adopted.returncode, 1)
        self.assertEqual(repeated_adopted.stdout, "")
        self.assertIn("ADOPTED_SNAPSHOT_IMMUTABLE:", repeated_adopted.stderr)
        self.assertEqual((pack / adopted_payload["snapshot_path"]).read_bytes(), adopted_bytes)
        self.assertEqual((pack / baseline_payload["result_path"]).read_bytes(), baseline_bytes)
        self._assert_non_git_has_no_delivery_side_effects(repository)


if __name__ == "__main__":
    unittest.main()
