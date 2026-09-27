FROM ubuntu:24.04

ENV DEBIAN_FRONTEND=noninteractive

# Official Prometheus release (the Ubuntu package ships without the web UI)
ARG PROMETHEUS_VERSION=3.1.0
ARG TARGETARCH

RUN apt-get update && \
    apt-get install -y \
        openssh-server \
        sudo \
        curl \
        wget \
        procps \
        iproute2 \
        python3 \
        prometheus-node-exporter \
        rsyslog \
        ufw \
        fail2ban && \
    rm -rf /var/lib/apt/lists/*

RUN wget -q "https://github.com/prometheus/prometheus/releases/download/v${PROMETHEUS_VERSION}/prometheus-${PROMETHEUS_VERSION}.linux-${TARGETARCH:-amd64}.tar.gz" -O /tmp/prometheus.tgz && \
    tar -xzf /tmp/prometheus.tgz -C /tmp && \
    install -m 0755 /tmp/prometheus-${PROMETHEUS_VERSION}.linux-*/prometheus /tmp/prometheus-${PROMETHEUS_VERSION}.linux-*/promtool /usr/local/bin/ && \
    rm -rf /tmp/prometheus* && \
    mkdir -p /var/lib/prometheus /etc/prometheus && \
    prometheus --version

COPY docker/common/harden-image.sh /tmp/harden-image.sh
RUN sh /tmp/harden-image.sh && rm /tmp/harden-image.sh

COPY docker/common/sshd_hardening.conf /etc/ssh/sshd_config.d/00-hardening.conf
COPY --chown=ansibleadmin:ansibleadmin docker/ansible/ssh/id_ed25519.pub /home/ansibleadmin/.ssh/authorized_keys
COPY docker/common/boot-security.sh /usr/local/bin/boot-security.sh
COPY docker/monitoring/entrypoint.sh /entrypoint.sh

RUN chmod 0600 /home/ansibleadmin/.ssh/authorized_keys && \
    chmod +x /usr/local/bin/boot-security.sh /entrypoint.sh && \
    sshd -t

EXPOSE 22 9090 9100

ENTRYPOINT ["/entrypoint.sh"]
