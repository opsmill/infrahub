import json
from pathlib import Path

from invoke.context import Context
from invoke.tasks import task

from .utils import ESCAPED_REPO_PATH, REPO_BASE

SDK_DIRECTORY = REPO_BASE / "generated" / "python-sdk"


@task
def generate_graphqlschema(context: Context) -> None:
    """Generate GraphQL schema into ./schema"""
    with context.cd(ESCAPED_REPO_PATH):
        context.run("poetry run infrahub dev export-graphql-schema --out schema/schema.graphql")


@task
def generate_jsonschema(context: Context) -> None:
    """Generate JSON schemas into ./schema"""
    with context.cd(ESCAPED_REPO_PATH):
        context.run("poetry run infrahub dev export-json-schema --out schema/openapi.json")


@task
def validate_graphqlschema(context: Context) -> None:
    """Validate that the generated GraphQL schema is up to date."""
    generate_graphqlschema(context)

    exec_cmd = "git diff --exit-code schema/schema.graphql"
    with context.cd(ESCAPED_REPO_PATH):
        context.run(exec_cmd)


@task
def validate_jsonschema(context: Context) -> None:
    """Validate that the generated JSON schema is up to date."""
    generate_jsonschema(context)

    exec_cmd = "git diff --exit-code schema/openapi.json"
    with context.cd(ESCAPED_REPO_PATH):
        context.run(exec_cmd)


def generate_sdk_repository_config() -> None:
    from infrahub_sdk.schema.repository import InfrahubRepositoryConfig

    repository_dir = SDK_DIRECTORY / "repository-config"
    repository_dir.mkdir(parents=True, exist_ok=True)
    schema = json.dumps(InfrahubRepositoryConfig.model_json_schema(), indent=4)

    write(file_path=repository_dir / "develop.json", content=schema)


def write(file_path: Path, content: str) -> None:
    file_path.write_text(content, encoding="utf-8")
    print(f"Wrote to {file_path}")
