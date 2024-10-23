from __future__ import annotations

import sys
from typing import TYPE_CHECKING

from .shared import (
    AVAILABLE_SERVICES,
    BUILD_NAME,
    SERVICE_SERVER_NAME,
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


def build_images(
    context: Context,
    python_ver: str,
    nocache: bool,
    database: str,
    namespace: Namespace,
    service: str | None = None,
) -> None:
    if service and service not in AVAILABLE_SERVICES:
        sys.exit(f"{service} is not a valid service ({AVAILABLE_SERVICES})")

    print("Building images")

    with context.cd(ESCAPED_REPO_PATH):
        compose_files_cmd = build_compose_files_cmd(database=database, namespace=namespace)
        compose_cmd = get_compose_cmd(namespace=namespace)
        base_cmd = f"{get_env_vars(context, namespace=namespace)} {compose_cmd} {compose_files_cmd} -p {BUILD_NAME}"
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
    namespace: Namespace,
) -> None:
    with context.cd(ESCAPED_REPO_PATH):
        compose_files_cmd = build_compose_files_cmd(database=database, namespace=namespace)
        compose_cmd = get_compose_cmd(namespace=namespace)
        command = f"{get_env_vars(context)} {compose_cmd} {compose_files_cmd} -p {BUILD_NAME} down --remove-orphans --volumes --timeout 1"
        execute_command(context=context, command=command)


def pull_images(context: Context, database: str, namespace: Namespace) -> None:
    with context.cd(ESCAPED_REPO_PATH):
        compose_files_cmd = build_compose_files_cmd(database=database, namespace=namespace)
        compose_cmd = get_compose_cmd(namespace=namespace)
        for service in AVAILABLE_SERVICES:
            if service in [SERVICE_SERVER_NAME, SERVICE_WORKER_NAME]:
                continue
            command = f"{get_env_vars(context, namespace=namespace)} {compose_cmd} {compose_files_cmd} -p {BUILD_NAME} pull {service}"
            execute_command(context=context, command=command)


def restart_services(context: Context, database: str, namespace: Namespace) -> None:
    with context.cd(ESCAPED_REPO_PATH):
        compose_files_cmd = build_compose_files_cmd(database=database, namespace=namespace)
        compose_cmd = get_compose_cmd(namespace=namespace)
        base_cmd = f"{get_env_vars(context, namespace=namespace)} {compose_cmd} {compose_files_cmd} -p {BUILD_NAME}"

        execute_command(context=context, command=f"{base_cmd} restart {SERVICE_SERVER_NAME}")
        execute_command(context=context, command=f"{base_cmd} restart {SERVICE_WORKER_NAME}")


def show_service_status(context: Context, database: str, namespace: Namespace) -> None:
    with context.cd(ESCAPED_REPO_PATH):
        compose_files_cmd = build_compose_files_cmd(database=database, namespace=namespace)
        compose_cmd = get_compose_cmd(namespace=namespace)
        command = f"{get_env_vars(context, namespace=namespace)} {compose_cmd} {compose_files_cmd} -p {BUILD_NAME} ps"
        execute_command(context=context, command=command)


def start_services(context: Context, database: str, namespace: Namespace, wait: bool) -> None:
    with context.cd(ESCAPED_REPO_PATH):
        compose_files_cmd = build_compose_files_cmd(database=database, namespace=namespace)
        compose_cmd = get_compose_cmd(namespace=namespace)
        should_wait = " --wait" if wait else ""
        command = f"{get_env_vars(context, namespace=namespace)} {compose_cmd} {compose_files_cmd} -p {BUILD_NAME} up -d{should_wait}"
        execute_command(context=context, command=command)


def stop_services(context: Context, database: str, namespace: Namespace) -> None:
    with context.cd(ESCAPED_REPO_PATH):
        compose_files_cmd = build_compose_files_cmd(database=database, namespace=namespace)
        compose_cmd = get_compose_cmd(namespace=namespace)
        command = f"{get_env_vars(context, namespace=namespace)} {compose_cmd} {compose_files_cmd} -p {BUILD_NAME} down"
        execute_command(context=context, command=command)


def migrate_database(context: Context, database: str, namespace: Namespace) -> None:
    """Apply the latest database migrations."""
    with context.cd(ESCAPED_REPO_PATH):
        compose_files_cmd = build_compose_files_cmd(database=database, namespace=namespace)
        compose_cmd = get_compose_cmd(namespace=namespace)
        base_cmd = f"{get_env_vars(context, namespace=namespace)} {compose_cmd} {compose_files_cmd} -p {BUILD_NAME}"
        command = f"{base_cmd} run {SERVICE_SERVER_NAME} infrahub db migrate"
        execute_command(context=context, command=command)


def update_core_schema(context: Context, database: str, namespace: Namespace, debug: bool = False) -> None:
    """Update the core schema."""
    with context.cd(ESCAPED_REPO_PATH):
        compose_files_cmd = build_compose_files_cmd(database=database, namespace=namespace)
        compose_cmd = get_compose_cmd(namespace=namespace)
        base_cmd = f"{get_env_vars(context, namespace=namespace)} {compose_cmd} {compose_files_cmd} -p {BUILD_NAME}"
        command = f"{base_cmd} run {SERVICE_SERVER_NAME} infrahub db update-core-schema"
        if debug:
            command += " --debug"
        execute_command(context=context, command=command)
