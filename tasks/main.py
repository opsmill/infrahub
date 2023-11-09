from invoke import Context, task

from .utils import ESCAPED_REPO_PATH

MAIN_DIRECTORY = "tasks"
NAMESPACE = "MAIN"


# ----------------------------------------------------------------------------
# Formatting tasks
# ----------------------------------------------------------------------------
@task
def format_ruff(context: Context):
    """Run black to format all Python files."""

    print(f" - [{NAMESPACE}] Format code with black")
    with context.cd(ESCAPED_REPO_PATH):
        exec_cmd = f"black {MAIN_DIRECTORY}/ models/"
        context.run(exec_cmd)


@task
def format_autoflake(context: Context):
    """Run autoflack to format all Python files."""

    print(f" - [{NAMESPACE}] Format code with autoflake")
    with context.cd(ESCAPED_REPO_PATH):
        exec_cmd = f"autoflake --recursive --verbose --in-place --remove-all-unused-imports --remove-unused-variables {MAIN_DIRECTORY} models"
        context.run(exec_cmd)


@task(name="format", default=True)
def format_all(context: Context):
    """This will run all formatter."""

    format_autoflake(context)
    format_ruff(context)

    print(f" - [{NAMESPACE}] All formatters have been executed!")
