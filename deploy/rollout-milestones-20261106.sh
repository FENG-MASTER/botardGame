#!/usr/bin/env bash
# One-time UI-only release; backend and its data mount remain running.
set -euo pipefail
cd /home/ubuntu/botardgame-release-milestones-20261106
old=boardgame-ui-before-milestones-20261106
sudo -n docker inspect boardgame-ui >/dev/null
if sudo -n docker inspect "$old" >/dev/null 2>&1; then exit 1; fi
sudo -n docker image inspect botardgame-ui:milestones-20261106 >/dev/null
sudo -n python3 deploy/backup-production.py /home/ubuntu/botardgame/backups/before-milestones-20261106.sqlite3
renamed=0
rollback() {
  trap - ERR
  if [[ "$renamed" == 1 ]]; then
    sudo -n docker rm -f boardgame-ui || true
    sudo -n docker rename "$old" boardgame-ui
  fi
  sudo -n docker update --restart=unless-stopped boardgame-ui >/dev/null
  sudo -n docker start boardgame-ui >/dev/null
  exit 1
}
trap rollback ERR
sudo -n docker stop boardgame-ui
sudo -n docker rename boardgame-ui "$old"
renamed=1
sudo -n docker update --restart=no "$old" >/dev/null
sudo -n docker run -d --name boardgame-ui --restart unless-stopped --network botardgame \
  -p 8082:5173 -v /home/ubuntu/botardgame/tls:/tls:ro \
  -e TLS_CERT_FILE=/tls/server.crt -e TLS_KEY_FILE=/tls/server.key botardgame-ui:milestones-20261106
healthy=0
for attempt in $(seq 1 10); do
  if curl --cacert /home/ubuntu/botardgame/tls/server.crt -fsS --max-time 5 https://127.0.0.1:8082/api/health; then healthy=1; break; fi
  sleep 2
done
[[ "$healthy" == 1 ]]
trap - ERR
echo 'Compact milestone UI healthy; previous UI retained.'
