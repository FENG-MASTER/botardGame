"""Dependency-free HTTP JSON transport. Deploy behind a TLS reverse proxy."""

import argparse
import json
import logging
import os
import re
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs
from boardgame.core import GameError, require
from boardgame.platform import Platform
from boardgame.openapi import specification

MAX_BODY = 256 * 1024


class Handler(BaseHTTPRequestHandler):
    server_version = "BoardgameAPI/0.1"

    def setup(self):
        super().setup()
        self.connection.settimeout(30)

    def log_message(self, fmt, *args):
        # Do not log request URLs (query parameters can contain sensitive input).
        logging.info("%s %s", self.command, args[1] if len(args) > 1 else "")

    def body(self, object_only=True):
        require(
            not self.headers.get("Transfer-Encoding"),
            "Transfer-Encoding is unsupported",
            "invalid_request",
            400,
        )
        raw = self.headers.get("Content-Length", "0")
        require(raw.isdigit(), "Invalid Content-Length", "invalid_request", 400)
        size = int(raw)
        require(
            0 < size <= MAX_BODY,
            "JSON body must be between 1 and 262144 bytes",
            "invalid_request",
            413,
        )
        require(
            self.headers.get("Content-Type", "").split(";")[0] == "application/json",
            "Content-Type must be application/json",
            "invalid_request",
            415,
        )
        data = self.rfile.read(size)
        require(len(data) == size, "Incomplete request body", "invalid_request", 400)

        def pairs(items):
            result = {}
            for key, value in items:
                require(
                    key not in result, "Duplicate JSON property", "invalid_json", 400
                )
                result[key] = value
            return result

        try:
            body = json.loads(
                data,
                object_pairs_hook=pairs,
                parse_constant=lambda value: (_ for _ in ()).throw(ValueError(value)),
            )
        except (ValueError, UnicodeDecodeError, RecursionError):
            raise GameError("invalid_json", "Invalid JSON body", 400)
        require(
            not object_only or isinstance(body, dict),
            "JSON body must be an object",
            "invalid_request",
            400,
        )
        return body

    def send_json(self, status, value):
        data = json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        self.dispatch()

    def do_POST(self):
        self.dispatch()

    def do_DELETE(self):
        self.dispatch()

    def mcp_route(self):
        from boardgame.mcp import MCP, SUPPORTED_VERSIONS, rpc_error

        origin = self.headers.get("Origin")
        allowed = getattr(self.server, "mcp_allowed_origins", ())
        if origin is not None and origin not in allowed:
            return self.send_json(403, rpc_error(None, -32000, "Origin not allowed"))
        auth = self.headers.get("Authorization", "")
        try:
            identity = self.server.platform.authenticate(
                auth[7:] if auth.startswith("Bearer ") else ""
            )
        except GameError as e:
            return self.send_json(e.status, rpc_error(None, -32000, e.message))
        if self.command != "POST":
            self.send_response(405)
            self.send_header("Allow", "POST")
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        accept = self.headers.get("Accept", "")
        if "application/json" not in accept or "text/event-stream" not in accept:
            return self.send_json(
                406,
                rpc_error(
                    None,
                    -32000,
                    "Accept must include application/json and text/event-stream",
                ),
            )
        version = self.headers.get("MCP-Protocol-Version")
        if version is not None and version not in SUPPORTED_VERSIONS:
            return self.send_json(
                400, rpc_error(None, -32000, "Unsupported MCP-Protocol-Version")
            )
        try:
            message = self.body(object_only=False)
        except GameError as e:
            return self.send_json(
                e.status,
                rpc_error(
                    None, -32700 if e.code == "invalid_json" else -32600, e.message
                ),
            )
        try:
            result = MCP(self.server.platform).handle(identity, message)
        except Exception:
            logging.exception("MCP request failed")
            request_id = message.get("id") if isinstance(message, dict) else None
            result = rpc_error(request_id, -32603, "Internal server error")
        if result is None:
            self.send_response(202)
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        self.send_json(200, result)

    def dispatch(self):
        try:
            self.route()
        except GameError as e:
            self.send_json(
                e.status,
                dict(error=dict(code=e.code, message=e.message, details=e.details)),
            )
        except (BrokenPipeError, ConnectionResetError, TimeoutError):
            pass
        except Exception:
            logging.exception("Unhandled API failure")
            self.send_json(
                500,
                dict(
                    error=dict(code="internal_error", message="Internal server error")
                ),
            )

    def route(self):
        platform = self.server.platform
        url = urlparse(self.path)
        path = url.path.rstrip("/") or "/"
        method = self.command
        if path == "/mcp":
            return self.mcp_route()
        if method == "GET" and path == "/health":
            return self.send_json(200, dict(status="ok"))
        if method == "GET" and path == "/openapi.json":
            return self.send_json(200, specification())
        if method == "GET" and path == "/v1/games":
            return self.send_json(200, dict(games=platform.registry.describe()))
        if method == "GET" and path.startswith("/v1/games/"):
            return self.send_json(
                200, platform.registry.get(path.rsplit("/", 1)[-1]).descriptor()
            )
        if method == "POST" and path == "/v1/identities":
            if self.server.registration_key:
                import secrets

                require(
                    secrets.compare_digest(
                        self.headers.get("X-Registration-Key", ""),
                        self.server.registration_key,
                    ),
                    "Registration key required",
                    "forbidden",
                    403,
                )
            b = self.body()
            return self.send_json(201, platform.register(b.get("name"), b.get("kind"), b.get("invite_code"), require_invite=True))
        auth = self.headers.get("Authorization", "")
        me = platform.authenticate(auth[7:] if auth.startswith("Bearer ") else "")
        pid = me["id"]
        if path == "/v1/me" and method == "GET":
            return self.send_json(200, me)
        if path == "/v1/invitations":
            if method == "GET":
                return self.send_json(200, platform.invitations(pid))
            if method == "POST":
                return self.send_json(201, platform.create_invitation(pid))
            raise GameError("method_not_allowed", "Method not allowed", 405)
        invite_match = re.fullmatch(r"/v1/invitations/([a-f0-9]{32})/revoke", path)
        if invite_match and method == "POST":
            return self.send_json(200, platform.revoke_invitation(pid, invite_match[1]))
        if path == "/v1/rooms":
            if method == "GET":
                return self.send_json(200, dict(rooms=platform.list_rooms(pid)))
            require(method == "POST", "Method not allowed", "method_not_allowed", 405)
            b = self.body()
            return self.send_json(
                201,
                platform.create_room(
                    pid,
                    b.get("game"),
                    b.get("capacity"),
                    b.get("config"),
                    b.get("seed"),
                ),
            )
        match = re.fullmatch(
            r"/v1/rooms/([a-f0-9]{32})(?:/(join|start|actions|validate-action|events))?",
            path,
        )
        require(match is not None, "Endpoint not found", "not_found", 404)
        rid, operation = match.groups()
        if method == "GET":
            if operation is None:
                return self.send_json(200, platform.get(pid, rid))
            if operation == "actions":
                return self.send_json(200, platform.actions(pid, rid))
            if operation == "events":
                q = parse_qs(url.query)
                try:
                    after = int(
                        q.get("after", [self.headers.get("Last-Event-ID", "0")])[0]
                    )
                    wait = int(q.get("wait", ["0"])[0])
                except ValueError:
                    raise GameError(
                        "invalid_parameters", "after and wait must be integers", 422
                    )
                require(0 <= wait <= 25, "wait must be in [0,25]")
                deadline = time.monotonic() + wait
                while True:
                    result = platform.events(pid, rid, after)
                    if result["events"] or time.monotonic() >= deadline:
                        break
                    time.sleep(0.25)
                if "text/event-stream" in self.headers.get("Accept", ""):
                    self.send_response(200)
                    self.send_header("Content-Type", "text/event-stream")
                    self.send_header("Cache-Control", "no-store")
                    self.send_header("Connection", "close")
                    self.end_headers()
                    for event in result["events"]:
                        self.wfile.write(
                            f"id: {event['version']}\nevent: game\ndata: {json.dumps(event)}\n\n".encode()
                        )
                    if not result["events"]:
                        self.wfile.write(b": heartbeat\n\n")
                    self.wfile.flush()
                    self.close_connection = True
                    return
                return self.send_json(200, result)
        if method == "POST":
            b = self.body()
            if operation == "join":
                return self.send_json(200, platform.join(pid, rid, b.get("join_code")))
            if operation in ("start", "actions", "validate-action"):
                start = operation == "start"
                result = platform.mutate(
                    pid,
                    rid,
                    b.get("expected_version"),
                    self.headers.get("Idempotency-Key"),
                    {"type": "start"} if start else b.get("action"),
                    start=start,
                    dry_run=operation == "validate-action",
                )
                return self.send_json(200, result)
        raise GameError(
            "method_not_allowed", "Method not allowed for this endpoint", 405
        )


def make_server(
    host="127.0.0.1",
    port=8000,
    database="boardgame.sqlite3",
    registration_key=None,
    mcp_allowed_origins=(),
):
    server = ThreadingHTTPServer((host, port), Handler)
    server.daemon_threads = True
    server.platform = Platform(database)
    server.registration_key = registration_key
    server.mcp_allowed_origins = frozenset(mcp_allowed_origins)
    return server


def main():
    parser = argparse.ArgumentParser(description="Human and agent boardgame API")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument(
        "--database", default=os.environ.get("BOARDGAME_DATABASE", "boardgame.sqlite3")
    )
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO)
    server = make_server(
        args.host,
        args.port,
        args.database,
        os.environ.get("BOARDGAME_REGISTRATION_KEY"),
        tuple(
            filter(None, os.environ.get("BOARDGAME_MCP_ALLOWED_ORIGINS", "").split(","))
        ),
    )
    logging.info("Listening on http://%s:%s", args.host, args.port)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
