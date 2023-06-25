import logging
import random
import time
from typing import List

from neo4j import AsyncDriver, AsyncSession

import infrahub.config as config
from infrahub.core import registry
from infrahub.core.node import Node
from infrahub.database import execute_write_query_async, get_db
from infrahub_client.batch import InfrahubBatch

# flake8: noqa
# pylint: skip-file


LOGGER = logging.getLogger("infrahub")

TAGS = [
    "black",
    "white",
    "red",
    "green",
    "yellow",
    "blue",
    "pink",
    "gray",
    "brown",
    "orange",
    "purple",
    "azure",
    "ivory",
    "teal",
    "silver",
    "maroon",
    "charcoal",
    "aquamarine",
    "coral",
    "fuchsia",
    "wheat",
    "lime",
    "crimson",
    "khaki",
    "magenta",
    "olden",
    "plum",
    "olive",
    "cyan",
]


BATCH_SIZE = 20

QUERY_START = ["MATCH (root:Root)"]
QUERY_MERGE = ["MERGE (bool_true:Boolean { value: true })", "MERGE (bool_false:Boolean { value: false })"]
QUERY_END = ["RETURN root"]


async def execute_query(db: AsyncDriver, query: List[str], deps: List[Node] = None):
    deps_query = []

    if deps:
        deps_query = [obj._query_bulk_get() for obj in deps]

    start_time = time.time()
    async with db.session(database=config.SETTINGS.database.database) as session:
        query_str = "\n".join(QUERY_START + deps_query + QUERY_MERGE + query + QUERY_END)
        result = await execute_write_query_async(session=session, query=query_str)
        duration = time.time() - start_time
        LOGGER.info(f"Executed query in {duration:.3f} sec")

    return result


async def load_data(
    session: AsyncSession,
    nbr_repository: int = 10,
    nbr_query: int = 1000,
    batch_size: int = 5,
    concurrent_execution: int = 1,
):
    """Generate a large number of GraphQLQuery associated with some Tags and some Repositories
    All the Tags and the repositories will be created at once but the GraphQLQuery will be created in batch.
    The size of the batch and the number of concurrent session can be controlled with "batch_size" and "concurrent_execution"
    """
    default_branch = await registry.get_branch(session=session)

    db = await get_db()

    start_time = time.time()

    tags = {}
    repository = {}
    gqlquery = {}

    tag_schema = registry.schema.get(name="Tag", branch=default_branch)
    repository_schema = registry.schema.get(name="Repository", branch=default_branch)
    gqlquery_schema = registry.schema.get(name="GraphQLQuery", branch=default_branch)

    # -------------------------------------------------------------------------------------
    # TAG
    # -------------------------------------------------------------------------------------
    query = []
    for tag in TAGS:
        obj = await Node.init(session=session, schema=tag_schema, branch=default_branch)
        await obj.new(session=session, name=tag)
        query.extend(obj._query_bulk_create())
        tags[tag] = obj

    LOGGER.info("Start Tag creation")
    await execute_query(db=db, query=query)

    # -------------------------------------------------------------------------------------
    # REPOSITORY
    # -------------------------------------------------------------------------------------
    query = []
    for idx in range(1, nbr_repository + 1):
        repo_name = f"repository-{idx:03}"
        obj = await Node.init(session=session, schema=repository_schema, branch=default_branch)
        random_tags = [tags[tag] for tag in random.choices(TAGS, k=3)]
        await obj.new(session=session, name=repo_name, location=f"git://{repo_name}", tags=random_tags)
        query.extend(obj._query_bulk_create())
        repository[repo_name] = obj

    LOGGER.info("Start Repository creation")
    await execute_query(db=db, query=query, deps=list(tags.values()))

    # -------------------------------------------------------------------------------------
    # GRAPHQL_QUERY
    # -------------------------------------------------------------------------------------
    batch = InfrahubBatch(max_concurrent_execution=concurrent_execution)

    nbr_tasks = int(nbr_query / batch_size)
    if nbr_query % batch_size:
        nbr_tasks += 1

    for batch_id in range(0, nbr_tasks):
        query = []
        ids = [
            idx + batch_id * batch_size for idx in range(1, batch_size + 1) if idx + batch_id * batch_size <= nbr_query
        ]

        random_tags = [tags[tag] for tag in random.choices(TAGS, k=3)]
        random_repo = repository[random.choice(list(repository.keys()))]

        for id in ids:
            name = f"query-{id:04}"
            query_str = "query Query%s { tag { name { value }}}" % f"{id:04}"
            obj = await Node.init(session=session, schema=gqlquery_schema, branch=default_branch)
            await obj.new(session=session, name=name, query=query_str, tags=random_tags, repository=random_repo)
            query.extend(obj._query_bulk_create())
            gqlquery[name] = obj

        LOGGER.info(f"Prepared batch {batch_id} IDS {ids[0]} - {ids[-1]} with {len(query)} lines of CYPHER")
        batch.add(task=execute_query, db=db, query=query, deps=random_tags + [random_repo])

    async for _, result in batch.execute():
        pass

    duration = time.time() - start_time
    LOGGER.info(f"Total Execution time script in {duration:.3f} sec")
