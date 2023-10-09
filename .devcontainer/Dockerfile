FROM python:3.11

RUN apt-get update \
    && apt-get install -y --no-install-recommends docker.io docker-compose \
    && rm -rf /var/lib/apt/lists/* \
    && getent group docker || groupadd docker 

WORKDIR /workspace

COPY . .

RUN apt-get update && \
    apt-get upgrade -y && \
    apt-get install --no-install-recommends -y pkg-config build-essential && \
    apt-get autoremove -y && \
    apt-get clean all && \
    rm -rf /var/lib/apt/lists/* && \
    pip --no-cache-dir install --upgrade pip wheel

RUN pip install --no-cache-dir --upgrade pip toml invoke \
    && curl -sSL https://install.python-poetry.org | python3 - \
    && poetry config virtualenvs.create false

RUN useradd -ms /bin/bash infrahub
USER infrahub

CMD ["poetry", "run", "invoke", "demo.destroy", "demo.init", "demo.start", "demo.load-infra-schema", "demo.load-infra-data"]
