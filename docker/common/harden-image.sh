#!/bin/sh
# Secure-by-default baseline baked into every telecom server image.
# Ansible still manages these settings at runtime; the image just never starts weak.
set -eu

ADMIN=ansibleadmin

# Automation account (SSH key only, passwordless sudo)
id "$ADMIN" >/dev/null 2>&1 || useradd -m -s /bin/bash -G sudo "$ADMIN"
printf '%s ALL=(ALL) NOPASSWD:ALL\n' "$ADMIN" > "/etc/sudoers.d/$ADMIN"
chmod 0440 "/etc/sudoers.d/$ADMIN"
visudo -cf "/etc/sudoers.d/$ADMIN"
install -d -m 0700 -o "$ADMIN" -g "$ADMIN" "/home/$ADMIN/.ssh"

# No password for root
passwd -l root

mkdir -p /run/sshd

# UFW inside a container: /proc/sys is read-only (kernel params come from
# Docker Compose 'sysctls'), and telecom-net is IPv4 only
touch /etc/ufw/sysctl-container.conf
sed -i 's|^IPT_SYSCTL=.*|IPT_SYSCTL=/etc/ufw/sysctl-container.conf|; s|^IPV6=.*|IPV6=no|' /etc/default/ufw

# rsyslog: containers have no access to the kernel log
sed -i '/imklog/s/^/#/' /etc/rsyslog.conf
