from __future__ import annotations

import os
import platform
import re
import sys
from enum import StrEnum
from pathlib import Path
from typing import TYPE_CHECKING

from invoke import Context, UnexpectedExit

from .utils import get_yamllint_rules, str_to_bool

if TYPE_CHECKING:
    from invoke.runners import Result
    from ruamel.yaml.main import YAML


class DatabaseType(StrEnum):
    NEO4J = "neo4j"
    MEMGRAPH = "memgraph"


class Namespace(StrEnum):
    DEFAULT = "default"  # aka demo
    DEV = "dev"
    TEST = "test"
    DEBUG = "debug"


INVOKE_SUDO = os.getenv("INVOKE_SUDO", None)
INVOKE_PTY = os.getenv("INVOKE_PTY", None)
DEBUG = os.environ.get("DEBUG", "").lower() in ("true", "1", "yes")
INFRAHUB_DATABASE = os.getenv("INFRAHUB_DB_TYPE", DatabaseType.NEO4J.value)
INFRAHUB_ADDRESS = os.getenv("INFRAHUB_ADDRESS", "http://localhost:8000")

INFRAHUB_DEBUG: bool = str_to_bool(value=os.getenv("INFRAHUB_DEBUG", "false"))
INFRAHUB_DEBUG_TRACE: bool = str_to_bool(value=os.getenv("INFRAHUB_DEBUG_TRACE", "false"))
INFRAHUB_USE_NATS: bool = str_to_bool(os.getenv("INFRAHUB_USE_NATS", "false"))

DATABASE_DOCKER_IMAGE = os.getenv("DATABASE_DOCKER_IMAGE", None)
MEMGRAPH_DOCKER_IMAGE = os.getenv("MEMGRAPH_DOCKER_IMAGE", "memgraph/memgraph-mage:1.19-memgraph-2.19-no-ml")
NEO4J_DOCKER_IMAGE = os.getenv("NEO4J_DOCKER_IMAGE", "neo4j:2025.10.1-enterprise")
MESSAGE_QUEUE_DOCKER_IMAGE = os.getenv(
    "MESSAGE_QUEUE_DOCKER_IMAGE",
    "rabbitmq:4.2.1-management" if not INFRAHUB_USE_NATS else "nats:2.10.14-alpine",
)
CACHE_DOCKER_IMAGE = os.getenv(
    "CACHE_DOCKER_IMAGE",
    "redis:8.4.0" if not INFRAHUB_USE_NATS else "nats:2.10.14-alpine",
)

here = Path(__file__).parent.resolve()
TOP_DIRECTORY_NAME = here.parent.name
BUILD_NAME = os.getenv("INFRAHUB_BUILD_NAME", re.sub(r"[^a-zA-Z0-9_/.]", "", str(TOP_DIRECTORY_NAME)))
PYTHON_VER = os.getenv("PYTHON_VER", "3.12")

PWD = Path.cwd()

NBR_WORKERS = int(os.getenv("PYTEST_XDIST_WORKER_COUNT", "1"))
GITHUB_ACTION = os.getenv("GITHUB_ACTION"), False


SERVICE_SERVER_NAME = "server"
SERVICE_WORKER_NAME = "task-worker"
SERVICE_TASK_MANAGER_NAME = "task-manager"
AVAILABLE_SERVICES = [
    SERVICE_SERVER_NAME,
    SERVICE_WORKER_NAME,
    "database",
    "message-queue",
    SERVICE_TASK_MANAGER_NAME,
    "cache",
]

SUPPORTED_DATABASES = [DatabaseType.MEMGRAPH.value, DatabaseType.NEO4J.value]

COMPOSE_FILES_DEPS = {
    False: Path("development/docker-compose-deps.yml"),
    True: Path("development/docker-compose-deps-nats.yml"),
}

IMAGE_NAME = os.getenv("INFRAHUB_IMAGE_NAME", "registry.opsmill.io/opsmill/infrahub")
REQUESTED_IMAGE_VER = os.getenv("INFRAHUB_IMAGE_VER")
IMAGE_VER = REQUESTED_IMAGE_VER or "latest"

OVERRIDE_FILE = Path("development/docker-compose.override.yml")
DEFAULT_FILE = Path("development/docker-compose.default.yml")
LOCAL_FILE = Path("development/docker-compose.local-build.yml")
LOCAL_FILE_DEPS = Path("development/docker-compose.local-build-deps.yml")
COMPOSE_FILES_MEMGRAPH = [
    COMPOSE_FILES_DEPS[INFRAHUB_USE_NATS],
    Path("development/docker-compose-database-memgraph.yml"),
    Path("development/docker-compose.yml"),
]
COMPOSE_FILES_NEO4J = [
    COMPOSE_FILES_DEPS[INFRAHUB_USE_NATS],
    Path("development/docker-compose-database-neo4j.yml"),
    Path("development/docker-compose-observability.yml"),
    Path("development/docker-compose.yml"),
]

DEV_COMPOSE_FILES_MEMGRAPH = [
    COMPOSE_FILES_DEPS[INFRAHUB_USE_NATS],
    Path("development/docker-compose-database-memgraph.yml"),
]
DEV_COMPOSE_FILES_NEO4J = [
    COMPOSE_FILES_DEPS[INFRAHUB_USE_NATS],
    Path("development/docker-compose-database-neo4j.yml"),
    Path("development/docker-compose-observability.yml"),
]
DEV_OVERRIDE_FILE = Path("development/docker-compose.dev-override.yml")

TEST_METRICS_OVERRIDE_FILE = Path("development/docker-compose-test-metrics.yml")


PLATFORMS_PTY_ENABLE = ["Linux", "Darwin"]
PLATFORMS_SUDO_DETECT = ["Linux"]

VOLUME_NAMES = [
    "database_data",
    "database_logs",
    "git_remote_data",
    "workflow_data",
    "workflow_db",
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
]

PYTHON_PRIMITIVE_MAP = {
    "boolean": "bool",
    "datetime": "datetime",
    "dropdown": "str",
    "enum": "str",
    "hashedpassword": "str",
    "iphost": "str",
    "ipnetwork": "str",
    "json": "dict",
    "list": "list",
    "number": "int",
    "password": "str",
    "text": "str",
    "textarea": "str",
    "url": "str",
}


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


def dumb_terminal() -> bool:
    return os.getenv("TERM", "").lower() == "dumb"


def get_compose_cmd(namespace: Namespace) -> str:
    options = []

    if namespace == Namespace.DEV:
        options.append("--profile dev")
    elif namespace == Namespace.DEFAULT:
        options.append("--profile demo")
    elif namespace == Namespace.TEST:
        options.append("--profile test")

    if INFRAHUB_DEBUG:
        options.append("--profile debug")
        if INFRAHUB_DEBUG_TRACE:
            options.append("--profile trace")
            os.environ["INFRAHUB_TRACE_ENABLE"] = "True"
            os.environ["INFRAHUB_TRACE_INSECURE"] = "True"
            os.environ["INFRAHUB_TRACE_EXPORTER_TYPE"] = "otlp"
            os.environ["INFRAHUB_TRACE_EXPORTER_ENDPOINT"] = "http://tempo:4317"

    if dumb_terminal():
        options.append("--ansi never")

    if len(options) > 0:
        return f"docker compose {' '.join(options)}"

    return "docker compose"


def execute_command(context: Context, command: str, print_cmd: bool = False, hide: bool = False) -> Result | None:
    params = check_environment(context=context)
    if params["sudo"]:
        command = f"sudo {command}"

    should_print = print_cmd or DEBUG
    should_hide = hide and not DEBUG

    if should_print:
        print(f"command={command}")
    return context.run(command, pty=params["pty"], hide=should_hide)


def get_env_vars(context: Context, namespace: Namespace = Namespace.DEFAULT) -> str:  # noqa: ARG001
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

    if namespace == Namespace.DEV and not REQUESTED_IMAGE_VER:
        ENV_VARS_DICT["IMAGE_VER"] = "local"

    if DATABASE_DOCKER_IMAGE:
        ENV_VARS_DICT["DATABASE_DOCKER_IMAGE"] = DATABASE_DOCKER_IMAGE
    elif DatabaseType.NEO4J.value == INFRAHUB_DATABASE:
        ENV_VARS_DICT["DATABASE_DOCKER_IMAGE"] = NEO4J_DOCKER_IMAGE
    elif DatabaseType.MEMGRAPH.value == INFRAHUB_DATABASE:
        ENV_VARS_DICT["DATABASE_DOCKER_IMAGE"] = MEMGRAPH_DOCKER_IMAGE
    return " ".join([f"{key}={value}" for key, value in ENV_VARS_DICT.items()])


def build_compose_files_cmd(database: str, namespace: Namespace = Namespace.DEFAULT) -> str:
    if database not in SUPPORTED_DATABASES:
        sys.exit(f"{database} is not a valid database ({SUPPORTED_DATABASES})")

    if database == DatabaseType.MEMGRAPH.value:
        COMPOSE_FILES = COMPOSE_FILES_MEMGRAPH.copy()
    elif database == DatabaseType.NEO4J.value:
        COMPOSE_FILES = COMPOSE_FILES_NEO4J.copy()

    if OVERRIDE_FILE.exists():
        print("!! Found an override file for docker-compose !!")
        COMPOSE_FILES.append(OVERRIDE_FILE)
    else:
        COMPOSE_FILES.append(DEFAULT_FILE)

    if "local" in IMAGE_VER or (namespace == Namespace.DEV and not REQUESTED_IMAGE_VER):
        COMPOSE_FILES.append(LOCAL_FILE)
        COMPOSE_FILES.append(LOCAL_FILE_DEPS)

    if os.getenv("CI") is not None:
        COMPOSE_FILES.append(TEST_METRICS_OVERRIDE_FILE)

    return f"-f {' -f '.join(map(str, COMPOSE_FILES))}"


def build_dev_compose_files_cmd(database: str) -> str:
    if database not in SUPPORTED_DATABASES:
        sys.exit(f"{database} is not a valid database ({SUPPORTED_DATABASES})")

    if database == DatabaseType.MEMGRAPH.value:
        DEV_COMPOSE_FILES = DEV_COMPOSE_FILES_MEMGRAPH.copy()
    elif database == DatabaseType.NEO4J.value:
        DEV_COMPOSE_FILES = DEV_COMPOSE_FILES_NEO4J.copy()

    if DEV_OVERRIDE_FILE.exists():
        print("!! Found a dev override file for docker-compose !!")
        DEV_COMPOSE_FILES.append(DEV_OVERRIDE_FILE)

    DEV_COMPOSE_FILES.append(LOCAL_FILE_DEPS)

    return f"-f {' -f '.join(map(str, DEV_COMPOSE_FILES))}"


def init_yaml_obj(line_length: int | None = None) -> YAML:
    """Instantiate a ruamel.yaml YAML object.

    Args:
        line_length (int, optional): Override the .yamllint.yml line length. Defaults to None.

    Returns:
        YAML: Instantiated ruamel.yaml.YAML object.
    """
    from ruamel.yaml import YAML

    yamllint_rules: dict = get_yamllint_rules()

    yaml = YAML(typ="rt")
    yaml.preserve_quotes = True
    yaml.indent(mapping=2, sequence=4, offset=2)
    yaml.explicit_start = True
    yaml.width = line_length or yamllint_rules.get("line-length", {}).get("max", 120)

    return yaml
