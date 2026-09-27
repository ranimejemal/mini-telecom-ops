#!/bin/sh
set -e

echo "[telecom] Starting web01 services..."

/usr/local/bin/boot-security.sh
/usr/bin/prometheus-node-exporter &
nginx || echo "[telecom] WARNING: nginx failed to start (SSH stays up so Ansible can repair it)"

echo "[telecom] web01 services started."
exec /usr/sbin/sshd -D
