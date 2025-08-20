from invoke import Context, task
from invoke.runners import Result

from .shared import (
    INFRAHUB_DATABASE,
    NBR_WORKERS,
)
from .utils import ESCAPED_REPO_PATH, REPO_BASE

MAIN_DIRECTORY = "python_sdk"
NAMESPACE = "SDK"
MAIN_DIRECTORY_PATH = REPO_BASE / MAIN_DIRECTORY


# ----------------------------------------------------------------------------
# Formatting tasks
# ----------------------------------------------------------------------------


def _format_ruff(context: Context) -> None:
    """Run ruff to format all Python files."""

    print(f" - [{NAMESPACE}] Format code with ruff")
    exec_cmd = f"ruff format {MAIN_DIRECTORY}/ --config {MAIN_DIRECTORY / 'pyproject.toml'} && "
    exec_cmd += f"ruff check --fix {MAIN_DIRECTORY}/ --config {MAIN_DIRECTORY / 'pyproject.toml'}"
    with context.cd(ESCAPED_REPO_PATH):
        context.run(exec_cmd)


@task(name="format")
def format_all(context: Context) -> None:
    """This will run all formatter."""

    _format_ruff(context)

    print(f" - [{NAMESPACE}] All formatters have been executed!")


# ----------------------------------------------------------------------------
# Testing tasks
# ----------------------------------------------------------------------------
@task
def ruff(context: Context) -> None:
    """Run ruff to check that Python files adherence to black standards."""

    print(f" - [{NAMESPACE}] Check code with ruff")
    exec_directory = MAIN_DIRECTORY_PATH
    exec_cmd = f"ruff check --diff {exec_directory} --config {exec_directory / 'pyproject.toml'}"

    with context.cd(exec_directory):
        context.run(exec_cmd)


@task
def mypy(context: Context) -> None:
    """This will run mypy for the specified name and Python version."""

    print(f" - [{NAMESPACE}] Check code with mypy")
    exec_cmd = "mypy --show-error-codes infrahub_sdk/"
    exec_directory = MAIN_DIRECTORY_PATH

    with context.cd(exec_directory):
        context.run(exec_cmd)


@task
def lint(context: Context) -> Result | None:
    """This will run all linter."""
    ruff(context)
    mypy(context)

    print(f" - [{NAMESPACE}] All tests have passed!")


@task
def test_unit(context: Context) -> Result | None:
    """Run unit tests for the Python SDK."""
    with context.cd(ESCAPED_REPO_PATH):
        exec_cmd = f"pytest -n {NBR_WORKERS} -v --cov=infrahub_sdk {MAIN_DIRECTORY / 'tests' / 'unit'}"
        return context.run(exec_cmd)


@task(optional=["database"])
def test_integration(context: Context, database: str = INFRAHUB_DATABASE) -> Result | None:  # noqa: ARG001
    """Run integration tests for the Python SDK."""
    with context.cd(ESCAPED_REPO_PATH):
        exec_cmd = f"pytest -n {NBR_WORKERS} -v --cov=infrahub_sdk {MAIN_DIRECTORY / 'tests' / 'integration'}"
        return context.run(exec_cmd)


@task(default=True)
def format_and_lint(context: Context) -> None:
    format_all(context)
    lint(context)
