#!/bin/sh
# Starts security services that do not survive a container restart
# (no systemd in containers). Safe to run before Ansible has configured anything.

# rsyslog: SSH events -> /var/log/auth.log (read by Fail2ban, later by Wazuh)
if command -v rsyslogd >/dev/null 2>&1 && ! pgrep -x rsyslogd >/dev/null 2>&1; then
    rm -f /run/rsyslogd.pid
    touch /var/log/auth.log
    rsyslogd
fi

# UFW: reload rules into this container's network namespace (only once Ansible enabled it)
if [ -x /usr/lib/ufw/ufw-init ] && grep -q '^ENABLED=yes' /etc/ufw/ufw.conf 2>/dev/null; then
    /usr/lib/ufw/ufw-init start >/dev/null 2>&1 || echo "[boot] WARNING: UFW failed to start"
fi

# Fail2ban (only once Ansible deployed jail.local)
if [ -f /etc/fail2ban/jail.local ] && command -v fail2ban-client >/dev/null 2>&1; then
    mkdir -p /run/fail2ban
    rm -f /run/fail2ban/fail2ban.sock
    fail2ban-client -x start >/dev/null 2>&1 || echo "[boot] WARNING: Fail2ban failed to start"
fi

# Wazuh SOC agent (only once Ansible installed it)
if [ -x /var/ossec/bin/wazuh-control ]; then
    /var/ossec/bin/wazuh-control start >/dev/null 2>&1 || echo "[boot] WARNING: Wazuh agent failed to start"
fi
