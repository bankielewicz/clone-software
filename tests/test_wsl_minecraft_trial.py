from __future__ import annotations

import hashlib
import json
import os
import shlex
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
INSTALLER = ROOT / "scripts" / "install_clone_software_wsl.sh"
PROMPT = ROOT / "assets" / "prompts" / "minecraft-clean-room-mvp.md"
STATIC_WEB_PATHS = (
    "README.md",
    "package.json",
    "index.html",
    "styles.css",
    "src/app.js",
    "tests/smoke.test.mjs",
)
PROMPT_REFERENCES = (
    "evidence-and-fidelity.md",
    "document-contracts.md",
    "greenfield.md",
    "game-simulation.md",
    "security-and-provenance.md",
    "pack-evolution.md",
)


class WslMinecraftTrialTests(unittest.TestCase):
    maxDiff = None

    def make_source_repository(self, root: Path, *, include_prompt: bool = True) -> Path:
        source = root / "source repository"
        (source / "agents").mkdir(parents=True)
        (source / "scripts").mkdir()
        (source / "assets" / "prompts").mkdir(parents=True)
        (source / "SKILL.md").write_text(
            "---\nname: clone-software\ndescription: fixture\n---\nfixture\n",
            encoding="utf-8",
        )
        (source / "agents" / "openai.yaml").write_text(
            "interface:\n"
            "  display_name: Clone Software\n"
            "  short_description: fixture clone skill\n"
            "  default_prompt: Use $clone-software for this fixture.\n",
            encoding="utf-8",
        )
        (source / "LICENSE").write_text("CC0 fixture\n", encoding="utf-8")
        (source / "scripts" / "clonepack").mkdir()
        (source / "scripts" / "clonepack" / "__init__.py").write_text(
            "__version__ = 'fixture'\n", encoding="utf-8"
        )
        (source / "assets" / "schemas").mkdir()
        (source / "assets" / "schemas" / "clone-pack-v2.schema.json").write_text(
            "{}\n", encoding="utf-8"
        )
        (source / "assets" / "templates-v2").mkdir()
        (source / "assets" / "templates-v2" / "clone_brief.md").write_text(
            "fixture\n", encoding="utf-8"
        )
        scaffold = source / "assets" / "scaffolds" / "static-web-esm"
        for relative in STATIC_WEB_PATHS:
            target = scaffold / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(f"fixture {relative}\n", encoding="utf-8")
        catalog = {
            "schema_version": "clone-scaffold-catalog/v2",
            "profiles": [
                {
                    "id": "static-web-esm",
                    "description": "fixture",
                    "template": "static-web-esm",
                    "required_paths": list(STATIC_WEB_PATHS),
                    "commands": {
                        "setup": None,
                        "test": ["npm", "test"],
                        "build": None,
                        "run": [
                            "npm",
                            "start",
                        ],
                    },
                }
            ],
        }
        (source / "assets" / "scaffolds" / "catalog.json").write_text(
            json.dumps(catalog, sort_keys=True) + "\n", encoding="utf-8"
        )
        (source / "references").mkdir()
        for name in PROMPT_REFERENCES:
            (source / "references" / name).write_text(f"fixture {name}\n", encoding="utf-8")
        (source / "scripts" / "clone_pack.py").write_text(
            "from __future__ import annotations\n"
            "import sys\n"
            "if sys.argv[1:] != ['--help']:\n"
            "    raise SystemExit(2)\n"
            "print('init validate migrate capture parity scaffold record-run record-manual '",
            encoding="utf-8",
        )
        with (source / "scripts" / "clone_pack.py").open("a", encoding="utf-8") as handle:
            handle.write(
                "      'gap-transition assure seal diff enhancement-init repo-snapshot baseline-run '")
            handle.write("\n")
            handle.write("      'regression verify-scope enhancement-transition rehash')\n")
        (source / "scripts" / "run_skill_tests.py").write_text(
            "print('fixture suite available')\n", encoding="utf-8"
        )
        if include_prompt:
            (source / "assets" / "prompts" / PROMPT.name).write_text(
                "Use $clone-software in mvp-build mode.\nfixture prompt bytes\n",
                encoding="utf-8",
            )

        subprocess.run(
            ["git", "init", "--initial-branch", "main", str(source)],
            check=True,
            capture_output=True,
            text=True,
        )
        subprocess.run(["git", "-C", str(source), "add", "."], check=True)
        subprocess.run(
            [
                "git",
                "-C",
                str(source),
                "-c",
                "user.name=Installer Test",
                "-c",
                "user.email=installer@example.invalid",
                "commit",
                "-m",
                "fixture",
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        return source

    def run_installer(
        self,
        destination: Path,
        source: Path | str,
        *extra: str,
        home: Path | None = None,
        trust_source: bool = True,
        tool_overrides: dict[str, str] | None = None,
        tools_parent: Path | None = None,
        codex_argument: str | None = None,
        environment_overrides: dict[str, str] | None = None,
    ) -> subprocess.CompletedProcess[str]:
        tools_dir = (tools_parent or destination.parent) / "installer test tools"
        tools_dir.mkdir(exist_ok=True)
        node = tools_dir / "node"
        node.write_text(
            "#!/bin/sh\n"
            "if [ \"${1:-}\" = \"-p\" ]; then printf '18\\n'; else exit 0; fi\n",
            encoding="utf-8",
        )
        npm = tools_dir / "npm"
        npm.write_text("#!/bin/sh\nprintf '10.0.0\\n'\n", encoding="utf-8")
        codex = tools_dir / "codex"
        codex.write_text("#!/bin/sh\nprintf 'codex-cli 0.0.0-test\\n'\n", encoding="utf-8")
        for executable in (node, npm, codex):
            executable.chmod(0o755)
        for name, content in (tool_overrides or {}).items():
            override = tools_dir / name
            override.write_text(content, encoding="utf-8")
            override.chmod(0o755)

        selected_home = home or destination.parent / "installer test home"
        selected_home.mkdir(parents=True, exist_ok=True)
        environment = os.environ.copy()
        environment["HOME"] = str(selected_home)
        environment["PATH"] = f"{tools_dir}:{environment['PATH']}"
        environment.update(environment_overrides or {})
        arguments = [
            "bash",
            str(INSTALLER),
            "--allow-non-wsl",
            "--repo-url",
            str(source),
            "--ref",
            "main",
            "--destination",
            str(destination),
            "--codex-bin",
            codex_argument or str(codex),
        ]
        if trust_source:
            arguments.append("--trust-custom-source-code")
        arguments.extend(extra)
        return subprocess.run(
            arguments,
            cwd=ROOT,
            capture_output=True,
            env=environment,
            text=True,
            timeout=60,
        )

    def test_installer_help_is_read_only(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            before = sorted(Path(temporary).iterdir())
            result = subprocess.run(
                ["bash", str(INSTALLER), "--help"],
                cwd=temporary,
                capture_output=True,
                text=True,
            )
            self.assertEqual(0, result.returncode, result.stderr)
            self.assertIn("--destination", result.stdout)
            self.assertIn("--verify", result.stdout)
            self.assertEqual(before, sorted(Path(temporary).iterdir()))

    def test_installer_publishes_isolated_workspace_with_exact_prompt_and_receipt(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = self.make_source_repository(root)
            destination = root / "new codex trial"

            result = self.run_installer(destination, source)

            self.assertEqual(0, result.returncode, result.stderr)
            project = destination / "clone-software"
            workspace = destination / "minecraft-clone"
            skill_link = workspace / ".agents" / "skills" / "clone-software"
            copied_prompt = workspace / "MINECRAFT_CLONE_PROMPT.md"
            receipt_path = destination / "installation-receipt.json"

            self.assertTrue((project / ".git").is_dir())
            source_objects = {
                path.relative_to(source / ".git" / "objects"): path.stat()
                for path in (source / ".git" / "objects").rglob("*")
                if path.is_file()
            }
            cloned_objects = {
                path.relative_to(project / ".git" / "objects"): path.stat()
                for path in (project / ".git" / "objects").rglob("*")
                if path.is_file()
            }
            shared_object_inodes = [
                str(relative)
                for relative in source_objects.keys() & cloned_objects.keys()
                if (
                    source_objects[relative].st_dev,
                    source_objects[relative].st_ino,
                )
                == (
                    cloned_objects[relative].st_dev,
                    cloned_objects[relative].st_ino,
                )
            ]
            self.assertEqual([], shared_object_inodes)
            self.assertTrue(skill_link.is_symlink())
            self.assertEqual(project.resolve(), skill_link.resolve())
            self.assertEqual(
                (project / "assets" / "prompts" / PROMPT.name).read_bytes(),
                copied_prompt.read_bytes(),
            )

            receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
            head = subprocess.run(
                ["git", "-C", str(project), "rev-parse", "HEAD"],
                check=True,
                capture_output=True,
                text=True,
            ).stdout.strip()
            self.assertEqual("clone-software-wsl-test-install/v1", receipt["schema_version"])
            self.assertEqual(head, receipt["resolved_head"])
            self.assertEqual(f"head={head};branch=main", receipt["checkout_state"])
            self.assertRegex(receipt["checkout_identity_sha256"], r"\A[0-9a-f]{64}\Z")
            self.assertEqual("main", receipt["requested_ref"])
            self.assertEqual("smoke", receipt["verification"])
            self.assertEqual(
                hashlib.sha256(copied_prompt.read_bytes()).hexdigest(),
                receipt["prompt_sha256"],
            )
            self.assertEqual(str(project), receipt["project_dir"])
            self.assertEqual(str(workspace), receipt["workspace_dir"])
            self.assertEqual(str(source), receipt["source_url"])
            self.assertEqual(str(skill_link), receipt["skill_link"])
            self.assertEqual(str(copied_prompt), receipt["prompt_path"])
            self.assertEqual(str(destination.parent / "installer test tools" / "codex"), receipt["codex_executable"])
            self.assertIn(f"workspace_dir={workspace}", result.stdout)
            self.assertIn("cd -- ", result.stdout)
            self.assertIn("codex", result.stdout)
            self.assertIn("/skills", result.stdout)
            self.assertIn("MINECRAFT_CLONE_PROMPT.md", result.stdout)

    def test_bare_codex_name_resolves_to_path_not_exported_function(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = self.make_source_repository(root)
            destination = root / "function shadow trial"

            result = self.run_installer(
                destination,
                source,
                codex_argument="codex",
                environment_overrides={
                    "BASH_FUNC_codex%%": "() { printf 'shadow function\\n'; }"
                },
            )

            self.assertEqual(0, result.returncode, result.stderr)
            receipt = json.loads(
                (destination / "installation-receipt.json").read_text(encoding="utf-8")
            )
            self.assertEqual(
                str(destination.parent / "installer test tools" / "codex"),
                receipt["codex_executable"],
            )

    def test_existing_destination_is_preserved_without_cloning(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "source-does-not-exist"
            destination = root / "occupied"
            destination.mkdir()
            sentinel = destination / "sentinel.txt"
            sentinel.write_bytes(b"preserve exactly\n")

            result = self.run_installer(destination, source)

            self.assertEqual(4, result.returncode)
            self.assertEqual(b"preserve exactly\n", sentinel.read_bytes())
            self.assertEqual([sentinel], sorted(destination.iterdir()))
            self.assertIn("DESTINATION_EXISTS", result.stderr)

    def test_absent_destination_parent_is_not_created(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = self.make_source_repository(root)
            absent_parent = root / "absent destination parent"
            destination = absent_parent / "trial"

            result = self.run_installer(
                destination,
                source,
                home=root / "stable home",
                tools_parent=root,
            )

            self.assertEqual(6, result.returncode)
            self.assertFalse(absent_parent.exists())
            self.assertFalse(destination.exists())
            self.assertIn("INSTALL_DESTINATION_FAILURE", result.stderr)

    def test_dangling_destination_symlink_is_preserved_and_target_is_not_created(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = self.make_source_repository(root)
            redirected_target = root / "redirected target"
            destination = root / "dangling destination"
            destination.symlink_to(redirected_target, target_is_directory=True)

            result = self.run_installer(destination, source)

            self.assertEqual(4, result.returncode)
            self.assertTrue(destination.is_symlink())
            self.assertEqual(redirected_target, Path(os.readlink(destination)))
            self.assertFalse(redirected_target.exists())
            self.assertIn("DESTINATION_SYMLINK", result.stderr)

    def test_destination_symlink_ancestor_is_preserved_and_not_followed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = self.make_source_repository(root)
            real_parent = root / "real parent"
            real_parent.mkdir()
            linked_parent = root / "linked parent"
            linked_parent.symlink_to(real_parent, target_is_directory=True)
            destination = linked_parent / "trial"

            result = self.run_installer(destination, source)

            self.assertEqual(4, result.returncode)
            self.assertTrue(linked_parent.is_symlink())
            self.assertFalse((real_parent / "trial").exists())
            self.assertIn("DESTINATION_SYMLINK", result.stderr)

    def test_destination_parent_replacement_during_staging_is_not_followed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = self.make_source_repository(root)
            destination_parent = root / "destination parent"
            destination_parent.mkdir()
            moved_parent = root / "moved original parent"
            redirected_parent = root / "redirected parent"
            redirected_parent.mkdir()
            destination = destination_parent / "trial"
            real_mktemp = shutil.which("mktemp")
            self.assertIsNotNone(real_mktemp)
            hostile_mktemp = (
                "#!/bin/sh\n"
                f"mv -- {shlex.quote(str(destination_parent))} {shlex.quote(str(moved_parent))}\n"
                f"ln -s -- {shlex.quote(str(redirected_parent))} {shlex.quote(str(destination_parent))}\n"
                f"exec {shlex.quote(str(real_mktemp))} \"$@\"\n"
            )

            result = self.run_installer(
                destination,
                source,
                tool_overrides={"mktemp": hostile_mktemp},
                tools_parent=root,
            )

            self.assertEqual(4, result.returncode)
            self.assertTrue(destination_parent.is_symlink())
            self.assertFalse((redirected_parent / "trial").exists())
            self.assertFalse(destination.exists())
            self.assertIn("DESTINATION_SYMLINK", result.stderr)

    def test_ordinary_destination_parent_replacement_before_binding_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = self.make_source_repository(root)
            destination_parent = root / "destination parent"
            destination_parent.mkdir()
            moved_parent = root / "moved original parent"
            destination = destination_parent / "trial"
            real_dirname = shutil.which("dirname")
            self.assertIsNotNone(real_dirname)
            counter = root / "dirname count"
            hostile_dirname = (
                "#!/bin/sh\n"
                f"counter={shlex.quote(str(counter))}\n"
                "count=0\n"
                "if [ -f \"$counter\" ]; then count=$(sed -n '1p' \"$counter\"); fi\n"
                "count=$((count + 1))\n"
                "printf '%s\\n' \"$count\" > \"$counter\"\n"
                "if [ \"$count\" -eq 2 ]; then\n"
                f"  mv -- {shlex.quote(str(destination_parent))} {shlex.quote(str(moved_parent))}\n"
                f"  mkdir -- {shlex.quote(str(destination_parent))}\n"
                "fi\n"
                f"exec {shlex.quote(str(real_dirname))} \"$@\"\n"
            )

            result = self.run_installer(
                destination,
                source,
                tool_overrides={"dirname": hostile_dirname},
                tools_parent=root,
            )

            self.assertEqual(4, result.returncode)
            self.assertTrue(destination_parent.is_dir())
            self.assertTrue(moved_parent.is_dir())
            self.assertFalse(destination.exists())
            self.assertFalse((moved_parent / "trial").exists())
            self.assertIn("INSTALL_DESTINATION_PARENT_CHANGED", result.stderr)

    def test_existing_user_scope_skill_blocks_ambiguous_trial_discovery(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = self.make_source_repository(root)
            home = root / "home"
            existing_skill = home / ".agents" / "skills" / "clone-software"
            existing_skill.mkdir(parents=True)
            sentinel = existing_skill / "sentinel"
            sentinel.write_bytes(b"existing skill\n")
            destination = root / "trial"

            result = self.run_installer(destination, source, home=home)

            self.assertEqual(4, result.returncode)
            self.assertFalse(destination.exists())
            self.assertEqual(b"existing skill\n", sentinel.read_bytes())
            self.assertIn("INSTALL_SKILL_DUPLICATE", result.stderr)

    def test_existing_ancestor_scope_skill_blocks_ambiguous_trial_discovery(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = self.make_source_repository(root)
            ancestor = root / "destination ancestor"
            existing_skill = ancestor / ".agents" / "skills" / "clone-software"
            existing_skill.mkdir(parents=True)
            sentinel = existing_skill / "sentinel"
            sentinel.write_bytes(b"ancestor skill\n")
            destination = ancestor / "trial"

            result = self.run_installer(destination, source)

            self.assertEqual(4, result.returncode)
            self.assertFalse(destination.exists())
            self.assertEqual(b"ancestor skill\n", sentinel.read_bytes())
            self.assertIn("INSTALL_SKILL_DUPLICATE", result.stderr)

    def test_credential_bearing_source_url_is_rejected_before_clone(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            destination = root / "trial"
            source = "https://user:secret@127.0.0.1:1/repository.git?token=secret"

            result = self.run_installer(destination, source)

            self.assertEqual(2, result.returncode)
            self.assertFalse(destination.exists())
            self.assertIn("INSTALL_SOURCE_UNSAFE", result.stderr)

    def test_scp_style_source_with_user_information_is_rejected_before_clone(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            destination = root / "trial"
            source = "git@127.0.0.1:repository.git"

            result = self.run_installer(destination, source)

            self.assertEqual(2, result.returncode)
            self.assertFalse(destination.exists())
            self.assertIn("INSTALL_SOURCE_UNSAFE", result.stderr)

    def test_scp_style_source_secret_query_is_rejected_without_echo(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            destination = root / "trial"
            source = "127.0.0.1:repository.git?token=secret"

            result = self.run_installer(destination, source)

            self.assertEqual(2, result.returncode)
            self.assertFalse(destination.exists())
            self.assertIn("INSTALL_SOURCE_UNSAFE", result.stderr)
            self.assertNotIn("token=secret", result.stderr)
            self.assertNotIn("token=secret", result.stdout)

    def test_custom_source_requires_explicit_code_execution_trust(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = self.make_source_repository(root)
            destination = root / "trial"

            result = self.run_installer(
                destination,
                source,
                trust_source=False,
            )

            self.assertEqual(2, result.returncode)
            self.assertFalse(destination.exists())
            self.assertIn("INSTALL_SOURCE_TRUST_REQUIRED", result.stderr)

    def test_uname_failure_uses_stable_infrastructure_exit_and_diagnostic(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = self.make_source_repository(root)
            destination = root / "uname failure trial"

            result = self.run_installer(
                destination,
                source,
                tool_overrides={"uname": "#!/bin/sh\nexit 42\n"},
            )

            self.assertEqual(7, result.returncode)
            self.assertFalse(destination.exists())
            self.assertIn("INSTALL_EXECUTABLE_FAILURE", result.stderr)

    def test_invalid_checkout_is_not_published_and_owned_stage_is_retained(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = self.make_source_repository(root, include_prompt=False)
            destination = root / "invalid trial"

            result = self.run_installer(destination, source)

            self.assertEqual(4, result.returncode)
            self.assertFalse(destination.exists())
            stages = sorted(root.glob(".clone-software-wsl-install.*"))
            self.assertEqual(1, len(stages))
            self.assertIn("INSTALL_ASSET_MISSING", result.stderr)
            self.assertIn("INSTALL_STAGE_RETAINED", result.stderr)
            self.assertIn(str(stages[0]), result.stderr)
            self.assertTrue(stages[0].is_dir())

    def test_full_verification_runs_the_cloned_offline_suite(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = self.make_source_repository(root)
            runner = source / "scripts" / "run_skill_tests.py"
            runner.write_text("print('fixture full suite passed')\n", encoding="utf-8")
            subprocess.run(["git", "-C", str(source), "add", str(runner)], check=True)
            subprocess.run(
                [
                    "git",
                    "-C",
                    str(source),
                    "-c",
                    "user.name=Installer Test",
                    "-c",
                    "user.email=installer@example.invalid",
                    "commit",
                    "-m",
                    "full verifier",
                ],
                check=True,
                capture_output=True,
                text=True,
            )
            destination = root / "full trial"

            result = self.run_installer(destination, source, "--verify", "full")

            self.assertEqual(0, result.returncode, result.stderr)
            receipt = json.loads(
                (destination / "installation-receipt.json").read_text(encoding="utf-8")
            )
            self.assertEqual("full", receipt["verification"])
            self.assertIn("fixture full suite passed", result.stdout)

    def test_full_verification_refuses_a_suite_that_dirties_the_clone(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = self.make_source_repository(root)
            runner = source / "scripts" / "run_skill_tests.py"
            runner.write_text(
                "from pathlib import Path\n"
                "Path('generated.cache').write_text('unexpected\\n', encoding='utf-8')\n",
                encoding="utf-8",
            )
            subprocess.run(["git", "-C", str(source), "add", str(runner)], check=True)
            subprocess.run(
                [
                    "git",
                    "-C",
                    str(source),
                    "-c",
                    "user.name=Installer Test",
                    "-c",
                    "user.email=installer@example.invalid",
                    "commit",
                    "-m",
                    "dirty verifier",
                ],
                check=True,
                capture_output=True,
                text=True,
            )
            destination = root / "dirty full trial"

            result = self.run_installer(destination, source, "--verify", "full")

            self.assertEqual(4, result.returncode)
            self.assertFalse(destination.exists())
            self.assertIn("INSTALL_CHECKOUT_MUTATED", result.stderr)
            self.assertEqual(1, len(sorted(root.glob(".clone-software-wsl-install.*"))))
            self.assertIn("INSTALL_STAGE_RETAINED", result.stderr)

    def test_full_verification_refuses_ignored_generated_output(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = self.make_source_repository(root)
            (source / ".gitignore").write_text(".cache/\n", encoding="utf-8")
            runner = source / "scripts" / "run_skill_tests.py"
            runner.write_text(
                "from pathlib import Path\n"
                "Path('.cache').mkdir()\n"
                "Path('.cache/probe.txt').write_text('ignored output\\n', encoding='utf-8')\n",
                encoding="utf-8",
            )
            subprocess.run(["git", "-C", str(source), "add", "."], check=True)
            subprocess.run(
                [
                    "git",
                    "-C",
                    str(source),
                    "-c",
                    "user.name=Installer Test",
                    "-c",
                    "user.email=installer@example.invalid",
                    "commit",
                    "-m",
                    "ignored verifier output",
                ],
                check=True,
                capture_output=True,
                text=True,
            )
            destination = root / "ignored full trial"

            result = self.run_installer(destination, source, "--verify", "full")

            self.assertEqual(4, result.returncode)
            self.assertFalse(destination.exists())
            self.assertIn("INSTALL_CHECKOUT_MUTATED", result.stderr)

    def test_smoke_refuses_clone_pack_help_that_mutates_the_checkout(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = self.make_source_repository(root)
            script = source / "scripts" / "clone_pack.py"
            script.write_text(
                "from pathlib import Path\n"
                "root = Path(__file__).resolve().parents[1]\n"
                "(root / 'assets/prompts/minecraft-clean-room-mvp.md').write_text("
                "'mutated by help\\n', encoding='utf-8')\n"
                "print('init validate migrate capture parity scaffold record-run record-manual '",
                encoding="utf-8",
            )
            with script.open("a", encoding="utf-8") as handle:
                handle.write(
                    "      'gap-transition assure seal diff enhancement-init repo-snapshot '")
                handle.write("\n")
                handle.write(
                    "      'baseline-run regression verify-scope enhancement-transition rehash')\n")
            subprocess.run(["git", "-C", str(source), "add", str(script)], check=True)
            subprocess.run(
                [
                    "git",
                    "-C",
                    str(source),
                    "-c",
                    "user.name=Installer Test",
                    "-c",
                    "user.email=installer@example.invalid",
                    "commit",
                    "-m",
                    "mutating help",
                ],
                check=True,
                capture_output=True,
                text=True,
            )
            destination = root / "mutated trial"

            result = self.run_installer(destination, source)

            self.assertEqual(4, result.returncode)
            self.assertFalse(destination.exists())
            self.assertIn("INSTALL_CHECKOUT_MUTATED", result.stderr)

    def test_smoke_refuses_detached_mutation_after_workspace_staging(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = self.make_source_repository(root)
            script = source / "scripts" / "clone_pack.py"
            child_code = (
                "import sys,time\n"
                "from pathlib import Path\n"
                "checkout = Path(sys.argv[1])\n"
                "workspace = checkout.parent / 'minecraft-clone'\n"
                "deadline = time.monotonic() + 5\n"
                "while not workspace.exists() and time.monotonic() < deadline:\n"
                "    time.sleep(0.001)\n"
                "if workspace.exists():\n"
                "    (checkout / 'SKILL.md').write_text('late mutation\\n', encoding='utf-8')\n"
            )
            script.write_text(
                "from pathlib import Path\n"
                "import subprocess\n"
                "import sys\n"
                f"child_code = {child_code!r}\n"
                "checkout = Path(__file__).resolve().parents[1]\n"
                "subprocess.Popen([sys.executable, '-c', child_code, str(checkout)], "
                "stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, "
                "stderr=subprocess.DEVNULL, start_new_session=True)\n"
                "print('init validate migrate capture parity scaffold record-run record-manual '",
                encoding="utf-8",
            )
            with script.open("a", encoding="utf-8") as handle:
                handle.write(
                    "      'gap-transition assure seal diff enhancement-init repo-snapshot '")
                handle.write("\n")
                handle.write(
                    "      'baseline-run regression verify-scope enhancement-transition rehash')\n")
            subprocess.run(["git", "-C", str(source), "add", str(script)], check=True)
            subprocess.run(
                [
                    "git",
                    "-C",
                    str(source),
                    "-c",
                    "user.name=Installer Test",
                    "-c",
                    "user.email=installer@example.invalid",
                    "commit",
                    "-m",
                    "delayed mutating help",
                ],
                check=True,
                capture_output=True,
                text=True,
            )
            destination = root / "late mutation trial"

            result = self.run_installer(destination, source)

            self.assertEqual(4, result.returncode)
            self.assertFalse(destination.exists())
            self.assertIn("INSTALL_CHECKOUT_MUTATED", result.stderr)

    def test_smoke_refuses_detached_handoff_artifact_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = self.make_source_repository(root)
            script = source / "scripts" / "clone_pack.py"
            child_code = (
                "import sys,time\n"
                "from pathlib import Path\n"
                "checkout = Path(sys.argv[1])\n"
                "stage = checkout.parent\n"
                "receipt = stage / 'installation-receipt.json'\n"
                "deadline = time.monotonic() + 5\n"
                "while not receipt.exists() and time.monotonic() < deadline:\n"
                "    time.sleep(0.001)\n"
                "if receipt.exists():\n"
                "    (stage / 'minecraft-clone/MINECRAFT_CLONE_PROMPT.md').write_text("
                "'tampered copied prompt\\n', encoding='utf-8')\n"
                "    receipt.write_text('{}\\n', encoding='utf-8')\n"
            )
            script.write_text(
                "from pathlib import Path\n"
                "import subprocess\n"
                "import sys\n"
                f"child_code = {child_code!r}\n"
                "checkout = Path(__file__).resolve().parents[1]\n"
                "subprocess.Popen([sys.executable, '-c', child_code, str(checkout)], "
                "stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, "
                "stderr=subprocess.DEVNULL, start_new_session=True)\n"
                "print('init validate migrate capture parity scaffold record-run record-manual '",
                encoding="utf-8",
            )
            with script.open("a", encoding="utf-8") as handle:
                handle.write(
                    "      'gap-transition assure seal diff enhancement-init repo-snapshot '")
                handle.write("\n")
                handle.write(
                    "      'baseline-run regression verify-scope enhancement-transition rehash')\n")
            subprocess.run(["git", "-C", str(source), "add", str(script)], check=True)
            subprocess.run(
                [
                    "git",
                    "-C",
                    str(source),
                    "-c",
                    "user.name=Installer Test",
                    "-c",
                    "user.email=installer@example.invalid",
                    "commit",
                    "-m",
                    "delayed handoff mutation",
                ],
                check=True,
                capture_output=True,
                text=True,
            )
            destination = root / "handoff mutation trial"

            result = self.run_installer(destination, source)

            self.assertEqual(4, result.returncode)
            self.assertFalse(destination.exists())
            self.assertIn("INSTALL_HANDOFF_MUTATED", result.stderr)

    def test_required_path_symlink_ancestor_is_rejected_without_execution(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = self.make_source_repository(root)
            external_scripts = root / "external scripts"
            shutil.copytree(source / "scripts", external_scripts)
            marker = root / "external executed"
            external_clone_pack = external_scripts / "clone_pack.py"
            original = external_clone_pack.read_text(encoding="utf-8")
            external_clone_pack.write_text(
                "from pathlib import Path\n"
                f"Path({str(marker)!r}).write_text('executed\\n', encoding='utf-8')\n"
                + original,
                encoding="utf-8",
            )
            shutil.rmtree(source / "scripts")
            (source / "scripts").symlink_to(external_scripts, target_is_directory=True)
            subprocess.run(["git", "-C", str(source), "add", "-A"], check=True)
            subprocess.run(
                [
                    "git",
                    "-C",
                    str(source),
                    "-c",
                    "user.name=Installer Test",
                    "-c",
                    "user.email=installer@example.invalid",
                    "commit",
                    "-m",
                    "escaping scripts symlink",
                ],
                check=True,
                capture_output=True,
                text=True,
            )
            destination = root / "symlink trial"

            result = self.run_installer(destination, source)

            self.assertEqual(4, result.returncode)
            self.assertFalse(destination.exists())
            self.assertFalse(marker.exists())
            self.assertIn("INSTALL_TREE_INVALID", result.stderr)

    def test_precreated_workspace_symlink_cannot_redirect_staged_writes(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = self.make_source_repository(root)
            external = root / "external workspace target"
            external.mkdir()
            sentinel = external / "sentinel"
            sentinel.write_bytes(b"preserve workspace target\n")
            script = source / "scripts" / "clone_pack.py"
            script.write_text(
                "from pathlib import Path\n"
                "import os\n"
                "stage = Path(__file__).resolve().parents[2]\n"
                f"os.symlink({str(external)!r}, stage / 'minecraft-clone')\n"
                "print('init validate migrate capture parity scaffold record-run record-manual '",
                encoding="utf-8",
            )
            with script.open("a", encoding="utf-8") as handle:
                handle.write(
                    "      'gap-transition assure seal diff enhancement-init repo-snapshot '")
                handle.write("\n")
                handle.write(
                    "      'baseline-run regression verify-scope enhancement-transition rehash')\n")
            subprocess.run(["git", "-C", str(source), "add", str(script)], check=True)
            subprocess.run(
                [
                    "git",
                    "-C",
                    str(source),
                    "-c",
                    "user.name=Installer Test",
                    "-c",
                    "user.email=installer@example.invalid",
                    "commit",
                    "-m",
                    "precreate workspace symlink",
                ],
                check=True,
                capture_output=True,
                text=True,
            )
            destination = root / "workspace link trial"

            result = self.run_installer(destination, source)

            self.assertEqual(6, result.returncode)
            self.assertFalse(destination.exists())
            self.assertEqual([sentinel], sorted(external.iterdir()))
            self.assertEqual(b"preserve workspace target\n", sentinel.read_bytes())
            self.assertIn("INSTALL_DESTINATION_FAILURE", result.stderr)

    def test_precreated_receipt_symlink_cannot_redirect_receipt_write(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = self.make_source_repository(root)
            external_receipt = root / "external receipt"
            external_receipt.write_bytes(b"preserve receipt target\n")
            script = source / "scripts" / "clone_pack.py"
            script.write_text(
                "from pathlib import Path\n"
                "import os\n"
                "stage = Path(__file__).resolve().parents[2]\n"
                f"os.symlink({str(external_receipt)!r}, stage / 'installation-receipt.json')\n"
                "print('init validate migrate capture parity scaffold record-run record-manual '",
                encoding="utf-8",
            )
            with script.open("a", encoding="utf-8") as handle:
                handle.write(
                    "      'gap-transition assure seal diff enhancement-init repo-snapshot '")
                handle.write("\n")
                handle.write(
                    "      'baseline-run regression verify-scope enhancement-transition rehash')\n")
            subprocess.run(["git", "-C", str(source), "add", str(script)], check=True)
            subprocess.run(
                [
                    "git",
                    "-C",
                    str(source),
                    "-c",
                    "user.name=Installer Test",
                    "-c",
                    "user.email=installer@example.invalid",
                    "commit",
                    "-m",
                    "precreate receipt symlink",
                ],
                check=True,
                capture_output=True,
                text=True,
            )
            destination = root / "receipt link trial"

            result = self.run_installer(destination, source)

            self.assertEqual(6, result.returncode)
            self.assertFalse(destination.exists())
            self.assertEqual(b"preserve receipt target\n", external_receipt.read_bytes())
            self.assertIn("INSTALL_RECEIPT_FAILURE", result.stderr)

    def test_malformed_skill_frontmatter_is_rejected_before_execution(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = self.make_source_repository(root)
            (source / "SKILL.md").write_text(
                "---\nname: a-different-skill\ndescription: fixture\n---\nfixture\n",
                encoding="utf-8",
            )
            subprocess.run(["git", "-C", str(source), "add", "SKILL.md"], check=True)
            subprocess.run(
                [
                    "git",
                    "-C",
                    str(source),
                    "-c",
                    "user.name=Installer Test",
                    "-c",
                    "user.email=installer@example.invalid",
                    "commit",
                    "-m",
                    "malformed skill metadata",
                ],
                check=True,
                capture_output=True,
                text=True,
            )
            destination = root / "metadata trial"

            result = self.run_installer(destination, source)

            self.assertEqual(4, result.returncode)
            self.assertFalse(destination.exists())
            self.assertIn("INSTALL_TREE_INVALID", result.stderr)

    def test_yaml_null_skill_description_is_rejected_before_execution(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = self.make_source_repository(root)
            (source / "SKILL.md").write_text(
                "---\nname: clone-software\ndescription: # YAML null\n---\nfixture\n",
                encoding="utf-8",
            )
            subprocess.run(["git", "-C", str(source), "add", "SKILL.md"], check=True)
            subprocess.run(
                [
                    "git",
                    "-C",
                    str(source),
                    "-c",
                    "user.name=Installer Test",
                    "-c",
                    "user.email=installer@example.invalid",
                    "commit",
                    "-m",
                    "null skill description",
                ],
                check=True,
                capture_output=True,
                text=True,
            )
            destination = root / "skill description trial"

            result = self.run_installer(destination, source)

            self.assertEqual(4, result.returncode)
            self.assertFalse(destination.exists())
            self.assertIn("INSTALL_TREE_INVALID", result.stderr)

    def test_yaml_collection_skill_description_is_rejected_before_execution(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = self.make_source_repository(root)
            (source / "SKILL.md").write_text(
                "---\nname: clone-software\ndescription: []\n---\nfixture\n",
                encoding="utf-8",
            )
            subprocess.run(["git", "-C", str(source), "add", "SKILL.md"], check=True)
            subprocess.run(
                [
                    "git",
                    "-C",
                    str(source),
                    "-c",
                    "user.name=Installer Test",
                    "-c",
                    "user.email=installer@example.invalid",
                    "commit",
                    "-m",
                    "collection skill description",
                ],
                check=True,
                capture_output=True,
                text=True,
            )
            destination = root / "skill collection trial"

            result = self.run_installer(destination, source)

            self.assertEqual(4, result.returncode)
            self.assertFalse(destination.exists())
            self.assertIn("INSTALL_TREE_INVALID", result.stderr)

    def test_yaml_numeric_skill_description_is_rejected_before_execution(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = self.make_source_repository(root)
            (source / "SKILL.md").write_text(
                "---\nname: clone-software\ndescription: 0x10\n---\nfixture\n",
                encoding="utf-8",
            )
            subprocess.run(["git", "-C", str(source), "add", "SKILL.md"], check=True)
            subprocess.run(
                [
                    "git",
                    "-C",
                    str(source),
                    "-c",
                    "user.name=Installer Test",
                    "-c",
                    "user.email=installer@example.invalid",
                    "commit",
                    "-m",
                    "numeric skill description",
                ],
                check=True,
                capture_output=True,
                text=True,
            )
            destination = root / "skill numeric trial"

            result = self.run_installer(destination, source)

            self.assertEqual(4, result.returncode)
            self.assertFalse(destination.exists())
            self.assertIn("INSTALL_TREE_INVALID", result.stderr)

    def test_malformed_quoted_skill_description_is_rejected_before_execution(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = self.make_source_repository(root)
            (source / "SKILL.md").write_text(
                "---\nname: clone-software\ndescription: \"valid close\" trailing \"\n---\nfixture\n",
                encoding="utf-8",
            )
            subprocess.run(["git", "-C", str(source), "add", "SKILL.md"], check=True)
            subprocess.run(
                [
                    "git",
                    "-C",
                    str(source),
                    "-c",
                    "user.name=Installer Test",
                    "-c",
                    "user.email=installer@example.invalid",
                    "commit",
                    "-m",
                    "malformed quoted description",
                ],
                check=True,
                capture_output=True,
                text=True,
            )
            destination = root / "malformed quote trial"

            result = self.run_installer(destination, source)

            self.assertEqual(4, result.returncode)
            self.assertFalse(destination.exists())
            self.assertIn("INSTALL_TREE_INVALID", result.stderr)

    def test_plain_skill_description_with_yaml_mapping_separator_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = self.make_source_repository(root)
            (source / "SKILL.md").write_text(
                "---\nname: clone-software\ndescription: Hello: value\n---\nfixture\n",
                encoding="utf-8",
            )
            subprocess.run(["git", "-C", str(source), "add", "SKILL.md"], check=True)
            subprocess.run(
                [
                    "git",
                    "-C",
                    str(source),
                    "-c",
                    "user.name=Installer Test",
                    "-c",
                    "user.email=installer@example.invalid",
                    "commit",
                    "-m",
                    "mapping separator description",
                ],
                check=True,
                capture_output=True,
                text=True,
            )
            destination = root / "mapping separator trial"

            result = self.run_installer(destination, source)

            self.assertEqual(4, result.returncode)
            self.assertFalse(destination.exists())
            self.assertIn("INSTALL_TREE_INVALID", result.stderr)

    def test_non_utf8_prompt_is_rejected_before_execution(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = self.make_source_repository(root)
            prompt_path = source / "assets" / "prompts" / PROMPT.name
            prompt_path.write_bytes(b"\xff\xfe\x00")
            subprocess.run(
                ["git", "-C", str(source), "add", str(prompt_path)], check=True
            )
            subprocess.run(
                [
                    "git",
                    "-C",
                    str(source),
                    "-c",
                    "user.name=Installer Test",
                    "-c",
                    "user.email=installer@example.invalid",
                    "commit",
                    "-m",
                    "non utf8 prompt",
                ],
                check=True,
                capture_output=True,
                text=True,
            )
            destination = root / "non utf8 prompt trial"

            result = self.run_installer(destination, source)

            self.assertEqual(4, result.returncode)
            self.assertFalse(destination.exists())
            self.assertIn("INSTALL_TREE_INVALID", result.stderr)

    def test_yaml_null_agent_interface_value_is_rejected_before_execution(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = self.make_source_repository(root)
            (source / "agents" / "openai.yaml").write_text(
                "interface:\n"
                "  display_name: # YAML null with a comment\n"
                "  short_description: fixture clone skill\n"
                "  default_prompt: Use $clone-software for this fixture.\n",
                encoding="utf-8",
            )
            subprocess.run(
                ["git", "-C", str(source), "add", "agents/openai.yaml"], check=True
            )
            subprocess.run(
                [
                    "git",
                    "-C",
                    str(source),
                    "-c",
                    "user.name=Installer Test",
                    "-c",
                    "user.email=installer@example.invalid",
                    "commit",
                    "-m",
                    "null agent metadata",
                ],
                check=True,
                capture_output=True,
                text=True,
            )
            destination = root / "agent metadata trial"

            result = self.run_installer(destination, source)

            self.assertEqual(4, result.returncode)
            self.assertFalse(destination.exists())
            self.assertIn("INSTALL_TREE_INVALID", result.stderr)

    def test_yaml_collection_agent_values_and_comment_invocation_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = self.make_source_repository(root)
            (source / "agents" / "openai.yaml").write_text(
                "interface:\n"
                "  display_name: []\n"
                "  short_description: {}\n"
                "  default_prompt: []\n"
                "# Use $clone-software only in this ignored comment.\n",
                encoding="utf-8",
            )
            subprocess.run(
                ["git", "-C", str(source), "add", "agents/openai.yaml"], check=True
            )
            subprocess.run(
                [
                    "git",
                    "-C",
                    str(source),
                    "-c",
                    "user.name=Installer Test",
                    "-c",
                    "user.email=installer@example.invalid",
                    "commit",
                    "-m",
                    "collection agent metadata",
                ],
                check=True,
                capture_output=True,
                text=True,
            )
            destination = root / "agent collection trial"

            result = self.run_installer(destination, source)

            self.assertEqual(4, result.returncode)
            self.assertFalse(destination.exists())
            self.assertIn("INSTALL_TREE_INVALID", result.stderr)

    def test_yaml_nonfinite_agent_value_is_rejected_before_execution(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = self.make_source_repository(root)
            (source / "agents" / "openai.yaml").write_text(
                "interface:\n"
                "  display_name: .inf\n"
                "  short_description: fixture clone skill\n"
                "  default_prompt: Use $clone-software for this fixture.\n",
                encoding="utf-8",
            )
            subprocess.run(
                ["git", "-C", str(source), "add", "agents/openai.yaml"], check=True
            )
            subprocess.run(
                [
                    "git",
                    "-C",
                    str(source),
                    "-c",
                    "user.name=Installer Test",
                    "-c",
                    "user.email=installer@example.invalid",
                    "commit",
                    "-m",
                    "nonfinite agent metadata",
                ],
                check=True,
                capture_output=True,
                text=True,
            )
            destination = root / "agent nonfinite trial"

            result = self.run_installer(destination, source)

            self.assertEqual(4, result.returncode)
            self.assertFalse(destination.exists())
            self.assertIn("INSTALL_TREE_INVALID", result.stderr)

    def test_wrong_scaffold_catalog_schema_is_rejected_before_execution(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = self.make_source_repository(root)
            catalog_path = source / "assets" / "scaffolds" / "catalog.json"
            catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
            catalog["schema_version"] = "wrong/v9"
            catalog_path.write_text(
                json.dumps(catalog, sort_keys=True) + "\n", encoding="utf-8"
            )
            subprocess.run(
                ["git", "-C", str(source), "add", "assets/scaffolds/catalog.json"],
                check=True,
            )
            subprocess.run(
                [
                    "git",
                    "-C",
                    str(source),
                    "-c",
                    "user.name=Installer Test",
                    "-c",
                    "user.email=installer@example.invalid",
                    "commit",
                    "-m",
                    "wrong scaffold catalog schema",
                ],
                check=True,
                capture_output=True,
                text=True,
            )
            destination = root / "catalog schema trial"

            result = self.run_installer(destination, source)

            self.assertEqual(4, result.returncode)
            self.assertFalse(destination.exists())
            self.assertIn("INSTALL_TREE_INVALID", result.stderr)

    def test_missing_prompt_prerequisite_is_rejected_before_execution(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = self.make_source_repository(root)
            (source / "LICENSE").unlink()
            subprocess.run(["git", "-C", str(source), "add", "-A"], check=True)
            subprocess.run(
                [
                    "git",
                    "-C",
                    str(source),
                    "-c",
                    "user.name=Installer Test",
                    "-c",
                    "user.email=installer@example.invalid",
                    "commit",
                    "-m",
                    "missing prompt prerequisite",
                ],
                check=True,
                capture_output=True,
                text=True,
            )
            destination = root / "missing prerequisite trial"

            result = self.run_installer(destination, source)

            self.assertEqual(4, result.returncode)
            self.assertFalse(destination.exists())
            self.assertIn("INSTALL_ASSET_MISSING", result.stderr)

    def test_replaced_stage_is_not_deleted_on_failure(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = self.make_source_repository(root)
            script = source / "scripts" / "clone_pack.py"
            script.write_text(
                "from pathlib import Path\n"
                "stage = Path(__file__).resolve().parents[2]\n"
                "moved = stage.parent / 'attacker-preserved-original-stage'\n"
                "stage.rename(moved)\n"
                "stage.mkdir()\n"
                "(stage / 'replacement-sentinel').write_text('do not delete\\n', encoding='utf-8')\n"
                "print('init validate migrate capture parity scaffold record-run record-manual '",
                encoding="utf-8",
            )
            with script.open("a", encoding="utf-8") as handle:
                handle.write(
                    "      'gap-transition assure seal diff enhancement-init repo-snapshot '")
                handle.write("\n")
                handle.write(
                    "      'baseline-run regression verify-scope enhancement-transition rehash')\n")
            subprocess.run(["git", "-C", str(source), "add", str(script)], check=True)
            subprocess.run(
                [
                    "git",
                    "-C",
                    str(source),
                    "-c",
                    "user.name=Installer Test",
                    "-c",
                    "user.email=installer@example.invalid",
                    "commit",
                    "-m",
                    "replace installer stage",
                ],
                check=True,
                capture_output=True,
                text=True,
            )
            destination = root / "replacement trial"

            result = self.run_installer(destination, source)

            self.assertNotEqual(0, result.returncode)
            self.assertFalse(destination.exists())
            replacements = [
                path
                for path in root.glob(".clone-software-wsl-install.*")
                if (path / "replacement-sentinel").is_file()
            ]
            self.assertEqual(1, len(replacements), result.stderr)
            self.assertEqual(
                b"do not delete\n",
                (replacements[0] / "replacement-sentinel").read_bytes(),
            )
            self.assertIn("STAGE_CLEANUP_REFUSED", result.stderr)

    def test_installer_contains_no_dependency_or_codex_install_command(self) -> None:
        script = INSTALLER.read_text(encoding="utf-8")
        forbidden = (
            "apt install",
            "apt-get install",
            "npm install",
            "npx playwright install",
            "pip install",
            "sudo ",
            "curl |",
            "wget |",
        )
        self.assertEqual([], [value for value in forbidden if value in script])
        self.assertNotIn("--force", script)
        self.assertNotIn("--overwrite", script)
        self.assertNotIn("rm -rf", script)
        for required in (
            "git clone --quiet --no-hardlinks",
            "create_staged_workspace",
            "validate_staged_handoff",
            "O_NOFOLLOW",
            "INSTALL_STAGE_RETAINED",
            "INSTALL_HANDOFF_MUTATED",
        ):
            self.assertIn(required, script)

    def test_minecraft_prompt_is_exact_clean_room_dependency_free_contract(self) -> None:
        prompt = PROMPT.read_text(encoding="utf-8")
        required = (
            "$clone-software",
            "mvp-build",
            "USER_PINNED",
            "game-simulation",
            "static-web-esm",
            "WebGL 2",
            "fixed simulation step",
            "localStorage",
            "CC0-1.0",
            "MUST NOT claim parity with Minecraft",
            "No Mojang or Minecraft source code, binaries, assets, textures, audio, fonts, logos, names, or trade dress",
            "npm test",
            "gaps_analysis.md",
            "full-stack QA disposition: `NOT_APPLICABLE`",
            "`Ready. Select Start to play.`",
            "`Block removed.`",
            "`Block placed.`",
            "`No block is in reach.`",
            "yaw = positive_mod(yaw + 3.141592653589793, 6.283185307179586) - 3.141592653589793",
            "tests/mesh.test.mjs",
            "tests/renderer.test.mjs",
            "6 faces, 24 vertices, and 36 indices",
            "10 faces, 40 vertices, and 60 indices",
            "Storage is unavailable; current changes remain in memory.",
            "Reset failed; saved data was not changed.",
            "docs/clone/evidence/manual/GUI-001/observation.json",
            "docs/clone/post-mvp/usability_critique.md",
            "HYPOTHESIS_UNVALIDATED",
            "HALT",
        )
        self.assertEqual([], [value for value in required if value not in prompt])
        self.assertNotRegex(prompt, r"\b(?:TODO|TBD|TBC|eventually|ideally)\b")
        for forbidden in (
            "npm install",
            "npx ",
            "playwright install",
            "curl ",
            "wget ",
        ):
            self.assertNotIn(forbidden, prompt)

    def test_minecraft_prompt_pins_executable_pack_and_parity_contracts(self) -> None:
        prompt = PROMPT.read_text(encoding="utf-8")
        required = (
            "`PROV-001` = immutable controlling-request provenance record",
            "`ASSURE-002` is the required threat-model case",
            "--case ASSURE-001 --case ASSURE-002",
            'attributes are exactly `environment_id:"ENV-001"` and `manual_procedure_sha256:"<prompt-sha256>"`',
            '`oracles:["ART-001","E-001"]`',
            '`E-001.links.requirements` is exactly `["REQ-001","REQ-002","REQ-003","REQ-004","REQ-005","REQ-006","REQ-007","REQ-008","REQ-009","REQ-010","REQ-011","REQ-012","REQ-013","REQ-014"]`',
            'attributes:{"case_sha256":"<current-case-sha256>"}',
            '`captures:["CAP-001","CAP-002"]`',
            "`GUI-001` remains a non-index reporting label",
            "Every fixed step uses `dt = 1/60` and performs exactly this order",
        )
        self.assertEqual([], [value for value in required if value not in prompt])
        self.assertNotIn("`WF-001`", prompt)
        self.assertNotIn("`WF-002`", prompt)
        self.assertNotIn("`WF-003`", prompt)

        seal = (
            "python3 <skill-root>/scripts/clone_pack.py seal docs/clone "
            "--profile verified-mvp"
        )
        validate = (
            "python3 <skill-root>/scripts/clone_pack.py validate docs/clone "
            "--profile verified-mvp --format json"
        )
        gate_start = prompt.index("| `GATE-007` |")
        gate_end = prompt.index("\n", gate_start)
        gate = prompt[gate_start:gate_end]
        self.assertLess(gate.index(seal), gate.index(validate))

        oracle_start_marker = (
            '```json\n{"schema_version":"voxel-sandbox-contract-oracle/v1"'
        )
        oracle_start = prompt.index(oracle_start_marker) + len("```json\n")
        oracle_end = prompt.index("\n```", oracle_start)
        oracle = json.loads(prompt[oracle_start:oracle_end])
        self.assertEqual(
            ["schema_version", "request_sha256", "number_normalization", "cases"],
            list(oracle),
        )
        self.assertEqual("<prompt-sha256>", oracle["request_sha256"])
        self.assertEqual(
            [
                "world-heights-strata",
                "fixed-step-yaw-movement",
                "ray-and-edit-records",
                "mesh-and-camera-matrices",
                "storage-canonical-write",
                "storage-obstructed-position-recovery",
                "storage-failure-retry-and-reset",
            ],
            [case["name"] for case in oracle["cases"]],
        )
        self.assertTrue(
            all(list(case) == ["name", "input", "expected"] for case in oracle["cases"])
        )

    def test_public_documentation_links_exact_installer_and_prompt(self) -> None:
        combined = "\n".join(
            (ROOT / path).read_text(encoding="utf-8")
            for path in (
                "README.md",
                "docs/getting-started.md",
                "docs/troubleshooting.md",
                "changelog.md",
            )
        )
        for required in (
            "scripts/install_clone_software_wsl.sh",
            "assets/prompts/minecraft-clean-room-mvp.md",
            "MINECRAFT_CLONE_PROMPT.md",
            "installation-receipt.json",
            "--destination",
            "--verify full",
            "--trust-custom-source-code",
            "--no-hardlinks",
            "INSTALL_STAGE_RETAINED",
            "INSTALL_HANDOFF_MUTATED",
            "does not install Codex",
            "does not install Node packages",
        ):
            self.assertIn(required, combined)
        self.assertNotIn("After creating the destination parent", combined)


if __name__ == "__main__":
    unittest.main()
