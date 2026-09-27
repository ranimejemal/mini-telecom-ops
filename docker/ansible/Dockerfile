FROM cytopia/ansible:latest

USER root

RUN apk add --no-cache openssh-client

RUN ansible-galaxy collection install \
    community.general \
    ansible.posix

RUN mkdir -p /etc/ansible /root/.ssh

COPY docker/ansible/ansible.cfg /etc/ansible/ansible.cfg
COPY docker/ansible/entrypoint.sh /usr/local/bin/ansible-entrypoint.sh

RUN chmod +x /usr/local/bin/ansible-entrypoint.sh

ENV ANSIBLE_CONFIG=/etc/ansible/ansible.cfg
ENV ANSIBLE_ROLES_PATH=/ansible/roles

WORKDIR /ansible

ENTRYPOINT ["/usr/local/bin/ansible-entrypoint.sh"]

CMD ["sleep", "infinity"]
