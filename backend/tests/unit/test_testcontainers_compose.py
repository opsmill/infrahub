from __future__ import annotations

from pathlib import Path

import pytest
import yaml

TESTCONTAINERS_DIR = Path(__file__).resolve().parents[3] / "python_testcontainers" / "infrahub_testcontainers"
INFRAHUB_IMAGE = "${INFRAHUB_TESTING_DOCKER_IMAGE}:${INFRAHUB_TESTING_IMAGE_VERSION}"


@pytest.mark.parametrize("file_name", ["docker-compose.test.yml", "docker-compose-cluster.test.yml"])
def test_every_infrahub_container_takes_the_log_format_and_level_of_the_test_stack(file_name: str) -> None:
    services = yaml.safe_load((TESTCONTAINERS_DIR / file_name).read_text(encoding="utf-8"))["services"]

    logging_environment = {
        name: (service["environment"].get("INFRAHUB_PRODUCTION"), service["environment"].get("INFRAHUB_LOG_LEVEL"))
        for name, service in services.items()
        if service.get("image") == INFRAHUB_IMAGE
    }

    assert logging_environment == {
        "task-manager": ("${INFRAHUB_TESTING_PRODUCTION}", "${INFRAHUB_TESTING_LOG_LEVEL:-INFO}"),
        "task-manager-background-svc": ("${INFRAHUB_TESTING_PRODUCTION}", "${INFRAHUB_TESTING_LOG_LEVEL:-INFO}"),
        "infrahub-server": ("${INFRAHUB_TESTING_PRODUCTION}", "${INFRAHUB_TESTING_LOG_LEVEL:-INFO}"),
        "task-worker": ("${INFRAHUB_TESTING_PRODUCTION}", "${INFRAHUB_TESTING_LOG_LEVEL}"),
    }
