# ****************************************************************
# STAGE : Base Python Image
# ****************************************************************
ARG PYTHON_VER=3.11
FROM docker.io/python:${PYTHON_VER} AS base

ENV PYTHONUNBUFFERED 1

RUN mkdir /prom_shared
RUN mkdir /remote

RUN apt-get update && \
    apt-get upgrade -y && \
    apt-get install --no-install-recommends -y pkg-config build-essential && \
    apt-get autoremove -y && \
    apt-get clean all && \
    rm -rf /var/lib/apt/lists/* && \
    pip --no-cache-dir install --upgrade pip wheel

RUN curl -sSL https://install.python-poetry.org | python3 -
ENV PATH="${PATH}:/root/.local/bin"

RUN poetry config virtualenvs.create false

# ****************************************************************
# STAGE : Frontend
# ****************************************************************
FROM docker.io/node:16-slim AS frontend

RUN mkdir /source

RUN npm install -g npm@latest
COPY frontend/package.json  frontend/package-lock.json /source/

WORKDIR /source

RUN npm install --omit=dev
COPY frontend/ /source/
RUN npm run build

# ****************************************************************
# STAGE : Backend
# ****************************************************************
FROM base AS backend

# --------------------------------------------
# Configure Git & Environment
# --------------------------------------------
RUN git config --global user.name "Infrahub"
RUN git config --global user.email "infrahub@opsmill.com"
RUN git config --global --add safe.directory '*'
RUN git config --global credential.usehttppath true
RUN git config --global credential.helper /usr/local/bin/infrahub-git-credential

RUN mkdir -p /opt/infrahub/git
RUN mkdir -p /opt/infrahub/storage

WORKDIR /source

# --------------------------------------------
# Import Frontend Build
# --------------------------------------------
RUN mkdir -p /opt/infrahub/frontend/dist
COPY --from=frontend /source/dist/ /opt/infrahub/frontend/dist

# --------------------------------------------
# Install Dependencies
#   Copy in only pyproject.toml/poetry.lock to help with caching this layer if no updates to dependencies
# --------------------------------------------
COPY poetry.lock pyproject.toml /source/
RUN poetry install --no-interaction --no-ansi --no-root

# --------------------------------------------
# Copy in the rest of the source code and install the project
# --------------------------------------------
COPY . /source
RUN poetry install --no-interaction --no-ansi

# ****************************************************************
# STAGE : Gitpod
# ****************************************************************

FROM backend as gitpod

# --------------------------------------------
# Create new user and assign the right permissions
# --------------------------------------------
ARG USER_ID=33333
ARG GROUP_ID=33333

RUN addgroup --gid ${GROUP_ID} user
RUN adduser --disabled-password --gecos '' --uid ${USER_ID} --gid ${GROUP_ID} user

RUN chown -R ${USER_ID}:${GROUP_ID} /prom_shared
RUN chown -R ${USER_ID}:${GROUP_ID} /opt
RUN chown -R ${USER_ID}:${GROUP_ID} /remote

USER user
