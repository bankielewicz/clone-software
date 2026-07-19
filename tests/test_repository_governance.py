from __future__ import annotations

import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
AGENTS = ROOT / "AGENTS.md"
CI_WORKFLOW = ROOT / ".github" / "workflows" / "ci.yml"
DEPENDENCY_REVIEW_WORKFLOW = ROOT / ".github" / "workflows" / "dependency-review.yml"
DEPENDABOT = ROOT / ".github" / "dependabot.yml"
CHECKOUT_SHA = "9c091bb21b7c1c1d1991bb908d89e4e9dddfe3e0"
SETUP_PYTHON_SHA = "ece7cb06caefa5fff74198d8649806c4678c61a1"
DEPENDENCY_REVIEW_SHA = "a1d282b36b6f3519aa1f3fc636f609c47dddb294"


def read_required(path: Path) -> str:
    if not path.is_file():
        raise AssertionError(f"required repository-governance file is missing: {path.relative_to(ROOT)}")
    return path.read_text(encoding="utf-8")


def top_level_block(text: str, key: str) -> str:
    lines = text.splitlines()
    start = next(
        (
            index
            for index, line in enumerate(lines)
            if re.fullmatch(rf"{re.escape(key)}\s*:\s*", line)
        ),
        None,
    )
    if start is None:
        return ""
    retained: list[str] = []
    for line in lines[start + 1 :]:
        if line and not line[0].isspace() and not line.lstrip().startswith("#"):
            break
        retained.append(line)
    return "\n".join(retained)


def normalized_shell(text: str) -> str:
    without_continuations = re.sub(r"\\\s*\n", " ", text)
    return re.sub(r"\s+", " ", without_continuations).strip()


def workflow_uses(text: str) -> list[str]:
    uses: list[str] = []
    for line in text.splitlines():
        match = re.match(r"^\s*(?:-\s*)?uses\s*:\s*['\"]?([^'\"\s#]+)", line)
        if match:
            uses.append(match.group(1))
    return uses


def nested_mapping_block(text: str, key: str, *, indent: int = 2) -> str:
    lines = text.splitlines()
    prefix = " " * indent
    start = next(
        (
            index
            for index, line in enumerate(lines)
            if re.fullmatch(rf"{re.escape(prefix + key)}\s*:\s*", line)
        ),
        None,
    )
    if start is None:
        return ""
    retained: list[str] = []
    for line in lines[start + 1 :]:
        if line.strip() and len(line) - len(line.lstrip()) <= indent:
            break
        retained.append(line)
    return "\n".join(retained)


class RepositoryGovernanceContractTests(unittest.TestCase):
    maxDiff = None

    def test_required_repository_governance_files_exist(self) -> None:
        required = (AGENTS, CI_WORKFLOW, DEPENDENCY_REVIEW_WORKFLOW, DEPENDABOT)
        self.assertEqual(
            [],
            sorted(path.relative_to(ROOT).as_posix() for path in required if not path.is_file()),
        )

    def test_agents_contract_requires_tdd_feature_branch_pr_and_no_merge(self) -> None:
        text = read_required(AGENTS)
        prose = re.sub(r"\s+", " ", text).lower()

        for required in ("red", "green", "refactor"):
            with self.subTest(tdd_phase=required):
                self.assertRegex(prose, rf"\b{required}\b")
        self.assertRegex(
            prose,
            r"fail(?:ing)? test.{0,120}before.{0,120}(?:implementation|production code)",
        )
        self.assertRegex(prose, r"(?:feature|topic) branch")
        self.assertRegex(prose, r"(?:never|do not|must not).{0,80}(?:commit|work|push).{0,40}(?:main|default branch)")
        self.assertRegex(prose, r"push.{0,100}(?:feature|topic|current) branch")
        self.assertRegex(prose, r"(?:open|create).{0,80}(?:pull request|\bpr\b)")
        self.assertRegex(prose, r"(?:never|do not|must not).{0,40}merge")

    def test_ci_has_expected_triggers_read_only_permissions_and_concurrency(self) -> None:
        text = read_required(CI_WORKFLOW)
        trigger_block = top_level_block(text, "on")
        self.assertTrue(trigger_block, "ci.yml requires a top-level on mapping")
        for trigger in ("push", "pull_request", "workflow_dispatch"):
            with self.subTest(trigger=trigger):
                self.assertRegex(trigger_block, rf"(?m)^\s+{trigger}\s*:")

        permissions = top_level_block(text, "permissions")
        permission_entries = {
            match.group(1): match.group(2)
            for match in re.finditer(r"(?m)^\s+([a-z-]+)\s*:\s*([a-z-]+)\s*$", permissions)
        }
        self.assertEqual({"contents": "read"}, permission_entries)
        self.assertNotRegex(text, r"(?m)^\s*permissions\s*:\s*(?:write-all|read-all)\s*$")
        self.assertNotRegex(text, r"(?m)^\s+[a-z-]+\s*:\s*write\s*$")

        concurrency = top_level_block(text, "concurrency")
        self.assertRegex(concurrency, r"(?m)^\s+group\s*:\s*\S+")
        self.assertRegex(concurrency, r"(?m)^\s+cancel-in-progress\s*:\s*true\s*$")

    def test_ci_tests_every_supported_python_runtime_without_installing_dependencies(self) -> None:
        text = read_required(CI_WORKFLOW)
        versions = set(re.findall(r"['\"](3\.(?:10|11|12|13|14))['\"]", text))
        self.assertEqual({"3.10", "3.11", "3.12", "3.13", "3.14"}, versions)
        self.assertRegex(text, r"python-version\s*:\s*['\"]?\$\{\{\s*matrix\.[^}]+\}\}")
        self.assertRegex(text, r"fail-fast\s*:\s*false")
        self.assertNotRegex(
            text,
            r"(?im)^\s*(?:run\s*:\s*)?(?:python(?:3)?\s+-m\s+pip|pip3?|npm|pnpm|yarn|cargo)\s+(?:install|add|fetch)\b",
        )

    def test_ci_runs_the_repository_exact_offline_gates(self) -> None:
        text = normalized_shell(read_required(CI_WORKFLOW))
        required_commands = (
            "python3 scripts/clone_pack.py --help",
            "PYTHONDONTWRITEBYTECODE=1 python3 scripts/run_skill_tests.py",
            "python3 -m unittest -v tests.test_capture_adversarial_security tests.test_capture_lifecycle_batch tests.test_capture_parity_contract",
            "PYTHONDONTWRITEBYTECODE=1 python3 -m unittest -v tests.test_documentation",
            "python3 -m compileall -q scripts tests",
        )
        for command in required_commands:
            with self.subTest(command=command):
                self.assertIn(command, text)
        self.assertIn("PYTHONPYCACHEPREFIX", text)

    def test_runner_context_is_used_only_in_step_level_environment(self) -> None:
        lines = read_required(CI_WORKFLOW).splitlines()
        runner_context_lines = [
            index for index, line in enumerate(lines) if "${{ runner.temp }}" in line
        ]
        self.assertTrue(runner_context_lines)
        for line_index in runner_context_lines:
            env_index = next(
                (
                    index
                    for index in range(line_index - 1, -1, -1)
                    if lines[index].strip() == "env:"
                ),
                None,
            )
            self.assertIsNotNone(env_index)
            assert env_index is not None
            env_indent = len(lines[env_index]) - len(lines[env_index].lstrip())
            self.assertGreater(
                env_indent,
                4,
                "runner context is unavailable in job-level env; bind it on a step",
            )

    def test_workflows_use_current_official_pins_and_ubuntu_2404(self) -> None:
        ci_text = read_required(CI_WORKFLOW)
        dependency_text = read_required(DEPENDENCY_REVIEW_WORKFLOW)

        self.assertNotRegex(
            "\n".join((ci_text, dependency_text)),
            r"(?m)^\s*runs-on\s*:\s*(?!ubuntu-24\.04\s*$)\S+",
        )
        self.assertEqual(
            {f"actions/checkout@{CHECKOUT_SHA}", f"actions/setup-python@{SETUP_PYTHON_SHA}"},
            set(workflow_uses(ci_text)),
        )
        self.assertEqual(
            [f"actions/dependency-review-action@{DEPENDENCY_REVIEW_SHA}"],
            workflow_uses(dependency_text),
        )
        self.assertIn(f"actions/checkout@{CHECKOUT_SHA} # v7.0.0", ci_text)
        self.assertIn(f"actions/setup-python@{SETUP_PYTHON_SHA} # v6.3.0", ci_text)
        self.assertIn(
            f"actions/dependency-review-action@{DEPENDENCY_REVIEW_SHA} # v5.0.0",
            dependency_text,
        )

    def test_ci_checkout_does_not_persist_github_credentials(self) -> None:
        text = read_required(CI_WORKFLOW)
        checkout_count = text.count(f"uses: actions/checkout@{CHECKOUT_SHA}")
        disabled_count = len(
            re.findall(r"(?m)^\s+persist-credentials\s*:\s*false\s*$", text)
        )
        self.assertGreater(checkout_count, 0)
        self.assertEqual(checkout_count, disabled_count)

    def test_ci_exposes_one_honest_stable_required_aggregate(self) -> None:
        text = read_required(CI_WORKFLOW)
        required = nested_mapping_block(text, "required")
        self.assertTrue(required, "ci.yml requires a stable required aggregate job")
        self.assertRegex(required, r"(?m)^\s+name\s*:\s*Required\s*$")
        self.assertRegex(required, r"(?m)^\s+if\s*:\s*\$\{\{\s*always\(\)\s*\}\}\s*$")
        self.assertRegex(required, r"(?m)^\s+-\s+test\s*$")
        self.assertRegex(required, r"(?m)^\s+-\s+repository-contracts\s*$")
        self.assertIn("${{ needs.test.result }}", required)
        self.assertIn("${{ needs.repository-contracts.result }}", required)
        self.assertIn('test "$TEST_RESULT" = "success"', required)
        self.assertIn('test "$CONTRACT_RESULT" = "success"', required)
        self.assertNotRegex(required, r"(?m)^\s*continue-on-error\s*:\s*true\s*$")

    def test_dependabot_updates_only_github_actions_weekly(self) -> None:
        text = read_required(DEPENDABOT)
        self.assertRegex(text, r"(?m)^version\s*:\s*2\s*$")
        ecosystems = re.findall(r"(?m)^\s*-?\s*package-ecosystem\s*:\s*['\"]?([^'\"\s#]+)", text)
        self.assertEqual(["github-actions"], ecosystems)
        self.assertRegex(text, r"(?m)^\s+directory\s*:\s*['\"]?/['\"]?\s*$")
        self.assertRegex(text, r"(?m)^\s+interval\s*:\s*['\"]?weekly['\"]?\s*$")

    def test_dependency_review_is_pull_request_only_and_read_only(self) -> None:
        text = read_required(DEPENDENCY_REVIEW_WORKFLOW)
        triggers = top_level_block(text, "on")
        self.assertRegex(triggers, r"(?m)^\s+pull_request\s*:")
        self.assertNotRegex(triggers, r"(?m)^\s+(?:push|schedule|workflow_run|pull_request_target)\s*:")

        permissions = top_level_block(text, "permissions")
        permission_entries = {
            match.group(1): match.group(2)
            for match in re.finditer(r"(?m)^\s+([a-z-]+)\s*:\s*([a-z-]+)\s*$", permissions)
        }
        self.assertEqual({"contents": "read"}, permission_entries)
        self.assertNotRegex(text, r"(?m)^\s+[a-z-]+\s*:\s*write\s*$")
        self.assertEqual(
            1,
            sum(reference.startswith("actions/dependency-review-action@") for reference in workflow_uses(text)),
        )

    def test_every_github_action_reference_is_pinned_to_a_full_commit_sha(self) -> None:
        workflows = sorted((ROOT / ".github" / "workflows").glob("*.y*ml"))
        self.assertTrue(workflows, "at least one GitHub Actions workflow is required")
        failures: list[str] = []
        all_references: list[str] = []
        for workflow in workflows:
            references = workflow_uses(workflow.read_text(encoding="utf-8"))
            all_references.extend(references)
            for reference in references:
                if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+@[0-9a-f]{40}", reference):
                    failures.append(f"{workflow.relative_to(ROOT).as_posix()}: {reference}")
        self.assertTrue(all_references, "workflows must contain pinned action references")
        self.assertEqual([], failures)
        self.assertTrue(any(reference.startswith("actions/checkout@") for reference in all_references))
        self.assertTrue(any(reference.startswith("actions/setup-python@") for reference in all_references))


if __name__ == "__main__":
    unittest.main()
