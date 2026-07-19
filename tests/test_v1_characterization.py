from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


SKILL_ROOT = Path(__file__).resolve().parents[1]
NEW_PACK = SKILL_ROOT / "scripts" / "new_clone_pack.py"
LEGACY_VALIDATE_PACK = SKILL_ROOT / "scripts" / "clonepack" / "legacy_v1.py"
DISPATCH_VALIDATE_PACK = SKILL_ROOT / "scripts" / "validate_clone_pack.py"
VALID_FIXTURE = Path(__file__).resolve().parent / "fixtures" / "v1-valid"

DOCUMENTS = [
    "clone_brief.md",
    "evidence_ledger.md",
    "clone_specification.md",
    "mvp_build_plan.md",
    "acceptance_matrix.md",
    "gaps_analysis.md",
    "gap_implementation_plan.md",
]


def run_script(script: Path, *arguments: object) -> subprocess.CompletedProcess[str]:
    environment = os.environ.copy()
    environment["LC_ALL"] = "C"
    environment["PYTHONHASHSEED"] = "0"
    return subprocess.run(
        [sys.executable, str(script), *(str(argument) for argument in arguments)],
        cwd=SKILL_ROOT,
        env=environment,
        text=True,
        encoding="utf-8",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )


class V1CharacterizationTests(unittest.TestCase):
    maxDiff = None

    def setUp(self) -> None:
        self.assertTrue(NEW_PACK.is_file(), f"missing legacy initializer: {NEW_PACK}")
        self.assertTrue(
            LEGACY_VALIDATE_PACK.is_file(),
            f"missing frozen v1 validator: {LEGACY_VALIDATE_PACK}",
        )
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)
        self.temp_root = Path(self.temporary_directory.name)
        self.repo_root = self.temp_root / "repository"
        self.repo_root.mkdir()

    def init_pack(self, output_dir: str = "docs/clone") -> subprocess.CompletedProcess[str]:
        return run_script(
            NEW_PACK,
            "--product-name",
            "Characterization Product",
            "--product-type",
            "cli",
            "--source-description",
            "Reference CLI 1.0",
            "--repo-root",
            self.repo_root,
            "--output-dir",
            output_dir,
        )

    def test_initializer_writes_exact_v1_manifest_and_document_set(self) -> None:
        result = self.init_pack()
        pack = self.repo_root / "docs" / "clone"

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stderr, "")
        self.assertEqual(
            {path.name for path in pack.iterdir()},
            {*DOCUMENTS, "clone_pack.json"},
        )

        manifest = json.loads((pack / "clone_pack.json").read_text(encoding="utf-8"))
        self.assertEqual(
            manifest,
            {
                "schema_version": "clone-pack/v1",
                "pack_id": manifest["pack_id"],
                "product_name": "Characterization Product",
                "product_type": "cli",
                "reference_source": "Reference CLI 1.0",
                "created_at": manifest["created_at"],
                "repository_root": self.repo_root.resolve().as_posix(),
                "documents": DOCUMENTS,
            },
        )
        self.assertRegex(
            manifest["pack_id"],
            r"^clone-characterization-product-\d{4}-\d{2}-\d{2}$",
        )
        self.assertRegex(
            manifest["created_at"],
            r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\+00:00$",
        )
        expected_stdout = (
            f"Created clone pack: {pack.resolve()}\n"
            + "".join(f"  {name}\n" for name in [*DOCUMENTS, "clone_pack.json"])
            + "The pack is scaffolding. Replace every [[REQUIRED: ...]] marker before validation.\n"
        )
        self.assertEqual(result.stdout, expected_stdout)

    def test_initializer_refuses_all_existing_pack_collisions(self) -> None:
        first = self.init_pack()
        self.assertEqual(first.returncode, 0, first.stderr)

        second = self.init_pack()
        pack = (self.repo_root / "docs" / "clone").resolve()
        collisions = [*(pack / name for name in DOCUMENTS), pack / "clone_pack.json"]
        expected_stderr = (
            "ERROR: refusing to overwrite existing pack files:\n  "
            + "\n  ".join(str(path) for path in collisions)
            + "\n"
        )

        self.assertEqual(second.returncode, 2)
        self.assertEqual(second.stdout, "")
        self.assertEqual(second.stderr, expected_stderr)

    def test_initializer_rejects_output_outside_or_equal_to_repository_root(self) -> None:
        outside = self.temp_root / "outside"
        outside_result = self.init_pack("../outside")
        root_result = self.init_pack(".")

        self.assertEqual(outside_result.returncode, 2)
        self.assertEqual(outside_result.stdout, "")
        self.assertEqual(
            outside_result.stderr,
            f"ERROR: output directory must remain inside repository root: {outside.resolve()}\n",
        )
        self.assertFalse(outside.exists())

        self.assertEqual(root_result.returncode, 2)
        self.assertEqual(root_result.stdout, "")
        self.assertEqual(
            root_result.stderr,
            "ERROR: output directory must not be the repository root\n",
        )

    def test_untouched_scaffold_fails_with_deterministic_diagnostics(self) -> None:
        initialized = self.init_pack()
        self.assertEqual(initialized.returncode, 0, initialized.stderr)
        pack = (self.repo_root / "docs" / "clone").resolve()

        first = run_script(LEGACY_VALIDATE_PACK, pack, "--max-problems", "8")
        second = run_script(LEGACY_VALIDATE_PACK, pack, "--max-problems", "8")

        self.assertEqual(first.returncode, 1)
        self.assertEqual(first.stdout, "")
        self.assertEqual(first.stderr, second.stderr)
        expected_lines = [
            "FAIL: 446 validation problem(s)",
            f"  {pack / 'clone_brief.md'}:1: document_state must be validated, active, closed, or superseded",
            f"  {pack / 'clone_brief.md'}:16: unresolved required marker: [[REQUIRED: name the requesting authority and product owner]]",
            f"  {pack / 'clone_brief.md'}:16: unresolved required marker: [[REQUIRED: E-### or DEC-###]]",
            f"  {pack / 'clone_brief.md'}:17: unresolved required marker: [[REQUIRED: ownership, license, engagement, or explicit permission]]",
            f"  {pack / 'clone_brief.md'}:17: unresolved required marker: [[REQUIRED: E-### or DEC-###]]",
            f"  {pack / 'clone_brief.md'}:18: unresolved required marker: [[REQUIRED: exact URLs, artifacts, accounts, endpoints, and environments]]",
            f"  {pack / 'clone_brief.md'}:18: unresolved required marker: [[REQUIRED: E-### or DEC-###]]",
            f"  {pack / 'clone_brief.md'}:19: unresolved required marker: [[REQUIRED: exact access, probe, write, or distribution exclusions]]",
            "  ... 438 additional problem(s); use --max-problems 0 to print all",
        ]
        self.assertEqual(first.stderr, "\n".join(expected_lines) + "\n")

    def test_hand_authored_v1_fixture_is_structurally_valid(self) -> None:
        result = run_script(LEGACY_VALIDATE_PACK, VALID_FIXTURE)

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stderr, "")
        self.assertEqual(
            result.stdout,
            f"PASS: clone pack is structurally valid: {VALID_FIXTURE.resolve()}\n"
            "Semantic fidelity and evidence quality still require manual review.\n",
        )

    def test_require_verified_mvp_accepts_verified_fixture(self) -> None:
        result = run_script(
            LEGACY_VALIDATE_PACK, VALID_FIXTURE, "--require-verified-mvp"
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stderr, "")
        self.assertEqual(
            result.stdout,
            f"PASS: clone pack is structurally valid: {VALID_FIXTURE.resolve()}\n"
            "PASS: every MVP requirement is VERIFIED and verdict is VERIFIED_MVP\n"
            "Semantic fidelity and evidence quality still require manual review.\n",
        )

    def test_require_verified_mvp_rejects_structurally_valid_hold(self) -> None:
        pack = self.temp_root / "v1-hold"
        shutil.copytree(VALID_FIXTURE, pack)
        acceptance_path = pack / "acceptance_matrix.md"
        acceptance = acceptance_path.read_text(encoding="utf-8")
        acceptance = acceptance.replace(
            "| REQ-001 | src/fixture.py:main | AC-001 | TEST-001 | VERIFIED | RUN-001 | none |",
            "| REQ-001 | src/fixture.py:main | AC-001 | TEST-001 | NOT_STARTED | none | none |",
        ).replace("- Verdict: VERIFIED_MVP", "- Verdict: HOLD")
        acceptance_path.write_text(acceptance, encoding="utf-8", newline="\n")

        ordinary = run_script(LEGACY_VALIDATE_PACK, pack)
        verified = run_script(
            LEGACY_VALIDATE_PACK, pack, "--require-verified-mvp"
        )

        self.assertEqual(ordinary.returncode, 0, ordinary.stderr)
        self.assertEqual(verified.returncode, 1)
        self.assertEqual(verified.stdout, "")
        self.assertEqual(
            verified.stderr,
            "FAIL: 2 validation problem(s)\n"
            f"  {acceptance_path}: MVP requirements are not VERIFIED: REQ-001\n"
            f"  {acceptance_path}: --require-verified-mvp requires Verdict: VERIFIED_MVP\n",
        )

    @unittest.skipUnless(
        DISPATCH_VALIDATE_PACK.is_file(),
        "v2 dispatcher wrapper is not present yet",
    )
    def test_dispatcher_requires_v2_migration_for_evidence_backed_verification(self) -> None:
        dispatched = run_script(
            DISPATCH_VALIDATE_PACK, VALID_FIXTURE, "--require-verified-mvp"
        )

        self.assertEqual(dispatched.returncode, 3)
        self.assertEqual(dispatched.stdout, "")
        self.assertEqual(
            dispatched.stderr,
            "MIGRATION_REQUIRED: v1 packs cannot receive evidence-backed v2 "
            "verified-mvp certification\n",
        )


if __name__ == "__main__":
    unittest.main()
