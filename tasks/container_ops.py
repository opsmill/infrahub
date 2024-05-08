from __future__ import annotations

import sys
from typing import TYPE_CHECKING, Optional

from .shared import AVAILABLE_SERVICES, BUILD_NAME, build_compose_files_cmd, execute_command, get_env_vars
from .utils import ESCAPED_REPO_PATH

if TYPE_CHECKING:
    from invoke.context import Context


def build_images(
    context: Context,
    python_ver: str,
    nocache: bool,
    database: str,
    namespace: str,
    service: Optional[str] = None,
) -> None:
    if service and service not in AVAILABLE_SERVICES:
        sys.exit(f"{service} is not a valid service ({AVAILABLE_SERVICES})")

    print("Building images")

    with context.cd(ESCAPED_REPO_PATH):
        compose_files_cmd = build_compose_files_cmd(database=database, namespace=namespace)
        base_cmd = f"{get_env_vars(context, namespace=namespace)} docker compose {compose_files_cmd} -p {BUILD_NAME}"
        print(f"base_cmd={base_cmd}")
        exec_cmd = f"build --build-arg PYTHON_VER={python_ver}"
        print(f"exec_cmd={exec_cmd}")
        if nocache:
            exec_cmd += " --no-cache"

        if service:
            exec_cmd += f" {service}"

        execute_command(context=context, command=f"{base_cmd} {exec_cmd}", print_cmd=True)


def destroy_environment(
    context: Context,
    database: str,
    namespace: str,
) -> None:
    with context.cd(ESCAPED_REPO_PATH):
        compose_files_cmd = build_compose_files_cmd(database=database, namespace=namespace)

        command = f"{get_env_vars(context)} docker compose {compose_files_cmd} -p {BUILD_NAME} down --remove-orphans --volumes --timeout 1"
        execute_command(context=context, command=command)


def pull_images(context: Context, database: str, namespace: str) -> None:
    with context.cd(ESCAPED_REPO_PATH):
        compose_files_cmd = build_compose_files_cmd(database=database, namespace=namespace)

        for service in AVAILABLE_SERVICES:
            if "infrahub" in service:
                continue
            command = f"{get_env_vars(context, namespace=namespace)} docker compose {compose_files_cmd} -p {BUILD_NAME} pull {service}"
            execute_command(context=context, command=command)


def restart_services(context: Context, database: str, namespace: str) -> None:
    with context.cd(ESCAPED_REPO_PATH):
        compose_files_cmd = build_compose_files_cmd(database=database, namespace=namespace)
        base_cmd = f"{get_env_vars(context, namespace=namespace)} docker compose {compose_files_cmd} -p {BUILD_NAME}"

        execute_command(context=context, command=f"{base_cmd} restart infrahub-server")
        execute_command(context=context, command=f"{base_cmd} restart infrahub-git")


def show_service_status(context: Context, database: str, namespace: str) -> None:
    with context.cd(ESCAPED_REPO_PATH):
        compose_files_cmd = build_compose_files_cmd(database=database, namespace=namespace)
        command = f"{get_env_vars(context, namespace=namespace)} docker compose {compose_files_cmd} -p {BUILD_NAME} ps"
        execute_command(context=context, command=command)


def start_services(context: Context, database: str, namespace: str) -> None:
    with context.cd(ESCAPED_REPO_PATH):
        compose_files_cmd = build_compose_files_cmd(database=database, namespace=namespace)
        command = (
            f"{get_env_vars(context, namespace=namespace)} docker compose {compose_files_cmd} -p {BUILD_NAME} up -d"
        )
        execute_command(context=context, command=command)


def stop_services(context: Context, database: str, namespace: str) -> None:
    with context.cd(ESCAPED_REPO_PATH):
        compose_files_cmd = build_compose_files_cmd(database=database, namespace=namespace)
        command = (
            f"{get_env_vars(context, namespace=namespace)} docker compose  {compose_files_cmd} -p {BUILD_NAME} down"
        )
        execute_command(context=context, command=command)


def migrate_database(context: Context, database: str, namespace: str) -> None:
    """Apply the latest database migrations."""
    with context.cd(ESCAPED_REPO_PATH):
        compose_files_cmd = build_compose_files_cmd(database=database, namespace=namespace)
        base_cmd = f"{get_env_vars(context, namespace=namespace)} docker compose {compose_files_cmd} -p {BUILD_NAME}"
        command = f"{base_cmd} run infrahub-server infrahub db migrate"
        execute_command(context=context, command=command)


def update_core_schema(context: Context, database: str, namespace: str, debug: bool = False) -> None:
    """Update the core schema."""
    with context.cd(ESCAPED_REPO_PATH):
        compose_files_cmd = build_compose_files_cmd(database=database, namespace=namespace)
        base_cmd = f"{get_env_vars(context, namespace=namespace)} docker compose {compose_files_cmd} -p {BUILD_NAME}"
        command = f"{base_cmd} run infrahub-server infrahub db update-core-schema"
        if debug:
            command += " --debug"
        execute_command(context=context, command=command)
