from invoke import Context, task

from .shared import (
    AVAILABLE_SERVICES,
    BASE_IMAGES,
    BUILD_NAME,
    build_test_compose_files_cmd,
    execute_command,
    get_env_vars,
)
from .utils import REPO_BASE


@task
def build(context: Context):
    """Start a local instance of Infrahub in debug mode."""
    with context.cd(REPO_BASE):
        compose_files_cmd = build_test_compose_files_cmd()
        exec_cmd = f"{get_env_vars(context=context)} docker compose {compose_files_cmd} -p {BUILD_NAME} build"

        return execute_command(context=context, command=exec_cmd)


@task(optional=["database"])
def pull(context: Context, database: str = "memgraph"):
    """Pull external containers from registry."""
    with context.cd(REPO_BASE):
        compose_files_cmd = build_test_compose_files_cmd(database=database)

        for service in AVAILABLE_SERVICES:
            if "infrahub" in service:
                continue
            command = f"{get_env_vars(context)} docker compose {compose_files_cmd} -p {BUILD_NAME} pull {service}"
            execute_command(context=context, command=command)


@task
def pull_build_deps(context: Context):
    """Pull external containers required for the build from the registry."""
    with context.cd(REPO_BASE):
        for base_image in BASE_IMAGES:
            command = f"docker pull {base_image}"
            execute_command(context=context, command=command)


@task
def destroy(context: Context):
    """Destroy the test environment."""
    with context.cd(REPO_BASE):
        compose_files_cmd = build_test_compose_files_cmd()
        exec_cmd = (
            f"{get_env_vars(context=context)} docker compose {compose_files_cmd} -p {BUILD_NAME} down --remove-orphans"
        )
        return execute_command(context=context, command=exec_cmd)
