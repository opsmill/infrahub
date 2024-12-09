"""Release related Invoke Tasks."""

import re
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING, Any

from invoke import Context, task

from tasks.shared import init_yaml_obj
from tasks.utils import (
    ESCAPED_REPO_PATH,
    check_if_command_available,
    get_version_from_pyproject,
)

if TYPE_CHECKING:
    from ruamel.yaml.main import YAML

VERSION_PATTERN_DOCKER = (
    r"\$\{INFRAHUB_DOCKER_IMAGE:-registry\.opsmill\.io/opsmill/infrahub\}:\$\{VERSION:-[\d\.\-a-zA-Z]+\}"
)


def get_normalized_version(version_str: str) -> str:
    """
    Normalizes a version string by stripping pre-release labels
    to be compatible with Docker or Helm chart versioning.
    """
    # Replace patterns like 'a0' with '-alpha.0', 'b1' with '-beta.1', etc.
    version_str = re.sub(r"(\d+\.\d+\.\d+)[a-zA-Z0-9\-\.]*", r"\1", version_str)
    return version_str


@task
def markdownlint(context: Context) -> None:
    has_markdownlint = check_if_command_available(context=context, command_name="markdownlint-cli2")

    if not has_markdownlint:
        print("Warning, markdownlint-cli2 is not installed")
        return
    exec_cmd = "markdownlint-cli2 'changelog/*.md' '!changelog/towncrier_template.md' 'CHANGELOG.md' 'docs/docs/release-notes/infrahub/*.{md,mdx}'"
    print(" - [release] Lint release files with markdownlint-cli2")
    with context.cd(ESCAPED_REPO_PATH):
        context.run(exec_cmd)


@task
def vale(context: Context) -> None:
    """Run vale to validate the release notes."""
    has_vale = check_if_command_available(context=context, command_name="vale")

    if not has_vale:
        print("Warning, Vale is not installed")
        return

    exec_cmd = "vale $(find ./changelog ./docs/docs/release-notes/infrahub -type f \\( -name '*.mdx' -o -name '*.md' \\)) CHANGELOG.md"
    print(" - [release] Lint release files with vale")
    with context.cd(ESCAPED_REPO_PATH):
        context.run(exec_cmd)


@task
def draft(context: Context) -> None:
    """Run `towncrier build --draft` to validate that Towncrier can read the Newsfragments."""
    has_towncrier = check_if_command_available(context=context, command_name="towncrier")

    if not has_towncrier:
        print("Warning, Towncrier is not installed")
        return

    exec_cmd = "towncrier build --draft"
    print(" - [release] Verify Towncrier render possible")
    with context.cd(ESCAPED_REPO_PATH):
        context.run(exec_cmd)


@task
def lint(context: Context) -> None:
    """This will run all linters."""
    markdownlint(context)
    vale(context)
    draft(context)


@task
def build_changelog(context: Context) -> None:
    has_towncrier = check_if_command_available(context=context, command_name="towncrier")

    if not has_towncrier:
        print("Warning, Towncrier is not installed")
        return

    # Ensure local environment is up to date
    print(" - [release] Update local environment")
    with context.cd(ESCAPED_REPO_PATH):
        context.run("poetry install --sync")

    print(" - [release] Build changelog")
    exec_cmd = "towncrier build --draft 2> /dev/null"
    with context.cd(ESCAPED_REPO_PATH):
        changelog_contents = context.run(exec_cmd, hide="stdout").stdout
    print(changelog_contents)


@task
def ship(context: Context) -> None:
    """This will generate the Release Notes and prepare to ship the release."""
    lint(context)


@task
def update_helm_chart(context: Context, chart_file: str | None = "helm/Chart.yaml") -> None:
    """Update helm/Chart.yaml with the current version from pyproject.toml."""
    print(" - [release] Update Helm chart")
    from semver import Version

    app_version: Version = Version.parse(
        version=get_normalized_version(get_version_from_pyproject()), optional_minor_and_patch=True
    )

    yaml: YAML = init_yaml_obj()

    chart_path = Path(chart_file)
    chart_yaml = yaml.load(chart_path)

    if "appVersion" not in chart_yaml.keys():
        raise ValueError(f"appVersion not found in {chart_file}; no updates made.")

    old_app_version: Version = Version.parse(chart_yaml["appVersion"], optional_minor_and_patch=True)
    if old_app_version == app_version:
        print(
            f"{chart_file} updates not required, `appVersion` of {old_app_version} matches current from `pyproject.toml`"
        )
        return

    old_helm_version: Version = Version.parse(chart_yaml["version"], optional_minor_and_patch=True)
    if app_version.major > old_app_version.major:
        helm_version: Version = old_helm_version.bump_major()
    elif app_version.minor > old_app_version.minor:
        helm_version: Version = old_helm_version.bump_minor()
    elif app_version.patch > old_app_version.patch:
        helm_version: Version = old_helm_version.bump_patch()
    else:
        helm_version = old_helm_version

    chart_yaml["appVersion"] = str(app_version)
    chart_yaml["version"] = str(helm_version)

    yaml.dump(chart_yaml, chart_path)

    print(f"{chart_file} updated with Helm `version`: {helm_version} and `appVersion`: {app_version}")


@task
def update_docker_compose(context: Context, docker_file: str | None = "docker-compose.yml") -> None:
    """Update docker-compose.yml with the current version from pyproject.toml."""
    print(" - [release] Update docker-compose.yml")
    from semver import Version

    # Parse the current version from pyproject.toml
    version: Version = Version.parse(
        version=get_normalized_version(get_version_from_pyproject()), optional_minor_and_patch=True
    )

    # Initialize YAML and load the docker-compose file
    yaml: YAML = init_yaml_obj(line_length=4096)
    docker_path = Path(docker_file)
    docker_yaml: dict = yaml.load(docker_path)

    services_to_update = ["infrahub-server", "task-worker"]
    updates_made = False

    # Iterate over the services and update their image versions
    for service in services_to_update:
        service_config = docker_yaml["services"].get(service)
        if not service_config or "image" not in service_config:
            print(f"Service {service} or its image field is missing; skipping.")
            continue

        image = service_config["image"]
        old_version_match = re.search(r"\d+\.\d+\.\d+", image)
        if old_version_match:
            old_version = Version.parse(old_version_match[0], optional_minor_and_patch=True)
            if old_version != version:
                # Replace old version with the new version in the image field
                new_image = re.sub(r"\d+\.\d+\.\d+", str(version), image)
                service_config["image"] = new_image
                updates_made = True
                print(f"Updated {service} image from {old_version} to {version}")

    # Check if updates were made
    if not updates_made:
        print(f"{docker_file} updates not required, all images are already up-to-date ({version}).")
        return

    yaml.dump(docker_yaml, docker_path)


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
    docker_file: str | None = "docker-compose.yml",
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
        if var.startswith("INFRAHUB_DEV"):
            continue
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
    context: Context,
    docker_file: str | None = "docker-compose.yml",
    update_docker_file: bool | None = False,
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
            env_vars=sorted(env_vars),
            env_defaults=env_defaults,
            enum_mappings=enum_mappings,
            docker_file=docker_file,
        )
    else:
        for var in sorted(env_vars):
            print(f"{var}:")
