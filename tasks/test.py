from invoke import Context, task

from .shared import BUILD_NAME, ENV_VARS, build_test_compose_files_cmd
from .utils import REPO_BASE


@task
def build(context: Context):
    """Start a local instance of Infrahub in debug mode."""
    with context.cd(REPO_BASE):
        compose_files_cmd = build_test_compose_files_cmd()
        exec_cmd = f"{ENV_VARS} docker compose {compose_files_cmd} -p {BUILD_NAME} build"
        # exec_cmd = f"{ENV_VARS} docker compose {compose_files_cmd} -p {BUILD_NAME} run infrahub-test bash"

        return context.run(exec_cmd, pty=True)


@task
def destroy(context: Context):
    """Start a local instance of Infrahub in debug mode."""
    with context.cd(REPO_BASE):
        compose_files_cmd = build_test_compose_files_cmd()
        exec_cmd = f"{ENV_VARS} docker compose {compose_files_cmd} -p {BUILD_NAME} down --remove-orphans"
        return context.run(exec_cmd, pty=True)
