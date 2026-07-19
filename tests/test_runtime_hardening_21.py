from __future__ import annotations

import copy
import hashlib
import re
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any
from unittest import mock

from scripts.clonepack import common
from scripts.clonepack.common import ClonePackError, load_json
from scripts.clonepack.pack import create_seal
from tests import test_gap_dossier_contract as dossier_support
from tests import test_gap_evidence_integrity as gap_support
from tests.test_v2_regression import (
    PINNED_TIMESTAMP,
    canonical_json,
    read_json,
    run_cli,
    write_json,
)


class RuntimeHardening21Tests(unittest.TestCase):
    maxDiff = None

    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)
        self.root = Path(self.temporary_directory.name)
        self.repository = self.root / "repository"
        self.repository.mkdir()

    def _init_pack(self, name: str) -> Path:
        initialized = run_cli(
            "init",
            "--product-name",
            f"Runtime Hardening {name}",
            "--product-type",
            "cli",
            "--source-description",
            "Authorized local synthetic fixture",
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
        manifest["reference_baseline_id"] = "BASELINE-HARDENING-001"
        manifest["repository_state"] = {
            "kind": "working-tree",
            "revision": "hardening-revision-001",
            "diff_sha256": "a" * 64,
        }
        write_json(pack / "clone_pack.json", manifest)
        return pack

    def _set_records(self, pack: Path, specifications: list[dict[str, Any]]) -> None:
        document = pack / "clone_brief.md"
        text = document.read_text(encoding="utf-8").rstrip("\n") + "\n"
        records: list[dict[str, Any]] = []
        lines: list[str] = []
        for number, specification in enumerate(specifications, 1):
            identifier = str(specification["id"])
            anchor = f"{identifier} runtime-hardening contract {number}"
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

    def _set_assurance_cases(self, pack: Path, cases: list[dict[str, Any]]) -> None:
        plan = read_json(pack / "assurance_plan.json")
        plan["risk_profile"] = "local-evaluation"
        plan["cases"] = cases
        write_json(pack / "assurance_plan.json", plan)
        self._set_records(
            pack,
            [
                {
                    "id": str(case["id"]),
                    "kind": "ASSURE",
                    "attributes": {
                        "case_sha256": hashlib.sha256(
                            canonical_json(
                                {key: value for key, value in case.items() if key != "result"}
                            ).encode("utf-8")
                        ).hexdigest()
                    },
                }
                for case in cases
            ],
        )

    @staticmethod
    def _assurance_case(
        identifier: str,
        *,
        required: bool,
        argv: list[str],
        kind: str = "threat-model",
    ) -> dict[str, Any]:
        return {
            "id": identifier,
            "kind": kind,
            "required": required,
            "argv": argv,
            "cwd": ".",
            "timeout_seconds": 30,
            "expected_exit": 0,
            "artifact_paths": [],
            "result": None,
        }

    def _advance_revision(
        self,
        pack: Path,
        revision: int,
        *,
        supersedes: dict[str, Any] | None,
    ) -> None:
        manifest_path = pack / "clone_pack.json"
        manifest = load_json(manifest_path)
        manifest["pack_revision"] = revision
        manifest["supersedes"] = supersedes
        for entry in manifest["documents"]:
            path = pack / entry["path"]
            text = re.sub(
                r"^pack_revision:\s*\d+\s*$",
                f"pack_revision: {revision}",
                path.read_text(encoding="utf-8"),
                count=1,
                flags=re.MULTILINE,
            )
            path.write_text(text, encoding="utf-8", newline="\n")
            entry["sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
        index_path = pack / manifest["index_path"]
        index = load_json(index_path)
        index["pack_revision"] = revision
        write_json(index_path, index)
        for plan_path_value in manifest["plans"].values():
            plan_path = pack / plan_path_value
            plan = load_json(plan_path)
            plan["pack_revision"] = revision
            write_json(plan_path, plan)
        write_json(manifest_path, manifest)

    def _interrupted_atomic_write(self, root: Path) -> tuple[list[Path], tuple[bytes, ...], tuple[bytes, ...]]:
        targets = [root / "one.txt", root / "two.txt", root / "three.txt"]
        before = (b"before-one\n", b"before-two\n", b"before-three\n")
        after = (b"after-one\n", b"after-two\n", b"after-three\n")
        for path, value in zip(targets, before, strict=True):
            path.write_bytes(value)

        recover = getattr(common, "recover_atomic_transactions", None)
        self.assertIsNotNone(
            recover,
            "2.1.0 requires recover_atomic_transactions(transaction_root)",
        )
        original_replace = common.os.replace
        injected = False

        def fail_second_destination(source: Any, destination: Any) -> None:
            nonlocal injected
            if Path(destination) == targets[1] and not injected:
                injected = True
                raise OSError("injected second-destination replacement failure")
            original_replace(source, destination)

        with mock.patch.object(common.os, "replace", side_effect=fail_second_destination):
            with self.assertRaises((OSError, ClonePackError)):
                try:
                    common.atomic_write_many(
                        {
                            path: value.decode("utf-8")
                            for path, value in zip(targets, after, strict=True)
                        },
                        transaction_root=root,
                        operation="runtime-hardening-test",
                    )
                except TypeError as exc:
                    self.fail(
                        "atomic_write_many requires transaction_root and operation in 2.1.0: "
                        f"{exc}"
                    )
        self.assertTrue(injected, "the transaction never reached its second destination")
        return targets, before, after

    def test_interrupted_multi_file_write_recovers_to_one_consistent_image(self) -> None:
        transaction_root = self.root / "transaction-recovery"
        transaction_root.mkdir()
        targets, before, after = self._interrupted_atomic_write(transaction_root)

        recover = getattr(common, "recover_atomic_transactions")
        recover(transaction_root)

        observed = tuple(path.read_bytes() for path in targets)
        self.assertEqual(observed, after)

    def test_transaction_recovery_stops_on_destination_divergence(self) -> None:
        transaction_root = self.root / "transaction-divergence"
        transaction_root.mkdir()
        targets, _, _ = self._interrupted_atomic_write(transaction_root)
        targets[0].write_bytes(b"neither-before-nor-after\n")

        recover = getattr(common, "recover_atomic_transactions")
        snapshot = tuple(path.read_bytes() for path in targets)
        with self.assertRaises(ClonePackError) as raised:
            recover(transaction_root)

        self.assertEqual(raised.exception.exit_code, 4)
        self.assertEqual(raised.exception.diagnostic, "TRANSACTION_DIVERGED")
        self.assertEqual(tuple(path.read_bytes() for path in targets), snapshot)

    def test_noninitial_gap_status_requires_a_complete_hash_chained_history(self) -> None:
        pack = self._init_pack("missing-gap-history")
        self._set_records(
            pack,
            [
                {
                    "id": "GAP-001",
                    "kind": "GAP",
                    "state": "IN_PROGRESS",
                    "links": {"dependencies": []},
                    "attributes": {"status": "IN_PROGRESS", "readiness": "READY"},
                }
            ],
        )

        validated = run_cli("validate", pack, "--profile", "scaffold", "--format", "json")
        payload = read_json_from_stdout(validated.stdout)

        self.assertEqual(validated.returncode, 4, validated.stderr or validated.stdout)
        self.assertTrue(
            any(
                item["code"] == "GAP_HISTORY_MISSING" and item["record_id"] == "GAP-001"
                for item in payload["diagnostics"]
            ),
            payload,
        )

    def test_gap_history_must_start_from_open_even_when_later_edges_are_legal(self) -> None:
        pack = self._init_pack("wrong-gap-history-origin")
        self._set_records(
            pack,
            [
                {
                    "id": "GAP-001",
                    "kind": "GAP",
                    "state": "IN_PROGRESS",
                    "links": {"dependencies": []},
                    "attributes": {"status": "IN_PROGRESS", "readiness": "READY"},
                }
            ],
        )
        events: list[dict[str, Any]] = []
        for sequence, from_status, to_status in (
            (1, "BLOCKED", "OPEN"),
            (2, "OPEN", "IN_PROGRESS"),
        ):
            event = {
                "schema_version": "clone-gap-event/v2",
                "event_id": f"GAPEVT-001-{sequence:03d}",
                "gap_id": "GAP-001",
                "sequence": sequence,
                "from": from_status,
                "to": to_status,
                "timestamp": f"2026-07-18T12:34:{55 + sequence:02d}+00:00",
                "actor": "runtime-hardening-test",
                "evidence_ids": [],
                "decision_ids": [],
                "reason": "synthetic complete-chain counterexample",
                "previous_event_sha256": events[-1]["event_sha256"] if events else "",
            }
            event["event_sha256"] = hashlib.sha256(
                canonical_json(event).encode("utf-8")
            ).hexdigest()
            events.append(event)
        (pack / "history" / "gap_events.jsonl").write_text(
            "".join(canonical_json(event).replace("\n", "") + "\n" for event in events),
            encoding="utf-8",
            newline="\n",
        )

        validated = run_cli("validate", pack, "--profile", "scaffold", "--format", "json")
        payload = read_json_from_stdout(validated.stdout)

        self.assertEqual(validated.returncode, 4, validated.stderr or validated.stdout)
        self.assertTrue(
            any(
                item["code"] == "GAP_HISTORY_INCOMPLETE" and item["record_id"] == "GAP-001"
                for item in payload["diagnostics"]
            ),
            payload,
        )

    def test_verified_transition_updates_the_gap_dossier_closure_exactly(self) -> None:
        lifecycle_fixture = gap_support.GapEvidenceIntegrityTests(methodName="runTest")
        lifecycle_fixture.setUp()
        self.addCleanup(lifecycle_fixture.doCleanups)
        pack, run_id = lifecycle_fixture._prepare("runtime-hardening-closure")

        dossier_fixture = dossier_support.GapDossierContractTests(methodName="runTest")
        dossier_fixture.setUp()
        self.addCleanup(dossier_fixture.doCleanups)
        dossier = replace_id(copy.deepcopy(dossier_fixture.dossier), "AC-GAP-001-01", "AC-001")
        dossier_fixture_records = {
            str(replace_id(identifier, "AC-GAP-001-01", "AC-001")): replace_id(
                copy.deepcopy(record), "AC-GAP-001-01", "AC-001"
            )
            for identifier, record in dossier_fixture.records.items()
        }
        (pack / "evidence" / "reference.txt").write_text(
            "reference observation\n", encoding="utf-8", newline="\n"
        )
        manifest_path = pack / "clone_pack.json"
        manifest = read_json(manifest_path)
        manifest["repository_root"] = str(dossier_fixture.repository)
        write_json(manifest_path, manifest)

        index_path = pack / "clone_index.json"
        index = read_json(index_path)
        records = {str(record["id"]): record for record in index["records"]}
        document = pack / "clone_brief.md"
        additions: list[str] = []
        for identifier, source_record in dossier_fixture_records.items():
            if identifier == "GAP-001":
                continue
            if identifier in records:
                merge_links(records[identifier], source_record.get("links", {}))
                continue
            anchor = f"{identifier} dossier closure contract"
            line = f"- {anchor}\n"
            additions.append(line)
            source_record["locator"] = {
                "path": "clone_brief.md",
                "anchor": anchor,
                "sha256": hashlib.sha256(line.encode("utf-8")).hexdigest(),
            }
            index["records"].append(source_record)
            records[identifier] = source_record
        document.write_text(
            document.read_text(encoding="utf-8").rstrip("\n") + "\n" + "".join(additions),
            encoding="utf-8",
            newline="\n",
        )
        gap = records["GAP-001"]
        gap["attributes"].update({"class": "QUALITY_GAP", "dossier": dossier})
        merge_links(gap, dossier_fixture_records["GAP-001"]["links"])
        write_json(index_path, index)

        verified = lifecycle_fixture._transition(
            pack,
            "VERIFIED",
            evidence=[run_id, "PAR-001", "ASSURE-001"],
        )
        self.assertEqual(verified.returncode, 0, verified.stderr)

        updated_index = read_json(index_path)
        updated_gap = next(record for record in updated_index["records"] if record["id"] == "GAP-001")
        self.assertEqual(
            updated_gap["attributes"]["dossier"]["closure"],
            {
                "state": "VERIFIED",
                "implemented_revision": "repository-revision-001",
                "run_ids": [run_id],
                "parity_ids": ["PAR-001"],
                "assurance_ids": ["ASSURE-001"],
                "residual_gap_ids": [],
            },
        )

    def test_successor_seal_requires_supersedes_to_bind_the_predecessor(self) -> None:
        pack = self._init_pack("seal-supersedes-required")
        create_seal(pack, "scaffold", PINNED_TIMESTAMP)
        self._advance_revision(pack, 2, supersedes=None)
        before = tree_bytes(pack)

        with self.assertRaises(ClonePackError) as raised:
            create_seal(pack, "scaffold", "2026-07-18T12:35:57+00:00")

        self.assertEqual(raised.exception.diagnostic, "SEAL_SUPERSEDES_REQUIRED")
        self.assertEqual(tree_bytes(pack), before)

    def test_successor_seal_rejects_a_mismatched_predecessor_manifest_hash(self) -> None:
        pack = self._init_pack("seal-supersedes-mismatch")
        first = create_seal(pack, "scaffold", PINNED_TIMESTAMP)
        self._advance_revision(
            pack,
            2,
            supersedes={
                "schema_version": "clone-pack/v2",
                "pack_id": first["pack_id"],
                "pack_revision": first["pack_revision"],
                "manifest_sha256": "f" * 64,
            },
        )
        before = tree_bytes(pack)

        with self.assertRaises(ClonePackError) as raised:
            create_seal(pack, "scaffold", "2026-07-18T12:35:57+00:00")

        self.assertEqual(raised.exception.diagnostic, "SEAL_SUPERSEDES_MISMATCH")
        self.assertEqual(tree_bytes(pack), before)

    def test_successor_seal_binds_the_exact_predecessor_seal_bytes(self) -> None:
        pack = self._init_pack("seal-predecessor-binding")
        first = create_seal(pack, "scaffold", PINNED_TIMESTAMP)
        predecessor_bytes = (pack / "seal.json").read_bytes()
        predecessor_digest = hashlib.sha256(predecessor_bytes).hexdigest()
        self._advance_revision(
            pack,
            2,
            supersedes={
                "schema_version": "clone-pack/v2",
                "pack_id": first["pack_id"],
                "pack_revision": first["pack_revision"],
                "manifest_sha256": first["manifest_sha256"],
            },
        )

        successor = create_seal(pack, "scaffold", "2026-07-18T12:35:57+00:00")

        self.assertEqual(successor.get("predecessor_seal_sha256"), predecessor_digest)

    def test_assure_without_selector_executes_required_cases_only(self) -> None:
        pack = self._init_pack("assurance-required-default")
        optional_marker = self.repository / "optional-assurance-executed.txt"
        cases = [
            self._assurance_case(
                "ASSURE-001",
                required=True,
                argv=[sys.executable, "-c", "print('required-pass')"],
            ),
            self._assurance_case(
                "ASSURE-002",
                required=False,
                kind="provenance",
                argv=[
                    sys.executable,
                    "-c",
                    (
                        "from pathlib import Path; "
                        f"Path({str(optional_marker)!r}).write_text('executed', encoding='utf-8')"
                    ),
                ],
            ),
        ]
        self._set_assurance_cases(pack, cases)

        assured = run_cli("assure", pack)

        self.assertEqual(assured.returncode, 0, assured.stderr)
        self.assertFalse(optional_marker.exists())
        updated = read_json(pack / "assurance_plan.json")
        self.assertIsInstance(updated["cases"][0]["result"], dict)
        self.assertIsNone(updated["cases"][1]["result"])

    def test_assure_all_uses_order_independent_infrastructure_precedence(self) -> None:
        observed_exits: list[int] = []
        for name, ordered_kinds in (
            ("failure-before-blocked", ("FAIL", "BLOCKED")),
            ("blocked-before-failure", ("BLOCKED", "FAIL")),
        ):
            pack = self._init_pack(name)
            cases: list[dict[str, Any]] = []
            for position, outcome in enumerate(ordered_kinds, 1):
                argv = (
                    [sys.executable, "-c", "raise SystemExit(1)"]
                    if outcome == "FAIL"
                    else ["clone-software-definitely-missing-executable"]
                )
                cases.append(
                    self._assurance_case(
                        f"ASSURE-{position:03d}",
                        required=True,
                        argv=argv,
                        kind="threat-model" if position == 1 else "provenance",
                    )
                )
            self._set_assurance_cases(pack, cases)

            assured = run_cli("assure", pack, "--all")
            observed_exits.append(assured.returncode)
            if assured.returncode != 2:
                updated = read_json(pack / "assurance_plan.json")
                self.assertEqual(
                    {str(case["result"]["status"]) for case in updated["cases"]},
                    {"FAIL", "BLOCKED"},
                )
                blocked_case = next(
                    case for case in updated["cases"] if case["result"]["status"] == "BLOCKED"
                )
                blocked_result = read_json(pack / blocked_case["result"]["path"])
                self.assertIsNone(blocked_result["observed_exit"])
                self.assertEqual(
                    sorted(Path(artifact["path"]).name for artifact in blocked_result["artifacts"]),
                    ["stderr.bin", "stdout.bin"],
                )
                self.assertTrue(
                    all(artifact["size"] == 0 for artifact in blocked_result["artifacts"]),
                    blocked_result,
                )

        self.assertEqual(observed_exits, [7, 7])


def replace_id(value: Any, old: str, new: str) -> Any:
    if isinstance(value, dict):
        return {key: replace_id(item, old, new) for key, item in value.items()}
    if isinstance(value, list):
        return [replace_id(item, old, new) for item in value]
    return new if value == old else value


def merge_links(record: dict[str, Any], additions: dict[str, Any]) -> None:
    links = record.setdefault("links", {})
    for relation, identifiers in additions.items():
        current = links.setdefault(relation, [])
        for identifier in identifiers:
            if identifier not in current:
                current.append(identifier)


def tree_bytes(root: Path) -> dict[str, bytes]:
    return {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def read_json_from_stdout(value: str) -> dict[str, Any]:
    import json

    parsed = json.loads(value)
    if not isinstance(parsed, dict):
        raise AssertionError("CLI JSON output must be an object")
    return parsed


if __name__ == "__main__":
    unittest.main()
