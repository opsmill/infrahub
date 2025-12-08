# ****************************************************************
# STAGE : Base Python Image
# ****************************************************************
ARG PYTHON_VER=3.12
ARG UV_VER
FROM docker.io/python:${PYTHON_VER}-slim AS base

ENV PYTHONUNBUFFERED=1

ENV PATH="${PATH}:/root/.local/bin" \
    PROMETHEUS_MULTIPROC_DIR="/prom_shared" \
    INFRAHUB_FRONTEND_DIRECTORY="/opt/infrahub/frontend/app" \
    INFRAHUB_DOCS_DIRECTORY="/opt/infrahub/docs"

RUN mkdir /prom_shared /remote

RUN apt-get update && \
    apt-get upgrade -y && \
    apt-get install --no-install-recommends -y tini curl git pkg-config build-essential ca-certificates gnupg2 && \
    install -m 0755 -d /etc/apt/keyrings && \
    curl -fsSL https://download.docker.com/linux/debian/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg && \
    chmod a+r /etc/apt/keyrings/docker.gpg && \
    echo "deb [arch="$(dpkg --print-architecture)" signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/debian \
    "$(. /etc/os-release && echo "$VERSION_CODENAME")" stable" | \
    tee /etc/apt/sources.list.d/docker.list > /dev/null && \
    apt-get update && \
    apt-get install --no-install-recommends -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin && \
    curl -sSL https://astral.sh/uv/$UV_VER/install.sh | sh - && \
    apt-get autoremove -y && \
    apt-get clean all && \
    rm -rf /var/lib/apt/lists/* && \
    pip --no-cache-dir install --no-compile --upgrade pip wheel

# ****************************************************************
# STAGE : Frontend
# ****************************************************************
FROM docker.io/node:22-slim AS frontend
ARG CI_ARG
ENV CI=$CI_ARG

RUN mkdir /source

COPY frontend/app/package.json  frontend/app/package-lock.json /source/

WORKDIR /source

RUN npm install --omit=dev
COPY frontend/app/ /source/
RUN npm run build && npm cache clean --force

# ****************************************************************
# STAGE : Documentation
# ****************************************************************
ENV DOCS_IN_APP=1

RUN mkdir /docs

COPY docs/package.json  docs/package-lock.json /docs/
COPY backend/infrahub/config.py /backend/infrahub/
COPY models/ /models/
COPY python_sdk/docs/docs/python-sdk/examples/  /python_sdk/examples/
COPY development/ /development/
WORKDIR /docs

RUN npm install --omit=dev
COPY docs/ /docs/
RUN npm run build && npm cache clean --force

# ****************************************************************
# STAGE : Backend
# ****************************************************************
FROM base AS backend

# --------------------------------------------
# Configure Git & Environment
# --------------------------------------------
RUN git config --global user.name "Infrahub" && \
    git config --global user.email "infrahub@opsmill.com" && \
    git config --global --add safe.directory '*' && \
    git config --global credential.usehttppath true && \
    git config --global credential.helper "/usr/bin/env infrahub-git-credential"

RUN mkdir -p /opt/infrahub/git /opt/infrahub/storage /opt/infrahub/source /opt/infrahub/frontend/app/dist /opt/infrahub/workflow

WORKDIR /source

ENV PREFECT_WORKER_QUERY_SECONDS="2" \
    PREFECT_SERVER_EVENTS_MAXIMUM_RELATED_RESOURCES=500 \
    PREFECT_API_DATABASE_TIMEOUT=60

# --------------------------------------------
# Import Frontend Build
# --------------------------------------------
COPY --from=frontend /source/dist/ /opt/infrahub/frontend/app/dist

# --------------------------------------------
# Import Documentation Build
# --------------------------------------------
COPY --from=frontend /docs/build/ /opt/infrahub/docs/build

# --------------------------------------------
# Install Dependencies
#   Copy in only pyproject.toml/uv.lock to help with caching this layer if no updates to dependencies
# --------------------------------------------
ENV UV_PROJECT_ENVIRONMENT="/.venv"
COPY uv.lock pyproject.toml python_sdk/pyproject.toml python_testcontainers/pyproject.toml python_testcontainers/uv.lock /source/
RUN --mount=type=cache,target=/root/.cache/uv uv sync --frozen --no-dev --no-install-project --no-install-workspace

# --------------------------------------------
# Copy in the rest of the source code and install the project
# --------------------------------------------
COPY . ./
RUN --mount=type=cache,target=/root/.cache/uv uv sync --frozen --no-dev

ENV PATH="/.venv/bin:$PATH"
ENTRYPOINT ["tini", "-g", "--"]
