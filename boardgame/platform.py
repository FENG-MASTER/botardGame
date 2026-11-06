"""SQLite transaction boundary, identity, lobbies, replay journal and redacted events."""

import hashlib
import json
import secrets
import sqlite3
import time
import uuid
from datetime import datetime, timezone, timedelta
from contextlib import closing, contextmanager
from copy import deepcopy
from boardgame.core import require, integer, GameError
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
        self._event_history_cache = {}
        with closing(sqlite3.connect(self.database)) as db:
            db.execute("PRAGMA journal_mode=WAL")
            db.executescript("""
                CREATE TABLE IF NOT EXISTS identities(id TEXT PRIMARY KEY,name TEXT NOT NULL,kind TEXT NOT NULL,token_hash TEXT UNIQUE NOT NULL,created REAL NOT NULL);
                CREATE TABLE IF NOT EXISTS rooms(id TEXT PRIMARY KEY,owner TEXT NOT NULL,game TEXT NOT NULL,engine_version TEXT NOT NULL,config TEXT NOT NULL,seed INTEGER NOT NULL,capacity INTEGER NOT NULL,join_hash TEXT NOT NULL,status TEXT NOT NULL,version INTEGER NOT NULL,state TEXT,created REAL NOT NULL);
                CREATE TABLE IF NOT EXISTS members(room TEXT NOT NULL,player TEXT NOT NULL,seat INTEGER NOT NULL,PRIMARY KEY(room,player),UNIQUE(room,seat));
                CREATE TABLE IF NOT EXISTS journal(room TEXT NOT NULL,version INTEGER NOT NULL,actor TEXT NOT NULL,action TEXT NOT NULL,events TEXT NOT NULL,created REAL NOT NULL,PRIMARY KEY(room,version));
                CREATE TABLE IF NOT EXISTS requests(room TEXT NOT NULL,actor TEXT NOT NULL,key TEXT NOT NULL,fingerprint TEXT NOT NULL,response TEXT NOT NULL,PRIMARY KEY(room,actor,key));
                CREATE INDEX IF NOT EXISTS member_player ON members(player);
                CREATE TABLE IF NOT EXISTS login_days(player TEXT NOT NULL REFERENCES identities(id), day TEXT NOT NULL, first_seen REAL NOT NULL, PRIMARY KEY(player,day));
                CREATE TABLE IF NOT EXISTS invitations(id TEXT PRIMARY KEY, code_hash TEXT UNIQUE NOT NULL, inviter TEXT NOT NULL REFERENCES identities(id), created REAL NOT NULL, expires REAL NOT NULL, invitee TEXT UNIQUE REFERENCES identities(id), used_at REAL, revoked_at REAL);
                CREATE INDEX IF NOT EXISTS invitation_inviter ON invitations(inviter);
                INSERT OR IGNORE INTO login_days(player,day,first_seen)
                    SELECT actor, strftime('%Y-%m-%d',created,'unixepoch','+8 hours'), min(created)
                    FROM journal WHERE actor IN (SELECT id FROM identities) GROUP BY actor, strftime('%Y-%m-%d',created,'unixepoch','+8 hours');
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

    def register(self, name, kind, invite_code=None, *, require_invite=False):
        """Local administrative bootstrap may omit a code; public transports MUST require it."""
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
        now = time.time()
        with self.connect(True) as db:
            invitation = None
            if require_invite:
                require(isinstance(invite_code, str) and 1 <= len(invite_code) <= 200,
                        "注册必须填写邀请码", "invitation_required", 403)
                invitation = db.execute("SELECT * FROM invitations WHERE code_hash=?", (digest(invite_code.strip()),)).fetchone()
                require(invitation is not None and invitation["invitee"] is None
                        and invitation["revoked_at"] is None and invitation["expires"] > now,
                        "邀请码无效、已使用、已撤销或已过期", "invalid_invitation", 403)
            db.execute(
                "INSERT INTO identities VALUES(?,?,?,?,?)",
                (pid, name.strip(), kind, digest(token), now),
            )
            db.execute("INSERT INTO login_days VALUES(?,?,?)", (pid, self.login_day(now), now))
            if invitation is not None:
                db.execute("UPDATE invitations SET invitee=?,used_at=? WHERE id=?", (pid, now, invitation["id"]))
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
        now = time.time()
        day = self.login_day(now)
        with self.connect() as db:
            recorded = db.execute("SELECT 1 FROM login_days WHERE player=? AND day=?", (row["id"], day)).fetchone()
        if not recorded:
            with self.connect(True) as db:
                db.execute("INSERT OR IGNORE INTO login_days VALUES(?,?,?)", (row["id"], day, now))
        return dict(row)

    @staticmethod
    def login_day(now):
        return datetime.fromtimestamp(now, timezone(timedelta(hours=8))).date().isoformat()

    def invitations(self, pid):
        now = time.time()
        with self.connect() as db:
            days = [r[0] for r in db.execute("SELECT day FROM login_days WHERE player=? ORDER BY day", (pid,))]
            rows = db.execute("SELECT v.id,v.created,v.expires,v.used_at,v.revoked_at,v.invitee,i.name AS invitee_name FROM invitations v LEFT JOIN identities i ON i.id=v.invitee WHERE v.inviter=? ORDER BY v.created DESC LIMIT 100", (pid,)).fetchall()
        invitations = []
        for row in rows:
            item = dict(row)
            item["status"] = "used" if row["used_at"] is not None else "revoked" if row["revoked_at"] is not None else "expired" if row["expires"] <= now else "available"
            invitations.append(item)
        return dict(login_days=len(days), required_days=3, timezone="Asia/Shanghai", eligible=len(days)>=3, dates=days, invitations=invitations)

    def create_invitation(self, pid):
        now = time.time()
        code = secrets.token_urlsafe(24)
        invitation_id = uid()
        with self.connect(True) as db:
            days = db.execute("SELECT count(*) FROM login_days WHERE player=?", (pid,)).fetchone()[0]
            require(days >= 3, "需在至少 3 个不同自然日登录后才能生成邀请码（北京时间）", "invitation_not_eligible", 403)
            active = db.execute("SELECT count(*) FROM invitations WHERE inviter=? AND invitee IS NULL AND revoked_at IS NULL AND expires>?", (pid, now)).fetchone()[0]
            today = db.execute("SELECT count(*) FROM invitations WHERE inviter=? AND created>?", (pid, now-86400)).fetchone()[0]
            require(active < 10 and today < 20, "未使用邀请码最多 10 个，24 小时最多生成 20 个", "invitation_limit", 429)
            expires = now + 7*86400
            db.execute("INSERT INTO invitations VALUES(?,?,?,?,?,NULL,NULL,NULL)", (invitation_id, digest(code), pid, now, expires))
        return dict(id=invitation_id, code=code, expires=expires, single_use=True)

    def revoke_invitation(self, pid, invitation_id):
        with self.connect(True) as db:
            row = db.execute("SELECT * FROM invitations WHERE id=? AND inviter=?", (invitation_id, pid)).fetchone()
            require(row is not None, "Invitation not found", "not_found", 404)
            require(row["used_at"] is None, "已使用的邀请码不能撤销", "invitation_used", 409)
            db.execute("UPDATE invitations SET revoked_at=COALESCE(revoked_at,?) WHERE id=?", (time.time(), invitation_id))
        return dict(id=invitation_id, status="revoked")

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
        game = self.registry.get(room["game"])
        if hasattr(game, "room_descriptor"):
            result["catalog"] = game.room_descriptor(result["config"])
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
        initial = game.create(
            [f"validation-{i}" for i in range(capacity)], deepcopy(config), seed
        )
        if hasattr(game, "validate_public_setup"):
            game.validate_public_setup(initial)
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
                    response = json.loads(cached["response"])
                    game = self.registry.get(room["game"])
                    if response.get("state") and hasattr(game, "project_observation"):
                        response["state"] = game.project_observation(response["state"])
                    if hasattr(game, "room_descriptor"):
                        response["catalog"] = game.room_descriptor(response["config"])
                    return response
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
                events = [dict(type="game_started", round=state.get("round"), phase=state.get("phase"))]
                action_round, action_phase = state.get("round"), state.get("phase")
            else:
                require(
                    room["status"] == "active", "Game is not active", "conflict", 409
                )
                state = json.loads(room["state"])
                action_round, action_phase = state.get("round"), state.get("phase")
                if hasattr(game, "validate_public_action"):
                    game.validate_public_action(state, action)
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
                    type="action_submitted", player=pid, action_type=action.get("type"), round=action_round, phase=action_phase
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
            history = None
            if room["game"] == "fcm" and any("round" not in e for r in rows for e in json.loads(r["events"])):
                history = self.legacy_event_history(db, room)
            events = [
                dict(
                    version=r["version"],
                    events=history.get(r["version"], json.loads(r["events"])) if history is not None else json.loads(r["events"]),
                    created=r["created"],
                )
                for r in rows
            ]
            game = self.registry.get(room["game"])
            if hasattr(game, "public_event"):
                config = json.loads(room["config"])
                for batch in events:
                    batch["events"] = [game.public_event(e, config) for e in batch["events"]]
            return dict(
                version=room["version"],
                cursor=events[-1]["version"] if events else after,
                events=events,
            )

    def legacy_event_history(self, db, room):
        """Reconstruct public round-tagged events, never expose stored raw actions.

        Old journals lacked round metadata. Only serve reconstructed events if the
        replay produces exactly the current persisted game state; otherwise retain
        the original events (the UI must not guess a round). No database writes.
        """
        key = (room["id"], room["version"])
        if key in self._event_history_cache:
            return self._event_history_cache[key]
        game = self.registry.get(room["game"])
        history, state = {}, None
        try:
            for row in db.execute("SELECT version,actor,action FROM journal WHERE room=? ORDER BY version", (room["id"],)):
                action = json.loads(row["action"])
                if action["type"] == "join":
                    events = [dict(type="player_joined", player=row["actor"], round=None, phase="lobby")]
                elif action["type"] == "start":
                    state = game.create([p["id"] for p in self.members(db, room["id"])], json.loads(room["config"]), room["seed"])
                    events = [dict(type="action_submitted", player=row["actor"], action_type="start", round=state["round"], phase=state["phase"]), dict(type="game_started", round=state["round"], phase=state["phase"])]
                else:
                    submitted = dict(type="action_submitted", player=row["actor"], action_type=action["type"], round=state["round"], phase=state["phase"])
                    events = [submitted] + game.apply(state, row["actor"], deepcopy(action))
                history[row["version"]] = events
            if encode(state) != room["state"] and not (state is None and room["state"] is None):
                return None
        except (ValueError, KeyError, TypeError, AssertionError, GameError):
            return None
        if len(self._event_history_cache) >= 8:
            self._event_history_cache.clear()
        self._event_history_cache[key] = history
        return history

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
