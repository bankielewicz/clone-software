#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import stat
import sys
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any


MANIFEST_SCHEMA = "allowlisted-static-server-manifest/v1"
READY_SCHEMA = "allowlisted-static-server-ready/v1"
MAX_MANIFEST_BYTES = 1024 * 1024
CONTENT_TYPES = {
    ".css": "text/css; charset=utf-8",
    ".html": "text/html; charset=utf-8",
    ".js": "text/javascript; charset=utf-8",
}
HEX_DIGITS = frozenset("0123456789abcdefABCDEF")
NOFOLLOW = getattr(os, "O_NOFOLLOW", 0)
NONBLOCK = getattr(os, "O_NONBLOCK", 0)
DIRECTORY = getattr(os, "O_DIRECTORY", 0)
SECURE_OPEN_AVAILABLE = (
    all(hasattr(os, name) for name in ("O_NOFOLLOW", "O_NONBLOCK", "O_DIRECTORY"))
    and all(function in os.supports_dir_fd for function in (os.open, os.stat, os.readlink))
    and os.scandir in os.supports_fd
)


class ContractError(Exception):
    pass


def require_secure_open_capabilities() -> None:
    if not SECURE_OPEN_AVAILABLE:
        raise ContractError("required secure open capabilities are unavailable")


def canonical_json_line(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key, item in pairs:
        if key in value:
            raise ContractError(f"duplicate JSON key: {key}")
        value[key] = item
    return value


def _identity(metadata: os.stat_result) -> tuple[int, int, int, int, int, int]:
    return (
        metadata.st_dev,
        metadata.st_ino,
        metadata.st_mode,
        metadata.st_size,
        metadata.st_mtime_ns,
        metadata.st_ctime_ns,
    )


def _relative_parts(value: object, *, role: str) -> tuple[str, ...]:
    if not isinstance(value, str) or not value or "\\" in value or "\x00" in value:
        raise ContractError(f"{role} must be a non-empty POSIX relative path")
    if value.startswith("/") or value.endswith("/"):
        raise ContractError(f"{role} must be a non-empty POSIX relative path")
    parts = tuple(value.split("/"))
    if any(not part or part in {".", ".."} or part.startswith(".") for part in parts):
        raise ContractError(f"{role} contains an unsafe path segment")
    return parts


def _open_regular(root_descriptor: int, parts: tuple[str, ...], *, role: str) -> tuple[int, os.stat_result]:
    directory_descriptor = os.dup(root_descriptor)
    try:
        for part in parts[:-1]:
            before = os.stat(part, dir_fd=directory_descriptor, follow_symlinks=False)
            if not stat.S_ISDIR(before.st_mode):
                raise ContractError(f"{role} has a non-directory or symlink ancestor")
            next_descriptor = os.open(
                part,
                os.O_RDONLY | DIRECTORY | NOFOLLOW,
                dir_fd=directory_descriptor,
            )
            after = os.fstat(next_descriptor)
            if not stat.S_ISDIR(after.st_mode) or _identity(before) != _identity(after):
                os.close(next_descriptor)
                raise ContractError(f"{role} has a changed or symlinked ancestor")
            os.close(directory_descriptor)
            directory_descriptor = next_descriptor

        before = os.stat(parts[-1], dir_fd=directory_descriptor, follow_symlinks=False)
        if not stat.S_ISREG(before.st_mode):
            raise ContractError(f"{role} must be a regular non-symlink file")
        descriptor = os.open(
            parts[-1],
            os.O_RDONLY | NONBLOCK | NOFOLLOW,
            dir_fd=directory_descriptor,
        )
        after = os.fstat(descriptor)
        if not stat.S_ISREG(after.st_mode) or _identity(before) != _identity(after):
            os.close(descriptor)
            raise ContractError(f"{role} changed while it was opened")
        return descriptor, after
    except (OSError, ValueError) as exc:
        raise ContractError(f"{role} is unavailable or unsafe") from exc
    finally:
        os.close(directory_descriptor)


def _read_regular(
    root_descriptor: int,
    parts: tuple[str, ...],
    *,
    role: str,
    maximum_bytes: int | None = None,
) -> bytes:
    descriptor, before = _open_regular(root_descriptor, parts, role=role)
    try:
        with os.fdopen(descriptor, "rb", closefd=False) as handle:
            value = handle.read(-1 if maximum_bytes is None else maximum_bytes + 1)
        after = os.fstat(descriptor)
    except OSError as exc:
        raise ContractError(f"{role} could not be read") from exc
    finally:
        os.close(descriptor)
    if maximum_bytes is not None and len(value) > maximum_bytes:
        raise ContractError(f"{role} exceeds the maximum size")
    if _identity(before) != _identity(after):
        raise ContractError(f"{role} changed while it was read")
    return value


def _request_route(raw_target: str) -> str:
    if (
        not raw_target.startswith("/")
        or raw_target.startswith("//")
        or "?" in raw_target
        or "#" in raw_target
        or "\\" in raw_target
        or any(ord(character) < 0x20 or ord(character) > 0x7E for character in raw_target)
    ):
        raise ContractError("request target is not an unambiguous origin-form path")

    position = 0
    while position < len(raw_target):
        if raw_target[position] != "%":
            position += 1
            continue
        if (
            position + 2 >= len(raw_target)
            or raw_target[position + 1] not in HEX_DIGITS
            or raw_target[position + 2] not in HEX_DIGITS
        ):
            raise ContractError("request target contains a malformed escape")
        escaped = raw_target[position + 1 : position + 3].lower()
        if escaped in {"2f", "5c"}:
            raise ContractError("request target contains an encoded separator")
        position += 3

    try:
        decoded = urllib.parse.unquote_to_bytes(raw_target).decode("utf-8", errors="strict")
    except UnicodeError as exc:
        raise ContractError("request target is not canonical UTF-8") from exc
    if (
        "%" in decoded
        or "?" in decoded
        or "#" in decoded
        or "\\" in decoded
        or "\x00" in decoded
        or any(ord(character) < 0x20 or ord(character) == 0x7F for character in decoded)
    ):
        raise ContractError("request target remains ambiguous after decoding")
    if decoded == "/":
        return decoded
    segments = decoded[1:].split("/")
    if any(not segment or segment in {".", ".."} or segment.startswith(".") for segment in segments):
        raise ContractError("request target contains a forbidden segment")
    return decoded


def _content_type(parts: tuple[str, ...]) -> str:
    name = parts[-1]
    suffix = name[name.rfind(".") :] if "." in name else ""
    try:
        return CONTENT_TYPES[suffix]
    except KeyError as exc:
        raise ContractError("manifest file has an unsupported media type") from exc


def load_manifest(root_descriptor: int, manifest_value: str) -> dict[str, tuple[tuple[str, ...], str]]:
    manifest_parts = _relative_parts(manifest_value, role="manifest path")
    raw = _read_regular(
        root_descriptor,
        manifest_parts,
        role="manifest",
        maximum_bytes=MAX_MANIFEST_BYTES,
    )
    try:
        text = raw.decode("utf-8", errors="strict")
        manifest = json.loads(text, object_pairs_hook=_unique_object)
    except (UnicodeError, json.JSONDecodeError, ContractError) as exc:
        raise ContractError("manifest must be unique-key UTF-8 JSON") from exc
    if not isinstance(manifest, dict) or set(manifest) != {"schema_version", "routes"}:
        raise ContractError("manifest must contain exactly schema_version and routes")
    if manifest["schema_version"] != MANIFEST_SCHEMA:
        raise ContractError("manifest schema_version is unsupported")
    routes = manifest["routes"]
    if not isinstance(routes, dict) or not routes:
        raise ContractError("manifest routes must be a non-empty object")

    retained: dict[str, tuple[tuple[str, ...], str]] = {}
    file_paths: set[tuple[str, ...]] = set()
    for route, file_value in routes.items():
        if not isinstance(route, str) or "%" in route or _request_route(route) != route:
            raise ContractError("manifest route is not a canonical URL path")
        file_parts = _relative_parts(file_value, role=f"manifest route {route}")
        if file_parts in file_paths:
            raise ContractError("manifest routes must map to unique files")
        content_type = _content_type(file_parts)
        descriptor, _ = _open_regular(root_descriptor, file_parts, role=f"manifest route {route}")
        os.close(descriptor)
        retained[route] = (file_parts, content_type)
        file_paths.add(file_parts)
    return retained


class AllowlistServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(
        self,
        address: tuple[str, int],
        root_descriptor: int,
        routes: dict[str, tuple[tuple[str, ...], str]],
    ) -> None:
        self.root_descriptor = root_descriptor
        self.routes = routes
        super().__init__(address, AllowlistHandler)


class AllowlistHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    raw_request_target: str | None = None

    @property
    def allowlist_server(self) -> AllowlistServer:
        return self.server  # type: ignore[return-value]

    def log_message(self, format: str, *args: object) -> None:
        return

    def send_error(
        self,
        code: int,
        message: str | None = None,
        explain: str | None = None,
    ) -> None:
        self._deny(code)

    def parse_request(self) -> bool:
        request_words = self.raw_requestline.rstrip(b"\r\n").split()
        if len(request_words) >= 2:
            self.raw_request_target = request_words[1].decode("iso-8859-1")
        else:
            self.raw_request_target = None
        return super().parse_request()

    def _headers(self, status: int, length: int, content_type: str | None = None) -> None:
        self.send_response_only(status)
        if content_type is not None:
            self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(length))
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Connection", "close")
        self.end_headers()
        self.close_connection = True

    def _deny(self, status: int, *, allow: bool = False) -> None:
        self.send_response_only(status)
        if allow:
            self.send_header("Allow", "GET, HEAD")
        self.send_header("Content-Length", "0")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Connection", "close")
        self.end_headers()
        self.close_connection = True

    def _serve(self, *, head_only: bool) -> None:
        try:
            if self.raw_request_target is None:
                raise ContractError("request target is unavailable")
            route = _request_route(self.raw_request_target)
        except ContractError:
            self._deny(400)
            return
        target = self.allowlist_server.routes.get(route)
        if target is None:
            self._deny(404)
            return
        parts, content_type = target
        try:
            value = _read_regular(
                self.allowlist_server.root_descriptor,
                parts,
                role=f"route {route}",
            )
        except ContractError:
            self._deny(404)
            return
        self._headers(200, len(value), content_type)
        if not head_only:
            try:
                self.wfile.write(value)
            except (BrokenPipeError, ConnectionResetError):
                return

    def do_GET(self) -> None:
        self._serve(head_only=False)

    def do_HEAD(self) -> None:
        self._serve(head_only=True)

    def _method_not_allowed(self) -> None:
        self._deny(405, allow=True)

    do_CONNECT = _method_not_allowed
    do_DELETE = _method_not_allowed
    do_OPTIONS = _method_not_allowed
    do_PATCH = _method_not_allowed
    do_POST = _method_not_allowed
    do_PUT = _method_not_allowed
    do_TRACE = _method_not_allowed

    def __getattr__(self, name: str) -> Any:
        if name.startswith("do_"):
            return self._method_not_allowed
        raise AttributeError(name)


def _arguments(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Serve exact manifest-allowlisted static files.")
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--bind", required=True)
    parser.add_argument("--port", required=True, type=int)
    arguments = parser.parse_args(argv)
    if not 0 <= arguments.port <= 65535:
        parser.error("--port must be between 0 and 65535")
    return arguments


def main(argv: list[str] | None = None) -> int:
    arguments = _arguments(sys.argv[1:] if argv is None else argv)
    root_descriptor: int | None = None
    try:
        require_secure_open_capabilities()
        root_descriptor = os.open(".", os.O_RDONLY | DIRECTORY)
        routes = load_manifest(root_descriptor, arguments.manifest)
        server = AllowlistServer((arguments.bind, arguments.port), root_descriptor, routes)
    except (ContractError, OSError) as exc:
        if root_descriptor is not None:
            os.close(root_descriptor)
        print(f"MANIFEST_INVALID: {exc}", file=sys.stderr)
        return 2
    try:
        ready = {
            "schema_version": READY_SCHEMA,
            "event": "ready",
            "bind": str(server.server_address[0]),
            "port": int(server.server_address[1]),
        }
        print(canonical_json_line(ready), end="", flush=True)
        server.serve_forever(poll_interval=0.1)
    except KeyboardInterrupt:
        return 0
    finally:
        server.server_close()
        os.close(root_descriptor)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
