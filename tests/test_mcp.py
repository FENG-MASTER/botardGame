"""MCP transport, authorization, discovery and game lifecycle regression tests."""

import io
import json
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from boardgame.mcp import PROTOCOL_VERSION
from boardgame.mcp_stdio import Bridge, serve
from boardgame.platform import Platform
from boardgame.server import Handler
from test_transport import Connection
from examples.play_agents import choose


class MCPTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.p = Platform(self.tmp.name + "/db")
        self.server = SimpleNamespace(
            platform=self.p,
            mcp_allowed_origins=(),
            server_name="localhost",
            server_port=8000,
        )
        self.a = self.p.register("human", "human")
        self.b = self.p.register("agent", "agent")
        self.rpc_id = 0

    def tearDown(self):
        self.tmp.cleanup()

    def raw(self, body, token=None, method="POST", headers=None):
        payload = json.dumps(body).encode() if body is not None else b""
        hs = {
            "Host": "localhost",
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
            "Content-Length": str(len(payload)),
            "Authorization": "Bearer " + (self.a["token"] if token is None else token),
        }
        hs.update(headers or {})
        data = (
            f"{method} /mcp HTTP/1.0\r\n"
            + "".join(f"{k}: {v}\r\n" for k, v in hs.items())
            + "\r\n"
        ).encode() + payload
        conn = Connection(data)
        Handler(conn, ("127.0.0.1", 123), self.server)
        head, raw = bytes(conn.output).split(b"\r\n\r\n", 1)
        return int(head.split()[1]), json.loads(raw) if raw else None

    def rpc(self, method, params=None, token=None):
        self.rpc_id += 1
        status, result = self.raw(
            {
                "jsonrpc": "2.0",
                "id": self.rpc_id,
                "method": method,
                "params": params or {},
            },
            token,
        )
        self.assertEqual(status, 200)
        self.assertEqual(result["id"], self.rpc_id)
        return result

    def call(self, name, args=None, token=None):
        result = self.rpc("tools/call", {"name": name, "arguments": args or {}}, token)[
            "result"
        ]
        self.assertFalse(result["isError"], result)
        return json.loads(result["content"][0]["text"])

    def test_expansion_rules_and_room_scoping(self):
        book = self.call("get_game_rules", {"game_id": "fcm"})
        self.assertIn("营销 API 坐标约定", book["rules_text"])
        self.assertIn("旋转后占地矩形的**左上角**", book["rules_text"])
        self.assertEqual(len(book["module_rules"]), 17)
        self.assertTrue(all(m["available"] for m in book["module_rules"].values()))
        self.assertIn("work.lobby", book["module_rules"]["lobbyists"]["rules_text"])
        self.assertIn("choose_bonus", book["module_rules"]["new_milestones"]["rules_text"])
        self.assertIn("coffee_shops", book["module_rules"]["coffee"]["rules_text"])
        self.assertIn("泡菜", book["module_rules"]["kimchi"]["rules_text"])
        self.assertIn("最短", book["module_rules"]["coffee"]["rules_text"])
        self.assertTrue(book["module_rules"]["coffee"]["available"])
        room = self.p.create_room(self.a["id"], "fcm", 2, {"modules": ["kimchi", "sushi"]}, 1)
        scoped = self.call("get_game_rules", {"game_id": "fcm", "room_id": room["id"]})
        self.assertEqual(scoped["enabled_modules"], ["kimchi", "sushi"])
        self.assertEqual(set(scoped["enabled_module_rules"]), {"kimchi", "sushi"})
        self.assertIn("## kimchi —", scoped["room_rules_text"])
        self.assertIn("## sushi —", scoped["room_rules_text"])
        self.assertNotIn("## coffee —", scoped["room_rules_text"])
        self.assertNotIn("## ketchup —", scoped["room_rules_text"])
        self.assertIn("泡菜+足量寿司", scoped["room_rules_text"])
        base = self.p.create_room(self.a["id"], "fcm", 2, {}, 1)
        base_rules = self.call("get_game_rules", {"game_id": "fcm", "room_id": base["id"]})
        self.assertEqual(base_rules["enabled_module_rules"], {})
        self.assertIn("无（基础版）", base_rules["room_rules_text"])
        self.assertNotIn("## kimchi —", base_rules["room_rules_text"])
        from boardgame.mcp import MCP
        from boardgame.core import GameError
        with self.assertRaises(GameError):
            MCP(self.p).call_tool(self.b, "get_game_rules", {"game_id": "fcm", "room_id": room["id"]})

    def test_wait_guidance_preserves_cursor_across_join_and_timeout(self):
        room = self.p.create_room(self.a["id"], "fcm", 2, {}, 1)
        options = self.call("get_available_actions", {"room_id": room["id"]})
        next_call = options["next_call"]
        self.assertEqual(next_call, {
            "name": "get_events",
            "arguments": {"room_id": room["id"], "after": options["version"], "wait": 25},
        })
        # A join between observing and waiting must not be missed.
        self.p.join(self.b["id"], room["id"], room["join_code"])
        events = self.call(next_call["name"], next_call["arguments"])
        self.assertTrue(events["events"])
        self.assertEqual(events["next_call"]["name"], "observe_game")
        timeout = self.call("get_events", {
            "room_id": room["id"], "after": events["cursor"], "wait": 0,
        })
        self.assertEqual(timeout["events"], [])
        self.assertEqual(timeout["next_call"]["arguments"]["after"], events["cursor"])
        self.assertEqual(timeout["next_call"]["arguments"]["wait"], 25)
        with patch.object(self.p, "actions", return_value={
            "version": 7, "can_act": False, "reason": "finished", "actions": [],
        }):
            self.assertNotIn("next_call", self.call("get_available_actions", {"room_id": room["id"]}))

    def test_initialize_discovery_and_rules(self):
        result = self.rpc(
            "initialize",
            {
                "protocolVersion": "future",
                "capabilities": {},
                "clientInfo": {"name": "test", "version": "1"},
            },
        )["result"]
        self.assertEqual(result["protocolVersion"], PROTOCOL_VERSION)
        self.assertIn("tools", result["capabilities"])
        self.assertIn("idempotency_key", result["instructions"])
        status, body = self.raw(
            {"jsonrpc": "2.0", "method": "notifications/initialized"}
        )
        self.assertEqual((status, body), (202, None))
        tools = self.rpc("tools/list")["result"]["tools"]
        self.assertEqual(len(tools), 15)
        self.assertFalse(
            next(t for t in tools if t["name"] == "create_room")["annotations"][
                "idempotentHint"
            ]
        )
        self.assertEqual(self.call("get_identity")["id"], self.a["id"])
        self.assertEqual(
            self.call("get_identity", token=self.b["token"])["id"], self.b["id"]
        )
        resources = self.rpc("resources/list")["result"]["resources"]
        for resource in resources:
            value = self.rpc("resources/read", {"uri": resource["uri"]})["result"][
                "contents"
            ][0]
            self.assertTrue(value["text"])
        rulebook = self.call("get_game_rules", {"game_id": "fcm"})
        self.assertIn("implementation_notes", rulebook)
        self.assertEqual(rulebook["rules_format"], "text/markdown")
        self.assertIn("目标与游戏结束", rulebook["rules_text"])
        self.assertIn("first_hundred", rulebook["rules_text"])
        resource = self.rpc("resources/read", {"uri": "boardgame://games/fcm"})[
            "result"
        ]
        self.assertEqual(json.loads(resource["contents"][0]["text"]), rulebook)

    def test_protocol_validation_and_origin(self):
        self.assertEqual(
            self.raw({"jsonrpc": "2.0", "id": 1, "method": "ping"}, token="bad")[0], 401
        )
        self.assertEqual(
            self.raw({}, headers={"Origin": "https://evil.example"})[0], 403
        )
        self.server.mcp_allowed_origins = ("https://allowed.example",)
        self.assertEqual(
            self.raw(
                {"jsonrpc": "2.0", "id": 1, "method": "ping"},
                headers={"Origin": "https://allowed.example"},
            )[0],
            200,
        )
        self.assertEqual(
            self.raw({}, headers={"MCP-Protocol-Version": "2099-01-01"})[0], 400
        )
        self.assertEqual(self.raw({}, headers={"Accept": "application/json"})[0], 406)
        self.assertEqual(self.raw(None, method="GET")[0], 405)
        self.assertEqual(self.raw(None, method="DELETE")[0], 405)
        self.assertEqual(self.rpc("no/such/method")["error"]["code"], -32601)
        self.assertEqual(
            self.rpc("tools/call", {"name": "unknown"})["error"]["code"], -32602
        )
        self.assertEqual(
            self.rpc(
                "tools/call", {"name": "observe_game", "arguments": {"room_id": 1}}
            )["error"]["code"],
            -32602,
        )
        self.assertEqual(
            self.rpc("resources/read", {"uri": "file:///etc/passwd"})["error"]["code"],
            -32002,
        )
        self.assertEqual(self.raw([])[1]["error"]["code"], -32600)

    def test_tool_errors_membership_and_notifications_never_mutate(self):
        room = self.call("create_room", {"game_id": "fcm", "capacity": 2})
        r = self.rpc(
            "tools/call",
            {"name": "observe_game", "arguments": {"room_id": room["id"]}},
            self.b["token"],
        )["result"]
        self.assertTrue(r["isError"])
        self.assertEqual(
            json.loads(r["content"][0]["text"])["error"]["code"], "forbidden"
        )
        self.raw(
            {
                "jsonrpc": "2.0",
                "method": "tools/call",
                "params": {
                    "name": "create_room",
                    "arguments": {"game_id": "fcm", "capacity": 2},
                },
            }
        )
        self.assertEqual(len(self.call("list_rooms")["rooms"]), 1)

    def setup_room(self):
        room = self.call("create_room", {"game_id": "fcm", "capacity": 2, "seed": 1})
        rid = room["id"]
        self.call(
            "join_room",
            {"room_id": rid, "join_code": room["join_code"]},
            self.b["token"],
        )
        start = {"room_id": rid, "expected_version": 1, "idempotency_key": "start"}
        initial = self.call("start_game", start)
        self.assertEqual(initial, self.call("start_game", start))
        return rid

    def test_full_game_via_mcp_and_replay(self):
        rid = self.setup_room()
        identities = {p["id"]: p for p in (self.a, self.b)}
        for i in range(600):
            obs = self.call("observe_game", {"room_id": rid})
            if obs["status"] == "finished":
                break
            actor = obs["state"]["actors"][0]
            token = identities[actor]["token"]
            obs = self.call("observe_game", {"room_id": rid}, token)
            options = self.call("get_available_actions", {"room_id": rid}, token)
            args = {
                "room_id": rid,
                "expected_version": options["version"],
                "action": choose(actor, obs, options),
            }
            self.assertTrue(self.call("validate_action", args, token)["valid"])
            args["idempotency_key"] = str(i)
            first = self.call("submit_action", args, token)
            self.assertEqual(first, self.call("submit_action", args, token))
        self.assertEqual(obs["status"], "finished")
        self.assertTrue(self.p.replay(rid)["valid"])
        self.assertTrue(self.call("get_events", {"room_id": rid})["events"])

    def test_private_reserves_and_version_conflict(self):
        rid = self.setup_room()
        for i in range(2):
            obs = self.call("observe_game", {"room_id": rid})
            pid = obs["state"]["actors"][0]
            token = next(p["token"] for p in (self.a, self.b) if p["id"] == pid)
            options = self.call("get_available_actions", {"room_id": rid}, token)
            self.call(
                "submit_action",
                {
                    "room_id": rid,
                    "expected_version": obs["version"],
                    "idempotency_key": str(i),
                    "action": options["placements"][0],
                },
                token,
            )
        version = self.call("observe_game", {"room_id": rid})["version"]
        self.call(
            "submit_action",
            {
                "room_id": rid,
                "expected_version": version,
                "idempotency_key": "reserve",
                "action": {"type": "choose_reserve", "amount": 300},
            },
        )
        obs = self.call("observe_game", {"room_id": rid}, self.b["token"])
        self.assertIsNone(obs["state"]["reserves"][self.a["id"]])
        self.assertNotIn(
            "amount",
            json.dumps(self.call("get_events", {"room_id": rid}, self.b["token"])),
        )
        r = self.rpc(
            "tools/call",
            {
                "name": "submit_action",
                "arguments": {
                    "room_id": rid,
                    "expected_version": version,
                    "idempotency_key": "stale",
                    "action": {"type": "choose_reserve", "amount": 100},
                },
            },
            self.b["token"],
        )["result"]
        self.assertEqual(
            json.loads(r["content"][0]["text"])["error"]["code"], "version_conflict"
        )

    def test_stdio_bridge_wire(self):
        def urlopen(req, timeout):
            headers = {k.title(): v for k, v in req.header_items()}
            self.assertEqual(headers["Authorization"], "Bearer " + self.a["token"])
            status, response = self.raw(
                json.loads(req.data), token=self.a["token"], headers=headers
            )
            self.assertIn(status, (200, 202))
            return io.BytesIO(json.dumps(response).encode() if response else b"")

        messages = [
            dict(
                jsonrpc="2.0",
                id=1,
                method="initialize",
                params=dict(
                    protocolVersion=PROTOCOL_VERSION,
                    capabilities={},
                    clientInfo={"name": "test", "version": "1"},
                ),
            ),
            dict(jsonrpc="2.0", method="notifications/initialized"),
            dict(jsonrpc="2.0", id=2, method="tools/list"),
        ]
        inp = io.BytesIO(("\n".join(map(json.dumps, messages)) + "\n").encode())
        out = io.StringIO()
        with patch("boardgame.mcp_stdio.urlopen", urlopen):
            bridge = Bridge("http://localhost/mcp", self.a["token"])
            serve(bridge, inp, out)
        lines = [json.loads(line) for line in out.getvalue().splitlines()]
        self.assertEqual([v["id"] for v in lines], [1, 2])
        self.assertEqual(bridge.version, PROTOCOL_VERSION)
        self.assertEqual(len(lines[1]["result"]["tools"]), 15)
        self.assertNotIn(self.a["token"], out.getvalue())
