import os
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

from invoke import Context, task

from .shared import (
    BUILD_NAME,
    build_test_compose_files_cmd,
    build_test_envs,
    get_env_vars,
)
from .utils import ESCAPED_REPO_PATH, check_if_command_available

CURRENT_DIRECTORY = Path(__file__).parent.resolve()
DOCUMENTATION_DIRECTORY = CURRENT_DIRECTORY.parent / "docs"


@task
def build(context: Context):
    """Build documentation website."""
    exec_cmd = "npm run build"

    with context.cd(DOCUMENTATION_DIRECTORY):
        output = context.run(exec_cmd)

    if output.exited != 0:
        sys.exit(-1)


@task
def generate(context: Context):
    """Generate all documentation output from code."""
    _generate(context=context)


@task
def generate_schema(context: Context):
    """Generate documentation for the schema."""
    _generate_infrahub_schema_documentation()


@task
def generate_infrahub_cli(context: Context):
    """Generate documentation for the infrahub cli."""
    _generate_infrahub_cli_documentation(context=context)


@task
def generate_infrahubctl(context: Context):
    """Generate documentation for the infrahubctl cli."""
    _generate_infrahubctl_documentation(context=context)


@task
def generate_infrahubsync_sync(context: Context):
    """Generate documentation for the infrahub-sync cli."""
    _generate_infrahubsync_documentation(context=context)


@task
def generate_repository(context: Context):
    """Generate documentation for the repository configuration file."""
    _generate_infrahub_repository_configuration_documentation(context=context)


@task
def generate_python_sdk(context: Context):
    """Generate documentation for the Python SDK."""
    _generate_infrahub_sdk_configuration_documentation(context=context)


@task
def generate_bus_events(context: Context):
    """Generate documentation for the Bus events."""
    _generate_infrahub_events_documentation(context=context)


@task
def install(context: Context):
    """Install documentation dependencies."""
    exec_cmd = "npm install"

    with context.cd(DOCUMENTATION_DIRECTORY):
        output = context.run(exec_cmd)

    if output.exited != 0:
        sys.exit(-1)


@task
def validate(context: Context, docker: bool = False):
    """Validate that the generated documentation is committed to Git."""

    if docker:
        compose_files_cmd = build_test_compose_files_cmd(database=False)
        exec_cmd = f"{get_env_vars(context)} docker compose {compose_files_cmd} -p {BUILD_NAME} run "
        exec_cmd += f"{build_test_envs()} infrahub-test inv docs.validate"
        with context.cd(ESCAPED_REPO_PATH):
            context.run(exec_cmd)
        return

    _generate(context=context)
    exec_cmd = "git diff --exit-code docs"
    with context.cd(ESCAPED_REPO_PATH):
        context.run(exec_cmd)


@task
def serve(context: Context):
    """Run documentation server in development mode."""

    exec_cmd = "npm run serve"

    with context.cd(DOCUMENTATION_DIRECTORY):
        context.run(exec_cmd)


@task
def vale(context: Context):
    """Run vale to validate the documentation."""
    has_vale = check_if_command_available(context=context, command_name="vale")

    if not has_vale:
        print("Warning, Vale is not installed")
        return

    exec_cmd = "vale ."
    print(" - [docs] Lint docs with vale")
    with context.cd(ESCAPED_REPO_PATH):
        context.run(exec_cmd)


@task
def markdownlint(context: Context):
    has_markdownlint = check_if_command_available(context=context, command_name="markdownlint-cli2")

    if not has_markdownlint:
        print("Warning, markdownlint-cli2 is not installed")
        return
    exec_cmd = "markdownlint-cli2 **/*.{md,mdx} '#**/node_modules/**'"
    print(" - [docs] Lint docs with markdownlint-cli2")
    with context.cd(ESCAPED_REPO_PATH):
        context.run(exec_cmd)


@task
def format_markdownlint(context: Context):
    """Run markdownlint-cli2 to format all .md/mdx files."""

    print(" - [docs] Format code with markdownlint-cli2")
    exec_cmd = "markdownlint-cli2 **/*.{md,mdx} --fix"
    with context.cd(ESCAPED_REPO_PATH):
        context.run(exec_cmd)


@task
def format(context: Context):
    """This will run all formatter."""
    format_markdownlint(context)


@task
def lint(context: Context):
    """This will run all linter."""
    vale(context)
    markdownlint(context)


def _generate_infrahub_cli_documentation(context: Context):
    """Generate the documentation for infrahub cli using typer-cli."""

    CLI_COMMANDS = (
        ("infrahub.cli.db", "infrahub db", "infrahub-db"),
        ("infrahub.cli.server", "infrahub server", "infrahub-server"),
        ("infrahub.cli.git_agent", "infrahub git-agent", "infrahub-git-agent"),
    )

    print(" - Generate Infrahub CLI documentation")
    with context.cd(ESCAPED_REPO_PATH):
        for command in CLI_COMMANDS:
            exec_cmd = f'poetry run typer {command[0]} utils docs --name "{command[1]}" --output docs/docs/reference/infrahub-cli/{command[2]}.mdx'
            context.run(exec_cmd)


def _generate(context: Context):
    """Generate documentation output from code."""
    _generate_infrahub_cli_documentation(context=context)
    # _generate_infrahubsync_documentation(context=context)
    _generate_infrahubctl_documentation(context=context)
    _generate_infrahub_schema_documentation()
    _generate_infrahub_repository_configuration_documentation()
    _generate_infrahub_sdk_configuration_documentation()
    _generate_infrahub_events_documentation()


def _generate_infrahubctl_documentation(context: Context):
    """Generate the documentation for infrahubctl using typer-cli."""
    from infrahub_sdk.ctl.cli import app

    print(" - Generate infrahubctl CLI documentation")
    for cmd in app.registered_commands:
        exec_cmd = f'poetry run typer --func {cmd.name} infrahub_sdk.ctl.cli_commands utils docs --name "infrahubctl {cmd.name}"'
        exec_cmd += f" --output docs/docs/infrahubctl/infrahubctl-{cmd.name}.mdx"
        with context.cd(ESCAPED_REPO_PATH):
            context.run(exec_cmd)

    for cmd in app.registered_groups:
        exec_cmd = f"poetry run typer infrahub_sdk.ctl.{cmd.name} utils docs"
        exec_cmd += f' --name "infrahubctl {cmd.name}" --output docs/docs/infrahubctl/infrahubctl-{cmd.name}.mdx'
        with context.cd(ESCAPED_REPO_PATH):
            context.run(exec_cmd)


def _generate_infrahubsync_documentation(context: Context):
    """Generate the documentation for infrahub-sync using typer-cli."""

    print(" - Generate infrahub-sync CLI documentation")
    exec_cmd = 'poetry run typer infrahub_sync.cli utils docs --name "infrahub-sync"'
    exec_cmd += " --output docs/docs/integrations/sync/reference/cli.mdx"
    with context.cd(ESCAPED_REPO_PATH):
        context.run(exec_cmd)


def _generate_infrahub_schema_documentation() -> None:
    """Generate documentation for the schema"""
    import jinja2

    from infrahub.core.schema import internal, internal_schema

    schemas_to_generate = {
        "node": internal_schema,
        "attribute": internal_schema,
        "relationship": internal_schema,
        "generic": internal_schema,
        "validator-migration": internal,
    }
    print(" - Generate Infrahub schema documentation")
    for schema_name, schema in schemas_to_generate.items():
        template_file = f"{DOCUMENTATION_DIRECTORY}/_templates/schema/{schema_name}.j2"
        output_file = f"{DOCUMENTATION_DIRECTORY}/docs/reference/schema/{schema_name}.mdx"
        output_label = f"docs/docs/reference/schema/{schema_name}.mdx"
        if not os.path.exists(template_file):
            print(f"Unable to find the template file at {template_file}")
            sys.exit(-1)

        template_text = Path(template_file).read_text(encoding="utf-8")

        environment = jinja2.Environment()
        template = environment.from_string(template_text)
        rendered_file = template.render(schema=schema)

        Path(output_file).write_text(rendered_file, encoding="utf-8")
        print(f"Docs saved to: {output_label}")


def _get_env_vars() -> dict[str, str]:
    from infrahub_sdk.config import ConfigBase
    from pydantic_settings import EnvSettingsSource

    env_vars: dict[str, list[str]] = defaultdict(list[str])
    settings = ConfigBase()
    env_settings = EnvSettingsSource(settings.__class__, env_prefix=settings.model_config.get("env_prefix"))

    for field_name, field in settings.model_fields.items():
        for field_key, field_env_name, _ in env_settings._extract_field_info(field, field_name):
            env_vars[field_key].append(field_env_name.upper())

    return env_vars


def _generate_infrahub_sdk_configuration_documentation() -> None:
    """Generate documentation for the Infrahub SDK configuration"""
    import jinja2
    from infrahub_sdk.config import ConfigBase

    schema = ConfigBase.model_json_schema()
    env_vars = _get_env_vars()
    definitions = schema["$defs"]

    properties = []
    for name, prop in schema["properties"].items():
        choices: list[dict[str, Any]] = []
        kind = ""
        composed_type = ""
        if "allOf" in prop:
            choices = definitions[prop["allOf"][0]["$ref"].split("/")[-1]].get("enum", [])
            kind = definitions[prop["allOf"][0]["$ref"].split("/")[-1]].get("type", "")
        if "anyOf" in prop:
            composed_type = ", ".join(i["type"] for i in prop.get("anyOf", []) if "type" in i and i["type"] != "null")
        properties.append(
            {
                "name": name,
                "description": prop.get("description", ""),
                "type": prop.get("type", kind) or composed_type or "object",
                "choices": choices,
                "default": prop.get("default", ""),
                "env_vars": env_vars[name],
            }
        )

    template_file = f"{DOCUMENTATION_DIRECTORY}/_templates/sdk_config.j2"
    output_file = f"{DOCUMENTATION_DIRECTORY}/docs/python-sdk/reference/config.mdx"
    output_label = "docs/docs/python-sdk/reference/config.mdx"

    if not os.path.exists(template_file):
        print(f"Unable to find the template file at {template_file}")
        sys.exit(-1)

    template_text = Path(template_file).read_text(encoding="utf-8")

    environment = jinja2.Environment(trim_blocks=True)
    template = environment.from_string(template_text)
    rendered_file = template.render(properties=properties)

    Path(output_file).write_text(rendered_file, encoding="utf-8")
    print(f"Docs saved to: {output_label}")


def _generate_infrahub_repository_configuration_documentation() -> None:
    """Generate documentation for the Infrahub repository configuration file"""
    from copy import deepcopy

    import jinja2
    from infrahub_sdk.schema import InfrahubRepositoryConfig

    schema = InfrahubRepositoryConfig.model_json_schema()

    properties = [
        {
            "name": name,
            "description": property["description"],
            "title": property["title"],
            "type": property["type"],
            "items_type": property["items"]["$ref"].split("/")[-1]
            if "$ref" in property["items"]
            else property["items"]["type"],
            "items_format": property["items"]["format"] if "format" in property["items"] else None,
        }
        for name, property in schema["properties"].items()
    ]

    definitions = deepcopy(schema["$defs"])

    for name, definition in schema["$defs"].items():
        for property, value in definition["properties"].items():
            definitions[name]["properties"][property]["required"] = (
                True if property in definition["required"] else False
            )
            if "anyOf" in value:
                definitions[name]["properties"][property]["type"] = ", ".join(
                    [i["type"] for i in value["anyOf"] if i["type"] != "null"]
                )

    print(" - Generate Infrahub repository configuration documentation")

    template_file = f"{DOCUMENTATION_DIRECTORY}/_templates/dotinfrahub.j2"
    output_file = f"{DOCUMENTATION_DIRECTORY}/docs/reference/dotinfrahub.mdx"
    if not os.path.exists(template_file):
        print(f"Unable to find the template file at {template_file}")
        sys.exit(-1)

    template_text = Path(template_file).read_text(encoding="utf-8")

    environment = jinja2.Environment()
    template = environment.from_string(template_text)
    rendered_file = template.render(properties=properties, definitions=definitions)

    Path(output_file).write_text(rendered_file, encoding="utf-8")


def _generate_infrahub_events_documentation() -> None:
    """
    Generate documentation for all classes in the event system into a single file
    using a Jinja2 template. Accessible via `invoke generate_infrahub_events_documentation`.
    """
    from collections import defaultdict
    from typing import Optional, Union

    from infrahub.message_bus import InfrahubMessage, InfrahubResponse

    def group_classes_by_category(
        classes: dict[str, type[Union[InfrahubMessage, InfrahubResponse]]],
        priority_map: Optional[dict[str, int]] = None,
    ) -> dict[str, dict[str, list[dict[str, any]]]]:
        """
        Group classes into a nested dictionary by primary and secondary categories, including priority.
        """
        grouped = defaultdict(lambda: defaultdict(list))
        for event_name, cls in classes.items():
            parts = event_name.split(".")
            primary, secondary = parts[0], ".".join(parts[:2])
            priority = priority_map.get(event_name, 3) if priority_map else -1
            description = cls.__doc__.strip() if cls.__doc__ else None

            event_info = {
                "event_name": event_name,
                "description": description,
                "priority": priority,
                "fields": [
                    {
                        "name": prop,
                        "type": details.get("type", "N/A"),
                        "description": details.get("description", "N/A"),
                        "default": details.get("default", "None"),
                    }
                    for prop, details in cls.model_json_schema().get("properties", {}).items()
                ],
            }
            grouped[primary][secondary].append(event_info)
        return grouped

    template_file = DOCUMENTATION_DIRECTORY / "_templates" / "message-bus-events.j2"
    output_file = DOCUMENTATION_DIRECTORY / "docs" / "reference" / "message-bus-events.mdx"

    print(" - Generate Infrahub Bus Events documentation")

    if not os.path.exists(template_file):
        print(f"Unable to find the template file at {template_file}")
        sys.exit(-1)

    import jinja2

    from infrahub.message_bus.messages import MESSAGE_MAP, PRIORITY_MAP, RESPONSE_MAP

    template_text = template_file.read_text(encoding="utf-8")
    environment = jinja2.Environment()
    template = environment.from_string(template_text)

    message_classes = group_classes_by_category(classes=MESSAGE_MAP, priority_map=PRIORITY_MAP)
    response_classes = group_classes_by_category(classes=RESPONSE_MAP, priority_map=PRIORITY_MAP)

    rendered_doc = template.render(message_classes=message_classes, response_classes=response_classes)

    output_file.parent.mkdir(exist_ok=True)
    output_file.write_text(rendered_doc, encoding="utf-8")
    print(f"Docs saved to: {output_file}")
