from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from scripts.clonepack.common import ClonePackError, load_json
from scripts.clonepack.pack import ValidationResult, _validate_seal, create_seal


SKILL_ROOT = Path(__file__).resolve().parents[1]
CLONE_PACK = SKILL_ROOT / "scripts" / "clone_pack.py"
TIMESTAMP = "2026-07-18T16:00:00+00:00"


def canonical_json(value: object) -> str:
    return json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def write_json(path: Path, value: object) -> None:
    path.write_text(canonical_json(value), encoding="utf-8", newline="\n")


def tree_bytes(root: Path) -> dict[str, bytes]:
    return {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


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


class PackHardeningTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)
        self.repository = Path(self.temporary_directory.name) / "repository"
        self.repository.mkdir()
        created = run_cli(
            "init",
            "--product-name",
            "Hardening Fixture",
            "--product-type",
            "cli",
            "--source-description",
            "authorized synthetic reference",
            "--repo-root",
            self.repository,
            "--output-dir",
            "pack",
            "--timestamp",
            TIMESTAMP,
        )
        self.assertEqual(created.returncode, 0, created.stderr)
        self.pack = self.repository / "pack"

    def advance_revision(self, revision: int) -> None:
        manifest_path = self.pack / "clone_pack.json"
        manifest = load_json(manifest_path)
        manifest["pack_revision"] = revision
        for entry in manifest["documents"]:
            path = self.pack / entry["path"]
            text = re.sub(
                r"^pack_revision:\s*\d+\s*$",
                f"pack_revision: {revision}",
                path.read_text(encoding="utf-8"),
                count=1,
                flags=re.MULTILINE,
            )
            path.write_text(text, encoding="utf-8", newline="\n")
            entry["sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
        index_path = self.pack / manifest["index_path"]
        index = load_json(index_path)
        index["pack_revision"] = revision
        write_json(index_path, index)
        for plan_path_value in manifest["plans"].values():
            plan_path = self.pack / plan_path_value
            plan = load_json(plan_path)
            plan["pack_revision"] = revision
            write_json(plan_path, plan)
        write_json(manifest_path, manifest)

    def test_plan_and_frontmatter_revisions_are_bound_to_the_manifest(self) -> None:
        brief = self.pack / "clone_brief.md"
        brief.write_text(
            brief.read_text(encoding="utf-8").replace("pack_revision: 1", "pack_revision: 2", 1),
            encoding="utf-8",
            newline="\n",
        )
        capture = json.loads((self.pack / "capture_plan.json").read_text(encoding="utf-8"))
        capture["pack_revision"] = 2
        write_json(self.pack / "capture_plan.json", capture)

        validated = run_cli("validate", self.pack, "--profile", "scaffold", "--format", "json")
        payload = json.loads(validated.stdout)
        revision_paths = {
            item["path"]
            for item in payload["diagnostics"]
            if item["code"] == "PACK_REVISION_MISMATCH"
        }

        self.assertEqual(validated.returncode, 1)
        self.assertEqual(revision_paths, {"capture_plan.json", "clone_brief.md"})

    def test_hybrid_requires_multiple_explicit_playbooks(self) -> None:
        insufficient = run_cli(
            "init",
            "--product-name",
            "Hybrid Fixture",
            "--product-type",
            "hybrid",
            "--playbook",
            "website",
            "--source-description",
            "authorized hybrid reference",
            "--repo-root",
            self.repository,
            "--output-dir",
            "hybrid-invalid",
            "--timestamp",
            TIMESTAMP,
        )
        self.assertEqual(insufficient.returncode, 2)
        self.assertIn("hybrid requires at least two --playbook values", insufficient.stderr)
        self.assertFalse((self.repository / "hybrid-invalid").exists())

        created = run_cli(
            "init",
            "--product-name",
            "Hybrid Fixture",
            "--product-type",
            "hybrid",
            "--playbook",
            "website",
            "--playbook",
            "api-service-server",
            "--source-description",
            "authorized hybrid reference",
            "--repo-root",
            self.repository,
            "--output-dir",
            "hybrid-valid",
            "--timestamp",
            TIMESTAMP,
        )
        self.assertEqual(created.returncode, 0, created.stderr)
        manifest = load_json(self.repository / "hybrid-valid" / "clone_pack.json")
        self.assertEqual(manifest["playbooks"], ["website", "api-service-server"])

    def test_non_ascii_product_identity_is_preserved_with_an_ascii_pack_id(self) -> None:
        created = run_cli(
            "init",
            "--product-name",
            "克隆工具",
            "--product-type",
            "cli",
            "--source-description",
            "授权的本地参考",
            "--repo-root",
            self.repository,
            "--output-dir",
            "unicode-pack",
            "--timestamp",
            TIMESTAMP,
        )
        self.assertEqual(created.returncode, 0, created.stderr)
        manifest = load_json(self.repository / "unicode-pack" / "clone_pack.json")
        self.assertEqual(manifest["product_name"], "克隆工具")
        self.assertEqual(manifest["reference_source"], "授权的本地参考")
        self.assertRegex(manifest["pack_id"], r"^clone-product-[0-9a-f]{12}-2026-07-18-[0-9a-f]{12}$")

    def test_ready_documents_reject_ambiguous_modal_language(self) -> None:
        marker = re.compile(r"\[\[(?:REQUIRED|MIGRATION_REQUIRED):[^\]]*\]\]")
        for name in ("clone_brief.md", "evidence_ledger.md"):
            path = self.pack / name
            text = marker.sub("RESOLVED", path.read_text(encoding="utf-8"))
            if name == "clone_brief.md":
                text += "\nThis behavior should remain stable.\n"
            path.write_text(text, encoding="utf-8", newline="\n")

        evidence = self.pack / "evidence_ledger.md"
        anchor = "ENV-001 synthetic baseline environment"
        anchor_line = f"- {anchor}\n"
        evidence.write_text(
            evidence.read_text(encoding="utf-8") + anchor_line,
            encoding="utf-8",
            newline="\n",
        )
        manifest = load_json(self.pack / "clone_pack.json")
        manifest["reference_baseline_id"] = "BASE-001"
        write_json(self.pack / "clone_pack.json", manifest)
        write_json(
            self.pack / "clone_index.json",
            {
                "schema_version": "clone-index/v2",
                "pack_id": manifest["pack_id"],
                "pack_revision": 1,
                "records": [
                    {
                        "id": "ENV-001",
                        "kind": "ENV",
                        "locator": {
                            "path": "evidence_ledger.md",
                            "anchor": anchor,
                            "sha256": hashlib.sha256(anchor_line.encode("utf-8")).hexdigest(),
                        },
                        "links": {},
                        "applicability": "MVP",
                        "state": "READY",
                        "attributes": {},
                    }
                ],
            },
        )
        capture = load_json(self.pack / "capture_plan.json")
        capture["cases"] = [
            {
                "id": "CAP-001",
                "adapter": "manual",
                "side": "reference",
                "environment_id": "ENV-001",
                "required": True,
                "authorization_decision_ids": ["DEC-001"],
                "safe_test_environment": True,
                "timeout_seconds": 30,
                "input": {"source_path": "evidence/manual.txt"},
                "lifecycle": {"setup": None, "teardown": None},
                "redactions": [],
                "result": None,
            }
        ]
        write_json(self.pack / "capture_plan.json", capture)

        validated = run_cli("validate", self.pack, "--profile", "baseline-ready", "--format", "json")
        payload = json.loads(validated.stdout)

        self.assertEqual(validated.returncode, 1)
        self.assertIn("AMBIGUOUS_LANGUAGE", {item["code"] for item in payload["diagnostics"]})
        self.assertTrue(any("'should'" in item["message"] for item in payload["diagnostics"]))

    def test_same_revision_reseal_is_refused_without_changing_bytes(self) -> None:
        create_seal(self.pack, "scaffold", TIMESTAMP)
        before = tree_bytes(self.pack)

        with self.assertRaises(ClonePackError) as raised:
            create_seal(self.pack, "scaffold", "2026-07-18T16:01:00+00:00")

        self.assertEqual(raised.exception.diagnostic, "SEAL_REVISION_NOT_ADVANCED")
        self.assertEqual(tree_bytes(self.pack), before)
        self.assertFalse((self.pack / "history" / "seals").exists())

    def test_revision_advanced_successor_archives_prior_revision_and_validates(self) -> None:
        first = create_seal(self.pack, "scaffold", TIMESTAMP)
        first_bytes = (self.pack / "seal.json").read_bytes()
        first_digest = hashlib.sha256(first_bytes).hexdigest()
        self.advance_revision(2)

        second = create_seal(self.pack, "scaffold", "2026-07-18T16:01:00+00:00")

        archive = self.pack / "history" / "seals" / f"revision-1-{first_digest[:16]}.json"
        self.assertEqual(archive.read_bytes(), first_bytes)
        self.assertEqual(first["pack_revision"], 1)
        self.assertEqual(second["pack_revision"], 2)
        self.assertIn(archive.relative_to(self.pack).as_posix(), second["files"])
        result = ValidationResult()
        _validate_seal(self.pack, load_json(self.pack / "clone_pack.json"), "scaffold", result)
        self.assertEqual(result.exit_code, 0, result.sorted_all())


if __name__ == "__main__":
    unittest.main()
