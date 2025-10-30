from invoke.context import Context
from invoke.tasks import task

from .utils import ESCAPED_REPO_PATH, REPO_BASE

SDK_DIRECTORY = REPO_BASE / "generated" / "python-sdk"
REPOSITORY_CONFIG_DIRECTORY = SDK_DIRECTORY / "repository-config"
REPOSITORY_CONFIG_PATH = REPOSITORY_CONFIG_DIRECTORY / "develop.json"
SCHEMA_PATH = REPO_BASE / "schema" / "schema.graphql"
OPENAPI_PATH = REPO_BASE / "schema" / "openapi.json"


@task
def generate_graphqlschema(context: Context) -> None:
    """Generate GraphQL schema into ./schema"""
    with context.cd(ESCAPED_REPO_PATH):
        context.run(f"poetry run infrahub dev export-graphql-schema --out {SCHEMA_PATH}")


@task
def generate_jsonschema(context: Context) -> None:
    """Generate JSON schemas into ./schema"""
    with context.cd(ESCAPED_REPO_PATH):
        context.run(f"poetry run infrahub dev export-json-schema --out {OPENAPI_PATH}")


@task
def generate_repositoryconfig(context: Context) -> None:
    """Generate repository config into generated/python-sdk/repository-config/develop.json"""
    with context.cd(ESCAPED_REPO_PATH):
        context.run(f"poetry run infrahub dev export-repository-config --out {REPOSITORY_CONFIG_PATH}")


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
