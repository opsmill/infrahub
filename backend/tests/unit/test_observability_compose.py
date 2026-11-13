from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import yaml

DEVELOPMENT_DIR = Path(__file__).resolve().parents[3] / "development"
TRACING_ENVIRONMENT = {
    # An operator turns tracing off by setting INFRAHUB_TRACE_ENABLE=false next to the Compose file.
    "INFRAHUB_TRACE_ENABLE": "${INFRAHUB_TRACE_ENABLE:-true}",
    "INFRAHUB_TRACE_EXPORTER_TYPE": "otlp",
    "INFRAHUB_TRACE_EXPORTER_PROTOCOL": "grpc",
    "INFRAHUB_TRACE_EXPORTER_ENDPOINT": "http://infrahub-tempo:4317",
    "INFRAHUB_TRACE_SAMPLE_RATIO": "${INFRAHUB_TRACE_SAMPLE_RATIO:-0.1}",
}


def _services(file_name: str) -> dict[str, Any]:
    return yaml.safe_load((DEVELOPMENT_DIR / file_name).read_text(encoding="utf-8"))["services"]


@pytest.mark.parametrize("service", ["infrahub-server", "task-worker"])
def test_standalone_observability_file_turns_tracing_on(service: str) -> None:
    assert _services("docker-compose-observability-standalone.yml")[service] == {"environment": TRACING_ENVIRONMENT}


def test_observability_file_leaves_the_infrahub_services_to_the_stack_that_loads_it() -> None:
    # The development stack loads this file too, and a service without an image makes Compose reject the project.
    assert {"server", "infrahub-server", "task-worker"} & set(_services("docker-compose-observability.yml")) == set()
