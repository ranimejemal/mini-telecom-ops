FROM ubuntu:24.04

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && \
    apt-get install -y \
        openssh-server \
        curl \
        wget \
        procps \
        iproute2 \
        python3 \
        prometheus \
        prometheus-node-exporter && \
    mkdir -p /run/sshd /var/lib/prometheus /etc/prometheus && \
    echo 'root:telecom' | chpasswd && \
    sed -i 's/^#\?PermitRootLogin.*/PermitRootLogin yes/' /etc/ssh/sshd_config && \
    sed -i 's/^#\?PasswordAuthentication.*/PasswordAuthentication yes/' /etc/ssh/sshd_config && \
    rm -rf /var/lib/apt/lists/*

COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

EXPOSE 22 9090 9100

ENTRYPOINT ["/entrypoint.sh"]