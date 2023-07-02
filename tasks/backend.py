from invoke import Context, task

from .shared import BUILD_NAME, ENV_VARS, build_test_compose_files_cmd, NBR_WORKERS
from .utils import REPO_BASE

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
    with context.cd(REPO_BASE):
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
    with context.cd(REPO_BASE):
        context.run(exec_cmd, pty=True)


@task
def format_autoflake(context: Context):
    """Run autoflack to format all Python files."""

    print(f" - [{NAMESPACE}] Format code with autoflake")
    exec_cmd = f"autoflake --recursive --verbose --in-place --remove-all-unused-imports --remove-unused-variables {MAIN_DIRECTORY}"
    with context.cd(REPO_BASE):
        context.run(exec_cmd, pty=True)


@task
def format_isort(context: Context):
    """Run isort to format all Python files."""

    print(f" - [{NAMESPACE}] Format code with isort")
    exec_cmd = f"isort {MAIN_DIRECTORY}"
    with context.cd(REPO_BASE):
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
    with context.cd(REPO_BASE):
        context.run(exec_cmd, pty=True)


@task
def isort(context: Context):
    """Run isort to check that Python files adherence to import standards."""

    print(f" - [{NAMESPACE}] Check code with isort")
    exec_cmd = f"isort --check --diff {MAIN_DIRECTORY}"
    with context.cd(REPO_BASE):
        context.run(exec_cmd, pty=True)


@task
def mypy(context: Context):
    """This will run mypy for the specified name and Python version."""

    print(f" - [{NAMESPACE}] Check code with mypy")
    exec_cmd = f"mypy --show-error-codes {MAIN_DIRECTORY}"
    with context.cd(REPO_BASE):
        context.run(exec_cmd, pty=True)


@task
def pylint(context: Context):
    """This will run pylint for the specified name and Python version."""

    print(f" - [{NAMESPACE}] Check code with pylint")
    exec_cmd = f"pylint --ignore-paths {MAIN_DIRECTORY}/tests {MAIN_DIRECTORY}"
    with context.cd(REPO_BASE):
        context.run(exec_cmd, pty=True)


@task
def ruff(context: Context):
    """This will run ruff."""

    print(f" - [{NAMESPACE}] Check code with ruff")
    exec_cmd = f"ruff check {MAIN_DIRECTORY}"
    with context.cd(REPO_BASE):
        context.run(exec_cmd, pty=True)


@task
def lint(context: Context):
    """This will run all linter."""
    ruff(context)
    black(context)
    isort(context)
    pylint(context)
    # mypy(context)

    print(f" - [{NAMESPACE}] All tests have passed!")


@task(optional=["database"])
def test_unit(context: Context, database: str = "memgraph"):
    with context.cd(REPO_BASE):
        compose_files_cmd = build_test_compose_files_cmd(database=database)
        exec_cmd = f"{ENV_VARS} docker compose {compose_files_cmd} -p {BUILD_NAME} run infrahub-test pytest -n {NBR_WORKERS} -v --cov=infrahub {MAIN_DIRECTORY}/tests/unit"

        return context.run(exec_cmd, pty=True)


@task(optional=["database"])
def test_integration(context: Context, database: str = "memgraph"):
    with context.cd(REPO_BASE):
        compose_files_cmd = build_test_compose_files_cmd(database=database)
        exec_cmd = f"{ENV_VARS} docker compose {compose_files_cmd} -p {BUILD_NAME} run infrahub-test pytest -n {NBR_WORKERS} -v --cov=infrahub {MAIN_DIRECTORY}/tests/integration"

        return context.run(exec_cmd, pty=True)


@task(default=True)
def format_and_lint(context: Context):
    format_all(context)
    lint(context)
