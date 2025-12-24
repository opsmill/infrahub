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
        context.run("uv sync --all-groups")

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
def update_helm_chart(context: Context, chart_repo: str | None = "helm/") -> None:  # noqa: ARG001
    """Update helm/Chart.yaml with the current version from pyproject.toml."""
    print(" - [release] Update Helm chart")

    # Get the app version directly from pyproject.toml
    app_version = get_version_from_pyproject()  # Returns a string like '1.1.0a1'

    for chart in ["infrahub", "infrahub-enterprise"]:
        # Initialize YAML and load the Chart.yaml file
        yaml: YAML = init_yaml_obj()
        chart_path = Path(chart_repo) / "charts" / Path(chart) / "Chart.yaml"
        chart_yaml = yaml.load(chart_path)

        if "appVersion" not in chart_yaml:
            raise ValueError(f"appVersion not found in {str(chart_path)}; no updates made.")

        old_app_version = chart_yaml.get("appVersion", "")
        if old_app_version == app_version:
            print(
                f"{str(chart_path)} updates not required, `appVersion` of {old_app_version} matches current from `pyproject.toml`"
            )
            return

        # Handle Helm chart version increment
        old_helm_version = chart_yaml.get("version", "")
        if not old_helm_version:
            raise ValueError(f"Helm chart `version` not found in {str(chart_path)}; no updates made.")

        # Split the Helm chart version into components for increment logic
        major, minor, patch = map(int, old_helm_version.split("."))
        new_helm_version = f"{major}.{minor}.{patch}"

        # Determine the appropriate increment
        try:
            if app_version > old_app_version:
                if int(app_version.split(".")[0]) > int(old_app_version.split(".")[0]):
                    new_helm_version = f"{major + 1}.0.0"
                elif int(app_version.split(".")[1]) > int(old_app_version.split(".")[1]):
                    new_helm_version = f"{major}.{minor + 1}.0"
                elif int(app_version.split(".")[2].split("a")[0]) > int(
                    old_app_version.split(".")[2].split("a")[0]
                ):  # For alpha, beta handling
                    new_helm_version = f"{major}.{minor}.{patch + 1}"
        except Exception:
            # Fallback in case app_version has non-standard format for Helm comparison
            print(f"Warning: Unable to strictly compare versions, using default Helm chart version: {new_helm_version}")

        # Update the YAML
        chart_yaml["appVersion"] = app_version
        chart_yaml["version"] = new_helm_version

        if chart == "infrahub":
            dependency_version = new_helm_version

            yaml_values: YAML = init_yaml_obj()
            values_path = Path(chart_repo) / "charts" / Path(chart) / "values.yaml"
            values_yaml = yaml_values.load(values_path)

            if (
                "prefect-server" not in values_yaml
                or "global" not in values_yaml["prefect-server"]
                or "prefect" not in values_yaml["prefect-server"]["global"]
                or "image" not in values_yaml["prefect-server"]["global"]["prefect"]
                or "prefectTag" not in values_yaml["prefect-server"]["global"]["prefect"]["image"]
                or "repository" not in values_yaml["prefect-server"]["global"]["prefect"]["image"]
                or values_yaml["prefect-server"]["global"]["prefect"]["image"]["repository"]
                != "registry.opsmill.io/opsmill/infrahub"
            ):
                print(f"prefect-server image tag not found in {str(values_path)}; no updates made.")
            else:
                values_yaml["prefect-server"]["global"]["prefect"]["image"]["prefectTag"] = app_version
                yaml_values.dump(values_yaml, values_path)
                print(f"{str(values_path)} updated with `prefectTag`: {app_version}")
        elif chart == "infrahub-enterprise":
            if "dependencies" in chart_yaml:
                for dependency in chart_yaml["dependencies"]:
                    if dependency["name"] == "infrahub":
                        # Update 'infrahub' dependencies in helm chart
                        dependency["version"] = dependency_version
                        print(f"'infrahub' dependency update to {dependency_version} in {chart}")
                        break

        yaml.dump(chart_yaml, chart_path)

        print(f"{str(chart_path)} updated with Helm `version`: {new_helm_version} and `appVersion`: {app_version}")


@task
def update_docker_compose(context: Context, docker_file: str | None = "docker-compose.yml") -> None:  # noqa: ARG001
    """Update docker-compose.yml with the current version from pyproject.toml.

    Uses text-based substitution to preserve YAML anchors and aliases.
    """
    print(" - [release] Update docker-compose.yml")

    # Get the version directly from pyproject.toml
    version = get_version_from_pyproject()  # Returns a string like '1.1.0a0'

    docker_path = Path(docker_file)
    content = docker_path.read_text(encoding="utf-8")

    # Pattern to match the infrahub_image anchor definition line only
    # This targets: image: &infrahub_image "...registry.opsmill.io/opsmill/infrahub...:${VERSION:-X.X.X}"
    # We only update the anchor definition, not the alias references (*infrahub_image)
    version_pattern = r"(\d+\.\d+\.\d+[-a-zA-Z0-9]*)"
    anchor_line_pattern = re.compile(r"^(\s*image:\s*&infrahub_image\s+.*?)" + version_pattern + r"(.*)$")

    updates_made = False
    new_lines = []

    for line in content.splitlines():
        match = anchor_line_pattern.match(line)
        if match:
            old_version = match.group(2)
            if old_version != version:
                new_line = match.group(1) + version + match.group(3)
                new_lines.append(new_line)
                updates_made = True
                print(f"Updated infrahub_image from {old_version} to {version}")
            else:
                new_lines.append(line)
        else:
            new_lines.append(line)

    if not updates_made:
        print(f"{docker_file} updates not required, all images are already up-to-date.")
        return

    docker_path.write_text("\n".join(new_lines) + "\n", encoding="utf-8")


@task
def update_test_containers(context: Context, toml_file: str | None = "python_testcontainers/pyproject.toml") -> None:  # noqa: ARG001
    """Update test containers pyproject.toml with the current version from pyproject.toml."""
    print(" - [release] Update python_testcontainers/pyproject.toml")

    # Get the version directly from pyproject.toml
    version = get_version_from_pyproject()  # Returns a string like '1.1.0a0'

    # Read the test containers pyproject.toml file
    test_containers_file = Path(toml_file)
    test_containers_toml = test_containers_file.read_text(encoding="utf8")

    # Replace the version referenced there
    new_toml = re.sub(r'^version = ".*"', f'version = "{version}"', test_containers_toml, flags=re.MULTILINE)

    # Print the new file out
    test_containers_file.write_text(new_toml, encoding="utf8")


def get_enum_mappings() -> dict:
    """Extracts enum mappings dynamically."""
    from infrahub.config import (
        BrokerDriver,
        CacheDriver,
        ExtraLogLevel,
        Oauth2Provider,
        OIDCProvider,
        SSOProtocol,
        StorageDriver,
        TraceExporterType,
        TraceTransportProtocol,
        WorkflowDriver,
    )
    from infrahub.constants.database import DatabaseType

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
        ExtraLogLevel,
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

    def get_env_vars_in_anchor(anchor_name: str, docker_compose: list[str]) -> tuple[dict, int | None, int | None]:
        in_config_section = False
        infrahub_config_start = None
        infrahub_config_end = None

        existing_vars = {}

        for i, line in enumerate(docker_compose):
            if line.strip().startswith(anchor_name):
                in_config_section = True
                infrahub_config_start = i + 1
                continue
            if in_config_section and (not line.strip() or line.strip().startswith("services:")):
                in_config_section = False
                infrahub_config_end = i
                break
            # Skip YAML alias in the config section
            if in_config_section and not line.strip().startswith("<<") and not line.strip().startswith("#"):
                var_name = line.split(":", 1)[0].strip()
                existing_vars[var_name] = i

        return existing_vars, infrahub_config_start, infrahub_config_end

    infrahub_base_config, infrahub_config_start, infrahub_config_end = get_env_vars_in_anchor(
        "x-infrahub-config: &infrahub_config", docker_compose
    )
    infrahub_sso_config, *_ = get_env_vars_in_anchor("x-infrahub-sso: &infrahub_sso", docker_compose)
    all_vars = sorted(infrahub_base_config.keys() | set(env_vars) - infrahub_sso_config.keys())
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

        if var in infrahub_base_config:
            line_idx = infrahub_base_config[var]
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
    context: Context,  # noqa: ARG001
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
        for field_name, field in subset.__class__.model_fields.items():
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
