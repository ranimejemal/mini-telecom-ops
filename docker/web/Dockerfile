FROM ubuntu:24.04

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && \
    apt-get install -y \
        nginx \
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

COPY docker/common/harden-image.sh /tmp/harden-image.sh
RUN sh /tmp/harden-image.sh && rm /tmp/harden-image.sh

COPY docker/common/sshd_hardening.conf /etc/ssh/sshd_config.d/00-hardening.conf
COPY --chown=ansibleadmin:ansibleadmin docker/ansible/ssh/id_ed25519.pub /home/ansibleadmin/.ssh/authorized_keys
COPY docker/common/boot-security.sh /usr/local/bin/boot-security.sh
COPY docker/web/entrypoint.sh /entrypoint.sh

RUN chmod 0600 /home/ansibleadmin/.ssh/authorized_keys && \
    chmod +x /usr/local/bin/boot-security.sh /entrypoint.sh && \
    sshd -t

EXPOSE 22 80

ENTRYPOINT ["/entrypoint.sh"]
