import json
import tempfile
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from boardgame.platform import Platform
from boardgame.core import GameError
from boardgame.server import make_server
from boardgame.client import Client, APIError
from examples.play_agents import run, choose


class PlatformTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = self.tmp.name + "/db.sqlite3"
        self.p = Platform(self.path)
        self.a = self.p.register("Human", "human")
        self.b = self.p.register("Agent", "agent")
        self.ids = [self.a["id"], self.b["id"]]
        self.room = self.p.create_room(self.a["id"], "fcm", 2, seed=3)
        self.rid = self.room["id"]
        self.p.join(self.b["id"], self.rid, self.room["join_code"])
        self.p.mutate(self.a["id"], self.rid, 1, "start", {"type": "start"}, start=True)
        self.counter = 0

    def tearDown(self):
        self.tmp.cleanup()

    def submit(self, pid, action):
        self.counter += 1
        return self.p.mutate(
            pid,
            self.rid,
            self.p.get(pid, self.rid)["version"],
            str(self.counter),
            action,
        )

    def placements(self):
        for _ in range(2):
            obs = self.p.get(self.a["id"], self.rid)
            actor = obs["state"]["actors"][0]
            self.submit(actor, self.p.actions(actor, self.rid)["placements"][0])

    def test_token_hash_and_equal_access(self):
        self.assertEqual(self.p.authenticate(self.a["token"])["kind"], "human")
        self.assertEqual(self.p.authenticate(self.b["token"])["kind"], "agent")
        with self.p.connect() as db:
            stored = db.execute(
                "SELECT token_hash FROM identities WHERE id=?", (self.a["id"],)
            ).fetchone()[0]
        self.assertNotEqual(stored, self.a["token"])
        with self.assertRaises(GameError):
            self.p.authenticate("wrong")

    def test_membership_and_invite(self):
        c = self.p.register("Outside", "agent")
        for fn in [
            lambda: self.p.get(c["id"], self.rid),
            lambda: self.p.events(c["id"], self.rid),
            lambda: self.p.actions(c["id"], self.rid),
            lambda: self.p.join(c["id"], self.rid, "bad"),
        ]:
            with self.assertRaises(GameError):
                fn()

    def test_idempotency_conflict_and_atomicity(self):
        obs = self.p.get(self.a["id"], self.rid)
        actor = obs["state"]["actors"][0]
        version = obs["version"]
        a = self.p.actions(actor, self.rid)["placements"][0]
        first = self.p.mutate(actor, self.rid, version, "repeat", a)
        self.assertEqual(first, self.p.mutate(actor, self.rid, version, "repeat", a))
        with self.assertRaises(GameError) as error:
            self.p.mutate(actor, self.rid, version, "repeat", {"type": "pass"})
        self.assertEqual(error.exception.code, "idempotency_conflict")
        with self.assertRaises(GameError) as error:
            self.p.mutate(actor, self.rid, version, "other", a)
        self.assertEqual(error.exception.code, "version_conflict")
        self.assertEqual(self.p.get(actor, self.rid)["version"], version + 1)

    def test_race_has_one_winner(self):
        obs = self.p.get(self.a["id"], self.rid)
        actor = obs["state"]["actors"][0]
        a = self.p.actions(actor, self.rid)["placements"][0]

        def go(i):
            try:
                self.p.mutate(actor, self.rid, obs["version"], str(i), a)
                return "ok"
            except GameError as e:
                return e.code

        with ThreadPoolExecutor(2) as pool:
            results = list(pool.map(go, [1, 2]))
        self.assertEqual(sorted(results), ["ok", "version_conflict"])

    def test_hidden_reserve_and_events(self):
        self.placements()
        self.submit(self.a["id"], {"type": "choose_reserve", "amount": 300})
        view = self.p.get(self.b["id"], self.rid)["state"]
        self.assertIsNone(view["reserves"][self.a["id"]])
        self.assertEqual(view["pending"], {})
        serialized = json.dumps(self.p.events(self.b["id"], self.rid))
        self.assertNotIn("300", serialized)
        self.assertNotIn("amount", serialized)
        self.assertEqual(
            self.p.get(self.a["id"], self.rid)["state"]["reserves"][self.a["id"]], 300
        )

    def test_validation_has_no_side_effects(self):
        before = self.p.get(self.a["id"], self.rid)
        actor = before["state"]["actors"][0]
        action = self.p.actions(actor, self.rid)["placements"][0]
        self.assertTrue(
            self.p.mutate(
                actor, self.rid, before["version"], None, action, dry_run=True
            )["valid"]
        )
        self.assertEqual(before, self.p.get(self.a["id"], self.rid))
        with self.assertRaises(GameError):
            self.submit(actor, dict(type="place_restaurant", position=[0, 0]))
        self.assertEqual(before, self.p.get(self.a["id"], self.rid))

    def test_persistence_and_replay(self):
        self.placements()
        p2 = Platform(self.path)
        self.assertEqual(
            p2.get(self.a["id"], self.rid), self.p.get(self.a["id"], self.rid)
        )
        self.assertTrue(p2.replay(self.rid)["valid"])

    def test_complete_game_and_replay(self):
        for _ in range(600):
            obs = self.p.get(self.a["id"], self.rid)
            if obs["status"] == "finished":
                break
            pid = obs["state"]["actors"][0]
            obs = self.p.get(pid, self.rid)
            self.submit(pid, choose(pid, obs, self.p.actions(pid, self.rid)))
        self.assertEqual(obs["status"], "finished")
        self.assertEqual(obs["state"]["bank_breaks"], 2)
        self.assertTrue(self.p.replay(self.rid)["valid"])

    def test_failed_work_rolls_back_earlier_hiring(self):
        self.placements()
        for pid in self.ids:
            self.submit(pid, {"type": "choose_reserve", "amount": 100})
        while self.p.get(self.a["id"], self.rid)["state"]["phase"] == "order":
            obs = self.p.get(self.a["id"], self.rid)
            pid = obs["state"]["actors"][0]
            options = self.p.actions(pid, self.rid)
            self.submit(
                pid,
                {"type": "choose_order", "position": options["available_positions"][0]},
            )
        obs = self.p.get(self.a["id"], self.rid)
        pid = obs["state"]["actors"][0]
        before = self.p.get(pid, self.rid)
        with self.assertRaises(GameError):
            self.submit(
                pid,
                {
                    "type": "work",
                    "hire": [{"recruiter": pid + ":ceo", "kind": "waitress"}],
                    "produce": [{"employee": "unknown", "product": "burger"}],
                },
            )
        self.assertEqual(before, self.p.get(pid, self.rid))
        self.assertTrue(self.p.replay(self.rid)["valid"])


class HTTPTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        try:
            self.server = make_server(port=0, database=self.tmp.name + "/http.db")
        except PermissionError:
            self.tmp.cleanup()
            self.skipTest(
                "Sandbox forbids sockets; raw HTTP transport is covered in memory"
            )
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.url = "http://127.0.0.1:" + str(self.server.server_port)
        self.client = Client(self.url)

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()
        self.tmp.cleanup()

    def test_http_discovery_auth(self):
        self.assertEqual(self.client.request("GET", "/health")["status"], "ok")
        self.assertEqual(
            self.client.request("GET", "/openapi.json")["openapi"], "3.1.0"
        )
        self.assertEqual(
            self.client.request("GET", "/v1/games")["games"][0]["id"], "fcm"
        )
        with self.assertRaises(APIError) as error:
            self.client.request("GET", "/v1/rooms")
        self.assertEqual(error.exception.status, 401)
        identity = self.client.register("Human", "human")
        self.assertEqual(self.client.request("GET", "/v1/me")["id"], identity["id"])

    def test_agents_finish_over_http(self):
        obs = run(self.url)
        self.assertEqual(obs["status"], "finished")
        self.assertTrue(self.server.platform.replay(obs["id"])["valid"])

    def test_malformed_action(self):
        self.client.register("test")
        with self.assertRaises(APIError) as error:
            self.client.request("POST", "/v1/rooms", dict(game="fcm", capacity=True))
        self.assertEqual(error.exception.status, 422)
