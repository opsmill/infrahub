from __future__ import annotations

from pathlib import Path
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

SCHEMA_PATCHES_LOCAL_PATH = "models/patches/schema/"
SCHEMA_PATCHES_CONTAINER_PATH = "/patches/schema"

SCRIPTS_PATCHES_LOCAL_PATH = "models/patches/data/"
SCRIPTS_PATCHES_CONTAINER_PATH = "/patches/scripts"

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
        command_schema = f"{base_cmd} run {SERVICE_WORKER_NAME} infrahubctl schema load {target}"
        if add_wait:
            command_schema += " --wait 30"
        execute_command(context=context, command=command_schema)


def load_infrastructure_menu(
    context: Context, database: str, namespace: Namespace, menu_target: str = "models/base_menu.yml"
) -> None:
    with context.cd(ESCAPED_REPO_PATH):
        compose_files_cmd = build_compose_files_cmd(database=database, namespace=namespace)
        compose_cmd = get_compose_cmd(namespace=namespace)
        base_cmd = f"{get_env_vars(context, namespace=namespace)} {compose_cmd} {compose_files_cmd} -p {BUILD_NAME}"
        command = f"{base_cmd} run {SERVICE_WORKER_NAME} infrahubctl menu load {menu_target}"
        execute_command(context=context, command=command)


def load_infrastructure_schema_patches(
    context: Context,
    database: str,
    namespace: Namespace,
) -> None:
    with context.cd(ESCAPED_REPO_PATH):
        compose_files_cmd = build_compose_files_cmd(database=database, namespace=namespace)
        compose_cmd = get_compose_cmd(namespace=namespace)
        base_cmd = f"{get_env_vars(context, namespace=namespace)} {compose_cmd} {compose_files_cmd} -p {BUILD_NAME}"

        command_schema = (
            f"{base_cmd} run -v {Path(SCHEMA_PATCHES_LOCAL_PATH).resolve()}:{SCHEMA_PATCHES_CONTAINER_PATH} "
            f"{SERVICE_WORKER_NAME} infrahubctl schema load {SCHEMA_PATCHES_CONTAINER_PATH}"
        )
        execute_command(context=context, command=command_schema)


def run_infrastructure_patch_scripts(
    context: Context,
    database: str,
    namespace: Namespace,
) -> None:
    with context.cd(ESCAPED_REPO_PATH):
        compose_files_cmd = build_compose_files_cmd(database=database, namespace=namespace)
        compose_cmd = get_compose_cmd(namespace=namespace)
        base_cmd = f"{get_env_vars(context, namespace=namespace)} {compose_cmd} {compose_files_cmd} -p {BUILD_NAME}"

        # TODO iterate over scripts within folder if/when we need multiple patch scripts
        script_name = "dedup_ip_addresses.py"

        command_schema = (
            f"{base_cmd} run -v {Path(SCRIPTS_PATCHES_LOCAL_PATH).resolve()}:{SCRIPTS_PATCHES_CONTAINER_PATH} "
            f"{SERVICE_WORKER_NAME} python {Path(SCRIPTS_PATCHES_CONTAINER_PATH) / script_name}"
        )
        execute_command(context=context, command=command_schema)
