from __future__ import annotations

import hashlib
import re
import unittest
from pathlib import Path

from scripts.clonepack import TOOL_VERSION
from scripts.clonepack.constants import PROFILES


ROOT = Path(__file__).resolve().parents[1]


class DocumentationContractTests(unittest.TestCase):
    def test_required_github_documentation_exists(self) -> None:
        required = {
            "LICENSE",
            "README.md",
            "changelog.md",
            "docs/getting-started.md",
            "docs/operating-workflows.md",
            "docs/cli-reference.md",
            "docs/clone-pack-authoring.md",
            "docs/runtime-enforcement-boundaries.md",
            "docs/troubleshooting.md",
            "docs/contributing.md",
        }
        self.assertEqual([], sorted(path for path in required if not (ROOT / path).is_file()))

    def test_cc0_public_domain_dedication_is_canonical_and_consistent(self) -> None:
        license_path = ROOT / "LICENSE"
        self.assertTrue(license_path.is_file())
        self.assertEqual(
            hashlib.sha256(license_path.read_bytes()).hexdigest(),
            "a2010f343487d3f7618affe54f789f5487602331c0a8d03f49e9a7c547cf0499",
        )

        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        contributing = (ROOT / "docs" / "contributing.md").read_text(encoding="utf-8")
        changelog = (ROOT / "changelog.md").read_text(encoding="utf-8")
        self.assertIn("CC0 1.0 Universal", readme)
        self.assertIn("[LICENSE](LICENSE)", readme)
        self.assertIn("CC0 1.0 Universal", contributing)
        self.assertIn("[LICENSE](../LICENSE)", contributing)
        self.assertIn("CC0 1.0 Universal", changelog)
        self.assertNotIn("No `LICENSE` file exists in the current repository", contributing)
        self.assertNotIn("Public distribution remains blocked", readme)

    def test_local_markdown_links_resolve(self) -> None:
        markdown_files = sorted(
            [
                ROOT / "SKILL.md",
                ROOT / "README.md",
                ROOT / "changelog.md",
                *(ROOT / "docs").glob("*.md"),
            ]
        )
        failures: list[str] = []
        pattern = re.compile(r"\[[^\]]+\]\(([^)]+)\)")
        for document in markdown_files:
            text = document.read_text(encoding="utf-8")
            for raw_target in pattern.findall(text):
                target = raw_target.strip().split(" ", 1)[0].strip("<>")
                if not target or target.startswith(("#", "http://", "https://", "mailto:")):
                    continue
                relative = target.split("#", 1)[0]
                resolved = (document.parent / relative).resolve()
                try:
                    resolved.relative_to(ROOT.resolve())
                except ValueError:
                    failures.append(f"{document.relative_to(ROOT)}: link escapes repository: {target}")
                    continue
                if not resolved.exists():
                    failures.append(f"{document.relative_to(ROOT)}: missing link target: {target}")
        self.assertEqual([], failures)

    def test_readme_covers_every_command_mode_and_profile(self) -> None:
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        commands = {
            "init",
            "validate",
            "migrate",
            "capture",
            "parity",
            "scaffold",
            "record-run",
            "record-manual",
            "gap-transition",
            "assure",
            "seal",
            "diff",
        }
        modes = {"mvp-build", "spec-only", "gap-plan", "gap-implement", "pack-migrate"}
        missing = sorted(
            value for value in {*commands, *modes, *PROFILES} if f"`{value}`" not in readme
        )
        self.assertEqual([], missing)

    def test_current_skill_discovery_locations_are_documented(self) -> None:
        combined = "\n".join(
            (ROOT / path).read_text(encoding="utf-8")
            for path in ("README.md", "docs/getting-started.md")
        )
        self.assertIn("$HOME/.agents/skills/clone-software", combined)
        self.assertIn(".agents/skills/clone-software", combined)
        self.assertNotIn("${CODEX_HOME:-$HOME/.codex}/skills", combined)

    def test_critical_non_certification_contracts_are_explicit(self) -> None:
        combined = "\n".join(
            (ROOT / path).read_text(encoding="utf-8")
            for path in ("README.md", "docs/cli-reference.md", "docs/troubleshooting.md")
        )
        required_statements = (
            "capture `PASS`",
            "does not execute the procedure",
            "Governed redaction is applied",
            "emits one canonical JSON result",
            "Differences still exit `0`",
            "unsigned integrity manifest",
        )
        self.assertEqual([], [statement for statement in required_statements if statement not in combined])

    def test_changelog_version_matches_runtime(self) -> None:
        changelog = (ROOT / "changelog.md").read_text(encoding="utf-8")
        self.assertIn(f"Tool `{TOOL_VERSION}` implementation baseline", changelog)

    def test_human_documentation_has_no_clone_pack_generator_markers(self) -> None:
        documents = [ROOT / "README.md", ROOT / "changelog.md", *(ROOT / "docs").glob("*.md")]
        failures: list[str] = []
        for path in documents:
            text = path.read_text(encoding="utf-8")
            prose = re.sub(r"```.*?```", "", text, flags=re.DOTALL)
            prose = re.sub(r"`[^`]*`", "", prose)
            if re.search(r"\[\[(?:REQUIRED|MIGRATION_REQUIRED):", prose):
                failures.append(str(path.relative_to(ROOT)))
        self.assertEqual([], failures)


if __name__ == "__main__":
    unittest.main()
