import asyncio
from pathlib import Path

from invoke.context import Context
from invoke.tasks import task

from .utils import ESCAPED_REPO_PATH, REPO_BASE

SDK_DIRECTORY = f"{REPO_BASE}/generated/python-sdk"
INFRAHUB_DIRECTORY = f"{REPO_BASE}/generated/python-sdk"


@task
def generate_graphqlschema(context: Context):
    """Generate GraphQL schema into ./schema"""
    asyncio.run(generate_graphql_schema())


@task
def generate_jsonschema(context: Context):
    """Generate JSON schemas into ./generated"""

    generate_sdk_repository_config()


@task
def validate_graphqlschema(context: Context):
    """Validate that the generated GraphQL schema is up to date."""

    asyncio.run(generate_graphql_schema())

    exec_cmd = "git diff --exit-code schema"
    with context.cd(ESCAPED_REPO_PATH):
        context.run(exec_cmd)


def generate_sdk_repository_config():
    from infrahub_sdk.schema import InfrahubRepositoryConfig

    repository_dir = f"{SDK_DIRECTORY}/repository-config"
    Path(repository_dir).mkdir(parents=True, exist_ok=True)
    schema = InfrahubRepositoryConfig.schema_json(indent=4)

    write(filename=f"{repository_dir}/develop.json", content=schema)


def write(filename: str, content: str) -> None:
    with open(filename, "w", encoding="utf-8") as fobj:
        fobj.write(content)
    print(f"Wrote to {filename}")


async def generate_graphql_schema() -> None:
    import neo4j.exceptions
    from graphql import print_schema

    from infrahub import config
    from infrahub.core.initialization import initialization
    from infrahub.core.registry import registry
    from infrahub.database import InfrahubDatabase, get_db
    from infrahub.lock import initialize_lock
    from infrahub.services import InfrahubServices

    config.load_and_exit()
    initialize_lock(local_only=True)

    db_loading = True
    attempt = 1
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
    service = InfrahubServices(
        database=database,
    )
    await service.initialize()

    async with service.database.start_session() as db:
        await initialization(db=db)

    schema = registry.schema.get_schema_branch(name=registry.default_branch)
    gql_schema = schema.get_graphql_schema()

    schema_file = f"{REPO_BASE}/schema/schema.graphql"
    write(filename=schema_file, content=print_schema(schema=gql_schema))
