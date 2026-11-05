"""Optional interoperability test against the official MCP Python SDK 2.3.

Run: uv run --locked --with 'mcp==2.3.0' python -m unittest discover -s tests -p test_mcp_sdk.py -v
The SDK's actual Streamable HTTP client runs over a mock network transport; the
server still receives raw HTTP and performs its normal authentication and routing.
"""

import json
import tempfile
import unittest
from types import SimpleNamespace
from boardgame.platform import Platform
from boardgame.server import Handler
from test_transport import Connection

try:
    import httpx2
    from mcp import ClientSession
    from mcp.client.streamable_http import streamable_http_client
except ImportError:
    ClientSession = None


@unittest.skipIf(
    ClientSession is None,
    "Install optional mcp==2.3.0 to run official SDK interoperability test",
)
class SDKTests(unittest.IsolatedAsyncioTestCase):
    async def test_official_streamable_http_client(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Platform(tmp + "/db")
            identity = p.register("SDK agent", "agent")
            server = SimpleNamespace(
                platform=p,
                mcp_allowed_origins=(),
                server_name="localhost",
                server_port=8000,
            )

            async def handle(request):
                payload = await request.aread()
                headers = dict(request.headers)
                headers["Content-Length"] = str(len(payload))
                wire = (
                    f"{request.method} /mcp HTTP/1.0\r\n"
                    + "".join(f"{k}: {v}\r\n" for k, v in headers.items())
                    + "\r\n"
                ).encode() + payload
                conn = Connection(wire)
                Handler(conn, ("127.0.0.1", 1), server)
                head, body = bytes(conn.output).split(b"\r\n\r\n", 1)
                lines = head.decode().split("\r\n")
                status = int(lines[0].split()[1])
                response_headers = dict(
                    line.split(": ", 1) for line in lines[1:] if ": " in line
                )
                return httpx2.Response(status, headers=response_headers, content=body)

            async with httpx2.AsyncClient(
                transport=httpx2.MockTransport(handle),
                headers={"Authorization": "Bearer " + identity["token"]},
            ) as http:
                async with streamable_http_client(
                    "http://localhost/mcp", http_client=http
                ) as streams:
                    async with ClientSession(*streams) as session:
                        init = await session.initialize()
                        self.assertEqual(init.protocol_version, "2025-11-25")
                        tools = await session.list_tools()
                        self.assertEqual(len(tools.tools), 12)
                        me = await session.call_tool("get_identity", {})
                        self.assertEqual(
                            json.loads(me.content[0].text)["id"], identity["id"]
                        )
                        resources = await session.list_resources()
                        for resource in resources.resources:
                            result = await session.read_resource(resource.uri)
                            self.assertTrue(result.contents)
                        rulebook = await session.call_tool(
                            "get_game_rules", {"game_id": "fcm"}
                        )
                        self.assertIn(
                            "目标与游戏结束",
                            json.loads(rulebook.content[0].text)["rules_text"],
                        )
                        room = await session.call_tool(
                            "create_room", {"game_id": "fcm", "capacity": 2}
                        )
                        rid = json.loads(room.content[0].text)["id"]
                        obs = await session.call_tool("observe_game", {"room_id": rid})
                        self.assertEqual(
                            json.loads(obs.content[0].text)["status"], "lobby"
                        )
