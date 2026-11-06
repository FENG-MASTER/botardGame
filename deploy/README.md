# 生产部署手册

本文件供后续会话直接执行部署使用。用户说“部署”时，默认更新以下实例，保留线上游玩数据。

## 当前生产环境

| 项目 | 值 |
| --- | --- |
| SSH | `ubuntu@106.55.228.236` |
| 连接方式 | `ssh -F /dev/null ubuntu@106.55.228.236`，默认密钥，免密码 sudo |
| UI | <https://106.55.228.236:8082> |
| API | `https://106.55.228.236:8082/api/v1/` |
| MCP | `https://106.55.228.236:8082/api/mcp`，沿用原 Bearer token |
| 健康检查 | `https://106.55.228.236:8082/api/health` |
| 前端容器 | `boardgame-ui`，`botardgame-ui:milestones-20261106`，`8082:5173` |
| 后端容器 | `boardgame-api`，`botardgame-api:scope-20261106`，内部 8000，不映射公网 |
| Docker 网络 | `botardgame` |
| 重启策略 | 两个容器都是 `unless-stopped` |
| 数据目录 | `/home/ubuntu/botardgame/data`，容器内 `/data` |
| SQLite | `/home/ubuntu/botardgame/data/boardgame.sqlite3` |
| 数据权限 | UID/GID 10001，目录 700，数据库 600 |
| 当前代码目录 | 后端 `/home/ubuntu/botardgame-release-scope-20261106`；前端 `/home/ubuntu/botardgame-release-milestones-20261106` |
| TLS | 自签名，服务器 `/home/ubuntu/botardgame/tls` 只读挂载 `/tls`；设置 `TLS_CERT_FILE=/tls/server.crt`、`TLS_KEY_FILE=/tls/server.key` |
| 公钥证书 | 本项目 `deploy/certs/production.crt`；私钥只在服务器，不能提交 Git |
| 前端上游 | `http://boardgame-api:8000`，通过 `/api/` 同源代理 |

**固定使用 8082，用户明确不要 80。** 8080 是 qqbot，8081 是 silentwerewolf，6099 是 napcat；不得占用这些端口或操作这些应用的容器。

## 日常更新流程

`publish.sh` 和 `install-remote.sh` 只用于首次安装并迁移开发库，遇到已有容器／数据库会拒绝执行。**日常更新不要直接运行它们，也不要把本地数据库覆盖到生产。** 后续执行者按以下流程更新：

1. 阅读本文件及根目录 `AGENTS.md`。检查 `docker ps`、端口、磁盘、目标容器 `docker inspect`。以实际配置为准，保留环境变量、挂载、网络和重启策略，不在输出中泄露凭证。
2. 按改动运行相关验证。Python 使用 `uv run --locked python -m unittest discover -s tests`；UI 使用 `node --test --test-isolation=none human-ui/tests/*.test.mjs` 和 `npm --prefix human-ui run check`。
3. 创建唯一发布目录，上传代码包（不含游玩数据库）。可在本机用以下命令打包：

   ```sh
   mkdir -p deploy/artifacts
   tar --exclude='__pycache__' --exclude='*.pyc' --exclude='node_modules' \
     --exclude='.env' --exclude='.env.*' --exclude='coverage' \
     -czf deploy/artifacts/code-release.tar.gz \
     boardgame human-ui pyproject.toml uv.lock .python-version README.md \
     Dockerfile .dockerignore doc/FCM_RULES.md doc/FCM_IMPLEMENTATION.md doc/FCM_EXPANSIONS.md
   ```

   使用 `ssh -F /dev/null` 创建 `~/botardgame-release-<时间戳>`（权限 700），用 `scp -F /dev/null` 上传，在该目录解压。
4. 在新目录先构建两个镜像，使用唯一版本标签，例如 `botardgame-api:<时间戳>`、`botardgame-ui:<时间戳>`。后端构建上下文为发布目录，前端为 `human-ui`。保留旧镜像，构建失败时不要停止现有服务。首次 uv 镜像从 ghcr.io 下载较慢，后续可复用缓存。
5. 切换前停止 `boardgame-ui`，再停止 `boardgame-api`，避免备份之后继续接受行动。记录短暂维护开始。使用宿主机 `sudo python3` 的 `sqlite3.Connection.backup()` 将线上库备份到 `/home/ubuntu/botardgame/backups/<时间戳>.sqlite3`，检查 `PRAGMA integrity_check` 为 `ok`；备份目录 700、文件 600。不要在运行期间仅复制主库而遗漏 WAL。备份失败即重启旧容器并停止发布。
6. 将旧容器重命名为带时间戳的名称，保留配置和镜像用于回滚；启动新容器。当前基础运行参数如下，如 inspect 发现新增配置须一并保留：

   ```sh
   sudo docker run -d --name boardgame-api --restart unless-stopped \
     --network botardgame -v /home/ubuntu/botardgame/data:/data \
     botardgame-api:<时间戳>
   sudo docker run -d --name boardgame-ui --restart unless-stopped \
     --network botardgame -p 8082:5173 \
     -v /home/ubuntu/botardgame/tls:/tls:ro \
     -e TLS_CERT_FILE=/tls/server.crt -e TLS_KEY_FILE=/tls/server.key \
     botardgame-ui:<时间戳>
   ```

   始终挂载原线上 data 目录，不导入开发库。若代码涉及数据库或游戏状态格式变化，部署前需明确迁移方式及回滚兼容性。
7. 检查服务器内及公网健康接口、首页和入口 JS；检查匿名 MCP 为 401。需要认证功能验证时使用经授权的凭证，不打印 token。核对已有房间与版本仍在，无意外清空、重置。
8. 成功后记录版本标签、发布目录、备份位置和验证结果。旧容器应关闭自动重启（`docker update --restart=no <旧容器>`），保持停止，防止重启宿主机时启动旧版。保留一个可回滚版本，后续按磁盘情况清理本项目旧版本；不执行全局 Docker prune。

### 回滚

若健康检查失败，停止并移除本次新建的两个容器，将保留的旧容器改回 `boardgame-api`、`boardgame-ui` 并恢复 `unless-stopped`，先启动后端再启动前端，然后再次检查。只操作本次发布涉及的容器。

代码兼容时继续使用现有线上数据库。**不要自动恢复数据库备份**：新版本可能已经接受玩家行动；恢复前必须评估数据损失与格式兼容性。存在不兼容迁移时执行事先确定的回滚方案。

## 常用检查

```sh
ssh -F /dev/null ubuntu@106.55.228.236
sudo docker ps
sudo docker logs --tail 100 boardgame-api
sudo docker logs --tail 100 boardgame-ui
curl --cacert /home/ubuntu/botardgame/tls/server.crt -fsS https://127.0.0.1:8082/api/health
```

公网检查（从本机执行）：

```sh
curl --cacert deploy/certs/production.crt --noproxy '*' --connect-timeout 8 --max-time 15 https://106.55.228.236:8082/api/health
curl --cacert deploy/certs/production.crt --noproxy '*' --connect-timeout 8 --max-time 15 -o /dev/null -w '%{http_code}\n' https://106.55.228.236:8082/
curl --cacert deploy/certs/production.crt --noproxy '*' --connect-timeout 8 --max-time 15 -o /dev/null -w '%{http_code}\n' https://106.55.228.236:8082/src/app.js
curl --cacert deploy/certs/production.crt --noproxy '*' --connect-timeout 8 --max-time 15 -o /dev/null -w '%{http_code}\n' https://106.55.228.236:8082/api/mcp
```

预期：健康接口 200 / `status=ok`，首页及 JS 200，匿名 MCP 401 / `Bearer token required`。401 仅证明公网鉴权入口响应正常，不等于已验证携带凭证的完整 MCP 调用。

若服务器内部正常但公网超时，检查腾讯云安全组／轻量服务器防火墙入站 TCP 8082。当前该规则已由用户放通并验证。沙箱阻止 SSH 时按工具权限申请宿主机执行，不要把本地 `socket: Operation not permitted` 误判为远端密码错误。

## 首次安装工具与数据说明

- `prepare.py`：SQLite backup API 一致性备份开发库并打包，输出到私有 `artifacts` 目录。
- `publish.sh`：上传首次安装包并调用 `install-remote.sh`；不是日常更新命令。
- `install-remote.sh`：初次构建容器并导入开发数据，拒绝覆盖已有线上库。
- `verify-remote.py`：首次迁移的逐表对照工具，要求容器内 `/snapshot.sqlite3`。线上开始新行动后，本就不应再等于初次快照，不能把此工具作为日常更新验收条件。
- `artifacts/` 已排除 Git；其中首次发布包含身份和游玩数据库，不得公开。

数据库保存的是凭证哈希，原 token 仍有效。浏览器 sessionStorage 不跨域迁移，用户需从旧 UI 保存身份凭证后在新 UI 导入，才能继续旧座位。Agent 只需修改 MCP URL 并沿用 token。

## 最近一次部署记录：2026-11-06

已将开发环境迁移到上述生产实例，包含 3 个身份、2 个房间、4 个成员关系、44 条行动日志、42 条幂等请求记录，逐表一致，SQLite 完整性检查通过。生产后续数据以线上库为准。

- 后端 105 项测试完成，4 项跳过；前端 17 项通过。
- 服务器内 MCP 规则及中文员工目录核对通过。
- 用户要求不用 80，最终映射改为 `8082:5173`。
- 用户放通 8082 后，公网首页、JS、健康接口均 200，匿名 MCP 401。
- 原有 qqbot、silentwerewolf、napcat 服务保持运行。

## 历史版本：邀请注册与自签名 HTTPS（2026-11-06）

当前镜像为 `botardgame-api:invitations-20261106` 与 `botardgame-ui:invitations-20261106`。后续部署必须保留 TLS 文件挂载和两个环境变量，不能回退成明文 HTTP。详见 [邀请与证书接入](INVITATIONS.md)。私钥不得上传、打印或提交 Git。公钥证书每次更新后必须记录指纹并通知客户端更新信任。

- 发布目录：`/home/ubuntu/botardgame-release-invitations-20261106`
- 发布前数据库备份：`/home/ubuntu/botardgame/backups/before-invitations-20261106.sqlite3`
- 旧容器：`boardgame-api-before-invitations-20261106`、`boardgame-ui-before-invitations-20261106`，均已停止且自动重启关闭。旧版本没有邀请注册和 TLS，若回滚会失去这两项保护，不能忽略这一影响。
- 证书有效期：2026-11-06 03:16:22 UTC 至 2027-11-06 03:16:22 UTC。
- SHA-256：`82:F2:D5:6B:9C:C1:CF:F5:A1:8E:EB:AA:D1:79:F9:87:AF:4F:7B:F0:CF:BB:03:13:D0:C2:E6:2B:A4:AB:8A:35`
- 109 项后端测试通过（4 项跳过），18 项前端测试通过。
- 使用公钥证书校验的公网 HTTPS 首页、JS 和健康检查均 200；缺少／伪造邀请码注册均 403，邀请审计及 MCP 匿名访问 401，私钥路径 404。
- 原 3 个账号、2 个房间、44 条行动日志等与发布前备份逐表一致；原 token 保留。首次上线时 3 个账号各有 1 个可证明的登录日，尚无满足 3 天门槛的用户，不绕过门槛发放邀请码。

`rollout-invitations-20261106.sh` 是本次一次性发布脚本，保留作为发布记录，不要原样重复执行。普通更新按上文流程生成新的版本标签与备份。`verify-invitations-production.py` 仅用于本次切换后对照备份；有新活动后不能再要求游戏数据完全相等。


## 历史版本：手机布局与本轮日志（2026-11-06）

- 镜像：`botardgame-api:mobile-20261106`、`botardgame-ui:mobile-20261106`。
- 发布目录：`/home/ubuntu/botardgame-release-mobile-20261106`。
- 发布前备份：`/home/ubuntu/botardgame/backups/before-mobile-20261106-r2.sqlite3`。
- 回滚容器：`boardgame-api-before-mobile-20261106-r2`、`boardgame-ui-before-mobile-20261106-r2`；保留邀请注册和 HTTPS 的前一版。
- 手机顺序：地图、玩家本轮排序、自己的公司及操作、本轮日志、同桌玩家详情、里程碑、完整对局记录。390px 实测无页面横向溢出，1280px 桌面操作栏正常。
- 后端 110 项测试完成（4 项跳过），前端 20 项通过；旧对局在一致性副本上重放均匹配，当前第 2 / 5 轮事件正常归属。
- 第一次切换因包内代码权限使非 root 进程无法读取 pyproject.toml，已自动回滚。Dockerfile 现在明确赋予镜像内代码读取权限，并验证普通用户能导入服务器模块；不改变数据库权限。
- 本次脚本 `rollout-mobile-20261106.sh` 为一次性记录，不要重复运行。日常发布仍按前述流程使用新标签和备份。
- 最终公网验证：使用 production.crt 校验 HTTPS，首页、app.js、round-log.js、style.css 和健康接口均 200；匿名 MCP 与房间列表均 401。
- 切换后与即时备份逐表核对：3 个身份、2 个房间、4 个成员关系、48 条行动记录、46 条幂等请求完全一致，身份凭证与邀请记录保留。两个旧容器已停止，自动重启关闭。


## 后端当前版本：按房间裁剪扩展公共接口（2026-11-06）

- 镜像：`botardgame-api:scope-20261106`、`botardgame-ui:scope-20261106`。
- 发布目录：`/home/ubuntu/botardgame-release-scope-20261106`。
- 备份：`/home/ubuntu/botardgame/backups/before-scope-20261106.sqlite3`。
- 回滚容器：`boardgame-api-before-scope-20261106`、`boardgame-ui-before-scope-20261106`，为上一版手机布局版本，已停止且关闭自动重启。
- 公共房间响应增加 `catalog`。库存、行动 Schema、员工晋升路径、里程碑、地图附属字段、MCP 指定房间规则和旧幂等响应按模块裁剪；全局发现目录仍明确保留全部可选扩展。提交不存在的扩展字段（包括空值）返回 invalid_parameters，旧 Agent 应重新读取本房间规则和动作 Schema。
- 内部持久化格式及历史重放行为不变，没有数据迁移。两个已有基础版对局的公开观察与 MCP 规则均仅返回基础五种产品；副本重放验证通过。
- 后端 113 项测试完成（4 项跳过），前端 20 项通过。模块矩阵覆盖全部 17 个模块、多扩展组合、禁用参数拒绝、幂等旧响应、HTTP / MCP 一致性和自定义场景约束。
- 一次性发布脚本 `rollout-scope-20261106.sh`；不可重复运行，后续必须新建版本目录、标签、备份。`verify-room-scope.py` 在副本上检验公共接口及重放，`verify-scope-production.py` 仅用于本次即时备份对照。
- 最终公网验证：信任 production.crt 的 HTTPS 首页、app.js、model.js、fcm.js 和健康接口均正常；匿名 MCP、房间列表均 401。发布后账号、房间、成员、日志、幂等表与即时备份逐表一致：3 / 2 / 4 / 48 / 46，凭证及邀请数据保留。


## 前端历史版本：紧凑员工卡（2026-11-06）

- 仅 CSS 调整：名称与状态合为一行，减少内边距，移除装饰图标和能力区固定留白；手机每行两张，自己与同桌玩家共用样式。
- UI 镜像 `botardgame-ui:compact-20261106`，代码目录 `/home/ubuntu/botardgame-release-compact-20261106`；后端保持 `botardgame-api:scope-20261106`，本次未重启。
- SQLite 在线一致性备份 `/home/ubuntu/botardgame/backups/before-compact-20261106.sqlite3`，完整性检查通过；此次前端发布不修改数据库。
- 回滚 UI `boardgame-ui-before-compact-20261106`，已停止且关闭自动重启。一次性脚本 `rollout-compact-20261106.sh` 不可重复运行。
- 浏览器验证：390px 下预览员工卡高约 79px；320px 下按内容换行约 79–94px，两种宽度均无页面横向溢出。
- 公网 CSS 与本地修改逐字一致；首页、JS、健康检查 200，匿名 MCP 401。HTTPS、端口和数据挂载保持现有配置。


## 前端当前版本：紧凑成就卡（2026-11-06）

- UI 镜像 `botardgame-ui:milestones-20261106`；目录 `/home/ubuntu/botardgame-release-milestones-20261106`。后端仍为 `botardgame-api:scope-20261106`。
- 成就卡手机每行两张，缩小内边距与间距，名称、领取状态及全部获得者保留。390px 和 320px 浏览器实测均无横向溢出；里程碑获得者、关闭状态及扩展池回归测试通过。
- 在线一致性备份 `/home/ubuntu/botardgame/backups/before-milestones-20261106.sqlite3`；本次只更新前端，不修改数据库。
- 回滚 UI `boardgame-ui-before-milestones-20261106`，已停止且自动重启关闭；一次性脚本 `rollout-milestones-20261106.sh` 不可重复运行。
- 公网 CSS 与本地一致；HTTPS 首页、JS、健康检查 200，匿名 MCP 401。
