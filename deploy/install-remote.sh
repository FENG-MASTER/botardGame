#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
release_dir="$PWD"
# This installs a new instance; never replace existing production data implicitly.
service_dir="$HOME/botardgame"
if sudo -n test -e "$service_dir/data/boardgame.sqlite3"; then
  echo "Existing server database found at $service_dir/data; refusing to overwrite it." >&2
  exit 1
fi
if ! command -v docker >/dev/null; then
  . /etc/os-release
  [[ "$ID" == ubuntu ]] || { echo 'Automatic Docker installation requires Ubuntu.' >&2; exit 1; }
  sudo -n apt-get update
  sudo -n apt-get install -y docker.io
fi
sudo -n systemctl enable --now docker
for name in boardgame-api boardgame-ui; do
  if sudo -n docker container inspect "$name" >/dev/null 2>&1; then
    echo "Container $name already exists; stopping installation without replacing it." >&2
    exit 1
  fi
done
sudo -n docker build -t botardgame-api:release "$release_dir"
sudo -n docker build -t botardgame-ui:release "$release_dir/human-ui"
mkdir -p "$service_dir"
chmod 700 "$service_dir"
sudo -n install -d -m 700 -o 10001 -g 10001 "$service_dir/data"
sudo -n install -m 600 -o 10001 -g 10001 migration/boardgame.sqlite3 "$service_dir/data/boardgame.sqlite3"
sudo -n docker network inspect botardgame >/dev/null 2>&1 || sudo -n docker network create botardgame
sudo -n docker run -d --name boardgame-api --restart unless-stopped \
  --network botardgame -v "$service_dir/data:/data" botardgame-api:release
bash deploy/generate-tls.sh
sudo -n docker run -d --name boardgame-ui --restart unless-stopped \
  --network botardgame -p 8082:5173 -v "$service_dir/tls:/tls:ro" \
  -e TLS_CERT_FILE=/tls/server.crt -e TLS_KEY_FILE=/tls/server.key botardgame-ui:release
for attempt in $(seq 1 30); do
  if sudo -n docker exec boardgame-ui env NODE_EXTRA_CA_CERTS=/tls/server.crt node -e 'fetch("https://127.0.0.1:5173/api/health").then(r=>{if(!r.ok)process.exit(1)}).catch(()=>process.exit(1))'; then
    echo 'Backend and UI proxy healthy. UI: https://106.55.228.236:8082  MCP: https://106.55.228.236:8082/api/mcp'
    exit 0
  fi
  sleep 2
done
sudo -n docker logs --tail 40 boardgame-api
sudo -n docker logs --tail 40 boardgame-ui
exit 1
