from __future__ import annotations

import re
import subprocess  # noqa: S404
from typing import TYPE_CHECKING

import pytest
from testcontainers.core.config import testcontainers_config

from infrahub_testcontainers.container import InfrahubDockerCompose
from infrahub_testcontainers.reaper import ComposeProjectReaper

if TYPE_CHECKING:
    import socket
    from pathlib import Path

ACKNOWLEDGEMENT_TIMEOUT_SECONDS = 1.0


class RefusingConnector:
    """Records each connection attempt to Ryuk and refuses it."""

    def __init__(self) -> None:
        self.attempts = 0

    def __call__(self) -> socket.socket:
        self.attempts += 1
        raise ConnectionRefusedError


def build_compose(tmp_path: Path, project_name: str | None, connector: RefusingConnector) -> InfrahubDockerCompose:
    return InfrahubDockerCompose(
        context=tmp_path,
        project_name=project_name,
        # `false` stands in for the docker binary so that reaching the compose command fails without Docker.
        docker_command_path="false",
        compose_project_reaper=ComposeProjectReaper(
            connect=connector, acknowledgement_timeout=ACKNOWLEDGEMENT_TIMEOUT_SECONDS
        ),
    )


@pytest.mark.parametrize("start_method", ["start", "start_container"])
def test_starting_fails_with_the_ryuk_opt_out_when_ryuk_refuses_the_registration(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, start_method: str
) -> None:
    monkeypatch.setattr(testcontainers_config, "ryuk_disabled", False)
    connector = RefusingConnector()
    compose = build_compose(tmp_path=tmp_path, project_name="infrahub-test-1a2b3c4d", connector=connector)
    start_arguments = {"service_name": "database"} if start_method == "start_container" else {}

    with pytest.raises(RuntimeError) as exc_info:
        getattr(compose, start_method)(**start_arguments)

    assert str(exc_info.value) == (
        "Could not register the compose project infrahub-test-1a2b3c4d with Ryuk, the testcontainers cleanup "
        "container; set TESTCONTAINERS_RYUK_DISABLED=true to start the stack without it"
    )
    assert isinstance(exc_info.value.__cause__, ConnectionRefusedError)
    assert connector.attempts == 1


@pytest.mark.parametrize(
    ("ryuk_disabled", "project_name"),
    [
        pytest.param(True, "infrahub-test-1a2b3c4d", id="ryuk_disabled"),
        pytest.param(False, None, id="no_project_name"),
    ],
)
def test_start_skips_the_ryuk_registration(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, *, ryuk_disabled: bool, project_name: str | None
) -> None:
    monkeypatch.setattr(testcontainers_config, "ryuk_disabled", ryuk_disabled)
    connector = RefusingConnector()
    compose = build_compose(tmp_path=tmp_path, project_name=project_name, connector=connector)

    with pytest.raises(subprocess.CalledProcessError, match=re.escape("'false', 'compose'")):
        compose.start()

    assert connector.attempts == 0
