"""Start a compose project, mark it as started, then block until the process is killed.

Usage: start_compose.py <compose directory> <project name> <started marker path>
"""

# ruff: noqa: INP001 - run as a standalone script, never imported

from __future__ import annotations

import sys
from pathlib import Path

from infrahub_testcontainers.container import InfrahubDockerCompose

compose_directory, project_name, started_marker = sys.argv[1:4]

compose = InfrahubDockerCompose(
    context=Path(compose_directory),
    compose_file_name=["compose.yml"],
    project_name=project_name,
    wait=False,
)
compose.start()
Path(started_marker).touch()
sys.stdin.read()
