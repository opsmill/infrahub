import os
import sys
from pathlib import Path

from invoke import Context, task

from .shared import (
    BUILD_NAME,
    build_test_compose_files_cmd,
    build_test_envs,
    get_env_vars,
)
from .utils import ESCAPED_REPO_PATH

CURRENT_DIRECTORY = os.path.abspath(os.path.dirname(__file__))
DOCUMENTATION_DIRECTORY = os.path.join(CURRENT_DIRECTORY, "../docs")


@task
def build(context: Context):
    """Build documentation website."""
    exec_cmd = "npx retypeapp build docs"
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
    _generate(context=context)


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

    exec_cmd = "npx retypeapp start docs"

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
            exec_cmd = f'poetry run typer {command[0]} utils docs --name "{command[1]}" --output docs/reference/infrahub-cli/{command[2]}.md'
            context.run(exec_cmd)


def _generate(context: Context):
    """Generate documentation output from code."""
    _generate_infrahub_cli_documentation(context=context)
    _generate_infrahubctl_documentation(context=context)
    _generate_infrahub_schema_documentation()


def _generate_infrahubctl_documentation(context: Context):
    """Generate the documentation for infrahubctl using typer-cli."""
    from infrahub_sdk.ctl.cli import app

    print(" - Generate infrahubctl CLI documentation")
    for cmd in app.registered_commands:
        exec_cmd = f'poetry run typer --func {cmd.name} infrahub_sdk.ctl.cli utils docs --name "infrahubctl {cmd.name}"'
        exec_cmd += f" --output docs/infrahubctl/infrahubctl-{cmd.name}.md"
        with context.cd(ESCAPED_REPO_PATH):
            context.run(exec_cmd)

    for cmd in app.registered_groups:
        exec_cmd = f"poetry run typer infrahub_sdk.ctl.{cmd.name} utils docs"
        exec_cmd += f' --name "infrahubctl {cmd.name}" --output docs/infrahubctl/infrahubctl-{cmd.name}.md'
        with context.cd(ESCAPED_REPO_PATH):
            context.run(exec_cmd)


def _generate_infrahub_schema_documentation() -> None:
    """Generate documentation for the schema"""
    import jinja2

    from infrahub.core.schema import internal_schema

    schemas_to_generate = ["node", "attribute", "relationship", "generic"]
    print(" - Generate Infrahub schema documentation")
    for schema_name in schemas_to_generate:
        template_file = f"{DOCUMENTATION_DIRECTORY}/_templates/schema/{schema_name}.j2"
        output_file = f"{DOCUMENTATION_DIRECTORY}/reference/schema/{schema_name}.md"
        output_label = f"docs/reference/schema/{schema_name}.md"
        if not os.path.exists(template_file):
            print(f"Unable to find the template file at {template_file}")
            sys.exit(-1)

        template_text = Path(template_file).read_text(encoding="utf-8")

        environment = jinja2.Environment()
        template = environment.from_string(template_text)
        rendered_file = template.render(schema=internal_schema)

        with open(output_file, "w", encoding="utf-8") as f:
            f.write(rendered_file)

        print(f"Docs saved to: {output_label}")
