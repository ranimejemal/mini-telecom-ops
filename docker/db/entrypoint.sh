#!/bin/sh
set -e

echo "[telecom] Starting db01 services..."

/usr/local/bin/boot-security.sh
/usr/bin/prometheus-node-exporter &
service postgresql start || echo "[telecom] WARNING: PostgreSQL failed to start (SSH stays up so Ansible can repair it)"

echo "[telecom] db01 services started."
exec /usr/sbin/sshd -D
