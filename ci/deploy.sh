#!/bin/bash
# Runs inside the short-lived deploy container (fixed IP 172.30.0.55, the only
# CI address the servers' firewalls accept SSH from). The commit to deploy is
# streamed in by the pipeline; credentials come from Gitea secrets.
set -euo pipefail

test -n "${SSH_KEY_B64:-}" || { echo "Secret ANSIBLE_SSH_KEY_B64 is not set"; exit 1; }
test -n "${VAULT_PASSWORD:-}" || { echo "Secret ANSIBLE_VAULT_PASSWORD is not set"; exit 1; }

install -d -m 0700 /root/.ssh
printf '%s' "$SSH_KEY_B64" | base64 -d | tr -d '\r' > /root/.ssh/id_ed25519
chmod 0600 /root/.ssh/id_ed25519
ssh-keygen -y -f /root/.ssh/id_ed25519 > /root/.ssh/id_ed25519.pub
printf '%s' "$VAULT_PASSWORD" > /root/.vault_pass
chmod 0600 /root/.vault_pass
unset SSH_KEY_B64 VAULT_PASSWORD

# Same paths as the telecom-ansible controller
ln -sfn "$PWD/ansible" /ansible
ln -sfn "$PWD/docker" /docker
export ANSIBLE_CONFIG=/ansible/ansible.cfg ANSIBLE_FORCE_COLOR=0

echo "=== Connectivity ==="
ansible telecom -m ansible.builtin.ping -o

echo "=== Deploy site.yml ==="
(cd ansible && ansible-playbook playbooks/site.yml --vault-password-file /root/.vault_pass)

echo "=== Smoke test ==="
curl -fsS -o /dev/null -w "web01 HTTP %{http_code}\n" http://172.30.0.10/
ansible monitoring01 -m ansible.builtin.uri -a "url=http://localhost:9090/-/healthy" -o | cut -c1-100
