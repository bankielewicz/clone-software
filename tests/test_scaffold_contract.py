from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from scripts.clonepack import scaffold as scaffold_module
from scripts.clonepack.common import ClonePackError
from tests.test_v2_regression import (
    PINNED_TIMESTAMP,
    SKILL_ROOT,
    read_json,
    run_cli,
    tree_bytes,
    write_json,
)


AUDITED_PROFILE_IDS = ("static-web-esm", "python-src", "typescript-src", "rust-crate")
NOT_APPLICABLE_COMMANDS = {"setup": None, "test": None, "build": None, "run": None}


class ScaffoldContractTests(unittest.TestCase):
    maxDiff = None

    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)
        self.repository = Path(self.temporary_directory.name) / "repository"
        self.repository.mkdir()
        initialized = run_cli(
            "init",
            "--product-name",
            "Scaffold Contract",
            "--product-type",
            "cli",
            "--source-description",
            "Pinned local scaffold reference",
            "--repo-root",
            self.repository,
            "--output-dir",
            "clone-pack",
            "--timestamp",
            PINNED_TIMESTAMP,
        )
        self.assertEqual(initialized.returncode, 0, initialized.stderr)
        self.pack = self.repository / "clone-pack"
        self.catalog = read_json(SKILL_ROOT / "assets" / "scaffolds" / "catalog.json")

    def profile(self, profile_id: str) -> dict[str, object]:
        return next(item for item in self.catalog["profiles"] if item["id"] == profile_id)

    def write_catalog_plan(self, profile_id: str, *, output_root: str = "generated") -> dict[str, object]:
        profile = self.profile(profile_id)
        plan_path = self.pack / "scaffold_plan.json"
        plan = read_json(plan_path)
        plan.update(
            {
                "stack_decision_id": "STACK-001",
                "profile_id": profile_id,
                "template": profile["template"],
                "output_root": output_root,
                "required_paths": profile["required_paths"],
                "commands": profile["commands"],
                "applied": False,
            }
        )
        write_json(plan_path, plan)
        return profile

    def expected_destinations(self, profile: dict[str, object], output_root: str = "generated") -> list[str]:
        prefix = "" if output_root == "." else f"{output_root}/"
        template_root = SKILL_ROOT / "assets" / "scaffolds" / str(profile["template"])
        return sorted(
            prefix + path.relative_to(template_root).as_posix()
            for path in template_root.rglob("*")
            if path.is_file()
        )

    def test_initial_plan_does_not_claim_a_stack_or_custom_profile(self) -> None:
        plan = read_json(self.pack / "scaffold_plan.json")
        before = tree_bytes(self.repository)

        rejected = run_cli("scaffold", self.pack)

        self.assertRegex(plan["stack_decision_id"], r"^\[\[REQUIRED:")
        self.assertNotIn("custom", plan["profile_id"])
        self.assertEqual(rejected.returncode, 1)
        self.assertIn("SCAFFOLD_PLAN_INVALID", rejected.stderr)
        self.assertEqual(tree_bytes(self.repository), before)

    def test_all_four_profiles_preview_exact_catalog_inventory_and_commands_without_writes(self) -> None:
        for profile_id in AUDITED_PROFILE_IDS:
            with self.subTest(profile_id=profile_id):
                profile = self.write_catalog_plan(profile_id)
                before = tree_bytes(self.repository)

                preview = run_cli("scaffold", self.pack)

                self.assertEqual(preview.returncode, 0, preview.stderr)
                self.assertEqual(preview.stderr, "")
                self.assertEqual(
                    json.loads(preview.stdout),
                    {
                        "applied": False,
                        "commands": profile["commands"],
                        "disposition": "catalog",
                        "files": self.expected_destinations(profile),
                        "profile_id": profile_id,
                    },
                )
                self.assertEqual(tree_bytes(self.repository), before)

    def test_apply_creates_exact_inventory_and_only_marks_the_plan_applied(self) -> None:
        profile = self.write_catalog_plan("python-src")
        before = tree_bytes(self.repository)

        applied = run_cli("scaffold", self.pack, "--apply")

        self.assertEqual(applied.returncode, 0, applied.stderr)
        payload = json.loads(applied.stdout)
        expected_files = self.expected_destinations(profile)
        self.assertEqual(payload["files"], expected_files)
        self.assertEqual(payload["commands"], profile["commands"])
        self.assertTrue(payload["applied"])
        self.assertEqual(payload["disposition"], "catalog")
        for path in expected_files:
            self.assertTrue((self.repository / path).is_file(), path)

        after = tree_bytes(self.repository)
        plan_relative = "clone-pack/scaffold_plan.json"
        for path, content in before.items():
            if path != plan_relative:
                self.assertEqual(after[path], content, path)
        plan = read_json(self.pack / "scaffold_plan.json")
        self.assertTrue(plan["applied"])
        self.assertEqual(plan["template"], profile["template"])
        self.assertEqual(plan["required_paths"], profile["required_paths"])
        self.assertEqual(plan["commands"], profile["commands"])

    def test_catalog_metadata_mismatches_fail_before_writes(self) -> None:
        mutations = {
            "template": lambda plan: plan.update({"template": "rust-crate"}),
            "required_paths": lambda plan: plan.update({"required_paths": list(reversed(plan["required_paths"]))}),
            "commands": lambda plan: plan["commands"].update({"setup": ["false"]}),
        }
        for field, mutate in mutations.items():
            with self.subTest(field=field):
                self.write_catalog_plan("python-src")
                plan_path = self.pack / "scaffold_plan.json"
                plan = read_json(plan_path)
                mutate(plan)
                write_json(plan_path, plan)
                before = tree_bytes(self.repository)

                rejected = run_cli("scaffold", self.pack)

                self.assertEqual(rejected.returncode, 1)
                self.assertEqual(rejected.stdout, "")
                self.assertIn("SCAFFOLD_PLAN_CATALOG_MISMATCH", rejected.stderr)
                self.assertIn(field, rejected.stderr)
                self.assertEqual(tree_bytes(self.repository), before)

    def test_custom_profile_is_rejected_by_the_plan_schema(self) -> None:
        self.write_catalog_plan("python-src")
        plan_path = self.pack / "scaffold_plan.json"
        plan = read_json(plan_path)
        plan["profile_id"] = "custom"
        write_json(plan_path, plan)
        before = tree_bytes(self.repository)

        rejected = run_cli("scaffold", self.pack)

        self.assertEqual(rejected.returncode, 1)
        self.assertEqual(rejected.stdout, "")
        self.assertIn("SCAFFOLD_PLAN_INVALID", rejected.stderr)
        self.assertEqual(tree_bytes(self.repository), before)

    def test_brownfield_not_applicable_is_an_explicit_no_op_for_preview_and_apply(self) -> None:
        adopted = self.repository / "adopted.txt"
        adopted.write_text("existing implementation\n", encoding="utf-8", newline="\n")
        plan_path = self.pack / "scaffold_plan.json"
        plan = read_json(plan_path)
        plan.update(
            {
                "stack_decision_id": "STACK-001",
                "profile_id": "not-applicable",
                "template": "not-applicable",
                "output_root": ".",
                "required_paths": [],
                "commands": dict(NOT_APPLICABLE_COMMANDS),
                "applied": False,
            }
        )
        write_json(plan_path, plan)
        before = tree_bytes(self.repository)
        expected = {
            "applied": False,
            "commands": NOT_APPLICABLE_COMMANDS,
            "disposition": "not-applicable",
            "files": [],
            "profile_id": "not-applicable",
        }

        preview = run_cli("scaffold", self.pack)
        applied = run_cli("scaffold", self.pack, "--apply")

        self.assertEqual(preview.returncode, 0, preview.stderr)
        self.assertEqual(applied.returncode, 0, applied.stderr)
        self.assertEqual(json.loads(preview.stdout), expected)
        self.assertEqual(json.loads(applied.stdout), expected)
        self.assertEqual(tree_bytes(self.repository), before)

    def test_apply_race_preserves_the_racer_path_and_rolls_back_owned_files(self) -> None:
        self.write_catalog_plan("python-src")
        target = self.repository / "generated" / "pyproject.toml"
        original_open = os.open

        def racing_open(path: object, flags: int, mode: int = 0o777, *, dir_fd: int | None = None) -> int:
            if Path(path) == target and flags & os.O_EXCL:
                target.write_text("owned by racer\n", encoding="utf-8", newline="\n")
            if dir_fd is None:
                return original_open(path, flags, mode)
            return original_open(path, flags, mode, dir_fd=dir_fd)

        with mock.patch.object(scaffold_module.os, "open", side_effect=racing_open):
            with self.assertRaises(ClonePackError) as raised:
                scaffold_module.apply_scaffold(SKILL_ROOT, self.pack, apply=True)

        self.assertEqual(raised.exception.diagnostic, "SCAFFOLD_COLLISION")
        self.assertEqual(target.read_text(encoding="utf-8"), "owned by racer\n")
        self.assertFalse((self.repository / "generated" / "README.md").exists())
        self.assertEqual(
            [path.relative_to(self.repository / "generated").as_posix() for path in (self.repository / "generated").rglob("*")],
            ["pyproject.toml"],
        )
        self.assertFalse(read_json(self.pack / "scaffold_plan.json")["applied"])

    def test_plan_write_failure_rolls_back_every_created_file_and_directory(self) -> None:
        self.write_catalog_plan("rust-crate")

        with mock.patch.object(scaffold_module, "atomic_write_json", side_effect=OSError("injected plan write failure")):
            with self.assertRaises(ClonePackError) as raised:
                scaffold_module.apply_scaffold(SKILL_ROOT, self.pack, apply=True)

        self.assertEqual(raised.exception.diagnostic, "SCAFFOLD_PLAN_WRITE_FAILED")
        self.assertFalse((self.repository / "generated").exists())
        self.assertFalse(read_json(self.pack / "scaffold_plan.json")["applied"])

    def test_existing_non_directory_parent_is_a_deterministic_collision(self) -> None:
        self.write_catalog_plan("static-web-esm")
        blocker = self.repository / "generated"
        blocker.write_text("not a directory\n", encoding="utf-8", newline="\n")
        before = tree_bytes(self.repository)

        rejected = run_cli("scaffold", self.pack, "--apply")

        self.assertEqual(rejected.returncode, 1)
        self.assertEqual(rejected.stdout, "")
        self.assertIn("SCAFFOLD_COLLISION", rejected.stderr)
        self.assertNotIn("INTERNAL_ERROR", rejected.stderr)
        self.assertEqual(tree_bytes(self.repository), before)


if __name__ == "__main__":
    unittest.main()
