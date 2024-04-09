import os
import sys
from pathlib import Path
from typing import Any, Dict, List

from invoke import Context, task

from .shared import (
    BUILD_NAME,
    build_test_compose_files_cmd,
    build_test_envs,
    get_env_vars,
)
from .utils import ESCAPED_REPO_PATH, check_if_command_available, group_classes_by_category

CURRENT_DIRECTORY = os.path.abspath(os.path.dirname(__file__))
DOCUMENTATION_DIRECTORY = os.path.join(CURRENT_DIRECTORY, "../docs")


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

        with open(output_file, "w", encoding="utf-8") as f:
            f.write(rendered_file)

        print(f"Docs saved to: {output_label}")


def _generate_infrahub_sdk_configuration_documentation() -> None:
    """Generate documentation for the Infrahub SDK configuration"""
    import jinja2
    from infrahub_sdk.config import ConfigBase

    schema = ConfigBase.schema()

    definitions = schema["definitions"]

    properties = []
    for name, prop in schema["properties"].items():
        choices: List[Dict[str, Any]] = []
        kind = ""
        if "allOf" in prop:
            choices = definitions[prop["allOf"][0]["$ref"].split("/")[-1]].get("enum", [])
            kind = definitions[prop["allOf"][0]["$ref"].split("/")[-1]].get("type", "")
        properties.append(
            {
                "name": name,
                "description": prop.get("description", ""),
                "type": prop.get("type", kind),
                "choices": choices,
                "default": prop.get("default", ""),
                "env_vars": list(prop.get("env_names", set())),
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

    with open(output_file, "w", encoding="utf-8") as f:
        f.write(rendered_file)

    print(f"Docs saved to: {output_label}")


def _generate_infrahub_repository_configuration_documentation() -> None:
    """Generate documentation for the Infrahub repository configuration file"""
    from copy import deepcopy

    import jinja2
    from infrahub_sdk.schema import InfrahubRepositoryConfig

    schema = InfrahubRepositoryConfig.schema()

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

    definitions = deepcopy(schema["definitions"])

    for name, definition in schema["definitions"].items():
        for property in definition["properties"].keys():
            definitions[name]["properties"][property]["required"] = (
                True if property in definition["required"] else False
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

    with open(output_file, "w", encoding="utf-8") as f:
        f.write(rendered_file)


def _generate_infrahub_events_documentation() -> None:
    """
    Generate documentation for all classes in the event system into a single file
    using a Jinja2 template. Accessible via `invoke generate_infrahub_events_documentation`.
    """
    template_file = f"{DOCUMENTATION_DIRECTORY}/_templates/message-bus-events.j2"
    output_file = f"{DOCUMENTATION_DIRECTORY}/docs/reference/message-bus-events.mdx"
    output_label = "docs/docs/reference/message-bus-events.mdx"

    print(" - Generate Infrahub Bus Events documentation")

    if not os.path.exists(template_file):
        print(f"Unable to find the template file at {template_file}")
        sys.exit(-1)

    import jinja2

    from infrahub.message_bus.messages import MESSAGE_MAP, PRIORITY_MAP, RESPONSE_MAP

    template_text = Path(template_file).read_text(encoding="utf-8")
    environment = jinja2.Environment()
    template = environment.from_string(template_text)

    message_classes = group_classes_by_category(classes=MESSAGE_MAP, priority_map=PRIORITY_MAP)
    response_classes = group_classes_by_category(classes=RESPONSE_MAP, priority_map=PRIORITY_MAP)

    rendered_doc = template.render(message_classes=message_classes, response_classes=response_classes)

    os.makedirs(os.path.dirname(output_file), exist_ok=True)
    with open(output_file, "w", encoding="utf-8") as f:
        f.write(rendered_doc)

    print(f"Docs saved to: {output_label}")
