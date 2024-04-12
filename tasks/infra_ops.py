from __future__ import annotations

from typing import TYPE_CHECKING

from .shared import BUILD_NAME, build_compose_files_cmd, execute_command, get_env_vars
from .utils import ESCAPED_REPO_PATH

if TYPE_CHECKING:
    from invoke.context import Context


def load_infrastructure_data(context: Context, database: str, namespace: str) -> None:
    with context.cd(ESCAPED_REPO_PATH):
        compose_files_cmd = build_compose_files_cmd(database=database)
        base_cmd = f"{get_env_vars(context, namespace=namespace)} docker compose {compose_files_cmd} -p {BUILD_NAME}"
        command = f"{base_cmd} run infrahub-git infrahubctl run models/infrastructure_edge.py"
        execute_command(context=context, command=command)


def load_infrastructure_schema(context: Context, database: str, namespace: str) -> None:
    with context.cd(ESCAPED_REPO_PATH):
        compose_files_cmd = build_compose_files_cmd(database=database)
        base_cmd = f"{get_env_vars(context, namespace=namespace)} docker compose {compose_files_cmd} -p {BUILD_NAME}"
        command = f"{base_cmd} run infrahub-git infrahubctl schema load models/infrastructure_base.yml --wait 30"
        execute_command(context=context, command=command)
