import pytest
from graphql import graphql

from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.database import InfrahubDatabase
from infrahub.graphql import generate_graphql_schema


@pytest.fixture(autouse=True)
def load_graphql_requirements(group_graphql):
    pass


async def test_delete_object(db: InfrahubDatabase, default_branch, car_person_schema):
    obj1 = await Node.init(db=db, schema="TestPerson")
    await obj1.new(db=db, name="John", height=180)
    await obj1.save(db=db)
    obj2 = await Node.init(db=db, schema="TestPerson")
    await obj2.new(db=db, name="Jim", height=160)
    await obj2.save(db=db)
    obj3 = await Node.init(db=db, schema="TestPerson")
    await obj3.new(db=db, name="Joe", height=170)
    await obj3.save(db=db)

    query = (
        """
    mutation {
        TestPersonDelete(data: {id: "%s"}) {
            ok
        }
    }
    """
        % obj1.id
    )
    result = await graphql(
        schema=await generate_graphql_schema(db=db, include_subscription=False, branch=default_branch),
        source=query,
        context_value={"infrahub_database": db},
        root_value=None,
        variable_values={},
    )

    assert result.errors is None
    assert result.data["TestPersonDelete"]["ok"] is True

    assert not await NodeManager.get_one(db=db, id=obj1.id)
