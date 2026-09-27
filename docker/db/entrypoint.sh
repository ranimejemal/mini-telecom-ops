#!/bin/sh
set -e

echo "[telecom] Starting db01 services..."

/usr/local/bin/boot-security.sh
/usr/bin/prometheus-node-exporter &
# The data volume outlives the image: re-align ownership in case package UIDs changed
chown -R postgres:postgres /var/lib/postgresql
service postgresql start || echo "[telecom] WARNING: PostgreSQL failed to start (SSH stays up so Ansible can repair it)"

echo "[telecom] db01 services started."
exec /usr/sbin/sshd -D