import http from "node:http";
import https from "node:https";
import { readFile } from "node:fs/promises";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import path from "node:path";

const root = fileURLToPath(new URL(".", import.meta.url));
const types = {
  ".html": "text/html; charset=utf-8",
  ".js": "text/javascript; charset=utf-8",
  ".css": "text/css; charset=utf-8",
  ".svg": "image/svg+xml",
  ".jpg": "image/jpeg",
};
export function createHandler(apiUrl = "http://127.0.0.1:8000") {
  const upstream = new URL(apiUrl);
  if (
    !["http:", "https:"].includes(upstream.protocol) ||
    upstream.username ||
    upstream.password ||
    upstream.pathname !== "/" ||
    upstream.search ||
    upstream.hash
  )
    throw new Error(
      "GAME_API_URL must be an HTTP(S) origin without credentials or path",
    );
  return async (req, res) => {
    res.setHeader("X-Content-Type-Options", "nosniff");
    res.setHeader("Referrer-Policy", "no-referrer");
    res.setHeader(
      "Content-Security-Policy",
      "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; font-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'",
    );
    try {
      const url = new URL(req.url, "http://localhost");
      if (url.pathname.startsWith("/api/")) {
        const apiPath = url.pathname.slice(4);
        if (
          !/^\/(v1(?:\/|$)|mcp$|health$|openapi\.json$)/.test(apiPath) ||
          !["GET", "POST"].includes(req.method)
        ) {
          res.writeHead(404);
          return res.end();
        }
        if (
          req.headers.origin &&
          req.headers.origin !== `http://${req.headers.host}` &&
          req.headers.origin !== `https://${req.headers.host}`
        ) {
          res.writeHead(403);
          return res.end();
        }
        const chunks = [];
        let size = 0;
        for await (const chunk of req) {
          size += chunk.length;
          if (size > 262144) {
            res.writeHead(413);
            res.end();
            return;
          }
          chunks.push(chunk);
        }
        const headers = {};
        for (const key of [
          "authorization",
          "content-type",
          "accept",
          "idempotency-key",
          "mcp-protocol-version",
          "x-registration-key",
          "last-event-id",
        ])
          if (req.headers[key]) headers[key] = req.headers[key];
        headers["content-length"] = String(size);
        const request = (upstream.protocol === "https:" ? https : http).request(
          new URL(apiPath + url.search, upstream),
          { method: req.method, headers, timeout: 30000 },
          (response) => {
            res.writeHead(response.statusCode, {
              "Content-Type":
                response.headers["content-type"] || "application/json",
              "Cache-Control": "no-store",
            });
            response.pipe(res);
          },
        );
        request.on("timeout", () =>
          request.destroy(new Error("Upstream timeout")),
        );
        request.on("error", () => {
          if (!res.headersSent)
            res.writeHead(502, { "Content-Type": "application/json" });
          res.end(
            JSON.stringify({
              error: {
                code: "upstream_unavailable",
                message: "游戏服务器暂时无法连接，请稍后重试。",
              },
            }),
          );
        });
        res.on("close", () => {
          if (!res.writableEnded) request.destroy();
        });
        request.end(Buffer.concat(chunks));
        return;
      }
      if (req.method !== "GET" && req.method !== "HEAD") {
        res.writeHead(405);
        return res.end();
      }
      const filename =
        url.pathname === "/" ? "/index.html" : decodeURIComponent(url.pathname);
      if (
        !/^\/(index\.html|src\/[a-zA-Z0-9_/-]+\.(js|css)|assets\/fcm\/tiles\/[a-zA-Z0-9_-]+\.jpg|favicon\.svg)$/.test(
          filename,
        ) ||
        filename.includes("..")
      ) {
        res.writeHead(404);
        return res.end();
      }
      const content = await readFile(path.join(root, filename));
      res.writeHead(200, {
        "Content-Type":
          types[path.extname(filename)] || "application/octet-stream",
        "Cache-Control": "no-cache",
      });
      res.end(req.method === "HEAD" ? undefined : content);
    } catch {
      if (!res.headersSent) res.writeHead(404);
      res.end();
    }
  };
}
if (
  process.argv[1] &&
  path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)
) {
  const host = process.env.HOST || "127.0.0.1";
  const port = Number(process.env.PORT || 5173);
  const handler = createHandler(process.env.GAME_API_URL || "http://127.0.0.1:8000");
  const tlsCert = process.env.TLS_CERT_FILE;
  const tlsKey = process.env.TLS_KEY_FILE;
  if (Boolean(tlsCert) !== Boolean(tlsKey)) throw new Error("Both TLS_CERT_FILE and TLS_KEY_FILE are required");
  const server = tlsCert ? https.createServer({cert: readFileSync(tlsCert), key: readFileSync(tlsKey), minVersion: "TLSv1.2"}, handler) : http.createServer(handler);
  server.requestTimeout = 35000;
  server.listen(port, host, () =>
    console.log(`围桌 UI: ${tlsCert ? "https" : "http"}://${host}:${port}`),
  );
}
