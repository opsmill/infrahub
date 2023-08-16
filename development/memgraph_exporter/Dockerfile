FROM python:3.9 as builder

RUN apt-get update \
  && apt-get -y upgrade \
  && python3 -m pip install --upgrade pip \
  && apt-get install -y curl \
  && curl -sSL https://install.python-poetry.org | python3 -

ENV PATH="/root/.local/bin:$PATH"

RUN git clone https://github.com/memgraph/prometheus-exporter.git

FROM python:3.9

RUN python3 -m pip install requests prometheus_client pyyaml

WORKDIR    /exporter

COPY --from=builder prometheus-exporter/*.py /exporter/
COPY config.yml /exporter/config.yaml

EXPOSE 9115

ENTRYPOINT ["python3", "main.py"]
