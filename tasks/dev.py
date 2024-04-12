from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from invoke.tasks import task

from .container_ops import build_images
from .shared import (
    BUILD_NAME,
    INFRAHUB_DATABASE,
    PYTHON_VER,
    build_dev_compose_files_cmd,
    execute_command,
    get_env_vars,
)
from .utils import ESCAPED_REPO_PATH

if TYPE_CHECKING:
    from invoke.context import Context


NAMESPACE = "DEV"


@task(optional=["database"])
def build(
    context: Context,
    service: Optional[str] = None,
    python_ver: str = PYTHON_VER,
    nocache: bool = False,
    database: str = INFRAHUB_DATABASE,
):
    """Build an image with the provided name and python version.

    Args:
        context (obj): Used to run specific commands
        python_ver (str): Define the Python version docker image to build from
        nocache (bool): Do not use cache when building the image
    """
    build_images(context=context, service=service, python_ver=python_ver, nocache=nocache, database=database)


@task(optional=["database"])
def deps(context: Context, database: str = INFRAHUB_DATABASE):
    """Start local instances of dependencies (Databases and Message Bus)."""
    with context.cd(ESCAPED_REPO_PATH):
        dev_compose_files_cmd = build_dev_compose_files_cmd(database=database)
        command = f"{get_env_vars(context)} docker compose {dev_compose_files_cmd} -p {BUILD_NAME} up -d"
        execute_command(context=context, command=command)
