"""Standard newline-delimited MCP stdio bridge to the remote /mcp endpoint.

Credentials stay in environment variables. stdout contains JSON-RPC only.
"""

import argparse
import json
import os
import sys
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import HTTPRedirectHandler, Request, build_opener

# Also usable as an absolute script path without requiring package installation.
if __package__ in (None, ""):
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from boardgame.mcp import rpc_error  # noqa: E402

MAX_LINE = 262144


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        # Never forward the player's Bearer token to a redirect destination.
        return None


def urlopen(request, timeout):
    return build_opener(NoRedirect).open(request, timeout=timeout)


class Bridge:
    def __init__(self, url, token):
        parsed = urlparse(url)
        if (
            parsed.scheme not in ("http", "https")
            or not parsed.hostname
            or parsed.username
            or parsed.password
            or parsed.query
            or parsed.fragment
        ):
            raise ValueError(
                "MCP URL must be an HTTP(S) URL without credentials, query or fragment"
            )
        self.url = url
        self.token = token
        self.version = None

    def forward(self, message):
        headers = {
            "Authorization": "Bearer " + self.token,
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
        }
        if self.version:
            headers["MCP-Protocol-Version"] = self.version
        req = Request(
            self.url, data=json.dumps(message).encode(), headers=headers, method="POST"
        )
        rid = message.get("id") if isinstance(message, dict) else None
        notification = isinstance(message, dict) and "id" not in message
        try:
            with urlopen(req, timeout=35) as response:
                raw = response.read()
                result = json.loads(raw) if raw else None
        except HTTPError as e:
            with e:
                # Authentication errors must not print response bodies or tokens.
                status = e.code
            result = rpc_error(
                rid,
                -32000,
                f"MCP HTTP error {status}; check endpoint, authorization and protocol version",
            )
        except (URLError, TimeoutError, OSError, ValueError):
            result = rpc_error(
                rid,
                -32000,
                "MCP transport failed; for mutations retry the exact original arguments and idempotency_key",
            )
        if notification:
            return None
        if (
            isinstance(result, dict)
            and isinstance(message, dict)
            and message.get("method") == "initialize"
        ):
            self.version = result.get("result", {}).get("protocolVersion")
        return result


def serve(bridge, input_stream, output_stream):
    while True:
        line = input_stream.readline(MAX_LINE + 1)
        if not line:
            return
        if len(line) > MAX_LINE:
            # Never interpret a remainder of an oversized request as a new one.
            while line and not line.endswith(b"\n"):
                line = input_stream.readline(MAX_LINE + 1)
            result = rpc_error(None, -32600, "Request exceeds 262144 bytes")
        else:
            try:
                message = json.loads(
                    line, parse_constant=lambda x: (_ for _ in ()).throw(ValueError(x))
                )
            except (ValueError, UnicodeDecodeError, RecursionError):
                result = rpc_error(None, -32700, "Invalid JSON")
            else:
                result = bridge.forward(message)
        if result is not None:
            output_stream.write(json.dumps(result, ensure_ascii=False) + "\n")
            output_stream.flush()


def main():
    parser = argparse.ArgumentParser(
        description="MCP stdio bridge to the boardgame API"
    )
    parser.add_argument(
        "--url",
        default=os.environ.get("BOARDGAME_MCP_URL", "http://127.0.0.1:8000/mcp"),
    )
    args = parser.parse_args()
    token = os.environ.get("BOARDGAME_TOKEN")
    if not token:
        parser.error("Set BOARDGAME_TOKEN to your own player's API token")
    try:
        bridge = Bridge(args.url, token)
    except ValueError as e:
        parser.error(str(e))
    serve(bridge, sys.stdin.buffer, sys.stdout)


if __name__ == "__main__":
    main()
