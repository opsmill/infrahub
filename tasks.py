"""Replacement for Makefile."""
import glob
import os
import sys
from datetime import datetime
from distutils.util import strtobool
from typing import Tuple

from invoke import Context, task  # type: ignore  # pylint: disable=import-error

try:
    import toml
except ImportError:
    sys.exit("Please make sure to `pip install toml` or enable the Poetry shell and run `poetry install`.")

# flake8: noqa: W605


def project_ver() -> str:
    """Find version from pyproject.toml to use for docker image tagging."""
    with open("pyproject.toml", encoding="UTF-8") as file:
        return toml.load(file)["tool"]["poetry"].get("version", "latest")


def git_info(context: Context) -> Tuple[str, str]:
    """Return the name of the current branch and hash of the current commit."""
    branch_name = context.run("git rev-parse --abbrev-ref HEAD", hide=True, pty=False)
    hash_value = context.run("git rev-parse --short HEAD", hide=True, pty=False)
    return branch_name.stdout.strip(), hash_value.stdout.strip()


def is_truthy(arg):
    """Convert "truthy" strings into Booleans.

    Examples:
        >>> is_truthy('yes')
        True
    Args:
        arg (str): Truthy string (True values are y, yes, t, true, on and 1; false values are n, no,
        f, false, off and 0. Raises ValueError if val is anything else.
    """
    if isinstance(arg, bool):
        return arg
    return bool(strtobool(arg))


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
    """This will build an image with the provided name and python version.

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
    """Start a local instance of Infrahub in debug mode.

    Args:
        context (obj): Used to run specific commands
    """
    exec_cmd = f"{ENV_VARS} docker compose {COMPOSE_FILES_CMD} -p {BUILD_NAME} up"
    return context.run(exec_cmd, pty=True)


@task
def start(context: Context):
    """Start a local instance of Infrahub within docker compose.

    Args:
        context (obj): Used to run specific commands
    """
    exec_cmd = f"{ENV_VARS} docker compose {COMPOSE_FILES_CMD} -p {BUILD_NAME} up -d"
    return context.run(exec_cmd, pty=True)


@task
def stop(context: Context):
    """Stop the running instance of Infrahub.

    Args:
        context (obj): Used to run specific commands
    """

    exec_cmd = f"{ENV_VARS} docker compose  {COMPOSE_FILES_CMD} -p {BUILD_NAME} down"
    return context.run(exec_cmd, pty=True)


@task
def destroy(context: Context):
    """Destroy all containers and volumes."""
    context.run(f"{ENV_VARS} docker compose {COMPOSE_FILES_CMD} -p {BUILD_NAME} down --remove-orphans", pty=True)

    for volume in VOLUME_NAMES:
        context.run(f"{ENV_VARS} docker volume rm -f {BUILD_NAME}_{volume}", pty=True)


@task
def cli_server(context):
    """Launch a bash shell inside the running Infrahub container."""
    context.run(
        f"{ENV_VARS} docker compose {COMPOSE_FILES_CMD} -p {BUILD_NAME} run infrahub-server bash",
        pty=True,
    )


@task
def cli_git(context):
    """Launch a bash shell inside the running Infrahub container."""
    context.run(
        f"{ENV_VARS} docker compose {COMPOSE_FILES_CMD} -p {BUILD_NAME} run infrahub-git bash",
        pty=True,
    )


@task
def init(context):
    """Initialize Infrahub database before using it the first time."""
    context.run(
        f"{ENV_VARS} docker compose {COMPOSE_FILES_CMD} -p {BUILD_NAME} run infrahub-server infrahub db init",
        pty=True,
    )


@task
def load_demo_data(context):
    """Launch a bash shell inside the running Infrahub container."""
    context.run(
        f"{ENV_VARS} docker compose {COMPOSE_FILES_CMD} -p {BUILD_NAME} run infrahub-server infrahub db load-test-data --dataset dataset03",
        pty=True,
    )


# ----------------------------------------------------------------------------
# Dev Environment tasks
# ----------------------------------------------------------------------------
@task
def dev_start(context: Context):
    """Start a local instance of NEO4J & RabbitMQ.

    Args:
        context (obj): Used to run specific commands
    """

    exec_cmd = f"{ENV_VARS} docker compose {DEV_COMPOSE_FILES_CMD} -p {BUILD_NAME} up -d"
    return context.run(exec_cmd, pty=True)


@task
def dev_stop(context: Context):
    """Start a local instance of NEO4J & RabbitMQ.

    Args:
        context (obj): Used to run specific commands
    """

    exec_cmd = f"{ENV_VARS} docker compose  {DEV_COMPOSE_FILES_CMD} -p {BUILD_NAME} down"
    return context.run(exec_cmd, pty=True)


# ----------------------------------------------------------------------------
# Misc tasks
# ----------------------------------------------------------------------------
@task
def performance_test(context, directory="utilities", dataset="dataset03"):
    PERFORMANCE_FILE_PREFIX = "locust_"
    NOW = datetime.now()
    date_format = NOW.strftime("%Y-%m-%d-%H-%M-%S")

    local_dir = os.path.dirname(os.path.abspath(__file__))
    test_files = glob.glob(f"{local_dir}/{directory}/{PERFORMANCE_FILE_PREFIX}{dataset}*.py")

    branch_name, hash = git_info(context)  # pylint: disable=redefined-builtin

    for test_file in test_files:
        cmd = f"locust -f {test_file} --host=http://localhost:8000 --headless --reset-stats -u 2 -r 2 -t 20s --only-summary"
        result = context.run(cmd, pty=True)

        result_file_name = f"{local_dir}/{directory}/summary_{dataset}_{branch_name}_{hash}_{date_format}.txt"
        with open(result_file_name, "w", encoding="UTF-8") as f:
            print(result.stdout, file=f)


# ----------------------------------------------------------------------------
# Formatting tasks
# ----------------------------------------------------------------------------
@task
def format_black(context: Context):
    """This will run black to format all Python files.

    Args:
        context (obj): Used to run specific commands
    """

    exec_cmd = "black --exclude=examples --exclude=repositories ."
    context.run(exec_cmd, pty=True)


@task
def format_autoflake(context: Context):
    """This will run autoflack to format all Python files.

    Args:
        context (obj): Used to run specific commands
    """

    exec_cmd = "autoflake --recursive --verbose --in-place --remove-all-unused-imports --remove-unused-variables ."
    context.run(exec_cmd, pty=True)


@task
def format_isort(context: Context):
    """This will run isort to format all Python files.

    Args:
        context (obj): Used to run specific commands
        name (str): Used to name the docker image
        image_ver (str): Define image version
        local (bool): Define as `True` to execute locally
    """

    exec_cmd = "isort --skip=examples --skip=repositories ."
    context.run(exec_cmd, pty=True)


@task(name="format")
def format_all(context: Context):
    """This will run all formatter.

    Args:
        context (obj): Used to run specific commands
        name (str): Used to name the docker image
        image_ver (str): Define image version
        local (bool): Define as `True` to execute locally
    """
    format_isort(context)
    format_autoflake(context)
    format_black(context)

    print("All formatters have been executed!")


# ----------------------------------------------------------------------------
# Testing tasks
# ----------------------------------------------------------------------------
@task
def pytest(context: Context):
    """This will run pytest for the specified name and Python version.

    Args:
        context (obj): Used to run specific commands
        name (str): Used to name the docker image
        image_ver (str): Will use the container version docker image
        local (bool): Define as `True` to execute locally
    """

    # Install python module
    exec_cmd = "pytest --cov=diffsync --cov-config pyproject.toml --cov-report html --cov-report term -vv"
    context.run(exec_cmd, pty=True)


@task
def black(context: Context):
    """This will run black to check that Python files adherence to black standards.

    Args:
        context (obj): Used to run specific commands
        name (str): Used to name the docker image
        image_ver (str): Define image version
    """

    exec_cmd = "black --check --diff ."
    context.run(exec_cmd, pty=True)


@task
def flake8(context: Context):
    """This will run flake8 for the specified name and Python version.

    Args:
        context (obj): Used to run specific commands
    """

    exec_cmd = "flake8 --ignore=E203,E501,W503,W504,E701,E251,E231 --exclude=examples,repositories ."
    context.run(exec_cmd, pty=True)


@task
def mypy(context: Context):
    """This will run mypy for the specified name and Python version.

    Args:
        context (obj): Used to run specific commands
    """

    exec_cmd = 'find . -name "*.py" -not -path "*/examples/*" -not -path "*/repositories/*" -not -path "*/tests/*" | xargs mypy --show-error-codes'
    context.run(exec_cmd, pty=True)


@task
def pylint(context: Context):
    """This will run pylint for the specified name and Python version.

    Args:
        context (obj): Used to run specific commands
    """

    exec_cmd = 'find . -name "*.py" -not -path "*/tests/*" -not -path "*/repositories/*" -not -path "*/examples/*" | xargs pylint'
    context.run(exec_cmd, pty=True)


@task
def yamllint(context: Context):
    """This will run yamllint to validate formatting adheres to NTC defined YAML standards.

    Args:
        context (obj): Used to run specific commands
    """

    exec_cmd = "yamllint ."
    context.run(exec_cmd, pty=True)


@task
def pydocstyle(context: Context):
    """This will run pydocstyle to validate docstring formatting adheres to NTC defined standards.

    Args:
        context (obj): Used to run specific commands
    """

    exec_cmd = "pydocstyle ."
    context.run(exec_cmd, pty=True)


@task
def tests(context: Context):
    """This will run all tests for the specified name and Python version.

    Args:
        context (obj): Used to run specific commands
        name (str): Used to name the docker image
        image_ver (str): Define image version
        local (bool): Define as `True` to execute locally
    """
    black(context)
    flake8(context)
    pylint(context)
    yamllint(context)
    pydocstyle(context)
    mypy(context)
    pytest(context)

    print("All tests have passed!")
