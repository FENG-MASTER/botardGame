#!/usr/bin/env bash
set -euo pipefail
# Run on the production host. Private key never leaves this directory.
tls_dir="$HOME/botardgame/tls"
mkdir -p "$tls_dir"
chmod 750 "$tls_dir"
if [[ ! -e "$tls_dir/server.key" && ! -e "$tls_dir/server.crt" ]]; then
  (umask 077; openssl req -x509 -newkey rsa:3072 -sha256 -nodes -days 365 \
    -keyout "$tls_dir/server.key" -out "$tls_dir/server.crt" \
    -subj '/CN=106.55.228.236/O=BotardGame' \
    -addext 'subjectAltName=IP:106.55.228.236,IP:127.0.0.1,DNS:localhost' \
    -addext 'basicConstraints=critical,CA:FALSE' \
    -addext 'keyUsage=critical,digitalSignature,keyEncipherment' \
    -addext 'extendedKeyUsage=serverAuth')
fi
openssl x509 -in "$tls_dir/server.crt" -checkend 0 -noout
# Node's non-root user in the official image is UID/GID 1000.
sudo -n chown -R 1000:1000 "$tls_dir"
chmod 600 "$tls_dir/server.key"
chmod 644 "$tls_dir/server.crt"
openssl x509 -in "$tls_dir/server.crt" -noout -dates -fingerprint -sha256
