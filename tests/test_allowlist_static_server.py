from __future__ import annotations

import contextlib
import importlib.util
import io
import json
import os
import selectors
import shutil
import socket
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "assets" / "scaffolds" / "static-web-esm-allowlist"
SERVER_RELATIVE = Path("tools/serve_static.py")
READY_SCHEMA = "allowlisted-static-server-ready/v1"
MANIFEST_SCHEMA = "allowlisted-static-server-manifest/v1"
SECRET = b"DO-NOT-LEAK-ALLOWLIST-SECRET\n"


def canonical_json_line(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"


class AllowlistStaticServerTests(unittest.TestCase):
    maxDiff = None

    def setUp(self) -> None:
        self.assertTrue((TEMPLATE / SERVER_RELATIVE).is_file(), "allowlist server template is missing")
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name) / "site"
        shutil.copytree(TEMPLATE, self.root)
        self.processes: list[subprocess.Popen[str]] = []
        self.addCleanup(self._stop_processes)

    def _stop_processes(self) -> None:
        for process in reversed(self.processes):
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=3)
            if process.stdout is not None:
                process.stdout.close()
            if process.stderr is not None:
                process.stderr.close()

    def _start(self, manifest: str = "serve_manifest.json") -> tuple[subprocess.Popen[str], dict[str, Any], str]:
        process = subprocess.Popen(
            [
                sys.executable,
                str(SERVER_RELATIVE),
                "--manifest",
                manifest,
                "--bind",
                "127.0.0.1",
                "--port",
                "0",
            ],
            cwd=self.root,
            text=True,
            encoding="utf-8",
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        self.processes.append(process)
        assert process.stdout is not None
        selector = selectors.DefaultSelector()
        selector.register(process.stdout, selectors.EVENT_READ)
        events = selector.select(timeout=5)
        selector.close()
        if not events:
            stderr = process.stderr.read() if process.poll() is not None and process.stderr else ""
            self.fail(f"server did not emit readiness; exit={process.poll()} stderr={stderr!r}")
        ready_line = process.stdout.readline()
        ready = json.loads(ready_line)
        self.assertEqual(
            set(ready),
            {"bind", "event", "port", "schema_version"},
        )
        self.assertEqual(ready["schema_version"], READY_SCHEMA)
        self.assertEqual(ready["event"], "ready")
        self.assertEqual(ready["bind"], "127.0.0.1")
        self.assertIsInstance(ready["port"], int)
        self.assertGreater(ready["port"], 0)
        self.assertEqual(ready_line, canonical_json_line(ready))
        return process, ready, ready_line

    def _raw_request(
        self,
        port: int,
        target: str,
        *,
        method: str = "GET",
    ) -> tuple[int, dict[str, str], bytes]:
        request = (
            f"{method} {target} HTTP/1.1\r\n"
            f"Host: 127.0.0.1:{port}\r\n"
            "Connection: close\r\n"
            "\r\n"
        ).encode("ascii")
        return self._raw_bytes(port, request)

    def _raw_bytes(
        self,
        port: int,
        request: bytes,
    ) -> tuple[int, dict[str, str], bytes]:
        with socket.create_connection(("127.0.0.1", port), timeout=3) as connection:
            connection.sendall(request)
            chunks: list[bytes] = []
            while True:
                try:
                    chunk = connection.recv(65536)
                except ConnectionResetError:
                    # An oversized parser-level request can leave unread input
                    # when the server closes its one-response connection.  Linux
                    # may report that close as a reset after delivering the
                    # complete HTTP response.  Retain and validate those bytes;
                    # the framing assertions below still reject a missing or
                    # partial response and any non-empty response body.
                    break
                if not chunk:
                    break
                chunks.append(chunk)
        response = b"".join(chunks)
        head, separator, body = response.partition(b"\r\n\r\n")
        self.assertEqual(separator, b"\r\n\r\n", response)
        lines = head.decode("iso-8859-1").split("\r\n")
        status = int(lines[0].split(" ", 2)[1])
        headers = {
            name.strip().lower(): value.strip()
            for name, value in (line.split(":", 1) for line in lines[1:] if ":" in line)
        }
        return status, headers, body

    def _load_server(self):
        server_path = self.root / SERVER_RELATIVE
        spec = importlib.util.spec_from_file_location("allowlist_static_server", server_path)
        self.assertIsNotNone(spec)
        self.assertIsNotNone(spec.loader)
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        try:
            spec.loader.exec_module(module)
        finally:
            sys.modules.pop(spec.name, None)
        return module

    def _write_manifest(self, value: object, name: str = "custom_manifest.json") -> str:
        (self.root / name).write_text(canonical_json_line(value), encoding="utf-8", newline="\n")
        return name

    def _run_invalid_manifest(self, content: str, name: str = "invalid_manifest.json") -> subprocess.CompletedProcess[str]:
        (self.root / name).write_text(content, encoding="utf-8", newline="\n")
        return self._run_manifest_path(name)

    def _run_manifest_path(self, name: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [
                sys.executable,
                str(SERVER_RELATIVE),
                "--manifest",
                name,
                "--bind",
                "127.0.0.1",
                "--port",
                "0",
            ],
            cwd=self.root,
            text=True,
            encoding="utf-8",
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=5,
            check=False,
        )

    def test_port_zero_ready_line_get_and_head_are_exact(self) -> None:
        _, ready, _ = self._start()
        expected = (self.root / "index.html").read_bytes()

        get_status, get_headers, get_body = self._raw_request(int(ready["port"]), "/")
        head_status, head_headers, head_body = self._raw_request(
            int(ready["port"]), "/", method="HEAD"
        )

        self.assertEqual(get_status, 200)
        self.assertEqual(get_body, expected)
        self.assertEqual(get_headers["content-length"], str(len(expected)))
        self.assertEqual(get_headers["content-type"], "text/html; charset=utf-8")
        self.assertEqual(get_headers["x-content-type-options"], "nosniff")
        self.assertEqual(head_status, get_status)
        self.assertEqual(head_headers, get_headers)
        self.assertEqual(head_body, b"")

    def test_only_manifest_routes_and_get_head_methods_are_served(self) -> None:
        (self.root / "undeclared.txt").write_bytes(SECRET)
        _, ready, _ = self._start()
        port = int(ready["port"])

        for target in ("/index.html", "/src", "/src/", "/undeclared.txt"):
            with self.subTest(target=target):
                status, headers, body = self._raw_request(port, target)
                self.assertIn(status, {400, 404})
                self.assertNotIn("location", headers)
                self.assertEqual(body, b"")
                self.assertNotIn(SECRET, body)

        for method in ("POST", "OPTIONS", "BREW"):
            with self.subTest(method=method):
                status, headers, body = self._raw_request(port, "/", method=method)
                self.assertEqual(status, 405)
                self.assertEqual(headers["allow"], "GET, HEAD")
                self.assertEqual(body, b"")

    def test_ambiguous_and_traversal_request_targets_are_denied_without_bytes(self) -> None:
        (self.root / "secret.txt").write_bytes(SECRET)
        _, ready, _ = self._start()
        port = int(ready["port"])
        targets = (
            "/?",
            "/?query=1",
            "/#fragment",
            "//styles.css",
            "/src//app.js",
            "/./styles.css",
            "/../secret.txt",
            "/%2e%2e/secret.txt",
            "/%252e%252e/secret.txt",
            "/%2fsecret.txt",
            "/%5csecret.txt",
            "/.hidden",
            "/%2ehidden",
            "/bad%",
            "/bad%2",
            "http://127.0.0.1/secret.txt",
        )

        for target in targets:
            with self.subTest(target=target):
                status, headers, body = self._raw_request(port, target)
                self.assertIn(status, {400, 404})
                self.assertNotIn("location", headers)
                self.assertEqual(body, b"")
                self.assertNotIn(SECRET, body)

        status, _, body = self._raw_request(port, "/../secret.txt", method="HEAD")
        self.assertIn(status, {400, 404})
        self.assertEqual(body, b"")

    def test_parser_level_errors_are_zero_body_for_get_head_and_malformed_lines(self) -> None:
        _, ready, _ = self._start()
        port = int(ready["port"])
        requests = (
            b"GET /" + (b"a" * 70_000) + b" HTTP/1.1\r\nHost: localhost\r\n\r\n",
            b"HEAD /" + (b"a" * 70_000) + b" HTTP/1.1\r\nHost: localhost\r\n\r\n",
            b"GET / HTTP/1.1\r\nHost: localhost\r\nX-Long: "
            + (b"a" * 70_000)
            + b"\r\n\r\n",
        )

        for request in requests:
            with self.subTest(prefix=request[:8]):
                status, headers, body = self._raw_bytes(port, request)
                self.assertIn(status, {400, 414, 431})
                self.assertEqual("0", headers["content-length"])
                self.assertEqual(body, b"")

    def test_raw_client_retains_complete_response_before_reset_and_rejects_partial(self) -> None:
        response = (
            b"HTTP/1.1 431 Request Header Fields Too Large\r\n"
            b"Content-Length: 0\r\nConnection: close\r\n\r\n"
        )
        connection = mock.MagicMock()
        connection.__enter__.return_value = connection
        connection.recv.side_effect = [response, ConnectionResetError()]

        with mock.patch.object(socket, "create_connection", return_value=connection):
            status, headers, body = self._raw_bytes(80, b"oversized request")

        self.assertEqual(status, 431)
        self.assertEqual(headers["content-length"], "0")
        self.assertEqual(body, b"")

        connection.recv.side_effect = [response[:-1], ConnectionResetError()]
        with mock.patch.object(socket, "create_connection", return_value=connection):
            with self.assertRaises(AssertionError):
                self._raw_bytes(80, b"oversized request")

    def test_missing_secure_open_capability_fails_before_server_start(self) -> None:
        server = self._load_server()
        stdout = io.StringIO()
        stderr = io.StringIO()

        with mock.patch.object(server, "SECURE_OPEN_AVAILABLE", False):
            with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                result = server.main(
                    [
                        "--manifest",
                        "serve_manifest.json",
                        "--bind",
                        "127.0.0.1",
                        "--port",
                        "0",
                    ]
                )

        self.assertEqual(2, result)
        self.assertEqual("", stdout.getvalue())
        self.assertIn("MANIFEST_INVALID", stderr.getvalue())
        self.assertIn("secure open capabilities", stderr.getvalue())

    @unittest.skipUnless(hasattr(os, "symlink"), "symlinks are unavailable")
    def test_symlink_target_and_ancestor_are_rejected_during_manifest_validation(self) -> None:
        (self.root / "secret.txt").write_bytes(SECRET)
        os.symlink("secret.txt", self.root / "linked.txt")
        target_manifest = {
            "schema_version": MANIFEST_SCHEMA,
            "routes": {"/linked": "linked.txt"},
        }
        target_result = self._run_invalid_manifest(canonical_json_line(target_manifest), "target.json")

        outside = self.root / "outside"
        outside.mkdir()
        (outside / "secret.txt").write_bytes(SECRET)
        os.symlink("outside", self.root / "linked-dir", target_is_directory=True)
        ancestor_manifest = {
            "schema_version": MANIFEST_SCHEMA,
            "routes": {"/linked": "linked-dir/secret.txt"},
        }
        ancestor_result = self._run_invalid_manifest(canonical_json_line(ancestor_manifest), "ancestor.json")

        for result in (target_result, ancestor_result):
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(result.stdout, "")
            self.assertIn("MANIFEST_INVALID", result.stderr)
            self.assertNotIn(SECRET.decode().strip(), result.stderr)

    @unittest.skipUnless(hasattr(os, "symlink"), "symlinks are unavailable")
    def test_manifest_path_and_ancestor_symlinks_are_rejected(self) -> None:
        os.symlink("serve_manifest.json", self.root / "linked-manifest.json")
        linked_manifest_result = self._run_manifest_path("linked-manifest.json")

        manifest_directory = self.root / "manifest-directory"
        manifest_directory.mkdir()
        shutil.copy2(self.root / "serve_manifest.json", manifest_directory / "manifest.json")
        os.symlink(
            "manifest-directory",
            self.root / "linked-manifest-directory",
            target_is_directory=True,
        )
        linked_ancestor_result = self._run_manifest_path(
            "linked-manifest-directory/manifest.json"
        )

        for result in (linked_manifest_result, linked_ancestor_result):
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(result.stdout, "")
            self.assertIn("MANIFEST_INVALID", result.stderr)

    @unittest.skipUnless(hasattr(os, "symlink"), "symlinks are unavailable")
    def test_post_start_symlink_swap_is_denied_without_target_bytes(self) -> None:
        (self.root / "secret.txt").write_bytes(SECRET)
        _, ready, _ = self._start()
        (self.root / "index.html").unlink()
        os.symlink("secret.txt", self.root / "index.html")

        status, _, body = self._raw_request(int(ready["port"]), "/")

        self.assertEqual(status, 404)
        self.assertEqual(body, b"")
        self.assertNotIn(SECRET, body)

    @unittest.skipUnless(hasattr(os, "mkfifo"), "FIFOs are unavailable")
    def test_non_regular_manifest_target_is_rejected(self) -> None:
        fifo = self.root / "stream"
        os.mkfifo(fifo)
        self.addCleanup(lambda: fifo.unlink(missing_ok=True))
        manifest = {
            "schema_version": MANIFEST_SCHEMA,
            "routes": {"/stream": "stream"},
        }

        result = self._run_invalid_manifest(canonical_json_line(manifest))

        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(result.stdout, "")
        self.assertIn("MANIFEST_INVALID", result.stderr)

    def test_manifest_schema_routes_and_duplicate_keys_are_strict(self) -> None:
        invalid_manifests = (
            {},
            {"schema_version": "wrong", "routes": {"/": "index.html"}},
            {"schema_version": MANIFEST_SCHEMA, "routes": {}},
            {"schema_version": MANIFEST_SCHEMA, "routes": {"/?q=1": "index.html"}},
            {"schema_version": MANIFEST_SCHEMA, "routes": {"/.hidden": "index.html"}},
            {"schema_version": MANIFEST_SCHEMA, "routes": {"/": "../index.html"}},
            {
                "schema_version": MANIFEST_SCHEMA,
                "routes": {"/": "index.html"},
                "unexpected": True,
            },
        )
        for position, manifest in enumerate(invalid_manifests):
            with self.subTest(position=position):
                result = self._run_invalid_manifest(
                    canonical_json_line(manifest), f"invalid-{position}.json"
                )
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(result.stdout, "")
                self.assertIn("MANIFEST_INVALID", result.stderr)

        duplicate = (
            '{"routes":{"/":"index.html","/":"styles.css"},'
            f'"schema_version":"{MANIFEST_SCHEMA}"}}\n'
        )
        result = self._run_invalid_manifest(duplicate, "duplicate.json")
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(result.stdout, "")
        self.assertIn("MANIFEST_INVALID", result.stderr)


if __name__ == "__main__":
    unittest.main()
