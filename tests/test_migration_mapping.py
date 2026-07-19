from __future__ import annotations

import copy
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any

from scripts.clonepack import TOOL_VERSION
from scripts.clonepack.common import ClonePackError
from scripts.clonepack.evolution import MIGRATION_OPERATIONS, _validate_migration_report


SKILL_ROOT = Path(__file__).resolve().parents[1]
CLONE_PACK = SKILL_ROOT / "scripts" / "clone_pack.py"
V1_DOCUMENTS = [
    "clone_brief.md",
    "evidence_ledger.md",
    "clone_specification.md",
    "mvp_build_plan.md",
    "acceptance_matrix.md",
    "gaps_analysis.md",
    "gap_implementation_plan.md",
]


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


def write_json(path: Path, value: object) -> None:
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )


class MigrationMappingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)
        self.root = Path(self.temporary_directory.name)
        self.repository = self.root / "repository"
        self.repository.mkdir()
        self.source = self.root / "legacy"
        self.source.mkdir()
        write_json(
            self.source / "clone_pack.json",
            {
                "schema_version": "clone-pack/v1",
                "pack_id": "clone-mapping-fixture-2026-07-18",
                "product_name": "Mapping Fixture",
                "product_type": "cli",
                "reference_source": "authorized synthetic fixture",
                "created_at": "2026-07-18T12:00:00+00:00",
                "repository_root": self.repository.as_posix(),
                "documents": V1_DOCUMENTS,
            },
        )
        for name in V1_DOCUMENTS:
            (self.source / name).write_text(f"# {name}\n", encoding="utf-8", newline="\n")
        (self.source / "mvp_build_plan.md").write_text(
            "# MVP plan\n\n| GATE-001 | MVP gate |\n",
            encoding="utf-8",
            newline="\n",
        )
        (self.source / "gap_implementation_plan.md").write_text(
            "# Gap plan\n\n| GATE-001 | gap gate |\n",
            encoding="utf-8",
            newline="\n",
        )

    def test_check_names_every_ambiguous_occurrence_and_incomplete_mapping_blocks_write(self) -> None:
        checked = run_cli("migrate", self.source, "--check")
        self.assertEqual(checked.returncode, 6, checked.stderr)
        payload = json.loads(checked.stdout)
        self.assertFalse(payload["migratable"])
        self.assertEqual(payload["tool_version"], TOOL_VERSION)
        self.assertEqual(
            [item["path"] for item in payload["source_files"]],
            ["clone_pack.json", *V1_DOCUMENTS],
        )
        for item in payload["source_files"]:
            self.assertEqual(
                item["sha256"],
                hashlib.sha256((self.source / item["path"]).read_bytes()).hexdigest(),
            )
        self.assertEqual(payload["ambiguous_ids"], ["GATE-001"])
        self.assertEqual(
            payload["ambiguous_candidates"]["GATE-001"],
            [
                "GATE-001@gap_implementation_plan.md:3",
                "GATE-001@mvp_build_plan.md:3",
            ],
        )

        mapping = self.root / "incomplete-map.json"
        write_json(mapping, {"GATE-001@mvp_build_plan.md:3": "GATE-001"})
        destination = self.root / "must-not-exist"
        migrated = run_cli("migrate", self.source, "--output", destination, "--mapping", mapping)
        self.assertEqual(migrated.returncode, 6)
        self.assertIn("MIGRATION_MAPPING_REQUIRED:", migrated.stderr)
        self.assertFalse(destination.exists())

    def test_complete_occurrence_mapping_preserves_both_definitions_with_unique_ids(self) -> None:
        mapping = self.root / "map.json"
        write_json(
            mapping,
            {
                "GATE-001@gap_implementation_plan.md:3": "GATE-002",
                "GATE-001@mvp_build_plan.md:3": "GATE-001",
            },
        )
        destination = self.root / "migrated"
        migrated = run_cli(
            "migrate",
            self.source,
            "--output",
            destination,
            "--mapping",
            mapping,
            "--timestamp",
            "2026-07-18T12:00:00+00:00",
        )
        self.assertEqual(migrated.returncode, 0, migrated.stderr)
        index = json.loads((destination / "clone_index.json").read_text(encoding="utf-8"))
        records = {record["id"]: record for record in index["records"]}
        self.assertEqual(set(records), {"GATE-001", "GATE-002"})
        self.assertEqual(records["GATE-001"]["attributes"]["source_path"], "history/migrations/MIG-001/source/mvp_build_plan.md")
        self.assertEqual(records["GATE-002"]["attributes"]["source_path"], "history/migrations/MIG-001/source/gap_implementation_plan.md")
        self.assertEqual(records["GATE-001"]["locator"]["path"], "history/migrations/MIG-001/record_map.md")
        report_path = destination / "history" / "migrations" / "MIG-001" / "migration_report.json"
        report_bytes = report_path.read_bytes()
        report = json.loads(report_bytes)
        self.assertEqual(
            set(report),
            {
                "schema_version",
                "migration_id",
                "tool_version",
                "source",
                "source_files",
                "preserved_record_ids",
                "resolved_record_ids",
                "occurrence_mapping",
                "transformations",
                "status_downgrades",
                "unresolved_losses",
                "required_reconciliation",
            },
        )
        self.assertEqual(report["tool_version"], TOOL_VERSION)
        self.assertEqual(report["source"]["tool_version"], TOOL_VERSION)
        self.assertEqual(
            [item["source_path"] for item in report["source_files"]],
            ["clone_pack.json", *V1_DOCUMENTS],
        )
        self.assertEqual(
            report["source"]["source_files"],
            [
                {"path": item["source_path"], "sha256": item["sha256"]}
                for item in report["source_files"]
            ],
        )
        for item in report["source_files"]:
            source_bytes = (self.source / item["source_path"]).read_bytes()
            archived_bytes = (destination / item["archived_path"]).read_bytes()
            self.assertEqual(archived_bytes, source_bytes)
            self.assertEqual(item["sha256"], hashlib.sha256(source_bytes).hexdigest())
        self.assertEqual(report["resolved_record_ids"], ["GATE-001", "GATE-002"])
        self.assertEqual(
            [item["sequence"] for item in report["transformations"]],
            list(range(1, len(MIGRATION_OPERATIONS) + 1)),
        )
        self.assertEqual(
            [item["operation"] for item in report["transformations"]],
            list(MIGRATION_OPERATIONS),
        )
        self.assertEqual(report["status_downgrades"], [])
        self.assertEqual(
            [
                (item["sequence"], item["loss_id"], item["category"])
                for item in report["unresolved_losses"]
            ],
            [
                (1, "LOSS-001", "v2-document-semantic-reconciliation"),
                (2, "LOSS-002", "trace-link-reconstruction"),
            ],
        )
        self.assertTrue(report["required_reconciliation"])
        _validate_migration_report(report)

        manifest = json.loads((destination / "clone_pack.json").read_text(encoding="utf-8"))
        migration = manifest["migration"]
        self.assertEqual(migration["tool_version"], TOOL_VERSION)
        self.assertEqual(migration["source_files"], report["source_files"])
        self.assertEqual(migration["transformations"], report["transformations"])
        self.assertEqual(migration["unresolved_losses"], report["unresolved_losses"])
        self.assertEqual(
            migration["report_path"],
            "history/migrations/MIG-001/migration_report.json",
        )
        self.assertEqual(migration["report_sha256"], hashlib.sha256(report_bytes).hexdigest())

        invalid_reports: dict[str, dict[str, Any]] = {}
        invalid_reports["additional top-level field"] = copy.deepcopy(report)
        invalid_reports["additional top-level field"]["unexpected"] = True
        invalid_reports["reordered transformations"] = copy.deepcopy(report)
        invalid_reports["reordered transformations"]["transformations"].reverse()
        invalid_reports["tool version mismatch"] = copy.deepcopy(report)
        invalid_reports["tool version mismatch"]["tool_version"] = "99.0.0"
        invalid_reports["source hash mismatch"] = copy.deepcopy(report)
        invalid_reports["source hash mismatch"]["source_files"][0]["sha256"] = "0" * 64
        invalid_reports["unstructured loss extension"] = copy.deepcopy(report)
        invalid_reports["unstructured loss extension"]["unresolved_losses"][0]["note"] = "not allowed"
        for label, invalid_report in invalid_reports.items():
            with self.subTest(label=label):
                with self.assertRaises(ClonePackError) as raised:
                    _validate_migration_report(invalid_report)
                self.assertEqual(raised.exception.diagnostic, "MIGRATION_REPORT_INVALID")
        validated = run_cli("validate", destination, "--profile", "scaffold", "--format", "json")
        self.assertEqual(validated.returncode, 0, validated.stdout + validated.stderr)


if __name__ == "__main__":
    unittest.main()
