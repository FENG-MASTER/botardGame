# 桌游 API 平台

纯 HTTP/JSON 服务器，人类应用和 agent 使用完全相同的身份、房间、观察与行动接口。独立的人类 Web UI 位于 `human-ui/`，通过同一 API 游玩。使用 uv 管理 Python 环境、依赖和锁文件；默认开发解释器为 Python 3.13，代码兼容 Python 3.11+。运行服务和基础测试无需第三方依赖，SQLite 保存对局。

**当前版本：可以完成整局的开发版。** 首个规则插件为 Food Chain Magnate，默认地图使用所提供 TTS 包的真实板块转录，员工和营销组件已按卡面校正。开房可多选扩展，全部 17 个模块均已接入，包括说客、新里程碑、咖啡和乡村营销员；冲突组合会在开房时拒绝。详见 [FCM 规则覆盖与差异](doc/FCM_IMPLEMENTATION.md)，不要把本版本当作已认证的完整官方规则服务器。

## 启动与验证

先安装 [uv](https://docs.astral.sh/uv/getting-started/installation/)，然后在项目目录同步环境。uv 会按 `.python-version` 选择 Python 3.13，必要时自动下载，并在 `.venv` 中创建环境：

```bash
uv sync --locked
```

启动服务器：

```bash
uv run --locked python -m boardgame.server --host 127.0.0.1 --port 8000 --database boardgame.sqlite3
```

另一个终端运行两名 agent 的完整对局：

```bash
uv run --locked python -m examples.play_agents --url http://127.0.0.1:8000
```

示例策略只招聘服务员、依靠小费推进银行破产，用于验证平台闭环，并非有竞争力的 FCM AI。它通过正式 HTTP API 注册、创建房间、加入、开始、观察和行动，没有读取数据库或修改游戏状态。

```bash
uv run --locked python -m unittest discover -s tests -v
```

受限环境若禁止 socket，3 个真实 TCP 测试会明确跳过；另一组测试仍用原始 HTTP 报文经过实际请求解析器、路由和未经修改的 SDK 完成整局。

## Python 环境与依赖管理

- `pyproject.toml`：项目元数据和依赖声明；采用 uv 非打包项目模式，直接运行仓库内模块。
- `uv.lock`：依赖解析锁文件，应随代码一起提交。
- `.python-version`：开发环境默认 Python 3.13。
- `.venv/`：uv 管理的本地虚拟环境，不提交。无需手工激活，统一使用 `uv run`。

添加依赖时使用 uv，避免手工修改 `.venv`：

```bash
uv add <运行依赖包名>
uv add --dev <开发依赖包名>
uv remove <包名>
```

修改依赖后提交 `pyproject.toml` 和 `uv.lock`。日常启动和 CI 使用 `--locked`，配置与锁文件不一致会直接报错。若要主动更新全部依赖，执行 `uv lock --upgrade`，再同步并测试。

目前默认依赖为空，锁文件仍然记录项目配置；官方 MCP SDK 互通测试通过 `uv run --locked --with 'mcp==2.3.0' ...` 使用独立的可选依赖，不进入服务运行环境。

Docker 构建也通过 uv 和锁文件创建环境，运行容器不会重新解析或安装依赖。

## MCP 接入（agent 自发现）

同一个服务器现在提供 `http://127.0.0.1:8000/mcp`，使用 Streamable HTTP。客户端配置该地址和 `Authorization: Bearer <token>` 后，即可自动发现游戏、房间、观察与行动工具，以及规则资源。

只支持本地 MCP 进程的客户端可运行 `boardgame/mcp_stdio.py`，通过 `BOARDGAME_MCP_URL` 和 `BOARDGAME_TOKEN` 环境变量连接同一平台。没有额外的游戏实例或 agent 专用权限。

agent 可通过 `get_game_rules(game_id="fcm")` 或 `boardgame://games/fcm` 读取基础及全部扩展说明、员工数据和实现范围。入房后调用 `get_game_rules(game_id="fcm", room_id="房间ID")`，读取 `room_rules_text`（基础规则及本局启用的扩展）和 `enabled_module_rules`；无需上传 PDF。

完整注册步骤、远程/stdio 配置、协议范围和接入任务示例见 **[MCP 接入说明](doc/MCP.md)**。

## API

完整接口定义：`GET /openapi.json`。具体游戏的行动 JSON Schema 由 `GET /v1/rooms/{id}/actions` 动态返回。

| 请求 | 用途 |
| --- | --- |
| `POST /v1/identities` | 注册身份，返回一次性展示的 Bearer token |
| `GET /v1/me` | 当前身份 |
| `GET /v1/games` | 发现游戏、规则版本、配件信息和支持范围 |
| `GET /v1/games/{game_id}` | 查询一个游戏的完整描述 |
| `POST /v1/rooms` | 创建带邀请码的房间 |
| `GET /v1/rooms` | 列出自己加入的房间 |
| `POST /v1/rooms/{id}/join` | 用邀请码加入 |
| `POST /v1/rooms/{id}/start` | 房主在人员到齐后开始 |
| `GET /v1/rooms/{id}` | 获取自己的授权视图及状态版本 |
| `GET /v1/rooms/{id}/actions` | 当前可用行动类型、参数 Schema、候选选项 |
| `POST /v1/rooms/{id}/validate-action` | 无副作用地验证完整行动 |
| `POST /v1/rooms/{id}/actions` | 提交行动 |
| `GET /v1/rooms/{id}/events?after=0&wait=25` | 按游标获取事件，支持长轮询 |

注册、健康检查和规则发现可匿名调用；其他接口使用 `Authorization: Bearer <token>`。身份的 `kind: human | agent` 只是描述，**不影响行动权限、信息可见性、顺序或规则**。房主身份仅用于开始房间。

创建和加入示例：

```python
from boardgame.client import Client
import uuid

human = Client()
agent = Client()
h = human.register("Alice", "human")
a = agent.register("Agent A", "agent")
room = human.request("POST", "/v1/rooms", {
    "game": "fcm", "capacity": 2, "seed": 42
})
rid = room["id"]
agent.request("POST", f"/v1/rooms/{rid}/join", {"join_code": room["join_code"]})
latest = human.observe(rid)
human.request("POST", f"/v1/rooms/{rid}/start", {
    "expected_version": latest["version"]
}, key=uuid.uuid4().hex)
```

## agent 接入约定

1. 读取自己的 observation 和 actions。如果 `can_act=false`，等待事件后重新读取。
2. 根据行动 Schema 和自己的可见状态生成候选行动。重组与工作计划是组合空间，接口不会枚举所有可能组合；初始餐厅位置和选顺序位置会给出合法候选列表。
3. 可调用 `validate-action` 检查计划。只返回 `valid` 和版本，不返回模拟产生的隐藏信息。
4. 提交 `expected_version`、完整 `action` 和唯一 `Idempotency-Key`。
5. 网络超时后，**重发同一个 key 和原始请求体**。服务端返回第一次成功的结果；不能用同一个 key 发送新内容。SDK 的 `submit(..., key=...)` 支持调用方管理重试 key。
6. 遇到 `version_conflict`，重新读取状态，用新 key 生成新行动。错误统一使用 `error.code` 和 `error.message`，不是只能解析自然语言的报错。

```json
{
  "expected_version": 12,
  "action": {
    "type": "work",
    "hire": [{"recruiter": "<player-id>:ceo", "kind": "kitchen_trainee"}],
    "train": [{"trainer": "e1", "hire_index": 0, "path": ["burger_cook"]}]
  }
}
```

同一 `work` 请求按招聘、培训、营销、生产、建房、餐厅的顺序原子执行；任意子行动非法，整个计划回滚。新员工可用本计划中的 `hire_index` 引用，不必猜员工编号。

事件接口使用 JSON 长轮询，也支持 `Accept: text/event-stream` 和 `Last-Event-ID`。SSE 每批返回后断开，客户端携带最后游标重新连接；没有新事件时返回 heartbeat。事件均经过规则侧的信息控制，不包含秘密储备值或尚未公开的重组计划。客户端仍须使用同一身份鉴权。

## 结构与扩展

- `boardgame/platform.py`：身份、房间、SQLite 事务、版本检查、幂等和持久化。
- `boardgame/server.py`：HTTP、错误格式、长轮询与 SSE。
- `boardgame/mcp.py` / `boardgame/mcp_stdio.py`：MCP 工具/资源协议层与 stdio 桥接。
- `boardgame/core.py`：规则插件契约。
- `boardgame/registry.py`：游戏注册中心。
- `boardgame/games/fcm/`：FCM 规则、地图算法、卡表与行动 Schema。
- `boardgame/client.py`：人类客户端和 agent 共用的 Python SDK。

新游戏实现 `Game` 协议并向 `Registry` 注册，不需要改身份、房间或 HTTP 路由。见 [插件开发说明](doc/ADDING_GAMES.md)。规则不能访问网络、数据库、身份 token 或客户端类型。

当前只运行一个引擎版本，不提供旧版对局兼容。规则升级后应新建房间；`engine_version` 用于校验回放版本。数据库保留每次成功提交的私有行动日志，用于确定性重放：

```python
from boardgame.platform import Platform
print(Platform("boardgame.sqlite3").replay("<room-id>"))
```

重放是本地管理功能，未暴露为 HTTP 接口，因为原始行动包含秘密信息。

## 部署边界

这是单实例起步架构；SQLite 事务协调并发写入，适合本地使用和小规模部署。HTTP 层基于 Python 标准库，公开部署请放在提供 TLS、请求并发限制及速率限制的反向代理后。当前没有账号恢复、自动匹配、离席托管或回合超时裁定，玩家断线不会自动代打；重启后可使用原 token 继续游戏。

设置 `BOARDGAME_REGISTRATION_KEY` 可限制注册，调用方需要额外携带 `X-Registration-Key`。默认不设置，方便本地开发。token 和房间邀请码在数据库中仅存哈希；完整游戏状态和私有日志仍包含玩家秘密，数据库文件只应由服务管理员访问。

没有启用跨域访问；浏览器客户端可以同源代理 API。房间目前为私有房间，没有旁观或管理员读取他人手牌的 HTTP 接口。
