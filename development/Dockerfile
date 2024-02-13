# ****************************************************************
# STAGE : Base Python Image
# ****************************************************************
ARG PYTHON_VER=3.11
FROM docker.io/python:${PYTHON_VER} AS base

ENV PYTHONUNBUFFERED 1

ENV PATH="${PATH}:/root/.local/bin" \
    PROMETHEUS_MULTIPROC_DIR="/prom_shared" \
    INFRAHUB_FRONTEND_DIRECTORY="/opt/infrahub/frontend" \
    INFRAHUB_DOCS_DIRECTORY="/opt/infrahub/docs"

RUN mkdir /prom_shared /remote

RUN apt-get update && \
    apt-get upgrade -y && \
    apt-get install --no-install-recommends -y curl git pkg-config build-essential ca-certificates && \
    curl -sSL https://install.python-poetry.org | python3 - && \
    rm -rf /var/lib/apt/lists/* && \
    rm -rf /var/lib/apt/lists/* && \
    pip --no-cache-dir install --no-compile --upgrade pip wheel

RUN poetry config virtualenvs.create false

# ****************************************************************
# STAGE : Frontend
# ****************************************************************
FROM docker.io/node:20-slim AS frontend

RUN mkdir /source

COPY frontend/package.json  frontend/package-lock.json /source/

WORKDIR /source

RUN npm install --omit=dev
COPY frontend/ /source/
RUN npm run build && npm cache clean --force \

# ****************************************************************
# STAGE : Documentation
# ****************************************************************
FROM frontend

RUN mkdir /docs

COPY docs/package.json  docs/package-lock.json /docs/
COPY backend/infrahub/config.py /backend/infrahub/
COPY models/ /models/
COPY python_sdk/examples/  /python_sdk/examples/
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
    git config --global credential.helper /usr/local/bin/infrahub-git-credential

RUN mkdir -p /opt/infrahub/git /opt/infrahub/storage /opt/infrahub/source /opt/infrahub/frontend/dist

WORKDIR /source

# --------------------------------------------
# Import Frontend Build
# --------------------------------------------
COPY --from=frontend /source/dist/ /opt/infrahub/frontend/dist

# --------------------------------------------
# Import Documentation Build
# --------------------------------------------
COPY --from=frontend /docs/build/ /opt/infrahub/docs/build

# --------------------------------------------
# Install Dependencies
#   Copy in only pyproject.toml/poetry.lock to help with caching this layer if no updates to dependencies
# --------------------------------------------
COPY poetry.lock pyproject.toml /source/
RUN poetry install --no-interaction --no-ansi --no-root --no-directory

# --------------------------------------------
# Copy in the rest of the source code and install the project
# --------------------------------------------
COPY . ./
RUN poetry install --no-interaction --no-ansi

# --------------------------------------------
# Purge & Cleanup
# --------------------------------------------
RUN apt-get autoremove -y && \
    apt-get clean all && \
    rm -rf /var/lib/apt/lists/*
