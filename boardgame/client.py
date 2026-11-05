"""Same dependency-free client for a human application or an autonomous agent."""

import json
import uuid
from urllib.request import Request, urlopen
from urllib.error import HTTPError


class APIError(Exception):
    def __init__(self, status, payload):
        self.status, self.payload = status, payload
        super().__init__(f"{status}: {payload}")


class Client:
    def __init__(self, base_url="http://127.0.0.1:8000", token=None):
        self.base_url = base_url.rstrip("/")
        self.token = token

    def request(self, method, path, body=None, key=None):
        headers = {"Accept": "application/json"}
        if self.token:
            headers["Authorization"] = "Bearer " + self.token
        if key:
            headers["Idempotency-Key"] = key
        if body is not None:
            headers["Content-Type"] = "application/json"
        req = Request(
            self.base_url + path,
            data=json.dumps(body).encode() if body is not None else None,
            headers=headers,
            method=method,
        )
        try:
            with urlopen(req, timeout=35) as response:
                return json.load(response)
        except HTTPError as e:
            with e:
                payload = json.load(e)
            raise APIError(e.code, payload) from e

    def register(self, name, kind="agent"):
        identity = self.request("POST", "/v1/identities", dict(name=name, kind=kind))
        self.token = identity["token"]
        return identity

    def observe(self, room):
        return self.request("GET", f"/v1/rooms/{room}")

    def actions(self, room):
        return self.request("GET", f"/v1/rooms/{room}/actions")

    def events(self, room, cursor=0, wait=25):
        return self.request(
            "GET", f"/v1/rooms/{room}/events?after={cursor}&wait={wait}"
        )

    def submit(self, room, version, action, key=None):
        """Persist key and envelope before sending; on network failure reuse both."""
        return self.request(
            "POST",
            f"/v1/rooms/{room}/actions",
            dict(expected_version=version, action=action),
            key or uuid.uuid4().hex,
        )

    def validate(self, room, version, action):
        return self.request(
            "POST",
            f"/v1/rooms/{room}/validate-action",
            dict(expected_version=version, action=action),
        )
