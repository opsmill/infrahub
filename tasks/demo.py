"""Replacement for Makefile."""

from typing import Optional

from invoke.context import Context
from invoke.tasks import task

from .container_ops import (
    build_images,
    destroy_environment,
    pull_images,
    restart_services,
    show_service_status,
    start_services,
    stop_services,
)
from .infra_ops import load_infrastructure_data, load_infrastructure_schema
from .shared import (
    BUILD_NAME,
    INFRAHUB_DATABASE,
    PYTHON_VER,
    build_compose_files_cmd,
    execute_command,
    get_env_vars,
)
from .utils import ESCAPED_REPO_PATH

NAMESPACE = "DEMO"


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
    build_images(
        context=context, service=service, python_ver=python_ver, nocache=nocache, database=database, namespace=NAMESPACE
    )


@task(optional=["database"])
def pull(context: Context, database: str = INFRAHUB_DATABASE):
    """Pull external containers from registry."""
    pull_images(context=context, database=database, namespace=NAMESPACE)


# ----------------------------------------------------------------------------
# Local Environment tasks
# ----------------------------------------------------------------------------


@task(optional=["database"])
def start(context: Context, database: str = INFRAHUB_DATABASE):
    """Start a local instance of Infrahub within docker compose."""
    start_services(context=context, database=database, namespace=NAMESPACE)


@task(optional=["database"])
def restart(context: Context, database: str = INFRAHUB_DATABASE):
    """Restart Infrahub API Server and Git Agent within docker compose."""
    restart_services(context=context, database=database, namespace=NAMESPACE)


@task(optional=["database"])
def stop(context: Context, database: str = INFRAHUB_DATABASE):
    """Stop the running instance of Infrahub."""
    stop_services(context=context, database=database, namespace=NAMESPACE)


@task
def destroy(context: Context, database: str = INFRAHUB_DATABASE):
    """Destroy all containers and volumes."""
    destroy_environment(context=context, database=database, namespace=NAMESPACE)


@task(optional=["database"])
def cli_server(context: Context, database: str = INFRAHUB_DATABASE):
    """Launch a bash shell inside the running Infrahub container."""
    with context.cd(ESCAPED_REPO_PATH):
        compose_files_cmd = build_compose_files_cmd(database=database)
        command = f"{get_env_vars(context)} docker compose {compose_files_cmd} -p {BUILD_NAME} run infrahub-server bash"
        execute_command(context=context, command=command)


@task(optional=["database"])
def cli_git(context: Context, database: str = INFRAHUB_DATABASE):
    """Launch a bash shell inside the running Infrahub container."""
    with context.cd(ESCAPED_REPO_PATH):
        compose_files_cmd = build_compose_files_cmd(database=database)
        command = f"{get_env_vars(context)} docker compose {compose_files_cmd} -p {BUILD_NAME} run infrahub-git bash"
        execute_command(context=context, command=command)


@task(optional=["database"])
def status(context: Context, database: str = INFRAHUB_DATABASE):
    """Display the status of all containers."""
    show_service_status(context=context, database=database, namespace=NAMESPACE)


@task(optional=["database"])
def load_infra_schema(context: Context, database: str = INFRAHUB_DATABASE):
    """Load the base schema for infrastructure.
    FIXME: This command needs to be updated to remove the restart before releasing 0.13.0
    """
    load_infrastructure_schema(
        context=context, database=database, namespace=NAMESPACE, add_wait=False, target="models/infrastructure_base.yml"
    )
    restart_services(context=context, database=database, namespace=NAMESPACE)


@task(optional=["database"])
def load_infra_data(context: Context, database: str = INFRAHUB_DATABASE):
    """Load infrastructure demo data."""
    load_infrastructure_data(context=context, database=database, namespace=NAMESPACE)
