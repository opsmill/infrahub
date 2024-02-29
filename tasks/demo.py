"""Replacement for Makefile."""
import re
import sys
from time import sleep

from invoke import Context, task

from .shared import (
    AVAILABLE_SERVICES,
    BUILD_NAME,
    INFRAHUB_ADDRESS,
    INFRAHUB_DATABASE,
    PYTHON_VER,
    build_compose_files_cmd,
    build_dev_compose_files_cmd,
    execute_command,
    get_env_vars,
)
from .utils import ESCAPED_REPO_PATH

ADD_REPO_QUERY = """
mutation($name: String!, $location: String!){
  CoreRepositoryCreate(
    data: {
      name: { value: $name }
      location: { value: $location }
    }
  ) {
    ok
  }
}
"""


@task(optional=["database"])
def build(
    context,
    service: str = None,
    python_ver: str = PYTHON_VER,
    nocache: bool = False,
    database: str = INFRAHUB_DATABASE,
):  # pylint: disable=too-many-arguments
    """Build an image with the provided name and python version.

    Args:
        context (obj): Used to run specific commands
        python_ver (str): Define the Python version docker image to build from
        nocache (bool): Do not use cache when building the image
    """
    print("Building images")

    if service and service not in AVAILABLE_SERVICES:
        sys.exit(f"{service} is not a valid service ({AVAILABLE_SERVICES})")
    with context.cd(ESCAPED_REPO_PATH):
        compose_files_cmd = build_compose_files_cmd(database=database)
        base_cmd = f"{get_env_vars(context)} docker compose {compose_files_cmd} -p {BUILD_NAME}"
        print(f"base_cmd={base_cmd}")
        # if not TEST_IN_DOCKER:
        exec_cmd = f"build --build-arg PYTHON_VER={python_ver}"
        print(f"exec_cmd={exec_cmd}")
        # else:
        #     user_id = get_user_id(context)
        #     group_id = get_group_id(context)
        #     exec_cmd = f"build --build-arg USER_ID {user_id} --build-arg GROUP_ID {group_id} --build-arg PYTHON_VER={python_ver}"
        if nocache:
            exec_cmd += " --no-cache"

        if service:
            exec_cmd += f" {service}"

        execute_command(context=context, command=f"{base_cmd} {exec_cmd}", print_cmd=True)


@task(optional=["database"])
def pull(context: Context, database: str = INFRAHUB_DATABASE):
    """Pull external containers from registry."""
    with context.cd(ESCAPED_REPO_PATH):
        compose_files_cmd = build_compose_files_cmd(database=database)

        for service in AVAILABLE_SERVICES:
            if "infrahub" in service:
                continue
            command = f"{get_env_vars(context)} docker compose {compose_files_cmd} -p {BUILD_NAME} pull {service}"
            execute_command(context=context, command=command)


# ----------------------------------------------------------------------------
# Local Environment tasks
# ----------------------------------------------------------------------------
@task(optional=["database"])
def debug(context: Context, database: str = INFRAHUB_DATABASE):
    """Start a local instance of Infrahub in debug mode."""
    with context.cd(ESCAPED_REPO_PATH):
        compose_files_cmd = build_compose_files_cmd(database=database)
        command = f"{get_env_vars(context)} docker compose {compose_files_cmd} -p {BUILD_NAME} up"
        execute_command(context=context, command=command)


@task(optional=["database"])
def start(context: Context, database: str = INFRAHUB_DATABASE):
    """Start a local instance of Infrahub within docker compose."""
    with context.cd(ESCAPED_REPO_PATH):
        compose_files_cmd = build_compose_files_cmd(database=database)
        command = f"{get_env_vars(context)} docker compose {compose_files_cmd} -p {BUILD_NAME} up -d"
        execute_command(context=context, command=command)


@task(optional=["database"])
def restart(context: Context, database: str = INFRAHUB_DATABASE):
    """Restart Infrahub API Server and Git Agent within docker compose."""
    with context.cd(ESCAPED_REPO_PATH):
        compose_files_cmd = build_compose_files_cmd(database=database)
        base_cmd = f"{get_env_vars(context)} docker compose {compose_files_cmd} -p {BUILD_NAME}"

        execute_command(context=context, command=f"{base_cmd} restart infrahub-server")
        execute_command(context=context, command=f"{base_cmd} restart infrahub-git")


@task(optional=["database"])
def stop(context: Context, database: str = INFRAHUB_DATABASE):
    """Stop the running instance of Infrahub."""
    with context.cd(ESCAPED_REPO_PATH):
        compose_files_cmd = build_compose_files_cmd(database=database)
        command = f"{get_env_vars(context)} docker compose  {compose_files_cmd} -p {BUILD_NAME} down"
        execute_command(context=context, command=command)


@task
def destroy(context: Context, database: str = INFRAHUB_DATABASE):
    """Destroy all containers and volumes."""
    with context.cd(ESCAPED_REPO_PATH):
        compose_files_cmd = build_compose_files_cmd(database=database)

        command = f"{get_env_vars(context)} docker compose {compose_files_cmd} -p {BUILD_NAME} down --remove-orphans --volumes --timeout 1"
        execute_command(context=context, command=command)


@task(optional=["database"])
def cli_server(context: Context, database: str = INFRAHUB_DATABASE):
    """Launch a bash shell inside the running Infrahub container."""
    with context.cd(ESCAPED_REPO_PATH):
        compose_files_cmd = build_compose_files_cmd(database=database)
        command = f"{get_env_vars(context)} docker compose {compose_files_cmd} -p {BUILD_NAME} run infrahub-server bash"
        execute_command(context=context, command=command)


@task(optional=["database"])
def cli_git(context: Context, database: str = INFRAHUB_DATABASE):
    """Launch a bash shell inside the running Infrahub container."""
    with context.cd(ESCAPED_REPO_PATH):
        compose_files_cmd = build_compose_files_cmd(database=database)
        command = f"{get_env_vars(context)} docker compose {compose_files_cmd} -p {BUILD_NAME} run infrahub-git bash"
        execute_command(context=context, command=command)


@task
def init(context: Context, database: str = INFRAHUB_DATABASE):
    """Initialize Infrahub database before using it the first time."""
    print("demo.init has been deprecated ... it's now included directly in demo.start.")


@task(optional=["database"])
def status(context: Context, database: str = INFRAHUB_DATABASE):
    """Display the status of all containers."""
    with context.cd(ESCAPED_REPO_PATH):
        compose_files_cmd = build_compose_files_cmd(database=database)
        command = f"{get_env_vars(context)} docker compose {compose_files_cmd} -p {BUILD_NAME} ps"
        execute_command(context=context, command=command)


@task(optional=["database"])
def load_infra_schema(context: Context, database: str = INFRAHUB_DATABASE):
    """Load the base schema for infrastructure."""
    with context.cd(ESCAPED_REPO_PATH):
        compose_files_cmd = build_compose_files_cmd(database=database)
        base_cmd = f"{get_env_vars(context)} docker compose {compose_files_cmd} -p {BUILD_NAME}"
        command = f"{base_cmd} run infrahub-git infrahubctl schema load models/infrastructure_base.yml"
        execute_command(context=context, command=command)

        command = f"{base_cmd} restart infrahub-server"
        execute_command(context=context, command=command)


@task(optional=["database"])
def load_infra_data(context: Context, database: str = INFRAHUB_DATABASE):
    """Load some demo data."""
    with context.cd(ESCAPED_REPO_PATH):
        compose_files_cmd = build_compose_files_cmd(database=database)
        base_cmd = f"{get_env_vars(context)} docker compose {compose_files_cmd} -p {BUILD_NAME}"
        command = f"{base_cmd} run infrahub-git infrahubctl run models/infrastructure_edge.py"
        execute_command(context=context, command=command)


@task(optional=["database"])
def infra_git_import(context: Context, database: str = INFRAHUB_DATABASE):
    """Load some demo data."""
    REPO_NAME = "infrahub-demo-edge"
    with context.cd(ESCAPED_REPO_PATH):
        compose_files_cmd = build_compose_files_cmd(database=database)
        base_cmd = f"{get_env_vars(context)} docker compose {compose_files_cmd} -p {BUILD_NAME}"
        execute_command(
            context=context,
            command=f"{base_cmd} run infrahub-git cp -r backend/tests/fixtures/repos/{REPO_NAME}/initial__main /remote/{REPO_NAME}",
        )
        execute_command(
            context=context,
            command=f"{base_cmd} exec --workdir /remote/{REPO_NAME} infrahub-git git init --initial-branch main",
        )
        execute_command(
            context=context,
            command=f"{base_cmd} exec --workdir /remote/{REPO_NAME} infrahub-git git add .",
        )
        execute_command(
            context=context,
            command=f"{base_cmd} exec --workdir /remote/{REPO_NAME} infrahub-git git commit -m first",
        )


@task(optional=["database"])
def infra_git_create(
    context: Context,
    database: str = INFRAHUB_DATABASE,
    name="demo-edge",
    location="/remote/infrahub-demo-edge",
):
    """Load some demo data."""
    clean_query = re.sub(r"\n\s*", "", ADD_REPO_QUERY)

    exec_cmd = """
    curl -g \
    -X POST \
    -H "Content-Type: application/json" \
    -H "X-INFRAHUB-KEY: 06438eb2-8019-4776-878c-0941b1f1d1ec" \
    -d '{"query":"%s", "variables": {"name": "%s", "location": "%s"}}' \
    %s/graphql
    """ % (clean_query, name, location, INFRAHUB_ADDRESS)
    execute_command(context=context, command=exec_cmd, print_cmd=True)


# ----------------------------- -----------------------------------------------
# Dev Environment tasks
# ----------------------------------------------------------------------------
@task(optional=["database"])
def dev_start(context: Context, database: str = INFRAHUB_DATABASE):
    """Start a local instance of NEO4J & RabbitMQ."""
    with context.cd(ESCAPED_REPO_PATH):
        dev_compose_files_cmd = build_dev_compose_files_cmd(database=database)
        command = f"{get_env_vars(context)} docker compose {dev_compose_files_cmd} -p {BUILD_NAME} up -d"
        execute_command(context=context, command=command)


@task(optional=["database"])
def dev_stop(context: Context, database: str = INFRAHUB_DATABASE):
    """Start a local instance of NEO4J & RabbitMQ."""
    with context.cd(ESCAPED_REPO_PATH):
        dev_compose_files_cmd = build_dev_compose_files_cmd(database=database)
        command = f"{get_env_vars(context)} docker compose  {dev_compose_files_cmd} -p {BUILD_NAME} down"
        execute_command(context=context, command=command)


@task(optional=["expected"])
def wait_healthy(context: Context, expected: int = 2):
    """Wait until containers are healthy before continuing."""
    missing_healthy = True
    while missing_healthy:
        output = context.run("docker ps --filter 'health=healthy' --format '{{ .Names}}'", hide=True)
        containers = output.stdout.splitlines()
        if len(containers) >= expected:
            missing_healthy = False
        else:
            print(f"Expected {expected} healthy containers only saw: {', '.join(containers)}")
            sleep(1)
