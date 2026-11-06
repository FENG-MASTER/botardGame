export class APIError extends Error {
  constructor(status, body) {
    super(body?.error?.message || `请求失败 (${status})`);
    this.status = status;
    this.code = body?.error?.code;
  }
}
export class API {
  constructor(token = "", fetcher = globalThis.fetch.bind(globalThis)) {
    this.token = token;
    this.fetcher = fetcher;
  }
  async request(path, { method = "GET", body, headers = {}, signal } = {}) {
    const response = await this.fetcher("/api" + path, {
      method,
      headers: {
        Accept: "application/json",
        ...(this.token ? { Authorization: `Bearer ${this.token}` } : {}),
        ...(body !== undefined ? { "Content-Type": "application/json" } : {}),
        ...headers,
      },
      body: body === undefined ? undefined : JSON.stringify(body),
      signal: signal || AbortSignal.timeout(35000),
    });
    let value;
    try {
      value = await response.json();
    } catch {
      throw new APIError(response.status, {
        error: { message: "服务器返回了无法识别的响应。" },
      });
    }
    if (!response.ok) throw new APIError(response.status, value);
    return value;
  }
  register(name, inviteCode, key = "") {
    return this.request("/v1/identities", {
      method: "POST",
      body: { name, kind: "human", invite_code: inviteCode },
      headers: key ? { "X-Registration-Key": key } : {},
    });
  }
  invitations() { return this.request("/v1/invitations"); }
  createInvitation() { return this.request("/v1/invitations", {method:"POST"}); }
  revokeInvitation(id) { return this.request(`/v1/invitations/${id}/revoke`, {method:"POST"}); }
  me() {
    return this.request("/v1/me");
  }
  games() {
    return this.request("/v1/games");
  }
  rooms() {
    return this.request("/v1/rooms");
  }
  create(body) {
    return this.request("/v1/rooms", { method: "POST", body });
  }
  join(id, code) {
    return this.request(`/v1/rooms/${id}/join`, {
      method: "POST",
      body: { join_code: code },
    });
  }
  room(id) {
    return this.request(`/v1/rooms/${id}`);
  }
  actions(id) {
    return this.request(`/v1/rooms/${id}/actions`);
  }
  events(id, after = 0) {
    return this.request(`/v1/rooms/${id}/events?after=${after}`);
  }
  validate(id, version, action) {
    return this.request(`/v1/rooms/${id}/validate-action`, {
      method: "POST",
      body: { expected_version: version, action },
    });
  }
  mutate(id, transaction) {
    return this.request(`/v1/rooms/${id}/${transaction.operation}`, {
      method: "POST",
      body: transaction.body,
      headers: { "Idempotency-Key": transaction.key },
    });
  }
  async rules(game, roomId) {
    const value = await this.request("/mcp", {
      method: "POST",
      headers: { Accept: "application/json, text/event-stream" },
      body: {
        jsonrpc: "2.0",
        id: 1,
        method: "tools/call",
        params: { name: "get_game_rules", arguments: { game_id: game, ...(roomId ? {room_id: roomId} : {}) } },
      },
    });
    if (value.error) throw new Error(value.error.message);
    const result = JSON.parse(value.result.content[0].text);
    if (value.result.isError) throw new Error(result.error.message);
    return result;
  }
}
export function makeTransaction(operation, version, action) {
  return {
    operation,
    key: crypto.randomUUID(),
    body: { expected_version: version, ...(action ? { action } : {}) },
  };
}
export function definitive(error) {
  return error instanceof APIError && error.status >= 400 && error.status < 500;
}
