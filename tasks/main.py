from invoke import (  # type: ignore  # pylint: disable=import-error
    Collection,
    Context,
    task,
)

# flake8: noqa: W605

MAIN_DIRECTORY = "tasks"
NAMESPACE = "MAIN"


# ----------------------------------------------------------------------------
# Formatting tasks
# ----------------------------------------------------------------------------
@task
def format_black(context: Context):
    """Run black to format all Python files."""

    print(f" - [{NAMESPACE}] Format code with black")
    exec_cmd = f"black {MAIN_DIRECTORY}/ models/"
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


@task(name="format", default=True)
def format_all(context: Context):
    """This will run all formatter."""

    format_isort(context)
    format_autoflake(context)
    format_black(context)

    print(f" - [{NAMESPACE}] All formatters have been executed!")
