import json
from pathlib import Path

from invoke.context import Context
from invoke.tasks import task

from .utils import ESCAPED_REPO_PATH, REPO_BASE

SDK_DIRECTORY = REPO_BASE / "generated" / "python-sdk"
INFRAHUB_DIRECTORY = REPO_BASE / "generated" / "infrahub"
SCHEMA_DIRECTORY = REPO_BASE / "schema"


@task
def generate_graphqlschema(context: Context) -> None:
    """Generate GraphQL schema into ./schema"""
    with context.cd(ESCAPED_REPO_PATH):
        context.run("poetry run infrahub schema export-graphql-schema --out schema/schema.graphql")


@task
def generate_jsonschema(context: Context) -> None:  # noqa: ARG001
    """Generate JSON schemas into ./generated"""

    generate_sdk_repository_config()
    generate_infrahub_node_schema()


@task
def validate_graphqlschema(context: Context) -> None:
    """Validate that the generated GraphQL schema is up to date."""
    generate_graphqlschema(context)

    exec_cmd = "git diff --exit-code schema/schema.graphql"
    with context.cd(ESCAPED_REPO_PATH):
        context.run(exec_cmd)


def generate_infrahub_node_schema() -> None:
    from infrahub.api.schema import SchemaLoadAPI

    schema_dir = INFRAHUB_DIRECTORY / "schema"
    schema_dir.mkdir(parents=True, exist_ok=True)

    schema = SchemaLoadAPI.model_json_schema()

    schema["title"] = "InfrahubSchema"

    content = json.dumps(schema, indent=4)

    write(file_path=schema_dir / "develop.json", content=content)


def generate_sdk_repository_config() -> None:
    from infrahub_sdk.schema.repository import InfrahubRepositoryConfig

    repository_dir = SDK_DIRECTORY / "repository-config"
    repository_dir.mkdir(parents=True, exist_ok=True)
    schema = json.dumps(InfrahubRepositoryConfig.model_json_schema(), indent=4)

    write(file_path=repository_dir / "develop.json", content=schema)


def write(file_path: Path, content: str) -> None:
    file_path.write_text(content, encoding="utf-8")
    print(f"Wrote to {file_path}")
