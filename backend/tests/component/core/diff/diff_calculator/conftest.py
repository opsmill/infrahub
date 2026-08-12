from collections.abc import Generator

import pytest

from infrahub import config
from infrahub.constants.database import Neo4jRuntime
from infrahub.database import InfrahubDatabase


@pytest.fixture(autouse=True)
def parallel_runtime(db: InfrahubDatabase) -> Generator[None, None, None]:
    original = db.default_neo4j_runtime
    db.default_neo4j_runtime = Neo4jRuntime.PARALLEL

    yield

    db.default_neo4j_runtime = original


@pytest.fixture(autouse=True, scope="module")
def low_query_size_limit() -> Generator[None, None, None]:
    original = config.SETTINGS.database.query_size_limit
    config.SETTINGS.database.query_size_limit = 5

    yield

    config.SETTINGS.database.query_size_limit = original
