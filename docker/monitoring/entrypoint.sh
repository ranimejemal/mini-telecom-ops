#!/bin/sh

set -e

echo "[telecom] Starting monitoring services..."

# Start SSH
/usr/sbin/sshd

# Start Node Exporter
if ! pgrep -x prometheus-node-exporter >/dev/null 2>&1; then
    echo "[telecom] Starting Node Exporter..."
    /usr/bin/prometheus-node-exporter &
fi

# Start Prometheus
if ! pgrep -x prometheus >/dev/null 2>&1; then
    echo "[telecom] Starting Prometheus..."
    /usr/bin/prometheus \
        --config.file=/etc/prometheus/prometheus.yml \
        --storage.tsdb.path=/var/lib/prometheus \
        --web.listen-address=0.0.0.0:9090 &
fi

echo "[telecom] Monitoring services started."

# Keep the container alive
exec tail -f /dev/null