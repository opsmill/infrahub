import pytest
from neo4j.exceptions import ClientError

import infrahub.config as config
from infrahub.database import validate_database


@pytest.fixture
async def dbs_for_test(db):
    databases = ["test41735", "test850e5"]
    default_db = db.session()
    await default_db.run(f"CREATE DATABASE {databases[0]} IF NOT EXISTS WAIT")

    yield databases

    # Delete both databases after the test
    default_db = db.session()
    for database in databases:
        await default_db.run(f"DROP DATABASE {database} IF EXISTS")


@pytest.mark.neo4j
async def test_validate_database(db, dbs_for_test):
    await validate_database(driver=db, database_name=config.SETTINGS.database.database, retry=2)

    with pytest.raises(ClientError):
        await validate_database(driver=db, database_name=dbs_for_test[1])
