"""OpenAPI 3.1 transport specification; game action schemas are discovered at runtime."""

from boardgame.schema import obj, STRING, INT, enum


def specification():
    error = obj(
        {
            "error": obj(
                {"code": STRING, "message": STRING, "details": {}}, ["code", "message"]
            )
        },
        ["error"],
    )

    def op(
        description,
        body=None,
        public=False,
        response=None,
        created=False,
        mutation=False,
    ):
        result = dict(
            summary=description,
            responses={
                str(201 if created else 200): dict(
                    description="Success",
                    content={
                        "application/json": {"schema": response or {"type": "object"}}
                    },
                ),
                **{
                    str(code): dict(
                        description=label,
                        content={"application/json": {"schema": error}},
                    )
                    for code, label in [
                        (400, "Bad request"),
                        (401, "Unauthorized"),
                        (403, "Forbidden"),
                        (404, "Not found"),
                        (409, "Conflict"),
                        (422, "Invalid action"),
                    ]
                },
            },
            security=[] if public else [{"bearerAuth": []}],
        )
        if body:
            result["requestBody"] = dict(
                required=True, content={"application/json": {"schema": body}}
            )
        if mutation:
            result["parameters"] = [
                dict(name="Idempotency-Key", in_="header", required=True, schema=STRING)
            ]
        for p in result.get("parameters", []):
            p["in"] = p.pop("in_")
        return result

    version = dict(type="integer", minimum=0)
    envelope = obj(
        {"expected_version": version, "action": {"type": "object"}},
        ["expected_version", "action"],
    )
    paths = {
        "/health": {"get": op("Liveness", public=True)},
        "/v1/identities": {
            "post": op(
                "Register a human or agent (identical privileges)",
                obj({"name": STRING, "kind": enum("human", "agent")}, ["name", "kind"]),
                public=True,
                created=True,
            )
        },
        "/v1/me": {"get": op("Current identity")},
        "/v1/games": {
            "get": op("Discover games and machine-readable rules metadata", public=True)
        },
        "/v1/games/{game_id}": {
            "get": op(
                "Game descriptor, employees and configuration schema", public=True
            ),
            "parameters": [
                {"name": "game_id", "in": "path", "required": True, "schema": STRING}
            ],
        },
        "/v1/rooms": {
            "get": op("List your rooms"),
            "post": op(
                "Create a private lobby",
                obj(
                    {
                        "game": STRING,
                        "capacity": INT,
                        "config": {"type": "object"},
                        "seed": INT,
                    },
                    ["game", "capacity"],
                ),
                created=True,
            ),
        },
        "/v1/rooms/{room_id}": {
            "get": op("Get your authorized observation, never raw engine state")
        },
        "/v1/rooms/{room_id}/join": {
            "post": op(
                "Join with room invite code", obj({"join_code": STRING}, ["join_code"])
            )
        },
        "/v1/rooms/{room_id}/start": {
            "post": op(
                "Owner starts a full lobby",
                obj({"expected_version": version}, ["expected_version"]),
                mutation=True,
            )
        },
        "/v1/rooms/{room_id}/actions": {
            "get": op("Discover available action types, JSON schemas and choices"),
            "post": op("Atomically submit an action", envelope, mutation=True),
        },
        "/v1/rooms/{room_id}/validate-action": {
            "post": op(
                "Validate a candidate action without saving or returning hidden outcomes",
                envelope,
            )
        },
        "/v1/rooms/{room_id}/events": {
            "get": op("Redacted event journal, JSON long polling or resumable SSE")
        },
        "/openapi.json": {"get": op("OpenAPI schema", public=True)},
    }
    for path, entry in paths.items():
        if "{room_id}" in path:
            entry["parameters"] = [
                {"name": "room_id", "in": "path", "required": True, "schema": STRING}
            ]
    paths["/v1/identities"]["post"]["parameters"] = [
        {
            "name": "X-Registration-Key",
            "in": "header",
            "required": False,
            "schema": STRING,
            "description": "Required if server registration key is configured.",
        }
    ]
    paths["/v1/rooms/{room_id}/events"]["get"]["parameters"] = [
        {
            "name": name,
            "in": "query",
            "schema": dict(
                type="integer", minimum=0, **({"maximum": 25} if name == "wait" else {})
            ),
        }
        for name in ("after", "wait")
    ]
    return dict(
        openapi="3.1.0",
        info=dict(title="Boardgame API", version="0.1.0"),
        paths=paths,
        components=dict(
            securitySchemes=dict(bearerAuth=dict(type="http", scheme="bearer"))
        ),
    )
