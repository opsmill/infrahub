import os
import sys
from pathlib import Path

from invoke import Context, task

from .utils import ESCAPED_REPO_PATH

CURRENT_DIRECTORY = os.path.abspath(os.path.dirname(__file__))
DOCUMENTATION_DIRECTORY = os.path.join(CURRENT_DIRECTORY, "../docs")


@task
def build(context: Context):
    """Build documentation website."""
    exec_cmd = "npx retype build docs"
    with context.cd(ESCAPED_REPO_PATH):
        output = context.run(exec_cmd)

    successful_build_checks = 0
    if output:
        for line in output.stdout.splitlines():
            if " 0 errors" in line:
                successful_build_checks += 1
            elif " 0 warnings" in line:
                successful_build_checks += 1

    if successful_build_checks < 2:
        sys.exit(-1)


@task
def generate(context: Context):
    """Generate documentation output from code."""
    _generate_infrahub_cli_documentation(context=context)
    _generate_infrahubctl_documentation(context=context)
    _generate_infrahub_schema_documentation()


@task
def serve(context: Context):
    """Run documentation server in development mode."""

    exec_cmd = "npx retype serve docs"

    with context.cd(ESCAPED_REPO_PATH):
        context.run(exec_cmd)


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
            exec_cmd = f'typer {command[0]} utils docs --name "{command[1]}" --output docs/reference/infrahub-cli/{command[2]}.md'
            context.run(exec_cmd)


def _generate_infrahubctl_documentation(context: Context):
    """Generate the documentation for infrahubctl using typer-cli."""
    from infrahub_ctl.cli import app

    print(" - Generate infrahubctl CLI documentation")
    for cmd in app.registered_commands:
        exec_cmd = f'typer --func {cmd.name} infrahub_ctl.cli utils docs --name "infrahubctl {cmd.name}"'
        exec_cmd += f" --output docs/infrahubctl/infrahubctl-{cmd.name}.md"
        with context.cd(ESCAPED_REPO_PATH):
            context.run(exec_cmd)

    for cmd in app.registered_groups:
        exec_cmd = f'typer infrahub_ctl.{cmd.name} utils docs --name "infrahubctl {cmd.name}" --output docs/infrahubctl/infrahubctl-{cmd.name}.md'
        with context.cd(ESCAPED_REPO_PATH):
            context.run(exec_cmd)


def _generate_infrahub_schema_documentation() -> None:
    """Generate documentation for the schema"""
    import jinja2

    from infrahub.core.schema import internal_schema

    schemas_to_generate = ["node", "attribute", "relationship", "generic"]

    for schema_name in schemas_to_generate:
        template_file = f"{DOCUMENTATION_DIRECTORY}/reference/schema/{schema_name}.j2"
        output_file = f"{DOCUMENTATION_DIRECTORY}/reference/schema/{schema_name}.md"
        if not os.path.exists(template_file):
            print(f"Unable to find the template file at {template_file}")
            sys.exit(-1)

        template_text = Path(template_file).read_text(encoding="utf-8")

        environment = jinja2.Environment()
        template = environment.from_string(template_text)
        rendered_file = template.render(schema=internal_schema)

        with open(output_file, "w", encoding="utf-8") as f:
            f.write(rendered_file)

        print(f"Schema generated for {schema_name}")

    print("Schema documentation generated")
