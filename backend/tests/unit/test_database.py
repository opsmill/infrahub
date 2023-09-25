import pytest
from neo4j.exceptions import ClientError

import infrahub.config as config
from infrahub.database import InfrahubDatabase, validate_database


@pytest.fixture
async def dbs_for_test(db: InfrahubDatabase):
    databases = ["test41735", "test850e5"]
    default_db = db.session()
    await default_db.run(f"CREATE DATABASE {databases[0]} IF NOT EXISTS WAIT")

    yield databases

    # Delete both databases after the test
    default_db = db.session()
    for database in databases:
        await default_db.run(f"DROP DATABASE {database} IF EXISTS")


@pytest.mark.neo4j
async def test_validate_database(db: InfrahubDatabase, dbs_for_test):
    await validate_database(driver=db, database_name=config.SETTINGS.database.database, retry=2)

    with pytest.raises(ClientError):
        await validate_database(driver=db, database_name=dbs_for_test[1])


@pytest.mark.xfail(reason="DISABLING FOR A TEMP TEST")
async def test_database_transaction(empty_database, db: InfrahubDatabase):
    query1 = 'CREATE (b:Book {name: "book1"}) RETURN b'
    query2 = 'CREATE (b:Book {name: "book2"}) RETURN b'
    query3 = 'CREATE (b:Book "book1"}) RETURN b'

    query_books = "MATCH (b:Book) RETURN b "

    # First check that no books are present
    results = await db.execute_query(query=query_books)
    assert len(results) == 0

    # Try to create some books in the same transaction
    # All should fail since query3 is invalid
    with pytest.raises(ClientError):
        async with db.start_transaction() as dbt:
            for query in [query1, query2, query3]:
                await dbt.execute_query(query=query)

    results = await db.execute_query(query=query_books)
    assert len(results) == 0

    # Try again without the transaction and validate that 2 books are present
    with pytest.raises(ClientError):
        for query in [query1, query2, query3]:
            await db.execute_query(query=query)

    results = await db.execute_query(query=query_books)
    assert len(results) == 2
