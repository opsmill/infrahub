import sys

from invoke import Context, task

from .utils import ESCAPED_REPO_PATH


@task
def build(context: Context):
    """Build documentation website."""
    exec_cmd = "npx retype build docs"
    with context.cd(ESCAPED_REPO_PATH):
        output = context.run(exec_cmd)

    successful_build_checks = 0
    if output:
        for line in output.stdout.splitlines():
            if " 0 errors" in line:
                successful_build_checks += 1
            elif " 0 warnings" in line:
                successful_build_checks += 1

    if successful_build_checks < 2:
        sys.exit(-1)


@task
def serve(context: Context):
    """Run documentation server in development mode."""

    exec_cmd = "npx retype serve docs"

    with context.cd(ESCAPED_REPO_PATH):
        context.run(exec_cmd)
