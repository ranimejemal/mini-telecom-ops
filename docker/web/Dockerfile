FROM ubuntu:24.04

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && \
    apt-get install -y \
        nginx \
        openssh-server \
        curl \
        wget \
        python3 \
        prometheus-node-exporter && \
    mkdir -p /run/sshd && \
    echo 'root:telecom' | chpasswd && \
    sed -i 's/^#\?PermitRootLogin.*/PermitRootLogin yes/' /etc/ssh/sshd_config && \
    sed -i 's/^#\?PasswordAuthentication.*/PasswordAuthentication yes/' /etc/ssh/sshd_config && \
    rm -rf /var/lib/apt/lists/*
EXPOSE 22 80

CMD ["bash", "-c", "/usr/bin/prometheus-node-exporter & nginx && /usr/sbin/sshd -D"]