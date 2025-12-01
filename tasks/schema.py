import json

from invoke.context import Context
from invoke.tasks import task

from .utils import ESCAPED_REPO_PATH, REPO_BASE

SDK_DIRECTORY = REPO_BASE / "generated" / "python-sdk"
INFRAHUB_DIRECTORY = REPO_BASE / "generated" / "infrahub"

REPOSITORY_CONFIG_DIRECTORY = SDK_DIRECTORY / "repository-config"
INFRAHUB_SCHEMA_DIRECTORY = INFRAHUB_DIRECTORY / "schema"

REPOSITORY_CONFIG_PATH = REPOSITORY_CONFIG_DIRECTORY / "develop.json"
INFRAHUB_NODE_SCHEMA_PATH = INFRAHUB_SCHEMA_DIRECTORY / "develop.json"

SCHEMA_PATH = REPO_BASE / "schema" / "schema.graphql"
OPENAPI_PATH = REPO_BASE / "schema" / "openapi.json"


@task
def generate_graphqlschema(context: Context) -> None:
    """Generate GraphQL schema into ./schema"""
    with context.cd(ESCAPED_REPO_PATH):
        context.run(f"uv run infrahub dev export-graphql-schema --out {SCHEMA_PATH}")
        print(f"Wrote to {SCHEMA_PATH}")


@task
def generate_jsonschema(context: Context) -> None:
    """Generate JSON schemas into ./schema and also run `generate_repositoryconfig`"""
    with context.cd(ESCAPED_REPO_PATH):
        context.run(f"uv run infrahub dev export-json-schema --out {OPENAPI_PATH}")
        print(f"Wrote to {OPENAPI_PATH}")

    generate_repositoryconfig(context)
    generate_infrahubnodeschema(context)


@task
def generate_repositoryconfig(context: Context) -> None:
    """Generate repository config into generated/python-sdk/repository-config/develop.json"""
    from infrahub_sdk.schema.repository import InfrahubRepositoryConfig

    with context.cd(ESCAPED_REPO_PATH):
        schema = json.dumps(InfrahubRepositoryConfig.model_json_schema(), indent=4)
        REPOSITORY_CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
        REPOSITORY_CONFIG_PATH.write_text(schema)
        print(f"Wrote to {REPOSITORY_CONFIG_PATH}")


@task
def generate_infrahubnodeschema(context: Context) -> None:
    """Generate infrahub node schema into generated/infrahub/schema/develop.json"""
    with context.cd(ESCAPED_REPO_PATH):
        context.run(f"uv run infrahub dev export-node-schema --out {INFRAHUB_NODE_SCHEMA_PATH}")
        print(f"Wrote to {INFRAHUB_NODE_SCHEMA_PATH}")


@task
def validate_graphqlschema(context: Context) -> None:
    """Validate that the generated GraphQL schema is up to date."""
    generate_graphqlschema(context)

    exec_cmd = f"git diff --exit-code {SCHEMA_PATH}"
    with context.cd(ESCAPED_REPO_PATH):
        context.run(exec_cmd)


@task
def validate_jsonschema(context: Context) -> None:
    """Validate that the generated JSON schema is up to date."""
    generate_jsonschema(context)

    exec_cmd = f"git diff --exit-code {OPENAPI_PATH}"
    with context.cd(ESCAPED_REPO_PATH):
        context.run(exec_cmd)
