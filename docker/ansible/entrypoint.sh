#!/bin/sh
set -e

mkdir -p /root/.ssh

cp /ssh/id_ed25519 /root/.ssh/id_ed25519
cp /ssh/id_ed25519.pub /root/.ssh/id_ed25519.pub

chmod 700 /root/.ssh
chmod 600 /root/.ssh/id_ed25519
chmod 644 /root/.ssh/id_ed25519.pub

exec "$@"
