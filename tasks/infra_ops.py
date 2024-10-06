from __future__ import annotations

from typing import TYPE_CHECKING

from .shared import (
    BUILD_NAME,
    SERVICE_WORKER_NAME,
    Namespace,
    build_compose_files_cmd,
    execute_command,
    get_compose_cmd,
    get_env_vars,
)
from .utils import ESCAPED_REPO_PATH

if TYPE_CHECKING:
    from invoke.context import Context


def load_infrastructure_data(context: Context, database: str, namespace: Namespace) -> None:
    with context.cd(ESCAPED_REPO_PATH):
        compose_files_cmd = build_compose_files_cmd(database=database, namespace=namespace)
        compose_cmd = get_compose_cmd(namespace=namespace)
        base_cmd = f"{get_env_vars(context, namespace=namespace)} {compose_cmd} {compose_files_cmd} -p {BUILD_NAME}"
        command = f"{base_cmd} run {SERVICE_WORKER_NAME} infrahubctl run models/infrastructure_edge.py"
        execute_command(context=context, command=command)


def load_infrastructure_schema(
    context: Context, database: str, namespace: Namespace, add_wait: bool = True, target: str = "models/base"
) -> None:
    with context.cd(ESCAPED_REPO_PATH):
        compose_files_cmd = build_compose_files_cmd(database=database, namespace=namespace)
        compose_cmd = get_compose_cmd(namespace=namespace)
        base_cmd = f"{get_env_vars(context, namespace=namespace)} {compose_cmd} {compose_files_cmd} -p {BUILD_NAME}"
        command = f"{base_cmd} run {SERVICE_WORKER_NAME} infrahubctl schema load {target}"
        if add_wait:
            command += " --wait 30"
        execute_command(context=context, command=command)
