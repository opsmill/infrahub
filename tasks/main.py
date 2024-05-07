from invoke import Context, task

from .utils import ESCAPED_REPO_PATH, REPO_BASE

MAIN_DIRECTORY = "tasks"
NAMESPACE = "MAIN"


# ----------------------------------------------------------------------------
# Formatting tasks
# ----------------------------------------------------------------------------


def _format_ruff(context: Context):
    """Run ruff to format all Python files."""

    print(f" - [{NAMESPACE}] Format code with ruff")
    exec_cmd = f"ruff format {MAIN_DIRECTORY} models utilities --config {REPO_BASE}/pyproject.toml && "
    exec_cmd += f"ruff check --fix {MAIN_DIRECTORY} models utilities --config {REPO_BASE}/pyproject.toml"
    with context.cd(ESCAPED_REPO_PATH):
        context.run(exec_cmd)


@task(name="format", default=True)
def format_all(context: Context):
    """This will run all formatters."""

    _format_ruff(context)

    print(f" - [{NAMESPACE}] All formatters have been executed!")
