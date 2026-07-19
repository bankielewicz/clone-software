from __future__ import annotations

import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any
from unittest import mock

from scripts.clonepack import common, operations
from scripts.clonepack.common import ClonePackError, case_contract_sha256
from scripts.clonepack.enhancement import transition_enhancement
from scripts.clonepack.lifecycle import transition_gap
from scripts.clonepack.operations import execute_assurance, record_run
from tests.test_v2_regression import (
    PINNED_TIMESTAMP,
    read_json,
    run_cli,
    write_json,
)


class TransactionBoundaryTests(unittest.TestCase):
    """Crash-boundary proof for every recoverable multi-file promotion."""

    maxDiff = None

    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)
        self.root = Path(self.temporary_directory.name)

    def _atomic_fixture(self, name: str) -> tuple[Path, list[Path], tuple[bytes, ...]]:
        root = self.root / name
        root.mkdir()
        targets = [root / "one.txt", root / "two.txt", root / "three.txt"]
        for position, target in enumerate(targets, 1):
            target.write_bytes(f"before-{position}\n".encode("utf-8"))
        after = tuple(f"after-{position}\n".encode("utf-8") for position in range(1, 4))
        return root, targets, after

    def test_recovery_rolls_forward_before_and_after_every_destination_replacement(self) -> None:
        for timing in ("before", "after"):
            for failure_position in range(3):
                with self.subTest(timing=timing, failure_position=failure_position):
                    root, targets, after = self._atomic_fixture(
                        f"boundary-{timing}-{failure_position}"
                    )
                    original_replace = common._replace_from_stage
                    observed_position = -1

                    def interrupted_replace(stage: Path, destination: Path) -> None:
                        nonlocal observed_position
                        observed_position += 1
                        if timing == "before" and observed_position == failure_position:
                            raise OSError("injected before destination replacement")
                        original_replace(stage, destination)
                        if timing == "after" and observed_position == failure_position:
                            raise OSError("injected after destination replacement")

                    with mock.patch.object(
                        common,
                        "_replace_from_stage",
                        side_effect=interrupted_replace,
                    ):
                        with self.assertRaisesRegex(OSError, "injected"):
                            common.atomic_write_many(
                                dict(zip(targets, after, strict=True)),
                                transaction_root=root,
                                operation=f"boundary-{timing}-{failure_position}",
                            )

                    journal_root = root / common.TRANSACTION_DIRECTORY
                    self.assertTrue(journal_root.is_dir())
                    recovered = common.recover_atomic_transactions(root)
                    self.assertEqual(len(recovered), 1)
                    self.assertEqual(tuple(target.read_bytes() for target in targets), after)
                    self.assertFalse(journal_root.exists())

    def test_divergence_refuses_every_destination_change(self) -> None:
        root, targets, after = self._atomic_fixture("divergence")
        original_replace = common._replace_from_stage
        calls = 0

        def fail_after_first(stage: Path, destination: Path) -> None:
            nonlocal calls
            original_replace(stage, destination)
            calls += 1
            if calls == 1:
                raise OSError("injected after first destination")

        with mock.patch.object(common, "_replace_from_stage", side_effect=fail_after_first):
            with self.assertRaises(OSError):
                common.atomic_write_many(
                    dict(zip(targets, after, strict=True)),
                    transaction_root=root,
                    operation="divergence",
                )

        targets[1].write_bytes(b"neither-before-nor-after\n")
        before_recovery = tuple(target.read_bytes() for target in targets)
        with self.assertRaises(ClonePackError) as raised:
            common.recover_atomic_transactions(root)
        self.assertEqual(raised.exception.exit_code, 4)
        self.assertEqual(raised.exception.diagnostic, "TRANSACTION_DIVERGED")
        self.assertEqual(tuple(target.read_bytes() for target in targets), before_recovery)

    def test_transaction_parent_validation_never_mutates_through_a_symlink(self) -> None:
        root = self.root / "symlink-root"
        outside = self.root / "outside"
        root.mkdir()
        outside.mkdir()
        link = root / "link"
        try:
            link.symlink_to(outside, target_is_directory=True)
        except OSError as exc:
            self.skipTest(f"directory symlinks are unavailable: {exc}")

        with self.assertRaises(ClonePackError) as raised:
            common.atomic_write_many(
                {link / "created-outside" / "result.json": b"{}\n"},
                transaction_root=root,
                operation="symlink-containment",
            )

        self.assertEqual(raised.exception.diagnostic, "TRANSACTION_DIVERGED")
        self.assertFalse((outside / "created-outside").exists())
        self.assertFalse((root / common.TRANSACTION_DIRECTORY).exists())

    def _init_greenfield_pack(self, name: str) -> tuple[Path, Path]:
        repository = self.root / f"{name}-repository"
        repository.mkdir()
        initialized = run_cli(
            "init",
            "--product-name",
            f"Transaction {name}",
            "--product-type",
            "cli",
            "--source-description",
            "Authorized local transaction fixture",
            "--repo-root",
            repository,
            "--output-dir",
            name,
            "--timestamp",
            PINNED_TIMESTAMP,
        )
        self.assertEqual(initialized.returncode, 0, initialized.stderr)
        pack = repository / name
        manifest_path = pack / "clone_pack.json"
        manifest = read_json(manifest_path)
        manifest["reference_baseline_id"] = "BASELINE-TRANSACTION-001"
        manifest["repository_state"] = {
            "kind": "working-tree",
            "revision": "transaction-revision-001",
            "diff_sha256": "1" * 64,
        }
        write_json(manifest_path, manifest)
        return repository, pack

    def _set_records(self, pack: Path, specifications: list[dict[str, Any]]) -> None:
        document = pack / "clone_brief.md"
        text = document.read_text(encoding="utf-8").rstrip("\n") + "\n"
        records: list[dict[str, Any]] = []
        lines: list[str] = []
        for position, specification in enumerate(specifications, 1):
            identifier = str(specification["id"])
            anchor = f"{identifier} transaction boundary {position}"
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
        index_path = pack / "clone_index.json"
        index = read_json(index_path)
        index["records"] = records
        write_json(index_path, index)

    def _run_records(self) -> list[dict[str, Any]]:
        return [
            {"id": "ENV-001", "kind": "ENV"},
            {"id": "E-001", "kind": "E"},
            {"id": "REQ-001", "kind": "REQ"},
            {"id": "AC-001", "kind": "AC"},
            {
                "id": "TEST-001",
                "kind": "TEST",
                "links": {
                    "requirements": ["REQ-001"],
                    "acceptance": ["AC-001"],
                    "oracles": ["E-001"],
                },
                "attributes": {"environment_id": "ENV-001"},
            },
            {
                "id": "GATE-001",
                "kind": "GATE",
                "attributes": {
                    "argv": [sys.executable, "-c", "print('gate-pass')"],
                    "cwd": ".",
                    "environment": {},
                    "timeout_seconds": 30,
                    "expected_exit": 0,
                    "covered_ids": ["REQ-001", "AC-001", "TEST-001"],
                    "oracle_ids": ["E-001"],
                    "artifact_paths": [],
                    "normalizations": ["exact-exit"],
                    "redactions": [],
                },
            },
        ]

    def test_gap_transition_recovers_before_loading_lifecycle_state(self) -> None:
        _, pack = self._init_greenfield_pack("gap-recovery")
        self._set_records(
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

        with mock.patch.object(
            common,
            "_replace_from_stage",
            side_effect=OSError("injected before gap destination"),
        ):
            with self.assertRaisesRegex(OSError, "injected"):
                transition_gap(
                    pack,
                    "GAP-001",
                    "IN_PROGRESS",
                    actor="transaction-test",
                    reason="exercise prepared gap transaction",
                    evidence_ids=[],
                    decision_ids=[],
                    timestamp=PINNED_TIMESTAMP,
                )

        with self.assertRaises(ClonePackError) as raised:
            transition_gap(
                pack,
                "GAP-001",
                "BLOCKED",
                actor="transaction-test",
                reason="must observe recovered IN_PROGRESS state",
                evidence_ids=[],
                decision_ids=[],
                timestamp="2026-07-19T12:01:00+00:00",
            )
        self.assertEqual(raised.exception.diagnostic, "GAP_ILLEGAL_TRANSITION")
        index = read_json(pack / "clone_index.json")
        gap = next(record for record in index["records"] if record["id"] == "GAP-001")
        self.assertEqual(gap["attributes"]["status"], "IN_PROGRESS")
        events = [
            json.loads(line)
            for line in (pack / "history" / "gap_events.jsonl")
            .read_text(encoding="utf-8")
            .splitlines()
        ]
        self.assertEqual(
            [(event["from"], event["to"]) for event in events],
            [("OPEN", "IN_PROGRESS")],
        )

    def _init_brownfield_pack(self) -> Path:
        repository = self.root / "enhancement-repository"
        repository.mkdir()
        (repository / "app.txt").write_text("version one\n", encoding="utf-8", newline="\n")
        (repository / "request.md").write_text(
            "# Authorized enhancement\n\nAdd deterministic status output.\n",
            encoding="utf-8",
            newline="\n",
        )
        initialized = run_cli(
            "enhancement-init",
            "--product-name",
            "Transaction Enhancement",
            "--product-type",
            "cli",
            "--playbook",
            "cli",
            "--enhancement-id",
            "ENH-001",
            "--title",
            "Add deterministic status output",
            "--change-type",
            "feature",
            "--request-file",
            repository / "request.md",
            "--repo-root",
            repository,
            "--output-dir",
            "clone-pack",
            "--timestamp",
            PINNED_TIMESTAMP,
        )
        self.assertEqual(initialized.returncode, 0, initialized.stderr)
        pack = repository / "clone-pack"
        adopted = run_cli("repo-snapshot", pack, "--role", "adopted", "--record")
        self.assertEqual(adopted.returncode, 0, adopted.stderr)
        return pack

    def test_enhancement_transition_recovers_before_loading_plan_and_index(self) -> None:
        pack = self._init_brownfield_pack()
        original_replace = common._replace_from_stage
        interrupted = False

        def fail_before_first_destination(stage: Path, destination: Path) -> None:
            nonlocal interrupted
            if not interrupted:
                interrupted = True
                raise OSError("injected before enhancement destination")
            original_replace(stage, destination)

        with mock.patch.object(
            common,
            "_replace_from_stage",
            side_effect=fail_before_first_destination,
        ):
            with self.assertRaisesRegex(OSError, "injected"):
                transition_enhancement(
                    pack,
                    "ENH-001",
                    "READY",
                    actor="transaction-test",
                    reason="repository adoption is complete",
                    timestamp=PINNED_TIMESTAMP,
                )
        self.assertTrue(interrupted)

        blocked = transition_enhancement(
            pack,
            "ENH-001",
            "BLOCKED",
            actor="transaction-test",
            reason="exercise recovered READY state",
            timestamp="2026-07-19T12:01:00+00:00",
        )
        self.assertEqual((blocked["sequence"], blocked["from"], blocked["to"]), (2, "READY", "BLOCKED"))
        events = [
            json.loads(line)
            for line in (pack / "history" / "enhancement_events.jsonl")
            .read_text(encoding="utf-8")
            .splitlines()
        ]
        self.assertEqual(
            [(event["from"], event["to"]) for event in events],
            [("DRAFT", "READY"), ("READY", "BLOCKED")],
        )

    def test_record_run_has_no_unjournaled_artifact_promotion_window(self) -> None:
        _, pack = self._init_greenfield_pack("run-recovery")
        self._set_records(pack, self._run_records())

        with mock.patch.object(
            operations,
            "atomic_write_many",
            side_effect=OSError("injected before run journal"),
        ):
            with self.assertRaisesRegex(OSError, "injected"):
                record_run(pack, "GATE-001", "ENV-001", PINNED_TIMESTAMP)

        run, exit_code = record_run(
            pack,
            "GATE-001",
            "ENV-001",
            "2026-07-19T12:01:00+00:00",
        )
        self.assertEqual(exit_code, 0)
        self.assertEqual(run["run_id"], "RUN-001")
        self.assertEqual(
            sorted(path.name for path in (pack / "runs" / "artifacts").glob("RUN-*") if path.is_dir()),
            ["RUN-001"],
        )

    def test_assurance_result_and_plan_pointer_share_one_recoverable_transaction(self) -> None:
        _, pack = self._init_greenfield_pack("assurance-recovery")
        case = {
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
        plan_path = pack / "assurance_plan.json"
        plan = read_json(plan_path)
        plan["risk_profile"] = "local-evaluation"
        plan["cases"] = [case]
        write_json(plan_path, plan)
        self._set_records(
            pack,
            [
                {
                    "id": "ASSURE-001",
                    "kind": "ASSURE",
                    "attributes": {"case_sha256": case_contract_sha256(case)},
                }
            ],
        )

        with mock.patch.object(
            operations,
            "atomic_write_many",
            side_effect=OSError("injected before assurance journal"),
        ):
            with self.assertRaisesRegex(OSError, "injected"):
                execute_assurance(pack, ["ASSURE-001"])

        self.assertFalse((pack / "evidence" / "assurance" / "ASSURE-001").exists())
        self.assertFalse((pack / "evidence" / "assurance" / ".ASSURE-001.staging").exists())
        aggregate, exit_code = execute_assurance(pack, ["ASSURE-001"])
        self.assertEqual(exit_code, 0)
        self.assertEqual(aggregate["status"], "PASS")
        updated = read_json(plan_path)
        self.assertEqual(updated["cases"][0]["result"]["status"], "PASS")


if __name__ == "__main__":
    unittest.main()
