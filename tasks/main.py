from invoke import Context, task

from .shared import execute_command
from .utils import ESCAPED_REPO_PATH

NAMESPACE = "MAIN"

# The python_sdk submodule is linted in its own repository and the .specify scripts come from spec-kit; CI uses the same scope.
RUFF_TARGET = "--exclude python_sdk,.specify ."

# ----------------------------------------------------------------------------
# Formatting tasks
# ----------------------------------------------------------------------------


def _format_ruff(context: Context) -> None:
    """Run ruff to format all Python files."""
    print(f" - [{NAMESPACE}] Format code with ruff")
    exec_cmd = f"uv run ruff format {RUFF_TARGET} && "
    exec_cmd += f"uv run ruff check --fix {RUFF_TARGET}"
    with context.cd(ESCAPED_REPO_PATH):
        context.run(exec_cmd)


@task(name="format", default=True)
def format_all(context: Context) -> None:
    """Format every Python file in the repository, except the python_sdk submodule and the spec-kit scripts, with ruff."""
    _format_ruff(context)

    print(f" - [{NAMESPACE}] All formatters have been executed!")


def _lint_ruff(context: Context) -> None:
    """Run ruff to check that Python files adhere to standards and are formatted."""
    print(f" - [{NAMESPACE}] Check code with ruff")
    exec_cmd = f"uv run ruff check {RUFF_TARGET} && "
    exec_cmd += f"uv run ruff format --check --diff {RUFF_TARGET}"

    with context.cd(ESCAPED_REPO_PATH):
        context.run(exec_cmd)


@task
def lint(context: Context) -> None:
    """Run ruff linter and format check against every Python file, except the python_sdk submodule and the spec-kit scripts."""
    _lint_ruff(context)

    print(f" - [{NAMESPACE}] All linters have been executed!")


@task(name="scan")
def scan(context: Context) -> None:
    """Scan the repository for prohibited keywords."""
    with context.cd(ESCAPED_REPO_PATH):
        base_cmd = "python utilities/scan.py"
        execute_command(context=context, command=base_cmd)
