import test from "node:test";
import assert from "node:assert/strict";
import { API, APIError, definitive } from "../src/api.js";

test("default fetch preserves the browser global receiver for registration and authenticated requests", async () => {
  const original = globalThis.fetch;
  const calls = [];
  globalThis.fetch = function (url, options) {
    // Browser Web IDL functions reject an API instance as their receiver.
    if (this !== globalThis) throw new TypeError("Illegal invocation");
    calls.push({ url, options });
    return Promise.resolve(
      Response.json({ id: "human-1", token: "test-token" }),
    );
  };
  try {
    const api = new API();
    const identity = await api.register("fengmaster", "invite-code", "registration-key");
    assert.equal(identity.id, "human-1");
    assert.equal(calls[0].url, "/api/v1/identities");
    assert.deepEqual(JSON.parse(calls[0].options.body), {
      name: "fengmaster",
      kind: "human",
      invite_code: "invite-code",
    });
    assert.equal(
      calls[0].options.headers["X-Registration-Key"],
      "registration-key",
    );
    api.token = identity.token;
    await api.me();
    assert.equal(calls[1].options.headers.Authorization, "Bearer test-token");
  } finally {
    globalThis.fetch = original;
  }
});

test("injected transport preserves mutation retries and server errors", async () => {
  const calls = [];
  const api = new API("token", async (url, options) => {
    calls.push({ url, options });
    return Response.json(
      { error: { code: "version_conflict", message: "版本已变化" } },
      { status: 409 },
    );
  });
  const transaction = {
    operation: "actions",
    key: "same-key",
    body: { expected_version: 2, action: { type: "pass" } },
  };
  for (let i = 0; i < 2; i++) {
    await assert.rejects(api.mutate("room-1", transaction), (error) => {
      assert.ok(error instanceof APIError);
      assert.equal(error.message, "版本已变化");
      assert.ok(definitive(error));
      return true;
    });
  }
  assert.equal(calls[0].options.body, calls[1].options.body);
  assert.equal(calls[1].options.headers["Idempotency-Key"], "same-key");
  assert.equal(definitive(new APIError(503, {})), false);
});
