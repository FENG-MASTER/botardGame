#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
python3 deploy/prepare.py
remote='ubuntu@106.55.228.236'
release="botardgame-release-$(date -u +%Y%m%dT%H%M%SZ)"
ssh_args=(-F /dev/null -o ConnectTimeout=15)
ssh "${ssh_args[@]}" "$remote" "umask 077; mkdir '$release'"
scp "${ssh_args[@]}" deploy/artifacts/boardgame-release.tar.gz "$remote:$release/release.tar.gz"
ssh "${ssh_args[@]}" "$remote" "cd '$release' && tar -xzf release.tar.gz && bash deploy/install-remote.sh"
