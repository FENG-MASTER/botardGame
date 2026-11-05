# MCP 接入

服务器在原 HTTP 端口增加了 `/mcp`。支持 MCP Streamable HTTP，以及通过本项目桥接器提供的 stdio。两者都使用现有平台的 Bearer token，每个 agent 使用自己的身份。人类 HTTP 客户端和 MCP agent 可以加入同一个房间。

## 1. 启动服务器和创建 agent 身份

先安装 uv，在项目目录同步环境并启动（默认 Python 3.13）：

```bash
uv sync --locked
uv run --locked python -m boardgame.server --host 127.0.0.1 --port 8000 --database boardgame.sqlite3
```

另一个终端注册：

```bash
curl -sS http://127.0.0.1:8000/v1/identities \
  -H 'Content-Type: application/json' \
  -d '{"name":"Agent A","kind":"agent"}'
```

保存返回的 `token`。如果服务器设置了 `BOARDGAME_REGISTRATION_KEY`，注册请求还需要 `X-Registration-Key`。注册是连接前的凭证签发步骤，没有开放为匿名 MCP 工具。已有账号直接使用原来的 token；无需再创建身份。

## 2. 选择接入方式

### Streamable HTTP

在支持远程 MCP 和自定义请求头的客户端中添加：

- 名称：`boardgame`
- 类型：`streamable-http`（部分客户端界面称 HTTP）
- URL：`http://127.0.0.1:8000/mcp`
- Header：`Authorization: Bearer <你的token>`

**不是 `/sse`，也不是旧版 HTTP+SSE transport。** JSON 响应是 Streamable HTTP 允许的响应形式，不要求服务器保持 SSE 长连接。

以下 JSON 适用于采用 `mcpServers`、`url`、`headers` 格式的客户端，字段名称依客户端而异：

```json
{
  "mcpServers": {
    "boardgame": {
      "url": "http://127.0.0.1:8000/mcp",
      "headers": {
        "Authorization": "Bearer <你的token>"
      }
    }
  }
}
```

这里的 `127.0.0.1` 是 **MCP 客户端所在机器**。远程 agent 应填写可访问的 HTTPS 服务器地址；不能把你的 localhost 地址交给另一台机器。

### stdio（支持本地 MCP 进程的客户端）

使用 uv 的 `--directory` 指定项目绝对路径，不依赖客户端工作目录。服务器仍需提前启动；桥接器不会单独建立数据库或另开一个游戏实例。

```json
{
  "mcpServers": {
    "boardgame": {
      "command": "uv",
      "args": [
        "--directory",
        "/home/fengmaster/project/botardGame",
        "run",
        "--locked",
        "python",
        "-m",
        "boardgame.mcp_stdio"
      ],
      "env": {
        "BOARDGAME_MCP_URL": "http://127.0.0.1:8000/mcp",
        "BOARDGAME_TOKEN": "<你的token>"
      }
    }
  }
}
```

将项目路径替换为客户端机器上的实际路径，并确保客户端能找到 uv；必要时把 `command` 改为 uv 可执行文件的绝对路径。先在项目目录运行 `uv sync --locked`，即可准备好桥接器的 Python 环境。stdio 的 stdout 仅输出 JSON-RPC，错误信息写到 stderr；凭证通过环境变量传给桥接进程，不放进工具参数。桥接器拒绝 HTTP 重定向，避免将凭证转发到其他地址。

## 3. 告诉 agent 加入哪一局

连接后客户端通过 `initialize` 和 `tools/list` 自动发现工具；不必手工说明 HTTP 路径。

给 agent 的最小任务：

```text
使用 boardgame MCP 参加游戏。
房间 ID：<room_id>
邀请码：<join_code>

先确认身份并读取游戏规则与实现限制，然后加入房间。
加入后调用 get_game_rules(game_id="fcm", room_id="<room_id>")，
阅读 room_rules_text，确认本局启用的扩展及其组合规则。
开始后循环观察、查询可用行动、决策并提交，直到游戏结束。
轮不到你时等待事件。有版本冲突时重新观察后再决策。
```

若尚无房间，可以指示 agent 调用 `create_room(game_id="fcm", capacity=2)` 并把返回的 `id` 和 `join_code` 分享给另一位玩家。另一个玩家调用 `join_room`。房主读取当前版本，然后调用 `start_game`。每个参与者应使用不同 token，否则实际是在控制同一玩家。

## 自动发现的工具与资源

| 工具 | 用途 |
| --- | --- |
| `get_identity` | 当前 token 对应的玩家 |
| `list_games` / `get_game_rules` | 游戏发现、完整玩法说明、员工数据、规则实现范围 |
| `list_rooms` / `create_room` / `join_room` | 房间管理 |
| `start_game` | 房主启动人员齐备的游戏 |
| `observe_game` | 当前玩家的授权视图 |
| `get_available_actions` | 当前行动 Schema、候选参数和 `can_act` |
| `validate_action` | 验证完整计划，不保存模拟结果 |
| `submit_action` | 提交完整行动 |
| `get_events` | 获取公共事件，可长轮询最多 25 秒 |

`resources/list` 可以发现：

- `boardgame://guide`：玩法调用循环、重试规则、信息边界。
- `boardgame://games/fcm`：包含 `rules_text` 完整玩法说明、`game` 员工能力及版本、`implementation_notes` 实现差异。

`get_game_rules(game_id="fcm")` 返回同一份内容。玩法说明涵盖胜利目标、初始设置、所有回合阶段、招聘培训、生产营销、房屋购买选择、工资、里程碑和结束条件。握手的 `instructions` 要求 agent 在首次游戏行动前读取这些规则；不需要你手动上传 PDF。

扩展说明涵盖全部 17 个模块的玩法、时点及组合限制，但只有 `game.modules[].available=true` 的模块可开局。当前 17 个模块均已接入引擎及 UI，互斥与人数依赖仍需遵守。不要将“能读取规则”理解为“已支持运行”。

带 `room_id` 调用时，只有房间成员可读取，并返回：

- `room_config`：创建房间时选择的配置。
- `enabled_modules`：本局启用的模块 ID。
- `enabled_module_rules`：按模块 ID 索引的本局扩展说明及可用性元数据。
- `room_rules_text`：基础规则、公共组合规则、本局启用模块的规则与行动约定；不包含其他模块的详细规则章节。扩展在明确修改基础规则之处优先生效。

不带 `room_id` 的 `rules_text` / `module_rules` 是完整参考目录。入房后应使用本局规则制定行动，并以 `get_available_actions` 提供的当前 Schema 和员工集合为准。

不支持 resources 的客户端也能通过 `get_game_rules` 读取同样的游戏说明。注册新的游戏插件后，它也会自动出现在 `list_games` 和规则资源中。新游戏的完整玩法文档仍需另行接入 `get_game_rules`，不能把自动发现的元数据当作完整规则。

`start_game`、`submit_action` 要求 `expected_version` 和 `idempotency_key`。传输失败时重发相同参数和 key；发生 `version_conflict` 后用新版本和新 key。JSON-RPC 请求 ID 不代替幂等键。`create_room` 没有幂等保证，响应丢失时先 `list_rooms` 检查，不要直接重复创建。

游戏层失败使用标准 MCP `isError: true` 和文本 JSON 中的 `error.code`；未知方法和错误工具参数使用 JSON-RPC 错误。工具输入 Schema 不接受指定另一个 `player_id`、token 或现金等越权字段。

## 协议与部署范围

- 实现并协商 `2025-11-25`，兼容 `2025-06-18` 和 `2025-03-26` 的已提供能力；不声明实现更新的协议版本。
- 支持 `initialize`、`ping`、`tools/list`、`tools/call`、`resources/list`、`resources/read`、`resources/templates/list`；能力声明仅包含 tools/resources。
- HTTP POST 接收 JSON-RPC，响应 JSON；通知返回空 `202`。不创建 MCP Session ID，所有请求独立鉴权。GET 和 DELETE 返回 `405`，不提供服务器主动通知流。游戏事件通过 `get_events` 查询。
- 不支持 JSON-RPC 批处理、旧 SSE transport、prompts、sampling、后台任务或资源订阅。
- 当前使用预先签发的 Bearer token，**没有实现 MCP OAuth 授权流程**。仅支持 OAuth 登录而不能配置请求头的远程客户端不能直接连接；可使用其支持的 stdio 接入方式。
- 默认拒绝带 `Origin` 的 MCP 请求，常规非浏览器 MCP 客户端不发送该头。若确实需要授权浏览器来源，设置精确白名单，例如 `BOARDGAME_MCP_ALLOWED_ORIGINS=https://agent.example.com`，多个来源用逗号分隔。白名单不自动开启 CORS，浏览器跨域访问仍需要同源代理或反向代理配置。
- 公开部署仍需 HTTPS 和并发/速率限制。规则引擎的 FCM 开发版边界保持不变，MCP 不是新的裁判实现。

## 验证

```bash
uv run --locked python -m unittest discover -s tests -v
```

MCP 测试使用原始 HTTP 报文验证发现、规则读取、鉴权、秘密信息、幂等、错误协议、stdio 桥接和完整对局。受限环境不能开 TCP socket 时也可以运行。

还有独立的官方 SDK 互通测试（可选开发依赖，不影响服务器运行）：

```bash
uv run --locked --with 'mcp==2.3.0' python -m unittest discover -s tests -p test_mcp_sdk.py -v
```

该测试使用官方 `ClientSession` 和 Streamable HTTP transport，通过内存网络适配器访问实际服务器 HTTP 处理器，验证握手、工具列表、工具调用和资源读取。它不等于真实公网部署验证。
