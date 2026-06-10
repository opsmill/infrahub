# ****************************************************************
# STAGE : Base Python Image
# ****************************************************************
ARG PYTHON_VER=3.13.11
ARG NODE_VER=24.15.0
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
# STAGE : Node base (shared by the frontend and docs builds)
# ****************************************************************
FROM docker.io/node:${NODE_VER}-slim AS node-base

# ****************************************************************
# STAGE : Frontend
#   pnpm comes via corepack, resolving the version from "packageManager"
#   in frontend/package.json (the single source of truth).
#   pnpm fetch keys on the lockfile alone; the install keys on manifests only.
#   schema-visualizer is a file: dependency, so its full sources must be
#   present at install time (pnpm copies file: deps into the store).
# ****************************************************************
FROM node-base AS frontend

ENV COREPACK_ENABLE_DOWNLOAD_PROMPT=0
RUN corepack enable

WORKDIR /frontend

COPY frontend/package.json frontend/pnpm-lock.yaml frontend/pnpm-workspace.yaml /frontend/
RUN --mount=type=cache,id=pnpm,target=/pnpm/store pnpm fetch --store-dir /pnpm/store

COPY frontend/app/package.json /frontend/app/
COPY frontend/packages/ui/package.json /frontend/packages/ui/
COPY frontend/packages/schema-visualizer/ /frontend/packages/schema-visualizer/
RUN --mount=type=cache,id=pnpm,target=/pnpm/store \
    pnpm install --frozen-lockfile --offline --store-dir /pnpm/store

COPY frontend/packages/ui/ /frontend/packages/ui/
COPY frontend/app/ /frontend/app/
WORKDIR /frontend/app
RUN pnpm build

# ****************************************************************
# STAGE : Documentation
#   models/, deploy.tf and k8s/ are raw-loaded by docs .mdx pages at build time
# ****************************************************************
FROM node-base AS docs

# Read by docusaurus.config.ts: sets url/baseUrl for serving inside the app at /docs
ENV DOCS_IN_APP=1

WORKDIR /docs
COPY docs/package.json docs/package-lock.json /docs/
RUN --mount=type=cache,target=/root/.npm npm ci --omit=dev

COPY models/ /models/
COPY development/deploy.tf /development/deploy.tf
COPY development/k8s/ /development/k8s/
COPY docs/ /docs/
RUN npm run build

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
    PREFECT_API_DATABASE_TIMEOUT=60 \
    PREFECT_FLOWS_HEARTBEAT_FREQUENCY=30

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

# --------------------------------------------
# Import Frontend & Documentation Builds
#   Last so frontend/docs edits don't invalidate any uv sync layer
# --------------------------------------------
COPY --from=frontend /frontend/app/dist/ /opt/infrahub/frontend/app/dist
COPY --from=docs /docs/build/ /opt/infrahub/docs/build

ENV PATH="/.venv/bin:$PATH"
ENTRYPOINT ["tini", "-g", "--"]
