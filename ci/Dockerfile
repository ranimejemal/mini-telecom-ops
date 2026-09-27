# Telecom CI toolbox: every quality/security gate runs from this local image,
# so pipelines need no third-party actions from the Internet.
FROM aquasec/trivy:0.74.0 AS trivy
FROM docker:27-cli AS dockercli

FROM ubuntu:24.04

ENV DEBIAN_FRONTEND=noninteractive

ARG GITLEAKS_VERSION=8.21.2
ARG PROMETHEUS_VERSION=3.1.0
ARG ALERTMANAGER_VERSION=0.28.0

ENV PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PATH=/opt/ci/bin:$PATH

RUN apt-get update && \
    apt-get install -y --no-install-recommends git bash curl ca-certificates openssh-client python3 python3-venv && \
    rm -rf /var/lib/apt/lists/*

RUN python3 -m venv /opt/ci && \
    pip install ansible yamllint ansible-lint

RUN curl -sSfL "https://github.com/gitleaks/gitleaks/releases/download/v${GITLEAKS_VERSION}/gitleaks_${GITLEAKS_VERSION}_linux_x64.tar.gz" \
      | tar -xz -C /usr/local/bin gitleaks && \
    curl -sSfL "https://github.com/prometheus/prometheus/releases/download/v${PROMETHEUS_VERSION}/prometheus-${PROMETHEUS_VERSION}.linux-amd64.tar.gz" \
      | tar -xz -C /usr/local/bin --strip-components=1 "prometheus-${PROMETHEUS_VERSION}.linux-amd64/promtool" && \
    curl -sSfL "https://github.com/prometheus/alertmanager/releases/download/v${ALERTMANAGER_VERSION}/alertmanager-${ALERTMANAGER_VERSION}.linux-amd64.tar.gz" \
      | tar -xz -C /usr/local/bin --strip-components=1 "alertmanager-${ALERTMANAGER_VERSION}.linux-amd64/amtool"

COPY --from=trivy /usr/local/bin/trivy /usr/local/bin/trivy
# Docker CLI: the deploy job starts a short-lived deploy container with a fixed IP
COPY --from=dockercli /usr/local/bin/docker /usr/local/bin/docker

RUN yamllint --version && ansible-lint --version && gitleaks version && \
    promtool --version && amtool --version && trivy --version && docker --version
