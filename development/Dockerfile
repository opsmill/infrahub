ARG PYTHON_VER
FROM python:3.9-slim

ENV PATH="${PATH}:/root/.local/bin"

RUN apt -y update && apt -y install git

RUN pip install poetry && \
    poetry config virtualenvs.create false && \
    poetry config installer.parallel false

WORKDIR /source

# Copy in only pyproject.toml/poetry.lock to help with caching this layer if no updates to dependencies
COPY poetry.lock pyproject.toml /source/
# --no-root declares not to install the project package since we're wanting to take advantage of caching dependency installation
# and the project is copied in and installed after this step
RUN poetry install --no-interaction --no-ansi --no-root

# Copy in the rest of the source code and install local Nautobot plugin
COPY . /source
RUN poetry install --no-interaction --no-ansi
