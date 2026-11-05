from boardgame.core import require
from boardgame.games.fcm.engine import FCM


class Registry:
    def __init__(self, games=None):
        self._games = {}
        for game in games if games is not None else [FCM()]:
            self.register(game)

    def register(self, game):
        require(game.id not in self._games, "Duplicate game id")
        self._games[game.id] = game

    def get(self, game_id):
        require(
            isinstance(game_id, str) and game_id in self._games,
            "Unknown game",
            "not_found",
            404,
        )
        return self._games[game_id]

    def describe(self):
        return [g.descriptor() for g in self._games.values()]
