"""SQLite transaction boundary, identity, lobbies, replay journal and redacted events."""

import hashlib
import json
import secrets
import sqlite3
import time
import uuid
from contextlib import closing, contextmanager
from copy import deepcopy
from boardgame.core import require, integer
from boardgame.registry import Registry


def encode(value):
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()


def uid():
    return uuid.uuid4().hex


class Platform:
    def __init__(self, database="boardgame.sqlite3", registry=None):
        self.database = str(database)
        self.registry = registry or Registry()
        with closing(sqlite3.connect(self.database)) as db:
            db.execute("PRAGMA journal_mode=WAL")
            db.executescript("""
                CREATE TABLE IF NOT EXISTS identities(id TEXT PRIMARY KEY,name TEXT NOT NULL,kind TEXT NOT NULL,token_hash TEXT UNIQUE NOT NULL,created REAL NOT NULL);
                CREATE TABLE IF NOT EXISTS rooms(id TEXT PRIMARY KEY,owner TEXT NOT NULL,game TEXT NOT NULL,engine_version TEXT NOT NULL,config TEXT NOT NULL,seed INTEGER NOT NULL,capacity INTEGER NOT NULL,join_hash TEXT NOT NULL,status TEXT NOT NULL,version INTEGER NOT NULL,state TEXT,created REAL NOT NULL);
                CREATE TABLE IF NOT EXISTS members(room TEXT NOT NULL,player TEXT NOT NULL,seat INTEGER NOT NULL,PRIMARY KEY(room,player),UNIQUE(room,seat));
                CREATE TABLE IF NOT EXISTS journal(room TEXT NOT NULL,version INTEGER NOT NULL,actor TEXT NOT NULL,action TEXT NOT NULL,events TEXT NOT NULL,created REAL NOT NULL,PRIMARY KEY(room,version));
                CREATE TABLE IF NOT EXISTS requests(room TEXT NOT NULL,actor TEXT NOT NULL,key TEXT NOT NULL,fingerprint TEXT NOT NULL,response TEXT NOT NULL,PRIMARY KEY(room,actor,key));
                CREATE INDEX IF NOT EXISTS member_player ON members(player);
            """)

    @contextmanager
    def connect(self, write=False):
        db = sqlite3.connect(self.database, timeout=15, isolation_level=None)
        db.row_factory = sqlite3.Row
        try:
            db.execute("PRAGMA foreign_keys=ON")
            db.execute("BEGIN IMMEDIATE" if write else "BEGIN")
            yield db
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    def register(self, name, kind):
        require(
            isinstance(name, str) and 1 <= len(name.strip()) <= 80,
            "name must contain 1–80 characters",
            "invalid_parameters",
        )
        require(
            kind in ("human", "agent"),
            "kind must be human or agent",
            "invalid_parameters",
        )
        token = secrets.token_urlsafe(32)
        pid = uid()
        with self.connect(True) as db:
            db.execute(
                "INSERT INTO identities VALUES(?,?,?,?,?)",
                (pid, name.strip(), kind, digest(token), time.time()),
            )
        return dict(id=pid, name=name.strip(), kind=kind, token=token)

    def authenticate(self, token):
        require(
            isinstance(token, str) and token,
            "Bearer token required",
            "unauthorized",
            401,
        )
        with self.connect() as db:
            row = db.execute(
                "SELECT id,name,kind FROM identities WHERE token_hash=?",
                (digest(token),),
            ).fetchone()
        require(row is not None, "Invalid bearer token", "unauthorized", 401)
        return dict(row)

    def room(self, db, rid, pid):
        room = db.execute("SELECT * FROM rooms WHERE id=?", (rid,)).fetchone()
        require(room is not None, "Room not found", "not_found", 404)
        require(
            db.execute(
                "SELECT 1 FROM members WHERE room=? AND player=?", (rid, pid)
            ).fetchone(),
            "Room membership required",
            "forbidden",
            403,
        )
        return dict(room)

    def members(self, db, rid):
        return [
            dict(row)
            for row in db.execute(
                "SELECT i.id,i.name,i.kind,m.seat FROM members m JOIN identities i ON i.id=m.player WHERE m.room=? ORDER BY seat",
                (rid,),
            )
        ]

    def snapshot(self, db, room, pid):
        result = {
            k: room[k]
            for k in (
                "id",
                "owner",
                "game",
                "engine_version",
                "capacity",
                "status",
                "version",
            )
        }
        result["members"] = self.members(db, room["id"])
        result["config"] = json.loads(room["config"])
        result["state"] = (
            self.registry.get(room["game"]).observe(json.loads(room["state"]), pid)
            if room["state"]
            else None
        )
        return result

    def create_room(self, pid, game_id, capacity, config=None, seed=None):
        game = self.registry.get(game_id)
        desc = game.descriptor()
        integer(capacity, desc["min_players"], desc["max_players"], "capacity")
        config = {} if config is None else config
        require(
            isinstance(config, dict), "config must be an object", "invalid_parameters"
        )
        seed = (
            secrets.randbelow(2**31)
            if seed is None
            else integer(seed, 0, 2**31 - 1, "seed")
        )
        # Validate scenario before making an unusable lobby. No IO in game engines.
        game.create(
            [f"validation-{i}" for i in range(capacity)], deepcopy(config), seed
        )
        rid = uid()
        code = secrets.token_urlsafe(18)
        with self.connect(True) as db:
            db.execute(
                "INSERT INTO rooms VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    rid,
                    pid,
                    game_id,
                    game.version,
                    encode(config),
                    seed,
                    capacity,
                    digest(code),
                    "lobby",
                    0,
                    None,
                    time.time(),
                ),
            )
            db.execute("INSERT INTO members VALUES(?,?,?)", (rid, pid, 0))
            result = self.snapshot(db, self.room(db, rid, pid), pid)
        result["join_code"] = code
        return result

    def list_rooms(self, pid):
        with self.connect() as db:
            return [
                dict(r)
                for r in db.execute(
                    "SELECT r.id,r.game,r.status,r.version,r.capacity FROM rooms r JOIN members m ON r.id=m.room WHERE m.player=? ORDER BY r.created DESC LIMIT 100",
                    (pid,),
                )
            ]

    def get(self, pid, rid):
        with self.connect() as db:
            return self.snapshot(db, self.room(db, rid, pid), pid)

    def join(self, pid, rid, code):
        require(
            isinstance(code, str), "join_code must be a string", "invalid_parameters"
        )
        with self.connect(True) as db:
            row = db.execute("SELECT * FROM rooms WHERE id=?", (rid,)).fetchone()
            require(row is not None, "Room not found", "not_found", 404)
            room = dict(row)
            require(
                secrets.compare_digest(room["join_hash"], digest(code)),
                "Invalid join code",
                "forbidden",
                403,
            )
            members = self.members(db, rid)
            if pid not in [p["id"] for p in members]:
                require(
                    room["status"] == "lobby" and len(members) < room["capacity"],
                    "Lobby unavailable",
                    "conflict",
                    409,
                )
                db.execute(
                    "INSERT INTO members VALUES(?,?,?)", (rid, pid, len(members))
                )
                room["version"] += 1
                db.execute(
                    "UPDATE rooms SET version=? WHERE id=?", (room["version"], rid)
                )
                self.journal(
                    db,
                    rid,
                    room["version"],
                    pid,
                    {"type": "join"},
                    [dict(type="player_joined", player=pid)],
                )
            return self.snapshot(db, room, pid)

    def journal(self, db, rid, version, pid, action, events):
        db.execute(
            "INSERT INTO journal VALUES(?,?,?,?,?,?)",
            (rid, version, pid, encode(action), encode(events), time.time()),
        )

    def mutate(self, pid, rid, expected, key, action, start=False, dry_run=False):
        integer(expected, 0, 2**53 - 1, "expected_version")
        require(
            isinstance(action, dict), "action must be an object", "invalid_parameters"
        )
        if not dry_run:
            require(
                isinstance(key, str) and 1 <= len(key) <= 128,
                "Idempotency-Key required (1–128 characters)",
                "invalid_parameters",
            )
        fingerprint = digest(encode(dict(version=expected, action=action, start=start)))
        with self.connect(not dry_run) as db:
            room = self.room(db, rid, pid)
            if not dry_run:
                cached = db.execute(
                    "SELECT * FROM requests WHERE room=? AND actor=? AND key=?",
                    (rid, pid, key),
                ).fetchone()
                if cached:
                    require(
                        cached["fingerprint"] == fingerprint,
                        "Idempotency key was used for a different request",
                        "idempotency_conflict",
                        409,
                    )
                    return json.loads(cached["response"])
            require(
                room["version"] == expected,
                "State changed; fetch latest observation",
                "version_conflict",
                409,
            )
            game = self.registry.get(room["game"])
            require(
                game.version == room["engine_version"],
                "Engine version changed; migrate this room before continuing",
                "engine_version_mismatch",
                409,
            )
            if start:
                require(
                    pid == room["owner"], "Only room owner can start", "forbidden", 403
                )
                require(
                    room["status"] == "lobby", "Room already started", "conflict", 409
                )
                members = self.members(db, rid)
                require(
                    len(members) == room["capacity"],
                    "Waiting for players",
                    "conflict",
                    409,
                )
                state = game.create(
                    [p["id"] for p in members], json.loads(room["config"]), room["seed"]
                )
                events = [dict(type="game_started")]
            else:
                require(
                    room["status"] == "active", "Game is not active", "conflict", 409
                )
                state = json.loads(room["state"])
                events = game.apply(state, pid, deepcopy(action))
            if dry_run:
                return dict(valid=True, version=room["version"])
            room["version"] += 1
            room["state"] = encode(state)
            room["status"] = "finished" if state["finished"] else "active"
            db.execute(
                "UPDATE rooms SET state=?,version=?,status=? WHERE id=?",
                (room["state"], room["version"], room["status"], rid),
            )
            # Raw actions are stored only in the private journal. Public events
            # never embed reserve choices or unrevealed organization plans.
            public = [
                dict(
                    type="action_submitted", player=pid, action_type=action.get("type")
                )
            ] + events
            self.journal(db, rid, room["version"], pid, action, public)
            response = self.snapshot(db, room, pid)
            db.execute(
                "INSERT INTO requests VALUES(?,?,?,?,?)",
                (rid, pid, key, fingerprint, encode(response)),
            )
            return response

    def actions(self, pid, rid):
        with self.connect() as db:
            room = self.room(db, rid, pid)
            return dict(
                version=room["version"],
                **(
                    self.registry.get(room["game"]).actions(
                        json.loads(room["state"]), pid
                    )
                    if room["state"]
                    else dict(can_act=False, actions=[], reason="lobby")
                ),
            )

    def events(self, pid, rid, after=0, limit=100):
        integer(after, 0, 2**53 - 1, "after")
        integer(limit, 1, 500, "limit")
        with self.connect() as db:
            room = self.room(db, rid, pid)
            rows = db.execute(
                "SELECT version,events,created FROM journal WHERE room=? AND version>? ORDER BY version LIMIT ?",
                (rid, after, limit),
            ).fetchall()
            events = [
                dict(
                    version=r["version"],
                    events=json.loads(r["events"]),
                    created=r["created"],
                )
                for r in rows
            ]
            return dict(
                version=room["version"],
                cursor=events[-1]["version"] if events else after,
                events=events,
            )

    def replay(self, rid):
        """Local administrative audit. Deliberately not exposed over HTTP."""
        with self.connect() as db:
            row = db.execute("SELECT * FROM rooms WHERE id=?", (rid,)).fetchone()
            require(row is not None, "Room not found", "not_found", 404)
            room = dict(row)
            game = self.registry.get(room["game"])
            require(
                game.version == room["engine_version"],
                "Replay needs the original engine version",
            )
            state = None
            for row in db.execute(
                "SELECT actor,action,events FROM journal WHERE room=? ORDER BY version",
                (rid,),
            ):
                action = json.loads(row["action"])
                if action["type"] == "start":
                    state = game.create(
                        [p["id"] for p in self.members(db, rid)],
                        json.loads(room["config"]),
                        room["seed"],
                    )
                elif action["type"] != "join":
                    game.apply(state, row["actor"], action)
            require(
                encode(state) == room["state"],
                "Replay mismatch",
                "replay_mismatch",
                500,
            )
            return dict(valid=True, version=room["version"])
