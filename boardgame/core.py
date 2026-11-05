"""Game-independent contracts. Engines never perform IO or authenticate clients."""

from typing import Protocol


class GameError(Exception):
    def __init__(self, code, message, status=422, details=None):
        super().__init__(message)
        self.code, self.message, self.status, self.details = (
            code,
            message,
            status,
            details,
        )


def require(condition, message, code="illegal_action", status=422):
    if not condition:
        raise GameError(code, message, status)


def integer(value, low, high, name):
    require(
        type(value) is int and low <= value <= high,
        f"{name} must be an integer in [{low}, {high}]",
        "invalid_parameters",
    )
    return value


class Game(Protocol):
    id: str
    version: str

    def descriptor(self) -> dict: ...
    def create(self, players: list[str], config: dict, seed: int) -> dict: ...
    def apply(self, state: dict, player: str, action: dict) -> list[dict]: ...
    def observe(self, state: dict, player: str | None) -> dict: ...
    def actions(self, state: dict, player: str) -> dict: ...
