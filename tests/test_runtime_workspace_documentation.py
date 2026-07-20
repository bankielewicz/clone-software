from __future__ import annotations

import json
import re
import unittest
from pathlib import Path

from scripts.clonepack import TOOL_VERSION


ROOT = Path(__file__).resolve().parents[1]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


class RuntimeWorkspaceDocumentationTests(unittest.TestCase):
    def test_tool_23_and_both_static_profiles_are_documented_as_implemented(self) -> None:
        self.assertEqual("2.3.0", TOOL_VERSION)
        catalog = json.loads(read("assets/scaffolds/catalog.json"))
        profile_ids = [profile["id"] for profile in catalog["profiles"]]
        self.assertIn("static-web-esm", profile_ids)
        self.assertIn("static-web-esm-allowlist", profile_ids)

        combined = "\n".join(
            read(path)
            for path in (
                "SKILL.md",
                "README.md",
                "docs/getting-started.md",
                "docs/runtime-enforcement-boundaries.md",
                "changelog.md",
            )
        )
        self.assertIn("Tool `2.3.0` implementation baseline", combined)
        self.assertIn("`static-web-esm-allowlist`", combined)
        self.assertIn("legacy `static-web-esm`", combined)

    def test_workspace_dispositions_and_evidence_boundary_are_exact(self) -> None:
        combined = "\n".join(
            read(path)
            for path in (
                "SKILL.md",
                "references/greenfield.md",
                "references/evidence-and-fidelity.md",
                "references/document-contracts.md",
                "docs/runtime-enforcement-boundaries.md",
            )
        )
        for disposition in (
            "PRODUCT_INPUT",
            "REPOSITORY_INSTRUCTION",
            "TOOL_RUNTIME_EXCLUDED",
            "UNKNOWN_BLOCKER",
        ):
            self.assertIn(f"`{disposition}`", combined)
        for field in (
            "pre_session_presence",
            "owner_claim",
            "allowed_operations",
            "content_inventory_or_hash",
        ):
            self.assertIn(f"`{field}`", combined)
        self.assertIn("does not prove provider ownership", combined)
        self.assertRegex(combined.lower(), r"(?:must not|never) infer")

    def test_minecraft_request_uses_checker_and_allowlisted_server(self) -> None:
        prompt = read("assets/prompts/minecraft-clean-room-mvp.md")
        self.assertIn("scripts/check_wsl_trial_workspace.py", prompt)
        self.assertIn("clone-software-wsl-test-install/v2", prompt)
        self.assertIn("`TOOL_RUNTIME_EXCLUDED`", prompt)
        self.assertIn("`RUNTIME-001`", prompt)
        self.assertIn("`DEC-004`", prompt)
        self.assertIn("`static-web-esm-allowlist`", prompt)
        self.assertIn(
            "python3 tools/serve_static.py --manifest serve_manifest.json --bind 127.0.0.1 --port 8000",
            prompt,
        )
        self.assertNotIn("python3 -m http.server", prompt)
        self.assertIn('"timeout_seconds":300', prompt)
        self.assertIn("before the first `record-run`", prompt)
        self.assertIn("before the first product write", prompt)
        self.assertIn("at handoff", prompt)
        self.assertIn("--phase handoff", prompt)
        self.assertIn(
            "docs/clone/evidence/raw/workspace-check/pre-write.json", prompt
        )
        self.assertIn("--baseline-result", prompt)
        self.assertIn("`sha256sum`", prompt)
        self.assertIn(".codex/                       optional only when --phase pre-write returns PASS", prompt)

    def test_minecraft_request_has_exact_normal_and_recovery_path_fences(self) -> None:
        prompt = read("assets/prompts/minecraft-clean-room-mvp.md")
        required = (
            "`docs/clone/` is the only pack root in the normal path",
            "`docs/clone-recovery/` is conditionally authorized only",
            "Require `docs/clone-recovery/` absent",
            "every clone-pack operand and every new pack evidence/result/post-MVP path",
            "checker baseline `docs/clone/evidence/raw/workspace-check/pre-write.json`",
            "changelog.md",
            "A failed `PAR-001` remains `FAIL`",
            "MUST NOT be relabeled as passing",
        )
        self.assertEqual([], [phrase for phrase in required if phrase not in prompt])

    def test_minecraft_handoff_inventory_transformation_is_deterministic(self) -> None:
        prompt = read("assets/prompts/minecraft-clean-room-mvp.md")
        required = (
            "sorted by their UTF-8 bytes",
            "Load `installed_workspace_inventory`",
            "subtract exactly those four records",
            "The fixed expected regular-file paths",
            "every non-root proper parent",
            "every `documents[].path`",
            "every non-null string value in `plans`",
            "every regular-file record recursively below `runs_path`, `evidence`, and `history`",
            "`seal_path` if that file exists",
            "Do not authorize another empty directory merely because it exists",
            "exactly fields `mode,path,sha256,size,type`",
            "exactly fields `mode,path,type`",
            "The resulting remaining array is the complete authorized-output inventory",
            "it is not product-only because it contains clone-pack records",
            "product-only inventory as its exact ordered subset",
        )
        self.assertEqual([], [phrase for phrase in required if phrase not in prompt])

    def test_wsl_prerequisite_lists_are_complete(self) -> None:
        readme = read("README.md")
        getting_started = read("docs/getting-started.md")
        for executable in (
            "uname",
            "realpath",
            "dirname",
            "basename",
            "mktemp",
            "git",
            "python3",
            "node",
            "npm",
            "mv",
            "stat",
        ):
            with self.subTest(executable=executable):
                self.assertIn(f"`{executable}`", readme)
                self.assertIn(f"`{executable}`", getting_started)
        self.assertIn("Codex", readme)
        self.assertIn("Codex", getting_started)
        self.assertIn("`sha256sum`", readme)
        self.assertIn("`sha256sum`", getting_started)

    def test_wsl_duplicate_discovery_and_git_oid_contracts_are_exact(self) -> None:
        readme = read("README.md")
        getting_started = read("docs/getting-started.md")
        troubleshooting = read("docs/troubleshooting.md")
        changelog = read("changelog.md")
        combined = "\n".join((readme, getting_started, troubleshooting, changelog))
        for path in (
            "$HOME/.agents/skills/clone-software",
            "$HOME/.codex/skills/clone-software",
            "$CODEX_HOME/skills/clone-software",
            "/etc/codex/skills/clone-software",
        ):
            with self.subTest(path=path):
                self.assertIn(path, combined)
        self.assertIn("`INSTALL_CODEX_HOME_INVALID`", troubleshooting)
        self.assertIn("lowercase 40-hex SHA-1 or 64-hex SHA-256", combined)

    def test_current_guides_use_finite_runner_versions(self) -> None:
        current_paths = (
            "README.md",
            "SKILL.md",
            "assets/prompts/minecraft-clean-room-mvp.md",
            "agents/openai.yaml",
            *(path.relative_to(ROOT).as_posix() for path in (ROOT / "docs").glob("*.md")),
            *(path.relative_to(ROOT).as_posix() for path in (ROOT / "references").glob("*.md")),
        )
        combined = "\n".join(read(path) for path in current_paths)
        self.assertIsNone(re.search(r"2\.2\.0.{0,32}or later", combined, re.IGNORECASE))
        self.assertNotIn("Tool-2.2", combined)
        self.assertNotIn("tool-2.2", combined)
        self.assertIn("tool version `2.2.0` or `2.3.0`", combined)

    def test_scaffold_policy_and_descriptor_capability_claims_are_bounded(self) -> None:
        readme = read("README.md")
        skill = read("SKILL.md")
        greenfield = read("references/greenfield.md")
        cli = read("docs/cli-reference.md")
        combined = "\n".join((readme, skill, greenfield, cli))
        self.assertIn("skill selection policy", combined)
        self.assertIn("schema and scaffolder accept both static profiles", combined)
        self.assertIn("RUNTIME_EXCLUSION_CAPABILITY_MISSING", readme)
        self.assertIn("RUNTIME_EXCLUSION_CAPABILITY_MISSING", skill)
        self.assertIn("exit `3`", readme)
        self.assertIn("exit `3`", skill)
        self.assertIn("`MANIFEST_INVALID`", readme)
        self.assertIn("`MANIFEST_INVALID`", skill)

    def test_handoff_checkout_identity_revalidation_is_documented(self) -> None:
        combined = "\n".join(
            read(path)
            for path in (
                "README.md",
                "docs/getting-started.md",
                "docs/troubleshooting.md",
                "docs/runtime-enforcement-boundaries.md",
            )
        )
        for phrase in (
            "receipt `project_dir`",
            "checkout_identity_sha256",
            "working-tree symlink",
            "multiply linked regular file",
            "concurrent mutation",
            "without following",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, combined)

    def test_runtime_capability_and_compatibility_field_boundaries_are_documented(self) -> None:
        runtime = read("docs/runtime-enforcement-boundaries.md")
        cli = read("docs/cli-reference.md")
        troubleshooting = read("docs/troubleshooting.md")
        changelog = read("changelog.md")
        combined = "\n".join((runtime, cli, troubleshooting, changelog))
        self.assertIn("RUNTIME_EXCLUSION_CAPABILITY_MISSING", combined)
        self.assertIn("exit `3`", combined)
        self.assertIn("no pruning or collection", combined)
        self.assertIn("compatibility field", combined)
        self.assertIn("repository-scoped skill input", combined)
        self.assertIn("`id`", cli)
        self.assertIn("`reason`", cli)

    def test_tool_runtime_reason_is_exact_and_scope_only_reason_remains_authored(self) -> None:
        controlled = "User-authorized empty tool-runtime directory excluded from product identity."
        for path in (
            "README.md",
            "SKILL.md",
            "docs/cli-reference.md",
            "docs/clone-pack-authoring.md",
            "docs/operating-workflows.md",
            "docs/runtime-enforcement-boundaries.md",
            "changelog.md",
        ):
            with self.subTest(path=path):
                self.assertIn(controlled, read(path))
        authoring = read("docs/clone-pack-authoring.md")
        self.assertIn(f'"reason": "{controlled}"', authoring)
        self.assertIn("MUST NOT be paraphrased", authoring)
        self.assertIn(
            "scope-only records retain their repository-authored nonempty reasons",
            read("docs/runtime-enforcement-boundaries.md"),
        )

    def test_codex_runtime_directory_is_never_globally_ignored(self) -> None:
        prompt = read("assets/prompts/minecraft-clean-room-mvp.md")
        self.assertIn("Add only `.agents/` to `.gitignore`", prompt)
        self.assertNotIn("Add `.codex/` to `.gitignore`", prompt)
        self.assertNotIn("Add `.agents/` and `.codex/` to `.gitignore`", prompt)

        combined = "\n".join(
            read(path)
            for path in (
                "references/greenfield.md",
                "docs/getting-started.md",
                "docs/troubleshooting.md",
            )
        )
        self.assertIn("never delete, rename, chmod, or globally ignore", combined.lower())

    def test_stale_immutable_run_recovery_never_fabricates_lineage(self) -> None:
        combined = "\n".join(
            read(path)
            for path in (
                "assets/prompts/minecraft-clean-room-mvp.md",
                "docs/troubleshooting.md",
            )
        )
        required = (
            "abandoned active failed-evidence pack",
            "fresh independent revision-1 pack",
            "new `pack_id`",
            "`supersedes: null`",
            "preserve `docs/clone/` byte-for-byte",
            "do not copy stale RUN evidence",
        )
        self.assertEqual([], [phrase for phrase in required if phrase not in combined])


if __name__ == "__main__":
    unittest.main()
