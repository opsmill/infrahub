from __future__ import annotations

import re
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING, Any, Optional

from invoke.tasks import task

from .container_ops import (
    build_images,
    destroy_environment,
    migrate_database,
    pull_images,
    restart_services,
    show_service_status,
    start_services,
    stop_services,
    update_core_schema,
)
from .infra_ops import load_infrastructure_data, load_infrastructure_schema
from .shared import (
    BUILD_NAME,
    INFRAHUB_DATABASE,
    PYTHON_VER,
    SERVICE_WORKER_NAME,
    Namespace,
    build_compose_files_cmd,
    build_dev_compose_files_cmd,
    execute_command,
    get_compose_cmd,
    get_env_vars,
)
from .utils import ESCAPED_REPO_PATH

if TYPE_CHECKING:
    from invoke.context import Context


NAMESPACE = Namespace.DEV


@task(optional=["database"])
def build(
    context: Context,
    service: Optional[str] = None,
    python_ver: str = PYTHON_VER,
    nocache: bool = False,
    database: str = INFRAHUB_DATABASE,
) -> None:
    """Build an image with the provided name and python version.

    Args:
        context (obj): Used to run specific commands
        python_ver (str): Define the Python version docker image to build from
        nocache (bool): Do not use cache when building the image
    """
    build_images(
        context=context, service=service, python_ver=python_ver, nocache=nocache, database=database, namespace=NAMESPACE
    )


@task(optional=["database"])
def debug(context: Context, database: str = INFRAHUB_DATABASE) -> None:
    """Start a local instance of Infrahub in debug mode."""
    with context.cd(ESCAPED_REPO_PATH):
        compose_files_cmd = build_compose_files_cmd(database=database)
        compose_cmd = get_compose_cmd(namespace=NAMESPACE)
        command = f"{get_env_vars(context, namespace=NAMESPACE)} {compose_cmd} {compose_files_cmd} -p {BUILD_NAME} up"
        execute_command(context=context, command=command)


@task(optional=["database"])
def deps(context: Context, database: str = INFRAHUB_DATABASE) -> None:
    """Start local instances of dependencies (Databases and Message Bus)."""
    with context.cd(ESCAPED_REPO_PATH):
        dev_compose_files_cmd = build_dev_compose_files_cmd(database=database)
        compose_cmd = get_compose_cmd(namespace=NAMESPACE)
        command = (
            f"{get_env_vars(context, namespace=NAMESPACE)} {compose_cmd} {dev_compose_files_cmd} -p {BUILD_NAME} up -d"
        )
        execute_command(context=context, command=command)


@task
def destroy(context: Context, database: str = INFRAHUB_DATABASE) -> None:
    """Destroy all containers and volumes."""
    destroy_environment(context=context, database=database, namespace=NAMESPACE)


@task(optional=["database"])
def infra_git_create(
    context: Context,
    database: str = INFRAHUB_DATABASE,
    name: str = "demo-edge",
    location: str = "/remote/infrahub-demo-edge",
) -> None:
    """Load some demo data."""
    with context.cd(ESCAPED_REPO_PATH):
        compose_files_cmd = build_compose_files_cmd(database=database, namespace=NAMESPACE)
        compose_cmd = get_compose_cmd(namespace=NAMESPACE)
        base_cmd = f"{get_env_vars(context, namespace=NAMESPACE)} {compose_cmd} {compose_files_cmd} -p {BUILD_NAME}"
        execute_command(
            context=context,
            command=f"{base_cmd} run {SERVICE_WORKER_NAME} infrahubctl repository add {name} {location}",
        )


@task(optional=["database"])
def infra_git_import(context: Context, database: str = INFRAHUB_DATABASE) -> None:
    """Load some demo data."""
    REPO_NAME = "infrahub-demo-edge"
    with context.cd(ESCAPED_REPO_PATH):
        compose_files_cmd = build_compose_files_cmd(database=database, namespace=NAMESPACE)
        compose_cmd = get_compose_cmd(namespace=NAMESPACE)
        base_cmd = f"{get_env_vars(context, namespace=NAMESPACE)} {compose_cmd} {compose_files_cmd} -p {BUILD_NAME}"
        execute_command(
            context=context,
            command=f"{base_cmd} run {SERVICE_WORKER_NAME} cp -r backend/tests/fixtures/repos/{REPO_NAME}/initial__main /remote/{REPO_NAME}",
        )
        execute_command(
            context=context,
            command=f"{base_cmd} exec --workdir /remote/{REPO_NAME} {SERVICE_WORKER_NAME} git init --initial-branch main",
        )
        execute_command(
            context=context,
            command=f"{base_cmd} exec --workdir /remote/{REPO_NAME} {SERVICE_WORKER_NAME} git add .",
        )
        execute_command(
            context=context,
            command=f"{base_cmd} exec --workdir /remote/{REPO_NAME} {SERVICE_WORKER_NAME} git commit -m first",
        )


@task(optional=["database"])
def load_infra_data(context: Context, database: str = INFRAHUB_DATABASE) -> None:
    """Load infrastructure demo data."""
    load_infrastructure_data(context=context, database=database, namespace=NAMESPACE)


@task(optional=["database"])
def load_infra_schema(context: Context, database: str = INFRAHUB_DATABASE) -> None:
    """Load the base schema for infrastructure."""
    load_infrastructure_schema(context=context, database=database, namespace=NAMESPACE, add_wait=False)
    restart_services(context=context, database=database, namespace=NAMESPACE)


@task(optional=["database"])
def pull(context: Context, database: str = INFRAHUB_DATABASE) -> None:
    """Pull external containers from registry."""
    pull_images(context=context, database=database, namespace=NAMESPACE)


@task(optional=["database"])
def restart(context: Context, database: str = INFRAHUB_DATABASE) -> None:
    """Restart Infrahub API Server and Git Agent within docker compose."""
    restart_services(context=context, database=database, namespace=NAMESPACE)


@task(optional=["database"])
def status(context: Context, database: str = INFRAHUB_DATABASE) -> None:
    """Display the status of all containers."""
    show_service_status(context=context, database=database, namespace=NAMESPACE)


@task(optional=["database"])
def start(context: Context, database: str = INFRAHUB_DATABASE, wait: bool = False) -> None:
    """Start a local instance of Infrahub within docker compose."""
    start_services(context=context, database=database, namespace=NAMESPACE, wait=wait)


@task(optional=["database"])
def stop(context: Context, database: str = INFRAHUB_DATABASE) -> None:
    """Stop the running instance of Infrahub."""
    stop_services(context=context, database=database, namespace=NAMESPACE)


@task(optional=["database"])
def migrate(context: Context, database: str = INFRAHUB_DATABASE) -> None:
    """Apply the latest database migrations."""
    migrate_database(context=context, database=database, namespace=NAMESPACE)
    update_core_schema(context=context, database=database, namespace=NAMESPACE, debug=True)


def get_version_from_pyproject() -> str:
    """Retrieve the current version from the pyproject.toml file."""
    import toml

    return toml.load("pyproject.toml")["tool"]["poetry"]["version"]


@task
def update_helm_chart(context: Context, chart_file: Optional[str] = "helm/Chart.yaml") -> None:
    """Update helm/Chart.yaml with the current version from pyproject.toml."""
    version = get_version_from_pyproject()
    version_pattern = r"^appVersion:\s*[\d\.\-a-zA-Z]+"

    def replace_version(match: str) -> str:
        return f"appVersion: {version}"

    chart_path = Path(chart_file)
    chart_yaml = chart_path.read_text(encoding="utf-8")

    updated_chart_yaml = re.sub(version_pattern, replace_version, chart_yaml, flags=re.MULTILINE)
    chart_path.write_text(updated_chart_yaml, encoding="utf-8")

    print(f"{chart_file} updated with appVersion {version}")


@task
def update_docker_compose(context: Context, docker_file: Optional[str] = "docker-compose.yml") -> None:
    """Update docker-compose.yml with the current version from pyproject.toml."""
    version = get_version_from_pyproject()
    version_pattern = r"registry.opsmill.io/opsmill/infrahub:\$\{VERSION:-[\d\.\-a-zA-Z]+\}"

    def replace_version(match: str) -> str:
        return f"registry.opsmill.io/opsmill/infrahub:${{VERSION:-{version}}}"

    docker_path = Path(docker_file)
    docker_compose = docker_path.read_text(encoding="utf-8")
    updated_docker_compose = re.sub(version_pattern, replace_version, docker_compose)
    docker_path.write_text(updated_docker_compose, encoding="utf-8")

    print(f"{docker_file} updated with version {version}")


def get_enum_mappings() -> dict:
    """Extracts enum mappings dynamically."""
    from infrahub.config import (
        BrokerDriver,
        CacheDriver,
        Oauth2Provider,
        OIDCProvider,
        SSOProtocol,
        StorageDriver,
        TraceExporterType,
        TraceTransportProtocol,
        WorkflowDriver,
    )
    from infrahub.database.constants import DatabaseType

    enum_mappings = {}

    for enum_class in [
        BrokerDriver,
        CacheDriver,
        Oauth2Provider,
        OIDCProvider,
        SSOProtocol,
        StorageDriver,
        TraceExporterType,
        TraceTransportProtocol,
        WorkflowDriver,
        DatabaseType,
    ]:
        for item in enum_class:
            enum_mappings[item] = item.value

    return enum_mappings


def update_docker_compose_env_vars(
    env_vars: list[str],
    env_defaults: dict[str, Any],
    enum_mappings: dict[Any, str],
    docker_file: Optional[str] = "docker-compose.yml",
) -> None:
    """Update the docker-compose.yml file with the environment variables."""
    import json

    docker_path = Path(docker_file)
    docker_compose = docker_path.read_text(encoding="utf-8").splitlines()

    in_infrahub_config_section = False
    infrahub_config_start = None
    infrahub_config_end = None

    existing_vars = {}

    for i, line in enumerate(docker_compose):
        if line.strip().startswith("x-infrahub-config: &infrahub_config"):
            in_infrahub_config_section = True
            infrahub_config_start = i + 1
            continue
        if in_infrahub_config_section and (not line.strip() or line.strip().startswith("services:")):
            in_infrahub_config_section = False
            infrahub_config_end = i
            break
        if in_infrahub_config_section:
            var_name = line.split(":", 1)[0].strip()
            existing_vars[var_name] = i

    all_vars = sorted(existing_vars.keys() | set(env_vars))
    pattern = re.compile(r"\$\{(.+):-([^}]+)\}")

    new_config_lines = []
    for var in all_vars:
        default_value = env_defaults.get(var, "")
        if isinstance(default_value, bool):
            default_value_str = str(default_value).lower()
        elif isinstance(default_value, Enum):
            default_value_str = enum_mappings.get(default_value, str(default_value))
        elif isinstance(default_value, list):
            default_value_str = json.dumps(default_value)
        else:
            default_value_str = str(default_value) if default_value is not None else ""

        if var in existing_vars:
            line_idx = existing_vars[var]
            existing_value = docker_compose[line_idx].split(":", 1)[1].strip().strip('"')

            match = pattern.match(existing_value)
            if match and match.group(1) == var and match.group(2) == default_value_str:
                new_config_lines.append(docker_compose[line_idx])
            elif var in [
                "INFRAHUB_BROKER_USERNAME",
                "INFRAHUB_BROKER_PASSWORD",
                "INFRAHUB_CACHE_USERNAME",
                "INFRAHUB_CACHE_PASSWORD",
            ]:
                key_name = var.replace("INFRAHUB_", "").lower()
                new_config_lines.append(f"  {var}: &{key_name} ${{{var}:-{default_value_str}}}")
            elif default_value_str:
                new_config_lines.append(f"  {var}: ${{{var}:-{default_value_str}}}")
            else:
                new_config_lines.append(f"  {var}:")
        elif var in [
            "INFRAHUB_BROKER_USERNAME",
            "INFRAHUB_BROKER_PASSWORD",
            "INFRAHUB_CACHE_USERNAME",
            "INFRAHUB_CACHE_PASSWORD",
        ]:
            key_name = var.replace("INFRAHUB_", "").lower()
            new_config_lines.append(f"  {var}: &{key_name} ${{{var}:-{default_value_str}}}")
        elif default_value_str:
            new_config_lines.append(f"  {var}: ${{{var}:-{default_value_str}}}")
        else:
            new_config_lines.append(f"  {var}:")

    docker_compose = docker_compose[:infrahub_config_start] + new_config_lines + docker_compose[infrahub_config_end:]

    docker_path.write_text("\n".join(docker_compose) + "\n", encoding="utf-8")
    print(f"{docker_file} updated with environment variables")


@task
def gen_config_env(
    context: Context, docker_file: Optional[str] = "docker-compose.yml", update_docker_file: Optional[bool] = False
) -> None:
    """Generate list of env vars required for configuration and update docker file.yml if need be."""
    from pydantic_settings import BaseSettings
    from pydantic_settings.sources import EnvSettingsSource

    from infrahub.config import Settings

    enum_mappings = get_enum_mappings()

    # These are environment variables used outside of Pydantic settings
    env_vars = {
        "INFRAHUB_LOG_LEVEL",
        "INFRAHUB_PRODUCTION",
        "INFRAHUB_CONFIG",
        "OTEL_RESOURCE_ATTRIBUTES",
        "INFRAHUB_ADDRESS",
    }
    settings = Settings()
    env_defaults = {}

    def fetch_fields(subset: BaseSettings) -> None:
        env_settings = EnvSettingsSource(
            subset.__class__,
            env_prefix=subset.model_config.get("env_prefix"),
        )
        for field_name, field in subset.model_fields.items():
            field_inst = getattr(subset, field_name)
            if issubclass(field_inst.__class__, BaseSettings):
                fetch_fields(field_inst)
            else:
                for _, field_env_name, _ in env_settings._extract_field_info(field, field_name):
                    env_vars.add(field_env_name.upper())
                    env_defaults[field_env_name.upper()] = field.get_default()

    for subsetting in dict(settings):
        subsettings = getattr(settings, subsetting)
        fetch_fields(subsettings)

    env_vars.discard("PATH")
    if update_docker_file:
        update_docker_compose_env_vars(
            env_vars=sorted(env_vars), env_defaults=env_defaults, enum_mappings=enum_mappings, docker_file=docker_file
        )
    else:
        for var in sorted(env_vars):
            print(f"{var}:")
