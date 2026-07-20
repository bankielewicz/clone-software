from __future__ import annotations

import contextlib
import hashlib
import importlib.util
import io
import json
import os
import stat
import struct
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
CHECKER = ROOT / "scripts" / "check_wsl_trial_workspace.py"


def reference_checkout_identity(root: Path) -> str:
    """Reproduce the installer's receipt digest independently of the checker."""

    digest = hashlib.sha256()

    def add_field(kind: bytes, value: bytes) -> None:
        digest.update(kind)
        digest.update(struct.pack(">Q", len(value)))
        digest.update(value)

    def stable_fields(value: os.stat_result) -> tuple[int, int, int, int, int, int]:
        return (
            value.st_dev,
            value.st_ino,
            value.st_mode,
            value.st_size,
            value.st_mtime_ns,
            value.st_ctime_ns,
        )

    def scan(directory: Path, relative: Path) -> None:
        before = directory.stat(follow_symlinks=False)
        add_field(b"D", os.fsencode(str(relative)))
        add_field(b"M", oct(stat.S_IMODE(before.st_mode)).encode("ascii"))
        for entry in sorted(os.scandir(directory), key=lambda item: os.fsencode(item.name)):
            child_relative = relative / entry.name
            encoded_relative = os.fsencode(str(child_relative))
            observed = entry.stat(follow_symlinks=False)
            if stat.S_ISLNK(observed.st_mode):
                if not child_relative.parts or child_relative.parts[0] != ".git":
                    raise AssertionError(f"fixture contains a forbidden symlink: {child_relative}")
                add_field(b"L", encoded_relative)
                add_field(b"M", oct(stat.S_IMODE(observed.st_mode)).encode("ascii"))
                add_field(b"T", os.fsencode(os.readlink(entry.path)))
            elif stat.S_ISDIR(observed.st_mode):
                scan(Path(entry.path), child_relative)
            elif stat.S_ISREG(observed.st_mode):
                descriptor = os.open(entry.path, os.O_RDONLY)
                try:
                    opened = os.fstat(descriptor)
                    if stable_fields(opened) != stable_fields(observed):
                        raise AssertionError("fixture file changed before digest")
                    add_field(b"F", encoded_relative)
                    add_field(b"M", oct(stat.S_IMODE(observed.st_mode)).encode("ascii"))
                    while True:
                        chunk = os.read(descriptor, 1024 * 1024)
                        if not chunk:
                            break
                        add_field(b"B", chunk)
                    if stable_fields(os.fstat(descriptor)) != stable_fields(opened):
                        raise AssertionError("fixture file changed during digest")
                finally:
                    os.close(descriptor)
            else:
                raise AssertionError(f"fixture contains a special file: {child_relative}")
        after = directory.stat(follow_symlinks=False)
        if (
            before.st_dev,
            before.st_ino,
            before.st_mode,
            before.st_mtime_ns,
            before.st_ctime_ns,
        ) != (
            after.st_dev,
            after.st_ino,
            after.st_mode,
            after.st_mtime_ns,
            after.st_ctime_ns,
        ):
            raise AssertionError("fixture directory changed during digest")

    scan(root, Path("."))
    return digest.hexdigest()


class WslTrialWorkspaceCheckerTests(unittest.TestCase):
    maxDiff = None

    def make_fixture(self, root: Path) -> tuple[Path, Path, dict[str, object]]:
        install_root = root / "installed trial"
        project = install_root / "clone-software"
        workspace = install_root / "minecraft-clone"
        skills = workspace / ".agents" / "skills"
        project.mkdir(parents=True)
        skills.mkdir(parents=True)
        skill_link = skills / "clone-software"
        skill_link.symlink_to("../../../clone-software", target_is_directory=True)
        prompt = workspace / "MINECRAFT_CLONE_PROMPT.md"
        prompt.write_bytes(b"Use $clone-software exactly.\n")

        link_text = os.readlink(skill_link)
        inventory: list[dict[str, object]] = [
            {
                "mode": stat.S_IMODE((workspace / ".agents").lstat().st_mode),
                "path": ".agents",
                "type": "directory",
            },
            {
                "mode": stat.S_IMODE(skills.lstat().st_mode),
                "path": ".agents/skills",
                "type": "directory",
            },
            {
                "mode": stat.S_IMODE(skill_link.lstat().st_mode),
                "path": ".agents/skills/clone-software",
                "sha256": hashlib.sha256(link_text.encode("utf-8")).hexdigest(),
                "target": link_text,
                "type": "symlink",
            },
            {
                "mode": stat.S_IMODE(prompt.lstat().st_mode),
                "path": "MINECRAFT_CLONE_PROMPT.md",
                "sha256": hashlib.sha256(prompt.read_bytes()).hexdigest(),
                "size": prompt.lstat().st_size,
                "type": "file",
            },
        ]
        receipt: dict[str, object] = {
            "schema_version": "clone-software-wsl-test-install/v2",
            "source_url": "https://example.invalid/clone-software.git",
            "requested_ref": "main",
            "resolved_head": "a" * 40,
            "checkout_state": f"head={'a' * 40};branch=main",
            "checkout_identity_sha256": reference_checkout_identity(project),
            "project_dir": str(project),
            "workspace_dir": str(workspace),
            "skill_link": str(skill_link),
            "prompt_path": str(prompt),
            "prompt_sha256": hashlib.sha256(prompt.read_bytes()).hexdigest(),
            "verification": "smoke",
            "codex_executable": "/usr/bin/false",
            "installed_workspace_inventory": inventory,
        }
        receipt_path = install_root / "installation-receipt.json"
        self.write_receipt(receipt_path, receipt)
        return workspace, receipt_path, receipt

    def write_receipt(self, path: Path, receipt: dict[str, object]) -> None:
        path.write_text(
            json.dumps(
                receipt,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            )
            + "\n",
            encoding="utf-8",
            newline="\n",
        )

    def checker_arguments(self, workspace: Path, receipt: Path) -> list[str]:
        return [
            sys.executable,
            str(CHECKER),
            "--workspace",
            str(workspace),
            "--receipt",
            str(receipt),
            "--allow-runtime-path",
            ".codex",
            "--authority-id",
            "DEC-004",
        ]

    def run_checker(
        self, workspace: Path, receipt: Path, *extra: str
    ) -> subprocess.CompletedProcess[str]:
        arguments = self.checker_arguments(workspace, receipt)
        arguments.extend(extra)
        return subprocess.run(
            arguments,
            cwd=workspace,
            capture_output=True,
            text=True,
            timeout=15,
        )

    def retain_prewrite_result(
        self, workspace: Path, receipt: Path
    ) -> tuple[Path, dict[str, object]]:
        result = self.run_checker(workspace, receipt)
        payload = self.assert_handled_result(
            result, exit_code=0, status="PASS", diagnostic=None
        )
        path = (
            workspace
            / "docs"
            / "clone"
            / "evidence"
            / "raw"
            / "workspace-check"
            / "pre-write.json"
        )
        path.parent.mkdir(parents=True)
        path.write_bytes(result.stdout.encode("utf-8"))
        return path, payload

    def assert_handled_result(
        self,
        result: subprocess.CompletedProcess[str],
        *,
        exit_code: int,
        status: str,
        diagnostic: str | None,
    ) -> dict[str, object]:
        self.assertEqual(exit_code, result.returncode, result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(
            {
                "schema_version",
                "status",
                "diagnostic",
                "workspace",
                "receipt",
                "product_inventory",
                "runtime_exclusions",
            },
            set(payload),
        )
        self.assertEqual(status, payload["status"])
        self.assertEqual(diagnostic, payload["diagnostic"])
        self.assertEqual(
            json.dumps(
                payload,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            )
            + "\n",
            result.stdout,
        )
        if diagnostic is None:
            self.assertEqual("", result.stderr)
        else:
            self.assertIn(diagnostic, result.stderr)
        return payload

    def load_checker(self):
        spec = importlib.util.spec_from_file_location("wsl_workspace_checker", CHECKER)
        self.assertIsNotNone(spec)
        self.assertIsNotNone(spec.loader)
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        try:
            spec.loader.exec_module(module)
        finally:
            sys.modules.pop(spec.name, None)
        return module

    def snapshot_tree(self, root: Path) -> list[tuple[str, str, int, object]]:
        records: list[tuple[str, str, int, object]] = []
        for current, directory_names, file_names in os.walk(root, followlinks=False):
            current_path = Path(current)
            for name in sorted(directory_names + file_names):
                path = current_path / name
                relative = path.relative_to(root).as_posix()
                observed = path.lstat()
                mode = stat.S_IMODE(observed.st_mode)
                if stat.S_ISLNK(observed.st_mode):
                    records.append((relative, "symlink", mode, os.readlink(path)))
                elif stat.S_ISDIR(observed.st_mode):
                    records.append((relative, "directory", mode, None))
                elif stat.S_ISREG(observed.st_mode):
                    records.append((relative, "file", mode, path.read_bytes()))
                else:
                    records.append((relative, "other", mode, None))
        return records

    def test_exact_installed_workspace_and_real_git_directory_pass(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            workspace, receipt_path, receipt = self.make_fixture(Path(temporary))
            git_directory = workspace / ".git"
            git_directory.mkdir()
            (git_directory / "HEAD").write_text("ref: refs/heads/main\n", encoding="utf-8")

            result = self.run_checker(workspace, receipt_path)

            payload = self.assert_handled_result(
                result, exit_code=0, status="PASS", diagnostic=None
            )
            self.assertEqual(str(workspace.resolve()), payload["workspace"])
            self.assertEqual(str(receipt_path.resolve()), payload["receipt"])
            self.assertEqual(receipt["installed_workspace_inventory"], payload["product_inventory"])
            self.assertEqual([], payload["runtime_exclusions"])

    def test_exact_empty_nonwritable_codex_directory_is_user_authorized_exclusion(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            workspace, receipt_path, receipt = self.make_fixture(Path(temporary))
            runtime = workspace / ".codex"
            runtime.mkdir(mode=0o555)
            runtime.chmod(0o555)
            observed = runtime.lstat()

            result = self.run_checker(workspace, receipt_path)

            payload = self.assert_handled_result(
                result, exit_code=0, status="PASS", diagnostic=None
            )
            self.assertEqual(receipt["installed_workspace_inventory"], payload["product_inventory"])
            self.assertEqual(
                [
                    {
                        "allowed_operations": [],
                        "authority_ids": ["DEC-004"],
                        "disposition": "TOOL_RUNTIME_EXCLUDED",
                        "evidence_ids": ["E-002"],
                        "expected_identity": {
                            "device": observed.st_dev,
                            "empty": True,
                            "inode": observed.st_ino,
                            "mode": stat.S_IMODE(observed.st_mode),
                            "type": "directory",
                        },
                        "owner_claim": "USER_PINNED",
                        "path": ".codex",
                        "pre_session_presence": False,
                    }
                ],
                payload["runtime_exclusions"],
            )
            self.assertNotIn("provider", result.stdout.lower())

    def test_missing_receipt_is_runtime_hold(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            workspace, receipt_path, _ = self.make_fixture(Path(temporary))
            receipt_path.unlink()

            result = self.run_checker(workspace, receipt_path)

            self.assert_handled_result(
                result, exit_code=4, status="HOLD", diagnostic="RUNTIME-001"
            )

    def test_v1_receipt_is_runtime_hold_not_accepted_as_absence_proof(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            workspace, receipt_path, receipt = self.make_fixture(Path(temporary))
            receipt["schema_version"] = "clone-software-wsl-test-install/v1"
            receipt.pop("installed_workspace_inventory")
            self.write_receipt(receipt_path, receipt)

            result = self.run_checker(workspace, receipt_path)

            self.assert_handled_result(
                result, exit_code=4, status="HOLD", diagnostic="RUNTIME-001"
            )

    def test_receipt_accepts_exact_lowercase_sha1_or_sha256_git_head(self) -> None:
        for length in (40, 64):
            with self.subTest(length=length), tempfile.TemporaryDirectory() as temporary:
                workspace, receipt_path, receipt = self.make_fixture(Path(temporary))
                head = "a" * length
                receipt["resolved_head"] = head
                receipt["checkout_state"] = f"head={head};branch=main"
                self.write_receipt(receipt_path, receipt)

                result = self.run_checker(workspace, receipt_path)

                self.assert_handled_result(
                    result, exit_code=0, status="PASS", diagnostic=None
                )

    def test_receipt_rejects_noncanonical_or_unsupported_git_head(self) -> None:
        values = (
            "a" * 39,
            "a" * 41,
            "a" * 63,
            "a" * 65,
            "A" * 40,
            "g" * 40,
        )
        for value in values:
            with self.subTest(value=value), tempfile.TemporaryDirectory() as temporary:
                workspace, receipt_path, receipt = self.make_fixture(Path(temporary))
                receipt["resolved_head"] = value
                receipt["checkout_state"] = f"head={value};branch=main"
                self.write_receipt(receipt_path, receipt)

                result = self.run_checker(workspace, receipt_path)

                self.assertEqual(2, result.returncode)
                self.assertEqual("", result.stdout)
                self.assertIn("RECEIPT_SCHEMA_INVALID", result.stderr)

    def test_noncanonical_or_malformed_receipt_is_schema_exit(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            workspace, receipt_path, receipt = self.make_fixture(Path(temporary))
            receipt_path.write_text(json.dumps(receipt, indent=2), encoding="utf-8")

            noncanonical = self.run_checker(workspace, receipt_path)

            self.assert_handled_result(
                noncanonical, exit_code=4, status="HOLD", diagnostic="RUNTIME-001"
            )

            receipt_path.write_text("{not-json}\n", encoding="utf-8")
            malformed = self.run_checker(workspace, receipt_path)
            self.assertEqual(2, malformed.returncode)
            self.assertEqual("", malformed.stdout)
            self.assertIn("RECEIPT_SCHEMA_INVALID", malformed.stderr)

    def test_product_byte_mismatch_is_runtime_hold(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            workspace, receipt_path, _ = self.make_fixture(Path(temporary))
            (workspace / "MINECRAFT_CLONE_PROMPT.md").write_bytes(b"changed\n")

            result = self.run_checker(workspace, receipt_path)

            self.assert_handled_result(
                result, exit_code=4, status="HOLD", diagnostic="RUNTIME-001"
            )

    def test_writable_codex_directory_is_runtime_hold(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            workspace, receipt_path, _ = self.make_fixture(Path(temporary))
            runtime = workspace / ".codex"
            runtime.mkdir(mode=0o755)
            runtime.chmod(0o755)

            result = self.run_checker(workspace, receipt_path)

            self.assert_handled_result(
                result, exit_code=4, status="HOLD", diagnostic="RUNTIME-001"
            )

    def test_nonempty_codex_directory_is_runtime_hold(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            workspace, receipt_path, _ = self.make_fixture(Path(temporary))
            runtime = workspace / ".codex"
            runtime.mkdir()
            (runtime / "AGENTS.md").write_text("must not be read\n", encoding="utf-8")
            runtime.chmod(0o555)

            result = self.run_checker(workspace, receipt_path)

            self.assert_handled_result(
                result, exit_code=4, status="HOLD", diagnostic="RUNTIME-001"
            )
            self.assertNotIn("must not be read", result.stdout + result.stderr)

    def test_codex_symlink_is_runtime_hold_and_target_is_untouched(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            workspace, receipt_path, _ = self.make_fixture(root)
            target = root / "external runtime"
            target.mkdir()
            sentinel = target / "sentinel"
            sentinel.write_bytes(b"preserve exactly\n")
            (workspace / ".codex").symlink_to(target, target_is_directory=True)

            result = self.run_checker(workspace, receipt_path)

            self.assert_handled_result(
                result, exit_code=4, status="HOLD", diagnostic="RUNTIME-001"
            )
            self.assertEqual(b"preserve exactly\n", sentinel.read_bytes())

    def test_git_symlink_is_runtime_hold(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            workspace, receipt_path, _ = self.make_fixture(root)
            target = root / "external git"
            target.mkdir()
            (workspace / ".git").symlink_to(target, target_is_directory=True)

            result = self.run_checker(workspace, receipt_path)

            self.assert_handled_result(
                result, exit_code=4, status="HOLD", diagnostic="RUNTIME-001"
            )

    def test_unrelated_root_entry_is_repo_hold(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            workspace, receipt_path, _ = self.make_fixture(Path(temporary))
            (workspace / "unrelated.txt").write_text("preserve\n", encoding="utf-8")

            result = self.run_checker(workspace, receipt_path)

            self.assert_handled_result(
                result, exit_code=4, status="HOLD", diagnostic="REPO-001"
            )

    def test_handoff_phase_revalidates_installed_inputs_and_reports_product_additions(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            workspace, receipt_path, receipt = self.make_fixture(root)
            runtime = workspace / ".codex"
            runtime.mkdir(mode=0o555)
            runtime.chmod(0o555)
            baseline, initial = self.retain_prewrite_result(workspace, receipt_path)
            (workspace / "README.md").write_text("# Product\n", encoding="utf-8")
            source = workspace / "src"
            source.mkdir()
            (source / "app.js").write_text("export const ready = true;\n", encoding="utf-8")

            result = self.run_checker(
                workspace,
                receipt_path,
                "--phase",
                "handoff",
                "--baseline-result",
                str(baseline),
            )

            payload = self.assert_handled_result(
                result, exit_code=0, status="PASS", diagnostic=None
            )
            paths = [record["path"] for record in payload["product_inventory"]]
            self.assertEqual(
                [
                    ".agents",
                    ".agents/skills",
                    ".agents/skills/clone-software",
                    "MINECRAFT_CLONE_PROMPT.md",
                    "README.md",
                    "docs",
                    "docs/clone",
                    "docs/clone/evidence",
                    "docs/clone/evidence/raw",
                    "docs/clone/evidence/raw/workspace-check",
                    "docs/clone/evidence/raw/workspace-check/pre-write.json",
                    "src",
                    "src/app.js",
                ],
                paths,
            )
            for installed in receipt["installed_workspace_inventory"]:
                self.assertIn(installed, payload["product_inventory"])
            self.assertEqual(initial["runtime_exclusions"], payload["runtime_exclusions"])

    def test_handoff_phase_rejects_changed_or_extended_installer_inputs(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            workspace, receipt_path, _ = self.make_fixture(root)
            baseline, _ = self.retain_prewrite_result(workspace, receipt_path)
            (workspace / "MINECRAFT_CLONE_PROMPT.md").write_text(
                "changed\n", encoding="utf-8"
            )

            changed = self.run_checker(
                workspace,
                receipt_path,
                "--phase",
                "handoff",
                "--baseline-result",
                str(baseline),
            )

            self.assert_handled_result(
                changed, exit_code=4, status="HOLD", diagnostic="RUNTIME-001"
            )

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            workspace, receipt_path, _ = self.make_fixture(root)
            baseline, _ = self.retain_prewrite_result(workspace, receipt_path)
            (workspace / ".agents" / "unexpected.txt").write_text(
                "not product\n", encoding="utf-8"
            )

            extended = self.run_checker(
                workspace,
                receipt_path,
                "--phase",
                "handoff",
                "--baseline-result",
                str(baseline),
            )

            self.assert_handled_result(
                extended, exit_code=4, status="HOLD", diagnostic="RUNTIME-001"
            )

    def test_handoff_rejects_changed_repository_scoped_skill_target_bytes(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            workspace, receipt_path, _ = self.make_fixture(root)
            baseline, _ = self.retain_prewrite_result(workspace, receipt_path)
            project = workspace.parent / "clone-software"
            (project / "SKILL.md").write_text(
                "injected repository instructions\n", encoding="utf-8"
            )

            result = self.run_checker(
                workspace,
                receipt_path,
                "--phase",
                "handoff",
                "--baseline-result",
                str(baseline),
            )

            self.assert_handled_result(
                result, exit_code=4, status="HOLD", diagnostic="RUNTIME-001"
            )

    @unittest.skipUnless(hasattr(os, "symlink"), "symlinks are unavailable")
    def test_handoff_rejects_checkout_symlink_without_reading_its_target(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            workspace, receipt_path, _ = self.make_fixture(root)
            baseline, _ = self.retain_prewrite_result(workspace, receipt_path)
            secret = root / "external-instructions"
            secret.write_text("must not be observed\n", encoding="utf-8")
            project = workspace.parent / "clone-software"
            (project / "SKILL.md").symlink_to(secret)

            result = self.run_checker(
                workspace,
                receipt_path,
                "--phase",
                "handoff",
                "--baseline-result",
                str(baseline),
            )

            self.assert_handled_result(
                result, exit_code=4, status="HOLD", diagnostic="RUNTIME-001"
            )
            self.assertNotIn("must not be observed", result.stdout + result.stderr)
            self.assertEqual("must not be observed\n", secret.read_text(encoding="utf-8"))

    @unittest.skipUnless(hasattr(os, "link"), "hard links are unavailable")
    def test_handoff_rejects_hardlinked_checkout_file_even_when_digest_matches(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            workspace, receipt_path, receipt = self.make_fixture(root)
            project = workspace.parent / "clone-software"
            governed = project / "SKILL.md"
            governed.write_bytes(b"governed skill bytes\n")
            receipt["checkout_identity_sha256"] = reference_checkout_identity(project)
            self.write_receipt(receipt_path, receipt)
            baseline, _ = self.retain_prewrite_result(workspace, receipt_path)

            external = root / "external-skill-bytes"
            external.write_bytes(governed.read_bytes())
            external.chmod(stat.S_IMODE(governed.stat().st_mode))
            governed.unlink()
            os.link(external, governed)
            self.assertEqual(
                receipt["checkout_identity_sha256"],
                reference_checkout_identity(project),
                "the installer digest intentionally does not encode link count",
            )

            result = self.run_checker(
                workspace,
                receipt_path,
                "--phase",
                "handoff",
                "--baseline-result",
                str(baseline),
            )

            self.assert_handled_result(
                result, exit_code=4, status="HOLD", diagnostic="RUNTIME-001"
            )

    def test_checkout_identity_rejects_concurrent_file_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            project = root / "clone-software"
            project.mkdir()
            governed = project / "SKILL.md"
            governed.write_bytes(b"a" * (2 * 1024 * 1024))
            governed_inode = governed.stat().st_ino
            checker = self.load_checker()
            real_read = checker.os.read
            changed = False

            def changing_read(descriptor: int, size: int) -> bytes:
                nonlocal changed
                chunk = real_read(descriptor, size)
                if (
                    chunk
                    and not changed
                    and checker.os.fstat(descriptor).st_ino == governed_inode
                ):
                    changed = True
                    governed.write_bytes(b"changed during scan\n")
                return chunk

            with mock.patch.object(checker.os, "read", side_effect=changing_read):
                with self.assertRaises(checker.HoldError) as raised:
                    checker._checkout_identity(project)

            self.assertTrue(changed)
            self.assertEqual("RUNTIME-001", raised.exception.diagnostic)

    def test_handoff_phase_requires_baseline_and_rejects_runtime_identity_replacement(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            workspace, receipt_path, _ = self.make_fixture(root)
            missing = self.run_checker(workspace, receipt_path, "--phase", "handoff")
            self.assertEqual(2, missing.returncode)
            self.assertEqual("", missing.stdout)

            runtime = workspace / ".codex"
            runtime.mkdir(mode=0o555)
            runtime.chmod(0o555)
            baseline, _ = self.retain_prewrite_result(workspace, receipt_path)
            runtime.chmod(0o755)
            runtime.rename(root / "original-codex-runtime")
            runtime.mkdir(mode=0o555)
            runtime.chmod(0o555)

            replaced = self.run_checker(
                workspace,
                receipt_path,
                "--phase",
                "handoff",
                "--baseline-result",
                str(baseline),
            )

            self.assert_handled_result(
                replaced, exit_code=4, status="HOLD", diagnostic="RUNTIME-001"
            )

    def test_handoff_baseline_path_is_exact_and_ancestor_symlinks_are_not_followed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            workspace, receipt_path, _ = self.make_fixture(root)
            baseline, _ = self.retain_prewrite_result(workspace, receipt_path)
            alternate = root / "alternate.json"
            alternate.write_bytes(baseline.read_bytes())

            wrong_path = self.run_checker(
                workspace,
                receipt_path,
                "--phase",
                "handoff",
                "--baseline-result",
                str(alternate),
            )

            self.assertEqual(2, wrong_path.returncode)
            self.assertEqual("", wrong_path.stdout)

            real_docs = root / "retained-docs"
            (workspace / "docs").rename(real_docs)
            (workspace / "docs").symlink_to(real_docs, target_is_directory=True)
            before = baseline.read_bytes()

            symlinked = self.run_checker(
                workspace,
                receipt_path,
                "--phase",
                "handoff",
                "--baseline-result",
                str(baseline),
            )

            self.assert_handled_result(
                symlinked, exit_code=4, status="HOLD", diagnostic="RUNTIME-001"
            )
            self.assertEqual(before, baseline.read_bytes())

    def test_phase_option_is_exact(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            workspace, receipt_path, _ = self.make_fixture(Path(temporary))
            result = self.run_checker(workspace, receipt_path, "--phase", "later")
            self.assertEqual(2, result.returncode)
            self.assertEqual("", result.stdout)

    def test_checker_does_not_modify_the_installation_tree(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            workspace, receipt_path, _ = self.make_fixture(root)
            runtime = workspace / ".codex"
            runtime.mkdir(mode=0o555)
            runtime.chmod(0o555)
            before = self.snapshot_tree(root)

            result = self.run_checker(workspace, receipt_path)

            self.assert_handled_result(
                result, exit_code=0, status="PASS", diagnostic=None
            )
            self.assertEqual(before, self.snapshot_tree(root))

    def test_runtime_identity_is_rechecked_before_pass(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            workspace, receipt_path, _ = self.make_fixture(Path(temporary))
            runtime = workspace / ".codex"
            runtime.mkdir(mode=0o555)
            runtime.chmod(0o555)
            runtime_absolute = str(runtime.resolve())
            checker = self.load_checker()
            real_lstat = checker.os.lstat
            runtime_calls = 0

            def changing_lstat(path, *args, **kwargs):
                nonlocal runtime_calls
                observed = real_lstat(path, *args, **kwargs)
                if os.path.abspath(os.fspath(path)) == runtime_absolute:
                    runtime_calls += 1
                    if runtime_calls > 1:
                        fields = list(observed)
                        fields[1] += 1
                        return os.stat_result(fields)
                return observed

            stdout = io.StringIO()
            stderr = io.StringIO()
            arguments = self.checker_arguments(workspace, receipt_path)[2:]
            with mock.patch.object(checker.os, "lstat", side_effect=changing_lstat):
                with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                    exit_code = checker.main(arguments)

            self.assertGreaterEqual(runtime_calls, 2)
            self.assertEqual(4, exit_code)
            payload = json.loads(stdout.getvalue())
            self.assertEqual("HOLD", payload["status"])
            self.assertEqual("RUNTIME-001", payload["diagnostic"])
            self.assertIn("RUNTIME-001", stderr.getvalue())

    def test_receipt_identity_and_bytes_are_rechecked_before_pass(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            workspace, receipt_path, receipt = self.make_fixture(Path(temporary))
            checker = self.load_checker()
            real_scan = checker._scan_inventory
            scan_calls = 0

            def changing_scan(path):
                nonlocal scan_calls
                result = real_scan(path)
                scan_calls += 1
                if scan_calls == 1:
                    receipt["source_url"] = "https://forged.example.invalid/replaced.git"
                    self.write_receipt(receipt_path, receipt)
                return result

            stdout = io.StringIO()
            stderr = io.StringIO()
            arguments = self.checker_arguments(workspace, receipt_path)[2:]
            with mock.patch.object(checker, "_scan_inventory", side_effect=changing_scan):
                with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                    exit_code = checker.main(arguments)

            self.assertGreaterEqual(scan_calls, 2)
            self.assertEqual(4, exit_code)
            payload = json.loads(stdout.getvalue())
            self.assertEqual("HOLD", payload["status"])
            self.assertEqual("RUNTIME-001", payload["diagnostic"])
            self.assertIn("RUNTIME-001", stderr.getvalue())

    @unittest.skipUnless(hasattr(os, "symlink"), "symlinks are unavailable")
    def test_receipt_symlink_loop_is_a_canonical_runtime_hold(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            workspace, receipt_path, _ = self.make_fixture(Path(temporary))
            receipt_path.unlink()
            receipt_path.symlink_to(receipt_path.name)

            result = self.run_checker(workspace, receipt_path)

            self.assert_handled_result(
                result, exit_code=4, status="HOLD", diagnostic="RUNTIME-001"
            )
            self.assertNotIn("Traceback", result.stderr)

    @unittest.skipUnless(os.name == "posix", "byte-named filesystem entries require POSIX")
    def test_non_utf8_workspace_name_is_a_canonical_runtime_hold(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            workspace, receipt_path, _ = self.make_fixture(Path(temporary))
            hostile = os.path.join(os.fsencode(workspace / ".agents"), b"hostile-\xff")
            descriptor = os.open(hostile, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            os.close(descriptor)

            result = self.run_checker(workspace, receipt_path)

            self.assert_handled_result(
                result, exit_code=4, status="HOLD", diagnostic="RUNTIME-001"
            )
            self.assertNotIn("INTERNAL_ERROR", result.stdout + result.stderr)

    def test_runtime_option_and_authority_are_exact_usage_contracts(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            workspace, receipt_path, _ = self.make_fixture(Path(temporary))
            arguments = self.checker_arguments(workspace, receipt_path)
            arguments[arguments.index(".codex")] = ".other"
            bad_path = subprocess.run(arguments, capture_output=True, text=True, timeout=15)
            self.assertEqual(2, bad_path.returncode)
            self.assertEqual("", bad_path.stdout)

            arguments = self.checker_arguments(workspace, receipt_path)
            arguments[arguments.index("DEC-004")] = "DEC-999"
            bad_authority = subprocess.run(
                arguments, capture_output=True, text=True, timeout=15
            )
            self.assertEqual(2, bad_authority.returncode)
            self.assertEqual("", bad_authority.stdout)

    def test_unexpected_failure_is_canonical_error_without_exception_text(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            workspace, receipt_path, _ = self.make_fixture(Path(temporary))
            checker = self.load_checker()
            stdout = io.StringIO()
            stderr = io.StringIO()
            arguments = self.checker_arguments(workspace, receipt_path)[2:]

            with mock.patch.object(
                checker,
                "_run_check",
                side_effect=RuntimeError("sensitive internal detail"),
            ):
                with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                    exit_code = checker.main(arguments)

            self.assertEqual(70, exit_code)
            payload = json.loads(stdout.getvalue())
            self.assertEqual("ERROR", payload["status"])
            self.assertEqual("INTERNAL_ERROR", payload["diagnostic"])
            self.assertEqual(
                json.dumps(
                    payload,
                    ensure_ascii=False,
                    sort_keys=True,
                    separators=(",", ":"),
                )
                + "\n",
                stdout.getvalue(),
            )
            self.assertIn("INTERNAL_ERROR", stderr.getvalue())
            self.assertNotIn("sensitive internal detail", stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
