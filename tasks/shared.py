import os
from enum import Enum

from .utils import project_ver


class DatabaseType(str, Enum):
    NEO4J = "neo4j"
    MEMGRAPH = "memgraph"


here = os.path.abspath(os.path.dirname(__file__))
TOP_DIRECTORY_NAME = os.path.basename(os.path.abspath(os.path.join(here, "..")))
BUILD_NAME = os.getenv("INFRAHUB_BUILD_NAME", TOP_DIRECTORY_NAME)
PYTHON_VER = os.getenv("PYTHON_VER", "3.11")
IMAGE_NAME = os.getenv("IMAGE_NAME", f"opsmill/{BUILD_NAME}-py{PYTHON_VER}")
IMAGE_VER = os.getenv("IMAGE_VER", project_ver())
PWD = os.getcwd()

NBR_WORKERS = os.getenv("PYTEST_XDIST_WORKER_COUNT", 1)

AVAILABLE_SERVICES = ["infrahub-git", "frontend", "infrahub-server", "database", "message-queue"]
SUPPORTED_DATABASES = [DatabaseType.MEMGRAPH.value, DatabaseType.NEO4J.value]


TEST_COMPOSE_FILES_MEMGRAPH = [
    "development/docker-compose-message-queue.yml",
    "development/docker-compose-test-database-memgraph.yml",
    "development/docker-compose-test.yml",
]
TEST_COMPOSE_FILES_NEO4J = [
    "development/docker-compose-message-queue.yml",
    "development/docker-compose-test-database-neo4j.yml",
    "development/docker-compose-test.yml",
]


IMAGE_NAME_FRONTEND = os.getenv("INFRAHUB_IMAGE_NAME_FRONTEND", f"opsmill/{BUILD_NAME}-backend-py{PYTHON_VER}")
IMAGE_NAME_BACKEND = os.getenv("INFRAHUB_IMAGE_NAME_BACKEND", f"opsmill/{BUILD_NAME}-frontend")
IMAGE_VER = os.getenv("INFRAHUB_IMAGE_VER", project_ver())

OVERRIDE_FILE_NAME = "development/docker-compose.override.yml"
DEFAULT_FILE_NAME = "development/docker-compose.default.yml"
COMPOSE_FILES_MEMGRAPH = [
    "development/docker-compose-message-queue.yml",
    "development/docker-compose-database-memgraph.yml",
    "development/docker-compose.yml",
]
COMPOSE_FILES_NEO4J = [
    "development/docker-compose-message-queue.yml",
    "development/docker-compose-database-neo4j.yml",
    "development/docker-compose.yml",
]

DEV_COMPOSE_FILES_MEMGRAPH = [
    "development/docker-compose-message-queue.yml",
    "development/docker-compose-database-memgraph.yml",
]
DEV_COMPOSE_FILES_NEO4J = [
    "development/docker-compose-message-queue.yml",
    "development/docker-compose-database-neo4j.yml",
]
DEV_OVERRIDE_FILE_NAME = "development/docker-compose.dev-override.yml"

AVAILABLE_SERVICES = ["infrahub-git", "frontend", "infrahub-server", "database", "message-queue"]
SUPPORTED_DATABASES = [DatabaseType.MEMGRAPH.value, DatabaseType.NEO4J.value]

ENV_VARS_DICT = {
    "IMAGE_NAME_FRONTEND": IMAGE_NAME_FRONTEND,
    "IMAGE_NAME_BACKEND": IMAGE_NAME_BACKEND,
    "IMAGE_VER": IMAGE_VER,
    "PYTHON_VER": PYTHON_VER,
    "INFRAHUB_BUILD_NAME": BUILD_NAME,
    "NBR_WORKERS": NBR_WORKERS,
}
ENV_VARS = " ".join([f"{key}={value}" for key, value in ENV_VARS_DICT.items()])

VOLUME_NAMES = ["database_data", "database_logs", "git_data"]


def build_compose_files_cmd(database: str) -> str:
    if database not in SUPPORTED_DATABASES:
        exit(f"{database} is not a valid database ({SUPPORTED_DATABASES})")

    if database == DatabaseType.MEMGRAPH.value:
        COMPOSE_FILES = COMPOSE_FILES_MEMGRAPH
    elif database == DatabaseType.NEO4J.value:
        COMPOSE_FILES = COMPOSE_FILES_NEO4J

    if os.path.exists(OVERRIDE_FILE_NAME):
        print("!! Found an override file for docker-compose !!")
        COMPOSE_FILES.append(OVERRIDE_FILE_NAME)
    else:
        COMPOSE_FILES.append(DEFAULT_FILE_NAME)

    return f"-f {' -f '.join(COMPOSE_FILES)}"


def build_dev_compose_files_cmd(database: str) -> str:
    if database not in SUPPORTED_DATABASES:
        exit(f"{database} is not a valid database ({SUPPORTED_DATABASES})")

    if database == DatabaseType.MEMGRAPH.value:
        DEV_COMPOSE_FILES = DEV_COMPOSE_FILES_MEMGRAPH
    elif database == DatabaseType.NEO4J.value:
        DEV_COMPOSE_FILES = DEV_COMPOSE_FILES_NEO4J

    if os.path.exists(DEV_OVERRIDE_FILE_NAME):
        print("!! Found a dev override file for docker-compose !!")
        DEV_COMPOSE_FILES.append(DEV_OVERRIDE_FILE_NAME)

    return f"-f {' -f '.join(DEV_COMPOSE_FILES)}"


def build_test_compose_files_cmd(database: str = DatabaseType.MEMGRAPH.value) -> str:
    if database not in SUPPORTED_DATABASES:
        exit(f"{database} is not a valid database ({SUPPORTED_DATABASES})")

    if database == DatabaseType.MEMGRAPH.value:
        DEV_COMPOSE_FILES = TEST_COMPOSE_FILES_MEMGRAPH
    elif database == DatabaseType.NEO4J.value:
        DEV_COMPOSE_FILES = TEST_COMPOSE_FILES_NEO4J

    # if os.path.exists(DEV_OVERRIDE_FILE_NAME):
    #     print("!! Found a dev override file for docker-compose !!")
    #     DEV_COMPOSE_FILES.append(DEV_OVERRIDE_FILE_NAME)

    return f"-f {' -f '.join(DEV_COMPOSE_FILES)}"
