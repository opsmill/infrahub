ARG PYTHON_VER=3.11

# --------------------------------------------------------------------------------
# Builder
#  - Retrieve Alpine docker image (latest)
#  - Install git
#  - Clone Memgraph Prometheus Exporter repository
# --------------------------------------------------------------------------------
FROM alpine:latest as builder

RUN apk update
RUN apk add git

RUN git clone https://github.com/memgraph/prometheus-exporter.git

# --------------------------------------------------------------------------------
# Base
#  - Retrieve Python docker image (PYTHON_VER)
#  - Install the dependencies
#  - Copy the python code from the builder
# --------------------------------------------------------------------------------

FROM docker.io/python:${PYTHON_VER}
RUN python3 -m pip install requests prometheus_client pyyaml

WORKDIR    /exporter
COPY --from=builder prometheus-exporter/*.py /exporter/
COPY config.yml /exporter/config.yaml

EXPOSE 9115
ENTRYPOINT ["python3", "main.py"]
