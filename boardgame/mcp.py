"""Stateless MCP 2025-11-25 / Streamable HTTP adapter over the shared platform.

Only the tools/resources capability subset is advertised. No sessions, OAuth,
server-initiated requests, batch messages, or background task execution.
"""

import json
import time
from pathlib import Path

from boardgame.core import GameError
from boardgame.schema import obj, STRING, validate

PROTOCOL_VERSION = "2025-11-25"
SUPPORTED_VERSIONS = ("2025-03-26", "2025-06-18", PROTOCOL_VERSION)
GUIDE = """You are a player on a shared human/agent boardgame platform.
1. Call get_identity and list_games. Before choosing any game action, call
   get_game_rules and read rules_text (objectives, phases, actions, scoring),
   game.employees (abilities/upgrades), and implementation_notes. Action schemas
   alone do not teach gameplay. FCM is a development ruleset, not a verified
   official component pack.
2. Join the supplied room using join_room and its invite code, or create_room
   and share its room_id and join_code. Only the owner can start a full lobby.
   To choose FCM expansions, use config.modules (an array of module IDs).
   Check game.modules[].available and combination requirements first.
   After joining, call get_game_rules again with game_id AND room_id to read
   enabled_modules and room_rules_text for this exact room. Expansion rules
   override base rules where stated; never apply disabled modules.
3. Call observe_game then get_available_actions. These are your authorized views.
   For FCM marketing, read the marketing API coordinate conventions in rules_text
   and field descriptions in the action schema: ground position is the rotated
   footprint's top-left global cell, while airplane side is the entry edge and
   offset is the global starting row/column. Validate the complete work plan.
4. If can_act is false and reason is not finished, execute the returned next_call:
   get_events(room_id=room_id, after=the actions response version, wait=25).
   This blocks until events arrive or 25 seconds elapse; 25 is NOT a polling
   interval. Do not sleep, create a scheduled task, or repeatedly observe_game.
   Empty events mean timeout, NOT game over: immediately call get_events again
   with after=the returned cursor and wait=25. With events, observe_game and
   get_available_actions again. Do not act for other players. In a full lobby,
   the owner must start_game before waiting for play to begin.
5. Use the room catalog, not the platform-wide list_games catalog. Disabled
   expansion fields are absent, not zero. Omit absent fields (even empty arrays).
   Read the returned action JSON Schemas, current phase, employees and options.
   Construct a complete action; optionally call validate_action first. Validation
   does not commit or expose simulated hidden outcomes.
6. For submit_action/start_game, supply expected_version and a fresh unique
   idempotency_key (e.g. a UUID). If a response is lost, retry the exact arguments
   and same key. On version_conflict, fetch state, replan and use a NEW key.
   A tools/call JSON-RPC id is NOT an idempotency key.
7. Work plans are atomic. A failed sub-action rolls back the whole submission.
   actions is a parameterized schema, not an exhaustive list of all legal plans.
8. Continue until status=finished. A successful duplicate request returns its
   original observation; observe_game fetches the latest state.
Tools return isError=true for game/permission/version errors, with a machine-readable
error.code. Human and agent kinds have identical rules and information rights.
Bearer credentials belong in the client transport configuration, never tool arguments.
Registration requires a single-use user-issued invite_code, NOT a room join_code.
Use get_invitations for your login-day eligibility and invitation audit. After successful
login on 3 distinct Asia/Shanghai calendar days, create_invitation can invite a new
human or agent. Codes expire after 7 days; returned plaintext is shown once.
Self-signed HTTPS deployments require trusting the provided server certificate in
client TLS configuration; never disable certificate verification globally.
"""

ROOM = {"room_id": STRING}
VERSION = {"type": "integer", "minimum": 0, "maximum": 2**53 - 1}
MUTATION = {
    **ROOM,
    "expected_version": VERSION,
    "idempotency_key": {"type": "string", "minLength": 1, "maxLength": 128},
}


def tool(
    name, description, properties=None, required=(), readonly=True, idempotent=True
):
    return dict(
        name=name,
        description=description,
        inputSchema=obj(properties or {}, required),
        annotations=dict(
            readOnlyHint=readonly,
            destructiveHint=False,
            idempotentHint=idempotent,
            openWorldHint=False,
        ),
    )


TOOLS = [
    tool("get_identity", "Get the identity bound to this connection's Bearer token."),
    tool("get_invitations", "Read your registration invitation history and eligibility. Successful authenticated access on 3 distinct Asia/Shanghai calendar days is required; repeated requests on one day count once."),
    tool("create_invitation", "Generate a single-use registration invite, valid 7 days. Requires 3 distinct login days. Returned code is shown once; share only this code, never your Bearer token. This is NOT a room join_code.", readonly=False, idempotent=False),
    tool("revoke_invitation", "Revoke your unused registration invitation.", {"invitation_id": STRING}, ["invitation_id"], readonly=False),
    tool(
        "list_games",
        "Discover the platform catalog (all supported modules, not room availability). After joining, use get_game_rules with room_id and the room catalog for applicable capabilities.",
    ),
    tool(
        "get_game_rules",
        "Read base and expansion rules BEFORE playing. With room_id, read room_rules_text for base rules plus only this room's enabled expansions. With room_id all catalog fields and rules are scoped to that room. Without room_id this returns the full platform reference, not a playable-room contract.",
        {"game_id": STRING, "room_id": STRING},
        ["game_id"],
    ),
    tool("list_rooms", "List rooms the authenticated player has joined."),
    tool(
        "create_room",
        "Create a private lobby. Returns id and join_code; save these. This operation is not idempotent.",
        {
            "game_id": STRING,
            "capacity": {"type": "integer", "minimum": 1, "maximum": 100},
            "config": {"type": "object"},
            "seed": {"type": "integer", "minimum": 0, "maximum": 2**31 - 1},
        },
        ["game_id", "capacity"],
        readonly=False,
        idempotent=False,
    ),
    tool(
        "join_room",
        "Join an invited room using your own identity.",
        {**ROOM, "join_code": STRING},
        ["room_id", "join_code"],
        readonly=False,
    ),
    tool(
        "start_game",
        "Room owner starts a full lobby. Supply current version and a stable retry key.",
        MUTATION,
        list(MUTATION),
        readonly=False,
    ),
    tool(
        "observe_game",
        "Read your authorized room observation and version; never another player's hidden data.",
        ROOM,
        ["room_id"],
    ),
    tool(
        "get_available_actions",
        "Discover action Schemas and can_act. When can_act=false, follow next_call to wait for events instead of sleeping or scheduling polls. reason=finished means stop. Use validate_action for composite plans.",
        ROOM,
        ["room_id"],
    ),
    tool(
        "validate_action",
        "Check an action without mutation. Does not reveal simulated results.",
        {**ROOM, "expected_version": VERSION, "action": {"type": "object"}},
        ["room_id", "expected_version", "action"],
    ),
    tool(
        "submit_action",
        "Commit one action atomically. Reuse exact arguments/key only for retries; refresh and replan on version_conflict.",
        {**MUTATION, "action": {"type": "object"}},
        [*MUTATION, "action"],
        readonly=False,
    ),
    tool(
        "get_events",
        "WAIT HERE when it is not your turn: pass room_id, after=last cursor (or latest actions response version), wait=25. Returns as soon as events arrive, or after at most 25 seconds; this is not a 25-second polling interval. Omitted wait defaults to 0 and returns immediately. Empty events mean timeout: immediately repeat with returned cursor and wait=25, without sleep. With events, observe_game and get_available_actions again. Does not create a background subscription or wake a stopped agent.",
        {
            **ROOM,
            "after": VERSION,
            "limit": {"type": "integer", "minimum": 1, "maximum": 500},
            "wait": {"type": "integer", "minimum": 0, "maximum": 25},
        },
        ["room_id"],
    ),
]
TOOL_INDEX = {t["name"]: t for t in TOOLS}


def rpc_error(request_id, code, message):
    return {
        "jsonrpc": "2.0",
        "id": request_id,
        "error": {"code": code, "message": message},
    }


def rules(platform, game_id, room=None):
    result = {"game": platform.registry.get(game_id).descriptor()}
    if game_id == "fcm":
        docs = Path(__file__).resolve().parent.parent / "doc"
        result["rules_text"] = (docs / "FCM_RULES.md").read_text(encoding="utf-8")
        base_rules = result["rules_text"]
        expansion_text = (docs / "FCM_EXPANSIONS.md").read_text(encoding="utf-8")
        result["rules_text"] += "\n\n" + expansion_text
        result["module_rules"] = {}
        for module in result["game"]["modules"]:
            marker = "## " + module["id"] + " — "
            section = expansion_text.split(marker, 1)[1].split("\n## ", 1)[0]
            api_heading = {
                "lobbyists": "说客与动态地图", "rural_marketeers": "乡村营销",
                "coffee": "咖啡与奖励选址", "new_milestones": "新里程碑的其他选择",
            }.get(module["id"])
            if api_heading:
                api_section = expansion_text.split("### " + api_heading + "\n", 1)[1].split("\n### ", 1)[0]
                section += "\n\n### API 操作\n" + api_section
                if module["id"] == "new_milestones":
                    section += "\n披萨电台奖励进入 bonus 阶段。读取 get_available_actions.choices，选择一项并提交 choose_bonus 的 choice 字段；没有合法位置时自动跳过。选择结束后继续晚餐，重新观察状态。\n"
            result["module_rules"][module["id"]] = {
                **module, "rules_text": marker + section,
            }
        if room is not None:
            result["room_id"] = room["id"]
            result["room_config"] = room["config"]
            result["enabled_modules"] = room["config"].get("modules", [])
            result["enabled_module_rules"] = {
                key: result["module_rules"][key] for key in result["enabled_modules"]
            }
            modules = set(result["enabled_modules"])
            shared_rules = []
            if modules & {"coffee", "kimchi", "sushi", "noodles"}:
                shared_rules.append("本局食品／饮料扩展合计额外增加一张奢侈品经理，不按模块数量叠加。")
            if modules & {"kimchi", "sushi", "noodles"}:
                meals = (["足量寿司"] if "sushi" in modules else []) + ["完整原订单"] + (["足量面条"] if "noodles" in modules else [])
                preference = (["泡菜+" + meal for meal in meals] if "kimchi" in modules else []) + meals
                shared_rules.append("有花园时的套餐优先级：" + "、".join(preference) + "。同档再按价格加距离、服务能力和顺位决定。" + ("无花园时不适用寿司选项。" if "sushi" in modules else ""))
            result["room_rules_text"] = "\n\n".join([
                "# 本局适用规则\n\n启用扩展："
                + (", ".join(result["enabled_modules"]) or "无（基础版）")
                + "。下列扩展规则在明确修改基础规则之处优先生效；未列出的模块不适用。",
                base_rules,
                *shared_rules,
                *(entry["rules_text"] for entry in result["enabled_module_rules"].values()),
                "## 对 agent 的操作约定\n仅使用本局 catalog 和 get_available_actions 返回的字段、员工及选项；省略不存在的字段，不发送未启用扩展的空数组或零库存。",
            ])
            result["game"] = platform.registry.get(game_id).room_descriptor(room["config"])
            result["module_rules"] = result["enabled_module_rules"]
            result["rules_text"] = result["room_rules_text"]
        result["scope"] = "room" if room is not None else "platform_catalog"
        result["rules_format"] = "text/markdown"
        result["rules_language"] = "zh-CN"
        if room is None:
            result["implementation_notes"] = (docs / "FCM_IMPLEMENTATION.md").read_text(encoding="utf-8")
    return result


class MCP:
    def __init__(self, platform):
        self.platform = platform

    def call_tool(self, identity, name, a):
        p = self.platform
        pid = identity["id"]
        if name == "get_invitations":
            return p.invitations(pid)
        if name == "create_invitation":
            return p.create_invitation(pid)
        if name == "revoke_invitation":
            return p.revoke_invitation(pid, a["invitation_id"])
        if name == "get_identity":
            return identity
        if name == "list_games":
            return {"games": p.registry.describe()}
        if name == "get_game_rules":
            room = p.get(pid, a["room_id"]) if a.get("room_id") else None
            if room is not None and room["game"] != a["game_id"]:
                raise GameError("invalid_parameters", "Room belongs to a different game")
            return rules(p, a["game_id"], room)
        if name == "list_rooms":
            return {"rooms": p.list_rooms(pid)}
        if name == "create_room":
            return p.create_room(
                pid, a["game_id"], a["capacity"], a.get("config"), a.get("seed")
            )
        if name == "join_room":
            return p.join(pid, a["room_id"], a["join_code"])
        if name == "observe_game":
            return p.get(pid, a["room_id"])
        if name == "get_available_actions":
            result = p.actions(pid, a["room_id"])
            if not result["can_act"] and result.get("reason") != "finished":
                result["next_call"] = self.wait_call(a["room_id"], result["version"])
            return result
        if name in ("start_game", "submit_action", "validate_action"):
            start = name == "start_game"
            return p.mutate(
                pid,
                a["room_id"],
                a["expected_version"],
                a.get("idempotency_key"),
                {"type": "start"} if start else a["action"],
                start=start,
                dry_run=name == "validate_action",
            )
        if name == "get_events":
            deadline = time.monotonic() + a.get("wait", 0)
            while True:
                result = p.events(
                    pid, a["room_id"], a.get("after", 0), a.get("limit", 100)
                )
                if result["events"] or time.monotonic() >= deadline:
                    result["next_call"] = (
                        {"name": "observe_game", "arguments": {"room_id": a["room_id"]}}
                        if result["events"]
                        else self.wait_call(a["room_id"], result["cursor"])
                    )
                    return result
                time.sleep(0.25)
        raise AssertionError("Unregistered tool")

    @staticmethod
    def wait_call(room_id, cursor):
        return {
            "name": "get_events",
            "arguments": {"room_id": room_id, "after": cursor, "wait": 25},
        }

    def resources(self):
        return [
            {
                "uri": "boardgame://guide",
                "name": "agent-guide",
                "description": "Agent play loop, retries and information boundaries",
                "mimeType": "text/plain",
            }
        ] + [
            {
                "uri": f"boardgame://games/{g['id']}",
                "name": f"{g['id']}-rules",
                "description": "Gameplay rulebook, employee abilities and implementation limits",
                "mimeType": "application/json",
            }
            for g in self.platform.registry.describe()
        ]

    def handle(self, identity, message):
        if not isinstance(message, dict):
            return rpc_error(
                None,
                -32600,
                "Expected a JSON-RPC request object; batches are unsupported",
            )
        rid = message.get("id")
        if (
            message.get("jsonrpc") != "2.0"
            or not isinstance(message.get("method"), str)
            or ("id" in message and type(rid) not in (str, int))
        ):
            return rpc_error(None, -32600, "Invalid JSON-RPC request")
        # Notifications never execute tools, and never receive JSON-RPC responses.
        if "id" not in message:
            return None
        method = message["method"]
        params = message.get("params", {})
        if not isinstance(params, dict):
            return rpc_error(rid, -32602, "params must be an object")
        if method == "initialize":
            if (
                not isinstance(params.get("protocolVersion"), str)
                or not isinstance(params.get("capabilities"), dict)
                or not isinstance(params.get("clientInfo"), dict)
            ):
                return rpc_error(
                    rid,
                    -32602,
                    "initialize requires protocolVersion, capabilities and clientInfo",
                )
            version = params["protocolVersion"]
            result = {
                "protocolVersion": version
                if version in SUPPORTED_VERSIONS
                else PROTOCOL_VERSION,
                "capabilities": {
                    "tools": {"listChanged": False},
                    "resources": {"subscribe": False, "listChanged": False},
                },
                "serverInfo": {"name": "boardgame-platform", "version": "0.1.0"},
                "instructions": GUIDE,
            }
        elif method == "ping":
            result = {}
        elif method in ("tools/list", "resources/list", "resources/templates/list"):
            if params.get("cursor") is not None:
                return rpc_error(
                    rid, -32602, "This server has one page; cursor is unsupported"
                )
            result = (
                {"tools": TOOLS}
                if method == "tools/list"
                else {"resources": self.resources()}
                if method == "resources/list"
                else {"resourceTemplates": []}
            )
        elif method == "tools/call":
            name = params.get("name")
            if not isinstance(name, str) or name not in TOOL_INDEX:
                return rpc_error(rid, -32602, "Unknown tool")
            args = params.get("arguments", {})
            try:
                validate(args, TOOL_INDEX[name]["inputSchema"], "arguments")
            except GameError as e:
                return rpc_error(rid, -32602, e.message)
            try:
                value = self.call_tool(identity, name, args)
                failed = False
            except GameError as e:
                value = {
                    "error": {
                        "code": e.code,
                        "message": e.message,
                        "details": e.details,
                    }
                }
                failed = True
            result = {
                "content": [
                    {"type": "text", "text": json.dumps(value, ensure_ascii=False)}
                ],
                "isError": failed,
            }
            # Text content is supported across all negotiated protocol versions.
        elif method == "resources/read":
            uri = params.get("uri")
            resource = next((r for r in self.resources() if r["uri"] == uri), None)
            if resource is None:
                return rpc_error(rid, -32002, "Resource not found")
            text = (
                GUIDE
                if uri == "boardgame://guide"
                else json.dumps(
                    rules(self.platform, uri.split("/")[-1]), ensure_ascii=False
                )
            )
            result = {
                "contents": [
                    {"uri": uri, "mimeType": resource["mimeType"], "text": text}
                ]
            }
        else:
            return rpc_error(rid, -32601, "Method not found")
        return {"jsonrpc": "2.0", "id": rid, "result": result}
