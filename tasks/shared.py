import os
import platform
import re
import sys
from enum import Enum
from typing import Optional, Union

from invoke import Context, UnexpectedExit
from invoke.runners import Result

from .utils import str_to_bool


class DatabaseType(str, Enum):
    NEO4J = "neo4j"
    MEMGRAPH = "memgraph"


INVOKE_SUDO = os.getenv("INVOKE_SUDO", None)
INVOKE_PTY = os.getenv("INVOKE_PTY", None)
INFRAHUB_DATABASE = os.getenv("INFRAHUB_DB_TYPE", DatabaseType.NEO4J.value)
INFRAHUB_ADDRESS = os.getenv("INFRAHUB_ADDRESS", "http://localhost:8000")

DATABASE_DOCKER_IMAGE = os.getenv("DATABASE_DOCKER_IMAGE", None)
MEMGRAPH_DOCKER_IMAGE = os.getenv(
    "MEMGRAPH_DOCKER_IMAGE", "memgraph/memgraph-platform:2.14.0-memgraph2.14.0-lab2.11.1-mage1.14"
)
NEO4J_DOCKER_IMAGE = os.getenv("NEO4J_DOCKER_IMAGE", "neo4j:5.16.0-enterprise")
MESSAGE_QUEUE_DOCKER_IMAGE = os.getenv("MESSAGE_QUEUE_DOCKER_IMAGE", "rabbitmq:3.12.12-management")
CACHE_DOCKER_IMAGE = os.getenv("CACHE_DOCKER_IMAGE", "redis:7.2.4")

here = os.path.abspath(os.path.dirname(__file__))
TOP_DIRECTORY_NAME = os.path.basename(os.path.abspath(os.path.join(here, "..")))
BUILD_NAME = os.getenv("INFRAHUB_BUILD_NAME", re.sub(r"[^a-zA-Z0-9_/.]", "", TOP_DIRECTORY_NAME))
PYTHON_VER = os.getenv("PYTHON_VER", "3.12")
IMAGE_NAME = os.getenv("IMAGE_NAME", "registry.opsmill.io/opsmill/infrahub")
IMAGE_VER = os.getenv("IMAGE_VER", "stable")
PWD = os.getcwd()

NBR_WORKERS = os.getenv("PYTEST_XDIST_WORKER_COUNT", 1)
GITHUB_ACTION = os.getenv("GITHUB_ACTION", False)

AVAILABLE_SERVICES = ["infrahub-git", "infrahub-server", "database", "message-queue"]
SUPPORTED_DATABASES = [DatabaseType.MEMGRAPH.value, DatabaseType.NEO4J.value]

TEST_COMPOSE_FILE = "development/docker-compose-test.yml"
TEST_COMPOSE_FILES_MEMGRAPH = [
    "development/docker-compose-deps.yml",
    "development/docker-compose-test-database-memgraph.yml",
    "development/docker-compose-test-cache.yml",
    "development/docker-compose-test-message-queue.yml",
    TEST_COMPOSE_FILE,
]
TEST_COMPOSE_FILES_NEO4J = [
    "development/docker-compose-deps.yml",
    "development/docker-compose-test-database-neo4j.yml",
    "development/docker-compose-test-cache.yml",
    "development/docker-compose-test-message-queue.yml",
    TEST_COMPOSE_FILE,
]

TEST_SCALE_COMPOSE_FILE = "development/docker-compose-test-scale.yml"
TEST_SCALE_COMPOSE_FILES_NEO4J = [
    "development/docker-compose-deps.yml",
    "development/docker-compose-database-neo4j.yml",
    "development/docker-compose-test-cache.yml",
    TEST_SCALE_COMPOSE_FILE,
]
TEST_SCALE_COMPOSE_FILES_MEMGRAPH = [
    "development/docker-compose-deps.yml",
    "development/docker-compose-database-memgraph.yml",
    "development/docker-compose-test-cache.yml",
    TEST_SCALE_COMPOSE_FILE,
]
TEST_SCALE_OVERRIDE_FILE_NAME = "development/docker-compose-test-scale-override.yml"

IMAGE_NAME = os.getenv("INFRAHUB_IMAGE_NAME", "registry.opsmill.io/opsmill/infrahub")
IMAGE_VER = os.getenv("INFRAHUB_IMAGE_VER", "stable")

OVERRIDE_FILE_NAME = "development/docker-compose.override.yml"
DEFAULT_FILE_NAME = "development/docker-compose.default.yml"
LOCAL_FILE_NAME = "development/docker-compose.local-build.yml"
COMPOSE_FILES_MEMGRAPH = [
    "development/docker-compose-deps.yml",
    "development/docker-compose-database-memgraph.yml",
    "development/docker-compose.yml",
]
COMPOSE_FILES_NEO4J = [
    "development/docker-compose-deps.yml",
    "development/docker-compose-database-neo4j.yml",
    "development/docker-compose.yml",
]

DEV_COMPOSE_FILES_MEMGRAPH = [
    "development/docker-compose-deps.yml",
    "development/docker-compose-database-memgraph.yml",
]
DEV_COMPOSE_FILES_NEO4J = [
    "development/docker-compose-deps.yml",
    "development/docker-compose-database-neo4j.yml",
]
DEV_OVERRIDE_FILE_NAME = "development/docker-compose.dev-override.yml"

TEST_METRICS_OVERRIDE_FILE_NAME = "development/docker-compose-test-metrics.yml"

ENV_VARS_DICT = {
    "IMAGE_NAME": IMAGE_NAME,
    "IMAGE_VER": IMAGE_VER,
    "PYTHON_VER": PYTHON_VER,
    "INFRAHUB_BUILD_NAME": BUILD_NAME,
    "NBR_WORKERS": NBR_WORKERS,
    "CACHE_DOCKER_IMAGE": CACHE_DOCKER_IMAGE,
    "MESSAGE_QUEUE_DOCKER_IMAGE": MESSAGE_QUEUE_DOCKER_IMAGE,
    "INFRAHUB_DB_TYPE": INFRAHUB_DATABASE,
}

PLATFORMS_PTY_ENABLE = ["Linux", "Darwin"]
PLATFORMS_SUDO_DETECT = ["Linux"]

VOLUME_NAMES = [
    "database_data",
    "database_logs",
    "git_data",
    "git_remote_data",
    "storage_data",
]

GITHUB_ENVS_TO_PASS = [
    "GITHUB_ACTION",
    "GITHUB_REF_NAME",
    "GITHUB_BASE_REF",
    "GITHUB_HEAD_REF",
    "GITHUB_REPOSITORY",
    "GITHUB_RUN_ATTEMPT",
    "GITHUB_SHA",
    "GITHUB_RUN_ID",
    "GITHUB_RUN_NUMBER",
    "BUILDKITE_BRANCH",
    "BUILDKITE_COMMIT",
    "BUILDKITE_ANALYTICS_TOKEN",
    "BUILDKITE_ANALYTICS_BRANCH",
]


def check_environment(context: Context) -> dict:
    params = {
        "sudo": False,
        "pty": False,
    }

    if INVOKE_SUDO is not None:
        params["sudo"] = str_to_bool(INVOKE_SUDO)

    elif platform.system() in PLATFORMS_SUDO_DETECT:
        try:
            context.run("docker ps", hide=True)
        except UnexpectedExit as exc:
            if exc.result.stderr and "denied" in exc.result.stderr:
                output_with_sudo = context.run("sudo docker ps", hide=True)
                if "CONTAINER" in output_with_sudo.stdout:
                    params["sudo"] = True

    if INVOKE_PTY is not None:
        params["pty"] = str_to_bool(INVOKE_PTY)
    elif platform.system() in PLATFORMS_PTY_ENABLE:
        params["pty"] = True

    return params


def execute_command(context: Context, command: str, print_cmd: bool = False) -> Optional[Result]:
    params = check_environment(context=context)

    if params["sudo"]:
        command = f"sudo {command}"

    if print_cmd:
        print(command)

    print(f"command={command}")
    return context.run(command, pty=params["pty"])


def get_env_vars(context: Context) -> str:
    if DATABASE_DOCKER_IMAGE:
        ENV_VARS_DICT["DATABASE_DOCKER_IMAGE"] = ENV_VARS_DICT
    elif INFRAHUB_DATABASE == DatabaseType.NEO4J.value:
        ENV_VARS_DICT["DATABASE_DOCKER_IMAGE"] = NEO4J_DOCKER_IMAGE
    elif INFRAHUB_DATABASE == DatabaseType.MEMGRAPH.value:
        ENV_VARS_DICT["DATABASE_DOCKER_IMAGE"] = MEMGRAPH_DOCKER_IMAGE
    return " ".join([f"{key}={value}" for key, value in ENV_VARS_DICT.items()])


def build_compose_files_cmd(database: str) -> str:
    if database not in SUPPORTED_DATABASES:
        sys.exit(f"{database} is not a valid database ({SUPPORTED_DATABASES})")

    if database == DatabaseType.MEMGRAPH.value:
        COMPOSE_FILES = COMPOSE_FILES_MEMGRAPH
    elif database == DatabaseType.NEO4J.value:
        COMPOSE_FILES = COMPOSE_FILES_NEO4J

    if os.path.exists(OVERRIDE_FILE_NAME):
        print("!! Found an override file for docker-compose !!")
        COMPOSE_FILES.append(OVERRIDE_FILE_NAME)
    else:
        COMPOSE_FILES.append(DEFAULT_FILE_NAME)

    if "local" in IMAGE_VER:
        COMPOSE_FILES.append(LOCAL_FILE_NAME)

    if os.getenv("CI") is not None:
        COMPOSE_FILES.append(TEST_METRICS_OVERRIDE_FILE_NAME)

    return f"-f {' -f '.join(COMPOSE_FILES)}"


def build_dev_compose_files_cmd(database: str) -> str:
    if database not in SUPPORTED_DATABASES:
        sys.exit(f"{database} is not a valid database ({SUPPORTED_DATABASES})")

    if database == DatabaseType.MEMGRAPH.value:
        DEV_COMPOSE_FILES = DEV_COMPOSE_FILES_MEMGRAPH
    elif database == DatabaseType.NEO4J.value:
        DEV_COMPOSE_FILES = DEV_COMPOSE_FILES_NEO4J

    if os.path.exists(DEV_OVERRIDE_FILE_NAME):
        print("!! Found a dev override file for docker-compose !!")
        DEV_COMPOSE_FILES.append(DEV_OVERRIDE_FILE_NAME)

    return f"-f {' -f '.join(DEV_COMPOSE_FILES)}"


def build_test_compose_files_cmd(
    database: Union[bool, str] = DatabaseType.MEMGRAPH.value,
) -> str:
    if database is False:
        return f"-f {TEST_COMPOSE_FILE}"

    if database not in SUPPORTED_DATABASES:
        sys.exit(f"{database} is not a valid database ({SUPPORTED_DATABASES})")

    if database == DatabaseType.MEMGRAPH.value:
        DEV_COMPOSE_FILES = TEST_COMPOSE_FILES_MEMGRAPH
    elif database == DatabaseType.NEO4J.value:
        DEV_COMPOSE_FILES = TEST_COMPOSE_FILES_NEO4J

    # if os.path.exists(DEV_OVERRIDE_FILE_NAME):
    #     print("!! Found a dev override file for docker-compose !!")
    #     DEV_COMPOSE_FILES.append(DEV_OVERRIDE_FILE_NAME)

    return f"-f {' -f '.join(DEV_COMPOSE_FILES)}"


def build_test_scale_compose_files_cmd(
    database: str = DatabaseType.NEO4J.value,
) -> str:
    if database not in SUPPORTED_DATABASES:
        sys.exit(f"{database} is not a valid database ({SUPPORTED_DATABASES})")

    if database == DatabaseType.MEMGRAPH.value:
        TEST_SCALE_COMPOSE_FILES = TEST_SCALE_COMPOSE_FILES_MEMGRAPH
    elif database == DatabaseType.NEO4J.value:
        TEST_SCALE_COMPOSE_FILES = TEST_SCALE_COMPOSE_FILES_NEO4J

    if os.path.exists(TEST_SCALE_OVERRIDE_FILE_NAME):
        print("!! Found a test scale override file for docker-compose !!")
        TEST_SCALE_COMPOSE_FILES.append(TEST_SCALE_OVERRIDE_FILE_NAME)

    if os.getenv("CI") is not None:
        TEST_SCALE_COMPOSE_FILES.append(TEST_METRICS_OVERRIDE_FILE_NAME)

    return f"-f {' -f '.join(TEST_SCALE_COMPOSE_FILES)}"


def build_test_envs():
    if GITHUB_ACTION:
        return f"-e {' -e '.join(GITHUB_ENVS_TO_PASS)}"

    return ""
