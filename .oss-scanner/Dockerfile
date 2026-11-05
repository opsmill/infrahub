# syntax=docker/dockerfile:1
# Image for Anthropic's OSS Scanner: the Infrahub checkout at /src, built, with every service Infrahub needs
# installed in the same image so the backend, its tests and the API server run without network access.
# Start the services with `.oss-scanner/start-services.sh`; threat_model.md describes how to exercise Infrahub.

# Keep these versions in line with development/Dockerfile, docker-compose.yml and .github/workflows/define-versions.yml.
ARG PYTHON_VER=3.14.10
ARG NODE_VER=24.15.0
ARG NEO4J_VER=2026.05.0-community
ARG RABBITMQ_VER=4.2.1-management
ARG REDIS_VER=8.4.0

FROM docker.io/neo4j:${NEO4J_VER} AS neo4j
FROM docker.io/rabbitmq:${RABBITMQ_VER} AS rabbitmq
FROM docker.io/redis:${REDIS_VER} AS redis
FROM docker.io/node:${NODE_VER}-slim AS node

# The full Python image already has git, curl and a compiler, and the services are copied from their official
# images, so the build does not depend on the Debian package mirrors.
FROM docker.io/python:${PYTHON_VER}
ARG UV_VER=0.13.6

ENV PYTHONUNBUFFERED=1 \
    JAVA_HOME=/opt/java/openjdk \
    NEO4J_HOME=/var/lib/neo4j \
    RABBITMQ_HOME=/opt/rabbitmq \
    RABBITMQ_NODENAME=rabbit@localhost \
    COREPACK_ENABLE_DOWNLOAD_PROMPT=0 \
    UV_PROJECT_ENVIRONMENT=/src/.venv \
    INFRAHUB_USE_TEST_CONTAINERS=false
ENV PATH="/src/.venv/bin:/var/lib/neo4j/bin:/opt/java/openjdk/bin:/opt/rabbitmq/sbin:/opt/erlang/bin:${PATH}"

RUN pip install --no-cache-dir "uv==${UV_VER}" \
    && git config --global --add safe.directory '*' \
    && git config --global user.name "Infrahub" \
    && git config --global user.email "infrahub@opsmill.com"

# Neo4j and the Java runtime it ships with, configured the way docker-compose.yml runs the database.
COPY --from=neo4j /opt/java/openjdk /opt/java/openjdk
COPY --from=neo4j /var/lib/neo4j /var/lib/neo4j
RUN mkdir -p /data /logs \
    && printf '%s\n' \
        'dbms.security.auth_minimum_password_length=4' \
        'server.memory.heap.initial_size=1g' \
        'server.memory.heap.max_size=1g' \
        'server.memory.pagecache.size=512m' \
        >> /var/lib/neo4j/conf/neo4j.conf \
    && neo4j-admin dbms set-initial-password admin

# RabbitMQ with the account Infrahub uses by default.
COPY --from=rabbitmq /opt/erlang /opt/erlang
COPY --from=rabbitmq /opt/openssl /opt/openssl
COPY --from=rabbitmq /opt/rabbitmq /opt/rabbitmq
COPY --from=rabbitmq /etc/rabbitmq /etc/rabbitmq
RUN mkdir -p /var/lib/rabbitmq /var/log/rabbitmq \
    && printf '%s\n' \
        'default_user = infrahub' \
        'default_pass = infrahub' \
        'loopback_users = none' \
        > /etc/rabbitmq/conf.d/90-infrahub.conf

COPY --from=redis /usr/local/bin/redis-server /usr/local/bin/redis-cli /usr/local/bin/

# Node.js and pnpm for the frontend.
COPY --from=node /usr/local/bin/node /usr/local/bin/node
COPY --from=node /usr/local/lib/node_modules /usr/local/lib/node_modules
RUN ln -s ../lib/node_modules/npm/bin/npm-cli.js /usr/local/bin/npm \
    && ln -s ../lib/node_modules/corepack/dist/corepack.js /usr/local/bin/corepack \
    && corepack enable

# scanner contract: the checkout lives inside the image, at /src
COPY . /src
WORKDIR /src

# The scanner clones without submodules; the backend needs the Python SDK and the frontend needs the schema visualizer.
RUN git submodule update --init --recursive

RUN uv sync --frozen --all-groups

RUN cd frontend && pnpm install --frozen-lockfile \
    && cd app && pnpm build

# The frontend unit tests run in a headless Chromium. Without it the frontend can still be read but not tested,
# so a failed download does not fail the build.
RUN cd frontend/app \
    && (pnpm exec playwright install --with-deps --only-shell chromium \
        || echo "WARNING: Chromium for the frontend unit tests is not installed")

RUN mkdir -p /opt/infrahub/storage /opt/infrahub/git /var/log/infrahub-scanner

# Start every service once and call the API, so a broken image fails here and not during the scan.
RUN .oss-scanner/start-services.sh all \
    && curl -sf http://localhost:8000/api/config > /dev/null \
    && .oss-scanner/start-services.sh stop

# The scan runs offline: `uv run` must use the environment built above instead of trying to sync it.
ENV UV_NO_SYNC=1 \
    UV_OFFLINE=1
