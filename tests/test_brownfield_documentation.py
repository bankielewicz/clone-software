from __future__ import annotations

import re
import unittest
from pathlib import Path

from scripts.clonepack import TOOL_VERSION


ROOT = Path(__file__).resolve().parents[1]


def read_required(relative: str) -> str:
    path = ROOT / relative
    if not path.is_file():
        raise AssertionError(f"required documentation file is missing: {relative}")
    return path.read_text(encoding="utf-8")


class BrownfieldDocumentationTests(unittest.TestCase):
    def test_21_documentation_set_exists(self) -> None:
        required = {
            "AGENTS.md",
            "references/brownfield-enhancement.md",
            "docs/brownfield-enhancement.md",
            ".github/workflows/ci.yml",
            ".github/workflows/dependency-review.yml",
            ".github/dependabot.yml",
        }
        self.assertEqual([], sorted(path for path in required if not (ROOT / path).is_file()))

    def test_runtime_reports_22_and_changelog_retains_21_history(self) -> None:
        self.assertEqual(TOOL_VERSION, "2.2.0")
        changelog = (ROOT / "changelog.md").read_text(encoding="utf-8")
        self.assertIn("Tool `2.2.0` implementation baseline", changelog)
        self.assertIn("Tool `2.1.0` implementation baseline", changelog)

    def test_skill_and_agent_metadata_route_brownfield_triggers(self) -> None:
        combined = "\n".join(read_required(path) for path in ("SKILL.md", "agents/openai.yaml")).lower()
        for trigger in ("enhance", "extend", "modernize", "refactor", "upgrade", "migrate", "harden"):
            self.assertIn(trigger, combined)
        self.assertIn("references/brownfield-enhancement.md", combined)

    def test_public_docs_cover_every_enhancement_command_mode_and_profile(self) -> None:
        combined = "\n".join(
            read_required(path)
            for path in (
                "README.md",
                "docs/operating-workflows.md",
                "docs/cli-reference.md",
                "docs/brownfield-enhancement.md",
            )
        )
        required = {
            "enhancement-plan",
            "enhancement-build",
            "enhancement-init",
            "repo-snapshot",
            "baseline-run",
            "regression",
            "verify-scope",
            "enhancement-transition",
            "rehash",
            "repository-adopted",
            "enhancement-ready",
            "implementation",
            "verified-enhancement",
        }
        self.assertEqual([], sorted(value for value in required if f"`{value}`" not in combined))

        profile_contract_docs = (
            "docs/cli-reference.md",
            "docs/runtime-enforcement-boundaries.md",
            "docs/clone-pack-authoring.md",
            "changelog.md",
        )
        self.assertEqual(
            [],
            [
                path
                for path in profile_contract_docs
                if "`implementation`" not in read_required(path)
            ],
        )

    def test_handoff_contract_and_no_delivery_boundary_are_exact(self) -> None:
        guide = read_required("docs/brownfield-enhancement.md")
        fields = (
            "mode",
            "enhancement ID",
            "change types",
            "adopted snapshot",
            "candidate snapshot",
            "affected surfaces",
            "compatibility decisions",
            "changed paths",
            "command results",
            "preservation results",
            "security and dependency deltas",
            "residual gaps",
            "seal path",
            "blockers",
        )
        self.assertEqual([], [field for field in fields if field not in guide])
        self.assertIn("not deployed or merged", guide)

    def test_research_basis_links_are_recorded_without_claiming_certification(self) -> None:
        guide = read_required("docs/brownfield-enhancement.md")
        links = (
            "https://www.sei.cmu.edu/library/architecture-reconstruction-guidelines-third-edition/",
            "https://nvlpubs.nist.gov/nistpubs/Legacy/IR/nistir6407.pdf",
            "https://git-scm.com/docs/git-status.html",
            "https://semver.org/",
            "https://csrc.nist.gov/pubs/sp/800/218/final",
            "https://docs.github.com/en/code-security/concepts/supply-chain-security/dependency-review",
            "https://docs.oasis-open.org/sarif/sarif/v2.1.0/os/sarif-v2.1.0-os.html",
            "https://documentation.red-gate.com/flyway/reference/commands/validate",
            "https://openfeature.dev/specification/",
            "https://opentelemetry.io/docs/concepts/semantic-conventions/",
            "https://learn.chatgpt.com/docs/build-skills.md",
            "https://learn.chatgpt.com/docs/agent-approvals-security#sandbox-and-approvals",
        )
        self.assertEqual([], [link for link in links if link not in guide])
        self.assertNotRegex(guide.lower(), r"\b(certified|guarantees all external consumers)\b")

    def test_published_docs_have_no_unresolved_or_aspirational_markers(self) -> None:
        documents = [
            ROOT / "README.md",
            ROOT / "changelog.md",
            ROOT / "SKILL.md",
            *(ROOT / "docs").glob("*.md"),
            *(ROOT / "references").glob("*.md"),
        ]
        failures: list[str] = []
        marker = re.compile(
            r"^\s*(?:[-*]\s*)?(?:TODO|TBD|FIXME|COMING SOON|NOT YET IMPLEMENTED|PLANNED FEATURE)\s*[:\-]",
            flags=re.IGNORECASE | re.MULTILINE,
        )
        for path in documents:
            text = path.read_text(encoding="utf-8")
            prose = re.sub(r"```.*?```", "", text, flags=re.DOTALL)
            if marker.search(prose):
                failures.append(path.relative_to(ROOT).as_posix())
        self.assertEqual([], failures)


if __name__ == "__main__":
    unittest.main()
