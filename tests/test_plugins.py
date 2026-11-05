"""The platform must support a game with no FCM phases or employees."""

import tempfile
import unittest
from copy import deepcopy
from boardgame.core import require
from boardgame.platform import Platform
from boardgame.registry import Registry


class CoinGame:
    id = "coin"
    version = "1"

    def descriptor(self):
        return {
            "id": self.id,
            "version": self.version,
            "min_players": 2,
            "max_players": 2,
        }

    def create(self, players, config, seed):
        return {"finished": False, "roster": players, "secret": seed % 2, "guesses": {}}

    def observe(self, state, player):
        return {k: deepcopy(v) for k, v in state.items() if k != "secret"}

    def actions(self, state, player):
        return {
            "can_act": not state["finished"] and player not in state["guesses"],
            "actions": [],
        }

    def apply(self, state, player, action):
        require(self.actions(state, player)["can_act"], "Cannot guess")
        require(
            action.get("type") == "guess" and action.get("side") in [0, 1],
            "Invalid guess",
        )
        state["guesses"][player] = action["side"]
        state["finished"] = len(state["guesses"]) == 2
        return [{"type": "guessed", "player": player}]


class PluginTests(unittest.TestCase):
    def test_non_fcm_game_uses_same_platform_and_replay(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Platform(tmp + "/db", Registry([CoinGame()]))
            a = p.register("Human", "human")["id"]
            b = p.register("Agent", "agent")["id"]
            room = p.create_room(a, "coin", 2, seed=9)
            rid = room["id"]
            p.join(b, rid, room["join_code"])
            obs = p.mutate(a, rid, 1, "s", {"type": "start"}, start=True)
            self.assertNotIn("secret", obs["state"])
            p.mutate(a, rid, 2, "a", {"type": "guess", "side": 1})
            obs = p.mutate(b, rid, 3, "b", {"type": "guess", "side": 0})
            self.assertEqual(obs["status"], "finished")
            self.assertTrue(p.replay(rid)["valid"])
