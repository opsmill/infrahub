from invoke import Context, task

from .shared import (
    AVAILABLE_SERVICES,
    BUILD_NAME,
    build_test_compose_files_cmd,
    execute_command,
    get_env_vars,
)
from .utils import ESCAPED_REPO_PATH


@task(optional=["database"])
def pull(context: Context, database: str = "memgraph"):
    """Pull external containers from registry."""
    with context.cd(ESCAPED_REPO_PATH):
        compose_files_cmd = build_test_compose_files_cmd(database=database)

        for service in AVAILABLE_SERVICES:
            if "infrahub" in service:
                continue
            command = f"{get_env_vars(context)} docker compose {compose_files_cmd} -p {BUILD_NAME} pull {service}"
            execute_command(context=context, command=command)


@task
def destroy(context: Context):
    """Destroy the test environment."""
    with context.cd(ESCAPED_REPO_PATH):
        compose_files_cmd = build_test_compose_files_cmd()
        exec_cmd = (
            f"{get_env_vars(context=context)} docker compose {compose_files_cmd} -p {BUILD_NAME} down --remove-orphans"
        )
        return execute_command(context=context, command=exec_cmd)
