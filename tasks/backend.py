from invoke import (  # type: ignore  # pylint: disable=import-error
    Collection,
    Context,
    task,
)

# flake8: noqa: W605

MAIN_DIRECTORY = "backend"
NAMESPACE = "BACKEND"


# ----------------------------------------------------------------------------
# Documentation
# ----------------------------------------------------------------------------
@task
def generate_doc(context: Context):
    """Generate the documentation for infrahub cli using typer-cli."""

    CLI_COMMANDS = (
        ("infrahub.cli.db", "infrahub db", "10_infrahub_db"),
        ("infrahub.cli.server", "infrahub server", "20_infrahub_server"),
        ("infrahub.cli.git_agent", "infrahub git-agent", "30_infrahub_git_agent"),
    )

    print(f" - [{NAMESPACE}] Generate CLI documentation")
    for command in CLI_COMMANDS:
        exec_cmd = f'typer {command[0]} utils docs --name "{command[1]}" --output docs/20_components/30_infrahub_cli/{command[2]}.md'
        context.run(exec_cmd, pty=True)


# ----------------------------------------------------------------------------
# Formatting tasks
# ----------------------------------------------------------------------------
@task
def format_black(context: Context):
    """Run black to format all Python files."""

    print(f" - [{NAMESPACE}] Format code with black")
    exec_cmd = f"black {MAIN_DIRECTORY}/"
    context.run(exec_cmd, pty=True)


@task
def format_autoflake(context: Context):
    """Run autoflack to format all Python files."""

    print(f" - [{NAMESPACE}] Format code with autoflake")
    exec_cmd = f"autoflake --recursive --verbose --in-place --remove-all-unused-imports --remove-unused-variables {MAIN_DIRECTORY}"
    context.run(exec_cmd, pty=True)


@task
def format_isort(context: Context):
    """Run isort to format all Python files."""

    print(f" - [{NAMESPACE}] Format code with isort")
    exec_cmd = f"isort {MAIN_DIRECTORY}"
    context.run(exec_cmd, pty=True)


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
    context.run(exec_cmd, pty=True)


@task
def flake8(context: Context):
    """This will run flake8 for the specified name and Python version."""

    print(f" - [{NAMESPACE}] Check code with flake8")
    exec_cmd = f"flake8 --ignore=E203,E501,W503,W504,E701,E251,E231 {MAIN_DIRECTORY}"
    context.run(exec_cmd, pty=True)


@task
def isort(context: Context):
    """Run isort to check that Python files adherence to import standards."""

    print(f" - [{NAMESPACE}] Check code with isort")
    exec_cmd = f"isort --check --diff {MAIN_DIRECTORY}"
    context.run(exec_cmd, pty=True)


@task
def mypy(context: Context):
    """This will run mypy for the specified name and Python version."""

    print(f" - [{NAMESPACE}] Check code with mypy")
    exec_cmd = f"mypy --show-error-codes {MAIN_DIRECTORY}"
    context.run(exec_cmd, pty=True)


@task
def pylint(context: Context):
    """This will run pylint for the specified name and Python version."""

    print(f" - [{NAMESPACE}] Check code with pylint")
    exec_cmd = f"pylint --ignore-paths {MAIN_DIRECTORY}/tests {MAIN_DIRECTORY}"
    context.run(exec_cmd, pty=True)


@task
def lint(context: Context):
    """This will run all linter."""
    black(context)
    isort(context)
    flake8(context)
    pylint(context)
    # mypy(context)

    print(f" - [{NAMESPACE}] All tests have passed!")


@task(default=True)
def format_and_lint(context: Context):
    format_all(context)
    lint(context)
