from __future__ import annotations

import os
from typing import TYPE_CHECKING

from invoke.tasks import task

from .container_ops import (
    build_images,
    destroy_environment,
    display_container_status,
    pull_images,
    restart_services,
    show_service_status,
    start_services,
    stop_services,
    upgrade_infrahub,
)
from .infra_ops import load_infrastructure_data, load_infrastructure_menu, load_infrastructure_schema
from .shared import (
    BUILD_NAME,
    INFRAHUB_DATABASE,
    PYTHON_VER,
    SERVICE_WORKER_NAME,
    Namespace,
    build_compose_files_cmd,
    build_dev_compose_files_cmd,
    execute_command,
    get_compose_cmd,
    get_env_vars,
)
from .utils import ESCAPED_REPO_PATH

if TYPE_CHECKING:
    from invoke.context import Context

NAMESPACE = Namespace.DEV


@task(optional=["database"])
def build(
    context: Context,
    service: str | None = None,
    python_ver: str = PYTHON_VER,
    nocache: bool = False,
    database: str = INFRAHUB_DATABASE,
) -> None:
    """Build an image with the provided name and python version.

    Args:
        context (obj): Used to run specific commands
        python_ver (str): Define the Python version docker image to build from
        nocache (bool): Do not use cache when building the image
    """
    build_images(
        context=context, service=service, python_ver=python_ver, nocache=nocache, database=database, namespace=NAMESPACE
    )


@task(optional=["database"])
def debug(context: Context, database: str = INFRAHUB_DATABASE) -> None:
    """Start a local instance of Infrahub in debug mode."""
    with context.cd(ESCAPED_REPO_PATH):
        compose_files_cmd = build_compose_files_cmd(database=database)
        compose_cmd = get_compose_cmd(namespace=NAMESPACE)
        command = f"{get_env_vars(context, namespace=NAMESPACE)} {compose_cmd} {compose_files_cmd} -p {BUILD_NAME} up"
        execute_command(context=context, command=command)


@task(optional=["database"])
def deps(context: Context, database: str = INFRAHUB_DATABASE) -> None:
    """Start local instances of dependencies (Databases and Message Bus)."""
    with context.cd(ESCAPED_REPO_PATH):
        dev_compose_files_cmd = build_dev_compose_files_cmd(database=database)
        compose_cmd = get_compose_cmd(namespace=NAMESPACE)
        command = (
            f"{get_env_vars(context, namespace=NAMESPACE)} {compose_cmd} {dev_compose_files_cmd} -p {BUILD_NAME} up -d"
        )
        execute_command(context=context, command=command)


@task
def destroy(context: Context, database: str = INFRAHUB_DATABASE) -> None:
    """Destroy all containers and volumes."""
    destroy_environment(context=context, database=database, namespace=NAMESPACE)


@task(optional=["database"])
def infra_git_create(
    context: Context,
    database: str = INFRAHUB_DATABASE,
    name: str = "demo-edge",
    location: str = "/remote/infrahub-demo-edge",
) -> None:
    """Load some demo data."""
    with context.cd(ESCAPED_REPO_PATH):
        compose_files_cmd = build_compose_files_cmd(database=database, namespace=NAMESPACE)
        compose_cmd = get_compose_cmd(namespace=NAMESPACE)
        base_cmd = f"{get_env_vars(context, namespace=NAMESPACE)} {compose_cmd} {compose_files_cmd} -p {BUILD_NAME}"
        execute_command(
            context=context,
            command=f"{base_cmd} run {SERVICE_WORKER_NAME} infrahubctl repository add {name} {location}",
        )


@task(optional=["database"])
def infra_git_import(context: Context, database: str = INFRAHUB_DATABASE) -> None:
    """Load some demo data."""
    REPO_NAME = "infrahub-demo-edge"
    with context.cd(ESCAPED_REPO_PATH):
        compose_files_cmd = build_compose_files_cmd(database=database, namespace=NAMESPACE)
        compose_cmd = get_compose_cmd(namespace=NAMESPACE)
        base_cmd = f"{get_env_vars(context, namespace=NAMESPACE)} {compose_cmd} {compose_files_cmd} -p {BUILD_NAME}"
        execute_command(
            context=context,
            command=f"{base_cmd} run {SERVICE_WORKER_NAME} cp -r backend/tests/fixtures/repos/{REPO_NAME}/initial__main /remote/{REPO_NAME}",
        )
        execute_command(
            context=context,
            command=f"{base_cmd} exec --workdir /remote/{REPO_NAME} {SERVICE_WORKER_NAME} git init --initial-branch main",
        )
        execute_command(
            context=context,
            command=f"{base_cmd} exec --workdir /remote/{REPO_NAME} {SERVICE_WORKER_NAME} git add .",
        )
        execute_command(
            context=context,
            command=f"{base_cmd} exec --workdir /remote/{REPO_NAME} {SERVICE_WORKER_NAME} git commit -m first",
        )


@task(optional=["database"])
def load_infra_data(context: Context, database: str = INFRAHUB_DATABASE) -> None:
    """Load infrastructure demo data."""
    load_infrastructure_data(context=context, database=database, namespace=NAMESPACE)


@task(optional=["database"])
def load_infra_schema(context: Context, database: str = INFRAHUB_DATABASE) -> None:
    """Load the base schema for infrastructure."""
    load_infrastructure_schema(context=context, database=database, namespace=NAMESPACE, add_wait=True)
    load_infrastructure_menu(context=context, database=database, namespace=NAMESPACE)


@task(optional=["database"])
def pull(context: Context, database: str = INFRAHUB_DATABASE) -> None:
    """Pull external containers from registry."""
    pull_images(context=context, database=database, namespace=NAMESPACE)


@task(optional=["database"])
def restart(context: Context, database: str = INFRAHUB_DATABASE) -> None:
    """Restart Infrahub API Server and Task worker within docker compose."""
    restart_services(context=context, database=database, namespace=NAMESPACE)


@task(optional=["database"])
def status(
    context: Context,
    database: str = INFRAHUB_DATABASE,
    watch: bool = False,
    interval: int = 2,
) -> None:
    """Display detailed status and metrics of all services."""
    try:
        display_container_status(
            context=context, database=database, namespace=NAMESPACE, watch=watch, interval=interval
        )
    except ImportError:
        show_service_status(context=context, database=database, namespace=NAMESPACE)


@task(optional=["database"])
def start(context: Context, database: str = INFRAHUB_DATABASE, wait: bool = False, reload: bool = False) -> None:
    """Start a local instance of Infrahub within docker compose."""

    if reload:
        # Need to use `uvicorn` instead of `gunicorn` for reload option because of this issue:
        # https://github.com/benoitc/gunicorn/issues/2339
        os.environ["INFRAHUB_SERVER_COMMAND"] = (
            "uvicorn infrahub.server:app --host 0.0.0.0 --port 8000 --workers 4 --timeout-keep-alive 90 --reload"
        )

    start_services(context=context, database=database, namespace=NAMESPACE, wait=wait)


@task(optional=["database"])
def stop(context: Context, database: str = INFRAHUB_DATABASE) -> None:
    """Stop the running instance of Infrahub."""
    stop_services(context=context, database=database, namespace=NAMESPACE)


@task(optional=["database"])
def upgrade(context: Context, database: str = INFRAHUB_DATABASE, rebase_branches: bool = False) -> None:
    """Upgrade Infrahub to the latest version and apply the required migrations."""
    upgrade_infrahub(context=context, database=database, namespace=NAMESPACE, rebase_branches=rebase_branches)


@task
def test_add_dummy_data(context: Context, branch: str = "main") -> str:  # noqa: ARG001
    """Load dummy data for testing"""
    from infrahub_sdk import InfrahubClientSync
    from infrahub_sdk.uuidt import generate_uuid

    client = InfrahubClientSync()

    node_name = f"test_rebase_{generate_uuid()}"

    # Create dummy data in main
    test_data = client.create(kind="LocationContinent", data={"name": node_name}, branch=branch)
    test_data.save()

    print(node_name)

    return node_name


@task
def test_branch_rebase(context: Context, branch: str, data_to_check: str = "") -> None:  # noqa: ARG001
    """Rebase branch and check for schema and data."""
    from infrahub_sdk import InfrahubClientSync
    from infrahub_sdk.exceptions import NodeNotFoundError
    from infrahub_sdk.task.models import TaskFilter
    from infrahub_sdk.uuidt import generate_uuid

    client = InfrahubClientSync()

    node_name = f"test_rebase_{generate_uuid()}"

    # Create dummy data in main
    test_data = client.create(kind="LocationContinent", data={"name": node_name}, branch="main")
    test_data.save()

    # Check that data is not present in branch
    try:
        client.get(kind="LocationContinent", hfid=node_name, branch=branch)
        raise AssertionError(
            f"Precondition failed: {node_name!r} unexpectedly exists on branch {branch!r} before rebase"
        )
    except NodeNotFoundError:
        pass

    client.branch.rebase(branch_name=branch)

    tasks = client.task.filter(filter=TaskFilter(workflow=["branch-rebase"]))
    for rebase_task in tasks:
        client.task.wait_for_completion(id=rebase_task.id)

    # Check schema
    schema_to_check = "LocationGeneric"
    full_schema = client.schema.all(branch=branch)
    if schema_to_check not in full_schema:
        raise AssertionError(f"Could not find {schema_to_check} in schema")

    # Check data
    client.get(kind="LocationContinent", hfid=node_name, branch=branch)

    if data_to_check:
        client.get(kind="LocationContinent", hfid=data_to_check, branch=branch)
