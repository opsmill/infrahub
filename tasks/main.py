from pathlib import Path

from invoke import Context, task

from .shared import execute_command
from .utils import ESCAPED_REPO_PATH, REPO_BASE

MAIN_DIRECTORY = Path("tasks")
NAMESPACE = "MAIN"


DIRECTORIES = [str(MAIN_DIRECTORY), "models", "utilities", "python_testcontainers"]

# ----------------------------------------------------------------------------
# Formatting tasks
# ----------------------------------------------------------------------------


def _format_ruff(context: Context) -> None:
    """Run ruff to format all Python files."""

    print(f" - [{NAMESPACE}] Format code with ruff")
    exec_cmd = f"uv run ruff format {' '.join(DIRECTORIES)} --config {REPO_BASE / 'pyproject.toml'} && "
    exec_cmd += f"uv run ruff check --fix {' '.join(DIRECTORIES)} --config {REPO_BASE / 'pyproject.toml'}"
    with context.cd(ESCAPED_REPO_PATH):
        context.run(exec_cmd)


@task(name="format", default=True)
def format_all(context: Context) -> None:
    """This will run all formatters."""

    _format_ruff(context)

    print(f" - [{NAMESPACE}] All formatters have been executed!")


def _lint_ruff(context: Context) -> None:
    """Run ruff to check that Python files adherence to standards."""

    print(f" - [{NAMESPACE}] Check code with ruff")
    exec_cmd = f"uv run ruff check --diff {' '.join(DIRECTORIES)} --config {REPO_BASE}/pyproject.toml"

    with context.cd(ESCAPED_REPO_PATH):
        context.run(exec_cmd)


@task
def lint(context: Context) -> None:
    """This will run all linters."""

    _lint_ruff(context)

    print(f" - [{NAMESPACE}] All linters have been executed!")


@task(name="scan")
def scan(context: Context) -> None:
    """
    Scan the repository for prohibited keywords.
    """

    with context.cd(ESCAPED_REPO_PATH):
        base_cmd = "python utilities/scan.py"
        execute_command(context=context, command=base_cmd)
