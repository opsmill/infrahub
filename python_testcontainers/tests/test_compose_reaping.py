from __future__ import annotations

import os
import subprocess  # noqa: S404
import sys
import time
import uuid
from pathlib import Path
from typing import TYPE_CHECKING

import docker
import pytest

if TYPE_CHECKING:
    from collections.abc import Callable, Generator

    from docker import DockerClient

FIXTURE_DIRECTORY = Path(__file__).parent / "fixtures" / "compose_reaping"
START_DEADLINE_SECONDS = 300
REMOVAL_DEADLINE_SECONDS = 120
POLL_INTERVAL_SECONDS = 1


@pytest.fixture(name="docker_client")
def fixture_docker_client() -> Generator[DockerClient, None, None]:
    client = docker.from_env()
    yield client
    client.close()


@pytest.fixture(name="project_name")
def fixture_project_name(docker_client: DockerClient) -> Generator[str, None, None]:
    project_name = f"infrahub-test-reaping-{uuid.uuid4().hex[:8]}"
    yield project_name

    label_filter = {"label": f"com.docker.compose.project={project_name}"}
    for container in docker_client.containers.list(all=True, filters=label_filter, ignore_removed=True):
        container.remove(force=True, v=True)
    for network in docker_client.networks.list(filters=label_filter):
        network.remove()
    for volume in docker_client.volumes.list(filters=label_filter):
        volume.remove(force=True)


def project_resources(docker_client: DockerClient, project_name: str) -> dict[str, list[str]]:
    label_filter = {"label": f"com.docker.compose.project={project_name}"}
    # Ryuk can remove a listed container before the client inspects it.
    containers = docker_client.containers.list(all=True, filters=label_filter, ignore_removed=True)
    return {
        "containers": sorted(container.name for container in containers),
        "networks": sorted(network.name for network in docker_client.networks.list(filters=label_filter)),
        "volumes": sorted(volume.name for volume in docker_client.volumes.list(filters=label_filter)),
    }


def wait_until(condition: Callable[[], bool], deadline_seconds: float) -> None:
    deadline = time.monotonic() + deadline_seconds
    while not condition() and time.monotonic() < deadline:
        time.sleep(POLL_INTERVAL_SECONDS)


def test_compose_project_is_removed_after_the_process_that_started_it_is_killed(
    tmp_path: Path, docker_client: DockerClient, project_name: str
) -> None:
    started_marker = tmp_path / "started"
    output_path = tmp_path / "start_compose.log"
    environment = {key: value for key, value in os.environ.items() if key != "TESTCONTAINERS_RYUK_DISABLED"}

    with output_path.open(mode="w", encoding="utf-8") as output:
        process = subprocess.Popen(  # noqa: S603
            [
                sys.executable,
                str(FIXTURE_DIRECTORY / "start_compose.py"),
                str(FIXTURE_DIRECTORY),
                project_name,
                str(started_marker),
            ],
            stdin=subprocess.PIPE,
            stdout=output,
            stderr=subprocess.STDOUT,
            env=environment,
        )
    try:
        wait_until(
            condition=lambda: started_marker.exists() or process.poll() is not None,
            deadline_seconds=START_DEADLINE_SECONDS,
        )
        assert started_marker.exists(), output_path.read_text(encoding="utf-8")
        assert project_resources(docker_client=docker_client, project_name=project_name) == {
            "containers": [f"{project_name}-idle-1"],
            "networks": [f"{project_name}_default"],
            "volumes": [f"{project_name}_data"],
        }
    finally:
        process.kill()
        process.wait()

    empty_project: dict[str, list[str]] = {"containers": [], "networks": [], "volumes": []}
    wait_until(
        condition=lambda: project_resources(docker_client=docker_client, project_name=project_name) == empty_project,
        deadline_seconds=REMOVAL_DEADLINE_SECONDS,
    )
    assert project_resources(docker_client=docker_client, project_name=project_name) == empty_project
