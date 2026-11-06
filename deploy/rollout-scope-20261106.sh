#!/usr/bin/env bash
# One-time production release. Both images and the server certificate must exist.
set -euo pipefail
cd /home/ubuntu/botardgame-release-scope-20261106
suffix='before-scope-20261106'
backup='/home/ubuntu/botardgame/backups/before-scope-20261106.sqlite3'
for service in boardgame-api boardgame-ui; do
  sudo -n docker inspect "$service" >/dev/null
  if sudo -n docker inspect "$service-$suffix" >/dev/null 2>&1; then
    echo "Rollback container already exists: $service-$suffix" >&2; exit 1
  fi
done
sudo -n docker image inspect botardgame-api:scope-20261106 >/dev/null
sudo -n docker image inspect botardgame-ui:scope-20261106 >/dev/null
openssl x509 -in /home/ubuntu/botardgame/tls/server.crt -checkend 0 -noout
sudo -n test ! -e "$backup"
renamed_api=0
renamed_ui=0
rollback() {
  trap - ERR
  echo 'Release failed; restoring previous containers. Database is not overwritten.' >&2
  if [[ "$renamed_ui" == 1 ]]; then
    sudo -n docker rm -f boardgame-ui >/dev/null 2>&1 || true
    sudo -n docker rename "boardgame-ui-$suffix" boardgame-ui
  fi
  if [[ "$renamed_api" == 1 ]]; then
    sudo -n docker rm -f boardgame-api >/dev/null 2>&1 || true
    sudo -n docker rename "boardgame-api-$suffix" boardgame-api
  fi
  sudo -n docker update --restart=unless-stopped boardgame-api boardgame-ui >/dev/null
  sudo -n docker start boardgame-api boardgame-ui >/dev/null
  exit 1
}
trap rollback ERR
sudo -n docker stop boardgame-ui
sudo -n docker stop boardgame-api
sudo -n python3 deploy/backup-production.py "$backup"
sudo -n docker rename boardgame-api "boardgame-api-$suffix"
renamed_api=1
sudo -n docker rename boardgame-ui "boardgame-ui-$suffix"
renamed_ui=1
sudo -n docker update --restart=no "boardgame-api-$suffix" "boardgame-ui-$suffix" >/dev/null
sudo -n docker run -d --name boardgame-api --restart unless-stopped --network botardgame \
  -v /home/ubuntu/botardgame/data:/data botardgame-api:scope-20261106
sudo -n docker run -d --name boardgame-ui --restart unless-stopped --network botardgame \
  -p 8082:5173 -v /home/ubuntu/botardgame/tls:/tls:ro \
  -e TLS_CERT_FILE=/tls/server.crt -e TLS_KEY_FILE=/tls/server.key botardgame-ui:scope-20261106
healthy=0
for attempt in $(seq 1 20); do
  if curl --cacert /home/ubuntu/botardgame/tls/server.crt -fsS --max-time 5 https://127.0.0.1:8082/api/health; then
    healthy=1; break
  fi
  sleep 2
done
[[ "$healthy" == 1 ]]
trap - ERR
echo 'Room-scoped expansion release is healthy; previous containers retained and stopped.'
