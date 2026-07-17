# syntax=docker/dockerfile:1-labs
# ****************************************************************
# STAGE : Base Python Image (build-time toolchain)
# ****************************************************************
ARG PYTHON_VER=3.14.3
ARG NODE_VER=24.15.0
ARG UV_VER
FROM docker.io/python:${PYTHON_VER}-slim AS base

ENV PYTHONUNBUFFERED=1

# uv installs to /root/.local/bin
ENV PATH="${PATH}:/root/.local/bin"

# Build toolchain only: build-essential/pkg-config compile any dependency that has no wheel,
# uv installs the dependencies. None of this is needed at runtime — the final `backend` stage
# copies only the built virtualenv, so this bloat stays out of the shipped image.
RUN apt-get update && \
    apt-get upgrade -y && \
    apt-get install --no-install-recommends -y curl git pkg-config build-essential ca-certificates && \
    curl -sSL https://astral.sh/uv/$UV_VER/install.sh | sh - && \
    apt-get autoremove -y && \
    apt-get clean all && \
    rm -rf /var/lib/apt/lists/* && \
    pip --no-cache-dir install --no-compile --upgrade pip wheel

# ****************************************************************
# STAGE : Base Node Image
# ****************************************************************
FROM docker.io/node:${NODE_VER}-slim AS node-base

# ****************************************************************
# STAGE : Frontend
# ****************************************************************
FROM node-base AS frontend

# pnpm comes via corepack, resolving the version from "packageManager" in frontend/package.json
RUN corepack enable

WORKDIR /frontend

COPY frontend/package.json frontend/pnpm-lock.yaml frontend/pnpm-workspace.yaml /frontend/
RUN --mount=type=cache,id=pnpm,target=/pnpm/store pnpm fetch --store-dir /pnpm/store

COPY frontend/app/package.json /frontend/app/
COPY frontend/packages/ui/package.json /frontend/packages/ui/
COPY frontend/packages/graph/package.json /frontend/packages/graph/
COPY frontend/packages/schema-visualizer/package.json /frontend/packages/schema-visualizer/
RUN --mount=type=cache,id=pnpm,target=/pnpm/store pnpm install --frozen-lockfile --offline --store-dir /pnpm/store

COPY frontend/packages/schema-visualizer/ /frontend/packages/schema-visualizer/
COPY frontend/packages/ui/ /frontend/packages/ui/
COPY frontend/packages/graph/ /frontend/packages/graph/
COPY frontend/app/ /frontend/app/
WORKDIR /frontend/app

# CI is used to customize config, like disabling animations at build time to avoid flaky e2e.
ARG CI_ARG
ENV CI=$CI_ARG
RUN pnpm build

# ****************************************************************
# STAGE : Documentation
# ****************************************************************
FROM node-base AS docs

# Read by docusaurus.config.ts: sets url/baseUrl for serving inside the app at /docs
ENV DOCS_IN_APP=1

WORKDIR /docs
COPY docs/package.json docs/package-lock.json /docs/
RUN --mount=type=cache,target=/root/.npm npm ci --omit=dev

COPY models/base/ /models/base/
COPY models/examples/extension_rack.yml /models/examples/
COPY development/deploy.tf /development/deploy.tf
COPY development/k8s/ /development/k8s/
COPY docs/ /docs/
RUN npm run build

# ****************************************************************
# STAGE : Builder — resolve & install the Python virtualenv at /.venv
#   Runs on the build-toolchain `base`; the resulting /.venv (and /source that its
#   editable installs point at) are the only things copied into the runtime stage.
# ****************************************************************
FROM base AS builder

WORKDIR /source

# hatch-vcs resolves the version from the bind-mounted .git during the project install below;
# mark the mount safe so git does not refuse it for "dubious ownership".
RUN git config --global --add safe.directory '*'

# --------------------------------------------
# Install Dependencies
#   Copy in only pyproject.toml/uv.lock to help with caching this layer if no updates to dependencies
# --------------------------------------------
ENV UV_PROJECT_ENVIRONMENT="/.venv"
COPY uv.lock pyproject.toml /source/
COPY python_sdk/pyproject.toml /source/python_sdk/
COPY python_testcontainers/pyproject.toml python_testcontainers/uv.lock /source/python_testcontainers/
RUN --mount=type=cache,target=/root/.cache/uv uv sync --frozen --no-dev --no-install-project --no-install-workspace

# --------------------------------------------
# Copy in the rest of the source code and install the project
#   .git is excluded from the copy so it never lands in the image; it is bind-mounted transiently
#   on the install step below so hatch-vcs can resolve the version from the git tag.
# --------------------------------------------
COPY --exclude=.git . ./
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=.git,target=/source/.git \
    uv sync --frozen --no-dev

# ****************************************************************
# STAGE : Backend (runtime) — slim image without any build toolchain
# ****************************************************************
FROM docker.io/python:${PYTHON_VER}-slim AS backend

ENV PYTHONUNBUFFERED=1

# The virtualenv built in the `builder` stage lives at /.venv and provides all console
# scripts (gunicorn, prefect, infrahub, infrahub-git-credential, ...).
ENV PATH="/.venv/bin:${PATH}" \
    PROMETHEUS_MULTIPROC_DIR="/prom_shared" \
    INFRAHUB_FRONTEND_DIRECTORY="/opt/infrahub/frontend/app" \
    INFRAHUB_DOCS_DIRECTORY="/opt/infrahub/docs"

ENV PREFECT_WORKER_QUERY_SECONDS="2" \
    PREFECT_SERVER_EVENTS_MAXIMUM_RELATED_RESOURCES=500 \
    PREFECT_API_DATABASE_TIMEOUT=60 \
    PREFECT_FLOWS_HEARTBEAT_FREQUENCY=30 \
    PREFECT_SERVER_API_MAX_PARAMETER_SIZE=0

# Runtime-only OS packages: tini (init/entrypoint), git (repository sync), curl (healthcheck).
# No build-essential/pkg-config — the compiler toolchain exists only in the builder stage.
RUN apt-get update && \
    apt-get upgrade -y && \
    apt-get install --no-install-recommends -y tini git curl ca-certificates && \
    apt-get autoremove -y && \
    apt-get clean all && \
    rm -rf /var/lib/apt/lists/*

# Ship the uv/uvx standalone binaries (not the compiler toolchain) so downstream images built
# `FROM` this one can install extra Python packages into /.venv when extending Infrahub.
COPY --from=base /root/.local/bin/uv /root/.local/bin/uvx /usr/local/bin/

RUN mkdir /prom_shared /remote && \
    mkdir -p /opt/infrahub/git /opt/infrahub/storage /opt/infrahub/source /opt/infrahub/frontend/app/dist /opt/infrahub/workflow

# --------------------------------------------
# Configure Git
# --------------------------------------------
RUN git config --global user.name "Infrahub" && \
    git config --global user.email "infrahub@opsmill.com" && \
    git config --global --add safe.directory '*' && \
    git config --global credential.usehttppath true && \
    git config --global credential.helper "/usr/bin/env infrahub-git-credential"

WORKDIR /source

# Bring in the built virtualenv and the source tree its editable installs
# (infrahub-server, infrahub-sdk, infrahub-testcontainers) resolve against.
COPY --from=builder /.venv /.venv
COPY --from=builder /source /source

# Import Frontend & Documentation builds last so frontend/docs edits don't invalidate the copies above
COPY --from=frontend /frontend/app/dist/ /opt/infrahub/frontend/app/dist
COPY --from=docs /docs/build/ /opt/infrahub/docs/build

ENTRYPOINT ["tini", "-g", "--"]
