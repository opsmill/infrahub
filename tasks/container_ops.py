from __future__ import annotations

import sys
from typing import TYPE_CHECKING, Optional

from .shared import (
    AVAILABLE_SERVICES,
    BUILD_NAME,
    INFRAHUB_DATABASE,
    PYTHON_VER,
    build_compose_files_cmd,
    execute_command,
    get_env_vars,
)
from .utils import ESCAPED_REPO_PATH

if TYPE_CHECKING:
    from invoke.context import Context


def build_images(
    context: Context,
    service: Optional[str] = None,
    python_ver: str = PYTHON_VER,
    nocache: bool = False,
    database: str = INFRAHUB_DATABASE,
):
    if service and service not in AVAILABLE_SERVICES:
        sys.exit(f"{service} is not a valid service ({AVAILABLE_SERVICES})")

    print("Building images")

    with context.cd(ESCAPED_REPO_PATH):
        compose_files_cmd = build_compose_files_cmd(database=database)
        base_cmd = f"{get_env_vars(context)} docker compose {compose_files_cmd} -p {BUILD_NAME}"
        print(f"base_cmd={base_cmd}")
        exec_cmd = f"build --build-arg PYTHON_VER={python_ver}"
        print(f"exec_cmd={exec_cmd}")
        if nocache:
            exec_cmd += " --no-cache"

        if service:
            exec_cmd += f" {service}"

        execute_command(context=context, command=f"{base_cmd} {exec_cmd}", print_cmd=True)
