"""Replacement for Makefile."""
import os
from time import sleep

from invoke import (  # type: ignore  # pylint: disable=import-error
    Collection,
    Context,
    task,
)

from .utils import project_ver

# flake8: noqa: W605

here = os.path.abspath(os.path.dirname(__file__))
TOP_DIRECTORY_NAME = os.path.basename(os.path.abspath(os.path.join(here, "..")))
BUILD_NAME = os.getenv("INFRAHUB_BUILD_NAME", TOP_DIRECTORY_NAME)
PYTHON_VER = os.getenv("PYTHON_VER", "3.10")
IMAGE_NAME = os.getenv("IMAGE_NAME", f"opsmill/{BUILD_NAME}-py{PYTHON_VER}")
IMAGE_VER = os.getenv("IMAGE_VER", project_ver())
PWD = os.getcwd()

OVERRIDE_FILE_NAME = "development/docker-compose.override.yml"
DEFAULT_FILE_NAME = "development/docker-compose.default.yml"
COMPOSE_FILES = ["development/docker-compose-deps.yml", "development/docker-compose.yml"]

DEV_COMPOSE_FILES = ["development/docker-compose-deps.yml"]
DEV_OVERRIDE_FILE_NAME = "development/docker-compose.dev-override.yml"

AVAILABLE_SERVICES = ["infrahub-git", "frontend", "infrahub-server", "database", "message-queue"]

ENV_VARS = f"IMAGE_NAME={IMAGE_NAME}, IMAGE_VER={IMAGE_VER} PYTHON_VER={PYTHON_VER}"
ENV_VARS = f"IMAGE_NAME={IMAGE_NAME}, IMAGE_VER={IMAGE_VER} PYTHON_VER={PYTHON_VER} INFRAHUB_BUILD_NAME={BUILD_NAME}"

VOLUME_NAMES = ["neo4j_data", "neo4j_logs", "git_data"]


def build_compose_files_cmd() -> str:
    if os.path.exists(OVERRIDE_FILE_NAME):
        print("!! Found an override file for docker-compose !!")
        COMPOSE_FILES.append(OVERRIDE_FILE_NAME)
    else:
        COMPOSE_FILES.append(DEFAULT_FILE_NAME)

    return f"-f {' -f '.join(COMPOSE_FILES)}"


def build_dev_compose_files_cmd() -> str:
    if os.path.exists(DEV_OVERRIDE_FILE_NAME):
        print("!! Found a dev override file for docker-compose !!")
        DEV_COMPOSE_FILES.append(DEV_OVERRIDE_FILE_NAME)

    return f"-f {' -f '.join(DEV_COMPOSE_FILES)}"


@task
def build(context, service=None, python_ver=PYTHON_VER, nocache=False):  # pylint: disable=too-many-arguments
    """Build an image with the provided name and python version.

    Args:
        context (obj): Used to run specific commands
        python_ver (str): Define the Python version docker image to build from
        nocache (bool): Do not use cache when building the image
    """
    print(f"Building images")

    if service and service not in AVAILABLE_SERVICES:
        exit(f"{service} is not a valid service ({AVAILABLE_SERVICES})")

    compose_files_cmd = build_compose_files_cmd()
    exec_cmd = (
        f"{ENV_VARS} docker compose {compose_files_cmd} -p {BUILD_NAME} build --build-arg PYTHON_VER={python_ver}"
    )
    if nocache:
        exec_cmd += " --no-cache"

    if service:
        exec_cmd += f" {service}"

    context.run(exec_cmd, pty=True)


# ----------------------------------------------------------------------------
# Local Environment tasks
# ----------------------------------------------------------------------------
@task
def debug(context):
    """Start a local instance of Infrahub in debug mode."""
    compose_files_cmd = build_compose_files_cmd()
    exec_cmd = f"{ENV_VARS} docker compose {compose_files_cmd} -p {BUILD_NAME} up"
    return context.run(exec_cmd, pty=True)


@task
def start(context: Context):
    """Start a local instance of Infrahub within docker compose."""
    compose_files_cmd = build_compose_files_cmd()
    exec_cmd = f"{ENV_VARS} docker compose {compose_files_cmd} -p {BUILD_NAME} up -d"
    return context.run(exec_cmd, pty=True)


@task
def restart(context: Context):
    """Restart Infrahub API Server and Git Agent within docker compose."""
    compose_files_cmd = build_compose_files_cmd()
    context.run(
        f"{ENV_VARS} docker compose {compose_files_cmd} -p {BUILD_NAME} restart infrahub-server",
        pty=True,
    )
    context.run(
        f"{ENV_VARS} docker compose {compose_files_cmd} -p {BUILD_NAME} restart infrahub-git",
        pty=True,
    )


@task
def stop(context: Context):
    """Stop the running instance of Infrahub."""
    compose_files_cmd = build_compose_files_cmd()
    exec_cmd = f"{ENV_VARS} docker compose  {compose_files_cmd} -p {BUILD_NAME} down"
    return context.run(exec_cmd, pty=True)


@task
def destroy(context: Context):
    """Destroy all containers and volumes."""
    compose_files_cmd = build_compose_files_cmd()
    context.run(f"{ENV_VARS} docker compose {compose_files_cmd} -p {BUILD_NAME} down --remove-orphans", pty=True)

    for volume in VOLUME_NAMES:
        context.run(f"{ENV_VARS} docker volume rm -f {BUILD_NAME}_{volume}", pty=True)


@task
def cli_server(context: Context):
    """Launch a bash shell inside the running Infrahub container."""
    compose_files_cmd = build_compose_files_cmd()
    context.run(
        f"{ENV_VARS} docker compose {compose_files_cmd} -p {BUILD_NAME} run infrahub-server bash",
        pty=True,
    )


@task
def cli_git(context: Context):
    """Launch a bash shell inside the running Infrahub container."""
    compose_files_cmd = build_compose_files_cmd()
    context.run(
        f"{ENV_VARS} docker compose {compose_files_cmd} -p {BUILD_NAME} run infrahub-git bash",
        pty=True,
    )


@task
def cli_frontend(context: Context):
    """Launch a bash shell inside the running Infrahub container."""
    compose_files_cmd = build_compose_files_cmd()
    context.run(
        f"{ENV_VARS} docker compose {compose_files_cmd} -p {BUILD_NAME} run frontend bash",
        pty=True,
    )


@task
def init(context: Context):
    """Initialize Infrahub database before using it the first time."""
    compose_files_cmd = build_compose_files_cmd()
    context.run(
        f"{ENV_VARS} docker compose {compose_files_cmd} -p {BUILD_NAME} run infrahub-server infrahub db init",
        pty=True,
    )


@task
def status(context: Context):
    """Display the status of all containers."""
    compose_files_cmd = build_compose_files_cmd()
    context.run(
        f"{ENV_VARS} docker compose {compose_files_cmd} -p {BUILD_NAME} ps",
        pty=True,
    )


@task
def load_infra_schema(context: Context):
    """Load the base schema for infrastructure."""
    compose_files_cmd = build_compose_files_cmd()
    context.run(
        f"{ENV_VARS} docker compose {compose_files_cmd} -p {BUILD_NAME} run infrahub-git infrahubctl schema load models/infrastructure_base.yml",
        pty=True,
    )

    context.run(
        f"{ENV_VARS} docker compose {compose_files_cmd} -p {BUILD_NAME} restart infrahub-server",
        pty=True,
    )


@task
def load_infra_data(context: Context):
    """Load some demo data."""
    compose_files_cmd = build_compose_files_cmd()
    context.run(
        f"{ENV_VARS} docker compose {compose_files_cmd} -p {BUILD_NAME} run infrahub-git infrahubctl run models/infrastructure_edge.py",
        pty=True,
    )


# ----------------------------------------------------------------------------
# Dev Environment tasks
# ----------------------------------------------------------------------------
@task
def dev_start(context: Context):
    """Start a local instance of NEO4J & RabbitMQ."""
    dev_compose_files_cmd = build_dev_compose_files_cmd()
    exec_cmd = f"{ENV_VARS} docker compose {dev_compose_files_cmd} -p {BUILD_NAME} up -d"
    return context.run(exec_cmd, pty=True)


@task
def dev_stop(context: Context):
    """Start a local instance of NEO4J & RabbitMQ."""
    dev_compose_files_cmd = build_dev_compose_files_cmd()
    exec_cmd = f"{ENV_VARS} docker compose  {dev_compose_files_cmd} -p {BUILD_NAME} down"
    return context.run(exec_cmd, pty=True)


@task(optional=["expected"])
def wait_healthy(context: Context, expected: int = 2):
    """Wait until containers are healthy before continuing."""
    missing_healthy = True
    while missing_healthy:
        output = context.run("docker ps --filter 'health=healthy' --format '{{ .Names}}'", hide=True)
        containers = output.stdout.splitlines()
        if len(containers) >= expected:
            missing_healthy = False
        else:
            print(f"Expected {expected} healthy containers only saw: {', '.join(containers)}")
            sleep(1)
