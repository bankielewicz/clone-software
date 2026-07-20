from __future__ import annotations

import unittest
from pathlib import Path
import re

from scripts.clonepack import TOOL_VERSION


ROOT = Path(__file__).resolve().parents[1]


class FullStackQaDocumentationTests(unittest.TestCase):
    def read(self, relative: str) -> str:
        path = ROOT / relative
        self.assertTrue(path.is_file(), f"missing required documentation: {relative}")
        return path.read_text(encoding="utf-8")

    def test_22_full_stack_qa_documentation_and_template_exist(self) -> None:
        self.assertEqual(TOOL_VERSION, "2.3.0")
        for relative in (
            "references/full-stack-qa.md",
            "docs/full-stack-qa.md",
            "assets/schemas/full-stack-qa-plan-v1.schema.json",
            "assets/schemas/full-stack-qa-result-v1.schema.json",
            "assets/templates-v2/full_stack_qa_plan.json",
            "assets/templates-v2/full_stack_qa_result.json",
        ):
            self.assertTrue((ROOT / relative).is_file(), relative)

    def test_skill_and_agent_metadata_route_full_stack_qa_requests(self) -> None:
        combined = "\n".join(self.read(path) for path in ("SKILL.md", "agents/openai.yaml")).lower()
        for term in ("playwright", "full-stack", "gui", "ci"):
            self.assertIn(term, combined)
        self.assertIn("references/full-stack-qa.md", combined)

    def test_documented_boundary_requires_ui_wire_api_and_persistence_proof(self) -> None:
        combined = "\n".join(
            self.read(path)
            for path in (
                "README.md",
                "references/full-stack-qa.md",
                "docs/full-stack-qa.md",
                "docs/runtime-enforcement-boundaries.md",
            )
        )
        for phrase in (
            "application-owned services",
            "UI",
            "request and response",
            "API or data postcondition",
            "persistence",
            "does not prove unobserved mid-tier control flow",
            "never installs Playwright",
            "BLOCKED",
            "clone-full-stack-qa-result/v1",
            "latest linked",
            "does not parse CI YAML",
            "does not inspect service internals",
            "independent",
            "supporting_services",
            "additional_exchanges",
            "blocked_exit_codes",
            "playwright_project",
            "same `service_id`",
            "protocol",
            "endpoint",
        ):
            self.assertIn(phrase, combined)

    def test_full_stack_commands_are_target_repository_safe(self) -> None:
        for relative in (
            "references/full-stack-qa.md",
            "docs/full-stack-qa.md",
            "docs/clone-pack-authoring.md",
            "docs/runtime-enforcement-boundaries.md",
            "docs/troubleshooting.md",
        ):
            content = self.read(relative)
            self.assertNotIn("python3 scripts/clone_pack.py", content, relative)
        combined = "\n".join(
            self.read(path)
            for path in (
                "references/full-stack-qa.md",
                "docs/full-stack-qa.md",
                "docs/clone-pack-authoring.md",
                "docs/troubleshooting.md",
            )
        )
        self.assertIn('sys.path.insert(0,sys.argv[1])', combined)

    def test_human_guide_records_primary_source_basis(self) -> None:
        guide = self.read("docs/full-stack-qa.md")
        for url in (
            "https://playwright.dev/docs/best-practices",
            "https://playwright.dev/docs/api-testing",
            "https://playwright.dev/docs/network",
            "https://playwright.dev/docs/test-webserver",
            "https://playwright.dev/docs/ci",
            "https://playwright.dev/docs/trace-viewer-intro",
            "https://playwright.dev/docs/test-snapshots",
            "https://docs.github.com/en/actions/tutorials/use-containerized-services/create-postgresql-service-containers",
        ):
            self.assertIn(url, guide)

    def test_docs_do_not_present_installer_shims_as_skill_behavior(self) -> None:
        combined = "\n".join(
            self.read(path)
            for path in ("README.md", "references/full-stack-qa.md", "docs/full-stack-qa.md")
        )
        executable_examples = "\n".join(re.findall(r"```(?:bash|sh|shell)\n(.*?)```", combined, re.DOTALL))
        for forbidden in ("npx playwright install", "pnpm dlx", "bunx playwright"):
            self.assertNotIn(forbidden, executable_examples)

    def test_cli_reference_documents_declared_blocked_gate_exits(self) -> None:
        reference = self.read("docs/cli-reference.md")
        for phrase in (
            "blocked_exit_codes",
            "RUN_DECLARED_BLOCK",
            "excluding `expected_exit`",
            "original repository `source_path`",
        ):
            self.assertIn(phrase, reference)

    def test_full_stack_contract_documents_hardening_fields_and_boundaries(self) -> None:
        required = (
            "fresh_artifact_paths",
            "RUN_ARTIFACT_STALE",
            "LOOPBACK",
            "AUTHORIZED_SANDBOX",
            "@playwright/test",
            "playwright-core",
            "does not parse the lockfile",
            "identity_bindings",
            "captured_value_sha256",
            "execution_contract",
        )
        for relative in (
            "README.md",
            "references/full-stack-qa.md",
            "docs/full-stack-qa.md",
            "docs/runtime-enforcement-boundaries.md",
        ):
            content = self.read(relative)
            for phrase in required:
                self.assertIn(phrase, content, f"{relative}: {phrase}")

        cli = self.read("docs/cli-reference.md")
        for phrase in ("fresh_artifact_paths", "RUN_ARTIFACT_STALE"):
            self.assertIn(phrase, cli)

    def test_review_hardening_boundaries_are_documented(self) -> None:
        normative = "\n".join(
            self.read(relative)
            for relative in (
                "README.md",
                "references/full-stack-qa.md",
                "docs/full-stack-qa.md",
                "docs/runtime-enforcement-boundaries.md",
            )
        )
        for phrase in (
            "percent-decodes the query",
            "referenced by the same journey",
            "gap-plan",
        ):
            self.assertIn(phrase, normative)

    def test_operational_mirrors_explain_review_hardening_recovery(self) -> None:
        for relative in (
            "docs/troubleshooting.md",
            "docs/clone-pack-authoring.md",
            "docs/operating-workflows.md",
            "docs/contributing.md",
        ):
            self.assertIn("execution_contract", self.read(relative), relative)

        troubleshooting = self.read("docs/troubleshooting.md")
        for phrase in (
            "RUN_CONTRACT_STALE",
            "percent-decodes",
            "same journey",
            "before process execution",
        ):
            self.assertIn(phrase, troubleshooting)

        for relative in (
            "references/full-stack-qa.md",
            "docs/full-stack-qa.md",
            "docs/runtime-enforcement-boundaries.md",
        ):
            self.assertIn("before process execution", self.read(relative), relative)


if __name__ == "__main__":
    unittest.main()
