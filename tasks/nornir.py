from invoke import Context, task

from .utils import REPO_BASE, escape_path

MAIN_DIRECTORY = "nornir_plugin"
NAMESPACE = "NORNIR"


# ----------------------------------------------------------------------------
# Formatting tasks
# ----------------------------------------------------------------------------
@task
def format_black(context: Context):
    """Run black to format all Python files."""

    print(f" - [{NAMESPACE}] Format code with black")
    exec_cmd = f"black {MAIN_DIRECTORY}/"
    with context.cd(escape_path(REPO_BASE)):
        context.run(exec_cmd)


@task
def format_autoflake(context: Context):
    """Run autoflack to format all Python files."""

    print(f" - [{NAMESPACE}] Format code with autoflake")
    exec_cmd = f"autoflake --recursive --verbose --in-place --remove-all-unused-imports --remove-unused-variables {MAIN_DIRECTORY}"
    with context.cd(escape_path(REPO_BASE)):
        context.run(exec_cmd)


@task
def format_isort(context: Context):
    """Run isort to format all Python files."""

    print(f" - [{NAMESPACE}] Format code with isort")
    exec_cmd = f"isort {MAIN_DIRECTORY}"
    with context.cd(escape_path(REPO_BASE)):
        context.run(exec_cmd)


@task(name="format")
def format_all(context: Context):
    """This will run all formatter."""

    format_isort(context)
    format_autoflake(context)
    format_black(context)

    print(f" - [{NAMESPACE}] All formatters have been executed!")


# ----------------------------------------------------------------------------
# Testing tasks
# ----------------------------------------------------------------------------
@task
def black(context: Context):
    """Run black to check that Python files adherence to black standards."""

    print(f" - [{NAMESPACE}] Check code with black")
    exec_cmd = f"black --check --diff {MAIN_DIRECTORY}"
    with context.cd(escape_path(REPO_BASE)):
        context.run(exec_cmd)


@task
def isort(context: Context):
    """Run isort to check that Python files adherence to import standards."""

    print(f" - [{NAMESPACE}] Check code with isort")
    exec_cmd = f"isort --check --diff {MAIN_DIRECTORY}"
    with context.cd(escape_path(REPO_BASE)):
        context.run(exec_cmd)


@task
def mypy(context: Context):
    """This will run mypy for the specified name and Python version."""

    print(f" - [{NAMESPACE}] Check code with mypy")
    exec_cmd = f"mypy --show-error-codes {MAIN_DIRECTORY}"
    with context.cd(escape_path(REPO_BASE)):
        context.run(exec_cmd)


@task
def pylint(context: Context):
    """This will run pylint for the specified name and Python version."""

    print(f" - [{NAMESPACE}] Check code with pylint")
    exec_cmd = f"pylint {MAIN_DIRECTORY}"
    with context.cd(escape_path(REPO_BASE)):
        context.run(exec_cmd)


@task
def ruff(context: Context):
    """This will run ruff."""

    print(f" - [{NAMESPACE}] Check code with ruff")
    exec_cmd = f"ruff check {MAIN_DIRECTORY}"
    with context.cd(escape_path(REPO_BASE)):
        context.run(exec_cmd)


@task
def lint(context: Context):
    """This will run all linter."""
    ruff(context)
    black(context)
    isort(context)
    pylint(context)
    mypy(context)

    print(f" - [{NAMESPACE}] All tests have passed!")


@task(default=True)
def format_and_lint(context: Context):
    format_all(context)
    lint(context)
