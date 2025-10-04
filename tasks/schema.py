import asyncio
import json
import re
from pathlib import Path
from typing import Match

from invoke.context import Context
from invoke.tasks import task

from .utils import ESCAPED_REPO_PATH, REPO_BASE

SDK_DIRECTORY = REPO_BASE / "generated" / "python-sdk"
INFRAHUB_DIRECTORY = REPO_BASE / "generated" / "infrahub"


@task
def generate_graphqlschema(context: Context) -> None:
    """Generate GraphQL schema into ./schema"""
    asyncio.run(generate_graphql_schema(context))


@task
def generate_jsonschema(context: Context) -> None:  # noqa: ARG001
    """Generate JSON schemas into ./generated"""

    generate_sdk_repository_config()
    generate_infrahub_node_schema()


@task
def validate_graphqlschema(context: Context) -> None:
    """Validate that the generated GraphQL schema is up to date."""

    asyncio.run(generate_graphql_schema(context))

    exec_cmd = "git diff --exit-code schema"
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


def sorted_schema(schema) -> str:  # noqa: ANN001
    from graphql import print_schema

    sdl = print_schema(schema)

    def sort_implements(match: Match[str]) -> str:
        interfaces = match.group(1).split("&")
        interfaces = [i.strip() for i in interfaces]
        interfaces.sort()
        return "implements " + " & ".join(interfaces)

    sdl = re.sub(r"implements (.*) {", lambda m: sort_implements(m) + " {", sdl)
    return sdl


async def generate_graphql_schema(context: Context) -> None:
    import neo4j.exceptions

    from infrahub import config
    from infrahub.core.initialization import initialization
    from infrahub.core.registry import registry
    from infrahub.database import InfrahubDatabase, get_db
    from infrahub.graphql.manager import GraphQLSchemaManager
    from infrahub.lock import initialize_lock
    from infrahub.services import InfrahubServices

    config.load_and_exit()
    initialize_lock(local_only=True)

    db_loading = True
    attempt = 1
    driver = None
    while db_loading:
        try:
            driver = await get_db()
            db_loading = False
        except neo4j.exceptions.ServiceUnavailable:
            if attempt > 9:
                raise
            await asyncio.sleep(delay=1)
            attempt += 1
    database = InfrahubDatabase(driver=driver)
    service = await InfrahubServices.new(database=database)

    async with service.database.start_session() as db:
        await initialization(db=db)

    schema_branch = registry.schema.get_schema_branch(name=registry.default_branch)

    gqlm = GraphQLSchemaManager(schema=schema_branch)
    gql_schema = gqlm.generate(
        include_query=True,
        include_mutation=True,
        include_subscription=True,
        include_types=True,
    )

    schema_file = Path(f"{REPO_BASE}/schema/schema.graphql")
    write(file_path=schema_file, content=sorted_schema(schema=gql_schema))

    with context.cd(f"{ESCAPED_REPO_PATH}/schema"):
        context.run("npm run format-graphql -- ./schema.graphql --write")
