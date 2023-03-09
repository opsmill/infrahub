"""Replacement for Makefile."""
import os

from invoke import (  # type: ignore  # pylint: disable=import-error
    Collection,
    Context,
    task,
)

from .utils import project_ver

# flake8: noqa: W605

PYTHON_VER = os.getenv("PYTHON_VER", "3.9")
IMAGE_NAME = os.getenv("IMAGE_NAME", f"opsmill/infrahub-py{PYTHON_VER}")
IMAGE_VER = os.getenv("IMAGE_VER", project_ver())
PWD = os.getcwd()

BUILD_NAME = "infrahub-dev"
USE_OVERRIDE_FILE = False
OVERRIDE_FILE_NAME = "development/docker-compose.override.yml"

COMPOSE_FILES = ["development/docker-compose-deps.yml", "development/docker-compose.yml"]
DEV_COMPOSE_FILES = ["development/docker-compose-deps.yml"]

if os.path.exists(OVERRIDE_FILE_NAME):
    print("!! Found an override file for docker compose !!")
    COMPOSE_FILES.append(OVERRIDE_FILE_NAME)
    DEV_COMPOSE_FILES.append(OVERRIDE_FILE_NAME)
    USE_OVERRIDE_FILE = True

COMPOSE_FILES_CMD = f"-f {' -f '.join(COMPOSE_FILES)}"
DEV_COMPOSE_FILES_CMD = f"-f {' -f '.join(DEV_COMPOSE_FILES)}"

ENV_VARS = f"IMAGE_NAME={IMAGE_NAME}, IMAGE_VER={IMAGE_VER} PYTHON_VER={PYTHON_VER}"

VOLUME_NAMES = ["neo4j_data", "neo4j_logs", "git_data"]


@task
def build(
    context, name=IMAGE_NAME, python_ver=PYTHON_VER, image_ver=IMAGE_VER, nocache=False
):  # pylint: disable=too-many-arguments
    """Build an image with the provided name and python version.

    Args:
        context (obj): Used to run specific commands
        name (str): Used to name the docker image
        python_ver (str): Define the Python version docker image to build from
        image_ver (str): Define image version
        nocache (bool): Do not use cache when building the image
    """
    print(f"Building image {name}:{image_ver}")
    exec_cmd = (
        f"{ENV_VARS} docker compose {COMPOSE_FILES_CMD} -p {BUILD_NAME} build --build-arg PYTHON_VER={python_ver}"
    )
    if nocache:
        exec_cmd += " --no-cache"
    context.run(exec_cmd, pty=True)


# ----------------------------------------------------------------------------
# Local Environment tasks
# ----------------------------------------------------------------------------
@task
def debug(context):
    """Start a local instance of Infrahub in debug mode."""

    exec_cmd = f"{ENV_VARS} docker compose {COMPOSE_FILES_CMD} -p {BUILD_NAME} up"
    return context.run(exec_cmd, pty=True)


@task
def start(context: Context):
    """Start a local instance of Infrahub within docker compose."""

    exec_cmd = f"{ENV_VARS} docker compose {COMPOSE_FILES_CMD} -p {BUILD_NAME} up -d"
    return context.run(exec_cmd, pty=True)


@task
def restart(context: Context):
    """Restart Infrahub API Server and Git Agent within docker compose."""

    context.run(
        f"{ENV_VARS} docker compose {COMPOSE_FILES_CMD} -p {BUILD_NAME} restart infrahub-server",
        pty=True,
    )
    context.run(
        f"{ENV_VARS} docker compose {COMPOSE_FILES_CMD} -p {BUILD_NAME} restart infrahub-git",
        pty=True,
    )

@task
def stop(context: Context):
    """Stop the running instance of Infrahub."""

    exec_cmd = f"{ENV_VARS} docker compose  {COMPOSE_FILES_CMD} -p {BUILD_NAME} down"
    return context.run(exec_cmd, pty=True)


@task
def destroy(context: Context):
    """Destroy all containers and volumes."""

    context.run(f"{ENV_VARS} docker compose {COMPOSE_FILES_CMD} -p {BUILD_NAME} down --remove-orphans", pty=True)

    for volume in VOLUME_NAMES:
        context.run(f"{ENV_VARS} docker volume rm -f {BUILD_NAME}_{volume}", pty=True)


@task
def cli_server(context: Context):
    """Launch a bash shell inside the running Infrahub container."""

    context.run(
        f"{ENV_VARS} docker compose {COMPOSE_FILES_CMD} -p {BUILD_NAME} run infrahub-server bash",
        pty=True,
    )


@task
def cli_git(context: Context):
    """Launch a bash shell inside the running Infrahub container."""

    context.run(
        f"{ENV_VARS} docker compose {COMPOSE_FILES_CMD} -p {BUILD_NAME} run infrahub-git bash",
        pty=True,
    )


@task
def cli_frontend(context: Context):
    """Launch a bash shell inside the running Infrahub container."""
    context.run(
        f"{ENV_VARS} docker compose {COMPOSE_FILES_CMD} -p {BUILD_NAME} run frontend bash",
        pty=True,
    )


@task
def init(context: Context):
    """Initialize Infrahub database before using it the first time."""

    context.run(
        f"{ENV_VARS} docker compose {COMPOSE_FILES_CMD} -p {BUILD_NAME} run infrahub-server infrahub db init",
        pty=True,
    )


@task
def status(context: Context):
    """Display the status of all containers."""

    context.run(
        f"{ENV_VARS} docker compose {COMPOSE_FILES_CMD} -p {BUILD_NAME} ps",
        pty=True,
    )


@task
def load_infra_schema(context: Context):
    """Load the base schema for infrastructure."""
    context.run(
        f"{ENV_VARS} docker compose {COMPOSE_FILES_CMD} -p {BUILD_NAME} run infrahub-git infrahubctl schema load models/infrastructure_base.json",
        pty=True,
    )

    context.run(
        f"{ENV_VARS} docker compose {COMPOSE_FILES_CMD} -p {BUILD_NAME} restart infrahub-server",
        pty=True,
    )


@task
def load_infra_data(context: Context):
    """Load some demo data."""
    context.run(
        f"{ENV_VARS} docker compose {COMPOSE_FILES_CMD} -p {BUILD_NAME} run infrahub-git infrahubctl run models/infrastructure_edge.py",
        pty=True,
    )


# ----------------------------------------------------------------------------
# Dev Environment tasks
# ----------------------------------------------------------------------------
@task
def dev_start(context: Context):
    """Start a local instance of NEO4J & RabbitMQ."""

    exec_cmd = f"{ENV_VARS} docker compose {DEV_COMPOSE_FILES_CMD} -p {BUILD_NAME} up -d"
    return context.run(exec_cmd, pty=True)


@task
def dev_stop(context: Context):
    """Start a local instance of NEO4J & RabbitMQ."""

    exec_cmd = f"{ENV_VARS} docker compose  {DEV_COMPOSE_FILES_CMD} -p {BUILD_NAME} down"
    return context.run(exec_cmd, pty=True)
