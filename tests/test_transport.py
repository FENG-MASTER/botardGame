"""Exercise real HTTP parsing and the unmodified SDK without opening a socket."""

import io
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch
from urllib.error import HTTPError
from boardgame.server import Handler
from boardgame.platform import Platform
from boardgame.client import Client, APIError
from examples.play_agents import run


class Connection:
    def __init__(self, data):
        self.input = io.BytesIO(data)
        self.output = bytearray()

    def makefile(self, *args):
        return self.input

    def settimeout(self, *args):
        pass

    def sendall(self, data):
        self.output.extend(data)


class TransportTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.server = SimpleNamespace(
            platform=Platform(self.tmp.name + "/db"),
            registration_key=None,
            server_name="localhost",
            server_port=80,
        )
        self.patch = patch("boardgame.client.urlopen", self.urlopen)
        self.patch.start()
        self.client = Client("http://localhost")

    def tearDown(self):
        self.patch.stop()
        self.tmp.cleanup()

    def raw(self, data):
        connection = Connection(data)
        Handler(connection, ("127.0.0.1", 12345), self.server)
        header, body = bytes(connection.output).split(b"\r\n\r\n", 1)
        return int(header.split(b" ")[1]), header, body

    def urlopen(self, request, timeout=0):
        from urllib.parse import urlparse

        url = urlparse(request.full_url)
        path = url.path + ("?" + url.query if url.query else "")
        body = request.data or b""
        headers = dict(request.header_items())
        headers.update({"Host": "localhost", "Content-Length": str(len(body))})
        data = (
            f"{request.method} {path} HTTP/1.0\r\n"
            + "".join(f"{k}: {v}\r\n" for k, v in headers.items())
            + "\r\n"
        ).encode() + body
        status, _, response = self.raw(data)
        if status >= 400:
            raise HTTPError(
                request.full_url, status, "API error", {}, io.BytesIO(response)
            )
        return io.BytesIO(response)

    def test_agents_complete_via_real_http_parser_and_client(self):
        result = run("http://localhost")
        self.assertEqual(result["status"], "finished")
        self.assertTrue(self.server.platform.replay(result["id"])["valid"])

    def test_auth_discovery_and_schema(self):
        with self.assertRaises(APIError) as error:
            self.client.request("GET", "/v1/rooms")
        self.assertEqual(error.exception.status, 401)
        self.assertEqual(
            self.client.request("GET", "/openapi.json")["openapi"], "3.1.0"
        )
        me = self.client.register("Human", "human")
        self.assertEqual(self.client.request("GET", "/v1/me")["id"], me["id"])
        room = self.client.request("POST", "/v1/rooms", dict(game="fcm", capacity=2))
        self.assertEqual(self.client.observe(room["id"])["status"], "lobby")

    def test_bad_json_types_duplicates_and_size(self):
        for body in [b"{", b'{"name":"a","name":"b"}', b"NaN", b"[]"]:
            request = (
                b"POST /v1/identities HTTP/1.0\r\nContent-Type: application/json\r\nContent-Length: "
                + str(len(body)).encode()
                + b"\r\n\r\n"
                + body
            )
            self.assertEqual(self.raw(request)[0], 400)
        self.assertEqual(
            self.raw(
                b"POST /v1/identities HTTP/1.0\r\nContent-Length: 9999999\r\n\r\n"
            )[0],
            413,
        )

    def test_registration_key(self):
        self.server.registration_key = "local-test-key"
        with self.assertRaises(APIError) as error:
            self.client.register("No invitation")
        self.assertEqual(error.exception.status, 403)

    def test_sse_resume_and_secret_redaction(self):
        a = self.client.register("a")
        other = Client("http://localhost")
        other.register("b")
        room = self.client.request("POST", "/v1/rooms", dict(game="fcm", capacity=2))
        rid = room["id"]
        other.request(
            "POST", f"/v1/rooms/{rid}/join", dict(join_code=room["join_code"])
        )
        response = self.raw(
            (
                f"GET /v1/rooms/{rid}/events HTTP/1.0\r\nAuthorization: Bearer {a['token']}\r\nAccept: text/event-stream\r\nLast-Event-ID: 0\r\n\r\n"
            ).encode()
        )
        self.assertEqual(response[0], 200)
        self.assertIn(b"text/event-stream", response[1])
        self.assertIn(b"id: 1", response[2])
        self.assertNotIn(room["join_code"].encode(), response[2])

    def test_invalid_game_type_is_client_error(self):
        self.client.register("a")
        with self.assertRaises(APIError) as error:
            self.client.request("POST", "/v1/rooms", dict(game=[], capacity=2))
        self.assertEqual(error.exception.status, 404)
