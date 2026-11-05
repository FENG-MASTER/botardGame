# 增加游戏规则插件

游戏插件与传输层无关。实现 `boardgame.core.Game`：

```python
class MyGame:
    id = "my-game"
    version = "1.0.0"

    def descriptor(self):
        return {
            "id": self.id, "version": self.version,
            "min_players": 2, "max_players": 4,
            "config_schema": {"type": "object"},
        }

    def create(self, players, config, seed):
        # 验证配置。只能使用传入的 seed 生成随机结果。
        return {"finished": False, "players": players}

    def apply(self, state, player, action):
        # 验证身份是否可以行动、参数及游戏规则；失败抛 GameError。
        # 原地修改 state，返回可向所有房间成员公开的事件列表。
        # 结束时必须设置 state["finished"] = True。
        raise NotImplementedError

    def observe(self, state, player):
        # 返回一个独立的、按 player 权限裁剪的 JSON 视图。
        # 绝对不要直接返回共享 state 或内部随机状态。
        raise NotImplementedError

    def actions(self, state, player):
        # can_act、行动 Schema、候选选项及机器可读约束。
        return {"can_act": False, "actions": []}
```

通过 `Registry([FCM(), MyGame()])` 或 `registry.register(MyGame())` 注册，并注入 `Platform(database, registry)`；内置默认注册修改 `boardgame/registry.py` 即可。

平台只要求状态是 JSON 可序列化对象，且含布尔字段 `finished`。不要求阶段名、回合顺序、资源、员工或具体行动类型。插件的 `descriptor` 必须提供 `min_players`、`max_players`。`create` 会在创建房间时用临时玩家 ID 验证一次配置，在开始游戏时用真实 ID 创建一次。

所有随机性必须由 `seed` 决定，不能依赖系统时间或全局随机数。规则处理不能做外部 IO。JSON 持久化后必须仍能重复执行同一组行动：不要在状态中使用 tuple 键、集合或自定义对象。

`apply` 在平台事务中的独立状态副本上执行。失败不会写数据库；不要求规则函数自己撤销原地修改。`validate-action` 运行同一段逻辑，但丢弃结果。`observe` 与 `actions` 必须无副作用。

每次改变规则语义都增加 `version`，避免旧局被新规则悄悄解释。测试应覆盖至少一局确定性重放、非法行动回滚、信息隔离和胜负结算。平台不会替插件判断事件是否包含秘密，必须由插件自行保证其公共事件安全。

## 无决策步骤与回放兼容

游戏引擎可以在 `apply` 内连续结算没有选择的步骤，直到下一个真正需要玩家决策的边界。整个过程属于同一次平台事务和版本更新，必须确定性执行，并通过事件记录自动操作；不要在客户端分别提交自动确认请求。自动规则属于各游戏引擎，不要把 FCM 阶段写入平台。

当前开发版本不提供跨版本旧局兼容；回放要求存档与引擎版本一致。
