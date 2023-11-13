import os

from invoke import Context, task

from .shared import (
    BUILD_NAME,
    INFRAHUB_DATABASE,
    NBR_WORKERS,
    build_test_compose_files_cmd,
    build_test_envs,
    execute_command,
    get_env_vars,
)
from .utils import ESCAPED_REPO_PATH

MAIN_DIRECTORY = "python_sdk"
NAMESPACE = "SDK"
MAIN_DIRECTORY_PATH = os.path.join(ESCAPED_REPO_PATH, MAIN_DIRECTORY)


# ----------------------------------------------------------------------------
# Formatting tasks
# ----------------------------------------------------------------------------
@task
def format_ruff(context: Context):
    """Run ruff to format all Python files."""

    print(f" - [{NAMESPACE}] Format code with ruff")
    exec_cmd = f"ruff format {MAIN_DIRECTORY}/ --config {MAIN_DIRECTORY}/pyproject.toml && "
    exec_cmd += f"ruff check --fix {MAIN_DIRECTORY}/ --config {MAIN_DIRECTORY}/pyproject.toml"
    with context.cd(ESCAPED_REPO_PATH):
        context.run(exec_cmd)


@task
def format_autoflake(context: Context):
    """Run autoflack to format all Python files."""

    print(f" - [{NAMESPACE}] Format code with autoflake")
    exec_cmd = "autoflake --recursive --verbose --in-place --remove-all-unused-imports --remove-unused-variables ."
    with context.cd(MAIN_DIRECTORY_PATH):
        context.run(exec_cmd)


@task(name="format")
def format_all(context: Context):
    """This will run all formatter."""

    format_autoflake(context)
    format_ruff(context)

    print(f" - [{NAMESPACE}] All formatters have been executed!")


# ----------------------------------------------------------------------------
# Testing tasks
# ----------------------------------------------------------------------------
@task
def ruff(context: Context, docker: bool = False):
    """Run ruff to check that Python files adherence to black standards."""

    print(f" - [{NAMESPACE}] Check code with ruff")
    exec_directory = MAIN_DIRECTORY_PATH
    if not docker:
        exec_cmd = f"ruff check --diff {exec_directory} --config {exec_directory}/pyproject.toml"

    if docker:
        exec_cmd = "ruff check --diff . --config pyproject.toml"
        compose_files_cmd = build_test_compose_files_cmd(database=False)
        exec_cmd = (
            f"{get_env_vars(context)} docker compose {compose_files_cmd} -p {BUILD_NAME}"
            f" run --workdir /source/{MAIN_DIRECTORY} infrahub-test {exec_cmd}"
        )
        exec_directory = ESCAPED_REPO_PATH
        print(exec_cmd)

    with context.cd(exec_directory):
        context.run(exec_cmd)


@task
def mypy(context: Context, docker: bool = False):
    """This will run mypy for the specified name and Python version."""

    print(f" - [{NAMESPACE}] Check code with mypy")
    exec_cmd = "mypy --show-error-codes infrahub_sdk/ infrahub_ctl/"
    exec_directory = MAIN_DIRECTORY_PATH

    if docker:
        compose_files_cmd = build_test_compose_files_cmd(database=False)
        exec_cmd = (
            f"{get_env_vars(context)} docker compose {compose_files_cmd} -p {BUILD_NAME}"
            f" run --workdir /source/{MAIN_DIRECTORY} infrahub-test {exec_cmd}"
        )
        exec_directory = ESCAPED_REPO_PATH
        print(exec_cmd)

    with context.cd(exec_directory):
        context.run(exec_cmd)


@task
def pylint(context: Context, docker: bool = False):
    """This will run pylint for the specified name and Python version."""

    print(f" - [{NAMESPACE}] Check code with pylint")
    exec_cmd = "pylint infrahub_sdk/ infrahub_ctl/"
    exec_directory = MAIN_DIRECTORY_PATH

    if docker:
        compose_files_cmd = build_test_compose_files_cmd(database=False)
        exec_cmd = (
            f"{get_env_vars(context)} docker compose {compose_files_cmd} -p {BUILD_NAME}"
            f" run --workdir /source/{MAIN_DIRECTORY} infrahub-test {exec_cmd}"
        )
        exec_directory = ESCAPED_REPO_PATH
        print(exec_cmd)

    with context.cd(exec_directory):
        context.run(exec_cmd)


@task
def lint(context: Context, docker: bool = False):
    """This will run all linter."""
    ruff(context, docker=docker)
    pylint(context, docker=docker)
    mypy(context, docker=docker)

    print(f" - [{NAMESPACE}] All tests have passed!")


@task
def test_unit(context: Context):
    with context.cd(ESCAPED_REPO_PATH):
        compose_files_cmd = build_test_compose_files_cmd(database=False)
        base_cmd = f"{get_env_vars(context)} docker compose {compose_files_cmd} -p {BUILD_NAME} run {build_test_envs()} infrahub-test"
        exec_cmd = f"pytest -n {NBR_WORKERS} -v --cov=infrahub_sdk {MAIN_DIRECTORY}/tests/unit"
        print(f"{base_cmd} {exec_cmd}")
        return execute_command(context=context, command=f"{base_cmd} {exec_cmd}")


@task(optional=["database"])
def test_integration(context: Context, database: str = INFRAHUB_DATABASE):
    with context.cd(ESCAPED_REPO_PATH):
        compose_files_cmd = build_test_compose_files_cmd(database=database)
        base_cmd = f"{get_env_vars(context)} docker compose {compose_files_cmd} -p {BUILD_NAME} run {build_test_envs()} infrahub-test"
        exec_cmd = f"pytest -n {NBR_WORKERS} -v --cov=infrahub_sdk {MAIN_DIRECTORY}/tests/integration"
        print(f"{base_cmd} {exec_cmd}")
        return execute_command(context=context, command=f"{base_cmd} {exec_cmd}")


@task(default=True)
def format_and_lint(context: Context):
    format_all(context)
    lint(context)
