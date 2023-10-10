FROM python:3.11

RUN apt-get update \
    && apt-get install -y --no-install-recommends docker.io docker-compose \
    && rm -rf /var/lib/apt/lists/* \
    && getent group docker || groupadd docker 

WORKDIR /workspace

COPY . .

RUN apt-get update && apt-get install -y \
    --no-install-recommends \
    build-essential \
    curl

RUN curl -sSL https://install.python-poetry.org | python3 - \
    && pip install invoke

CMD ["poetry", "run", "invoke", "demo.destroy", "demo.build", "demo.init", "demo.start", "demo.load-infra-schema", "demo.load-infra-data"]
