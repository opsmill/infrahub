from graphql import graphql

from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.database import InfrahubDatabase
from infrahub.graphql import prepare_graphql_params


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
    gql_params = prepare_graphql_params(db=db, include_subscription=False, branch=default_branch)
    result = await graphql(
        schema=gql_params.schema,
        source=query,
        context_value=gql_params.context,
        root_value=None,
        variable_values={},
    )

    assert result.errors is None
    assert result.data["TestPersonDelete"]["ok"] is True

    assert not await NodeManager.get_one(db=db, id=obj1.id)


async def test_delete_prevented(
    db: InfrahubDatabase, default_branch, car_person_schema, car_camry_main, person_jane_main
):
    query = (
        """
    mutation {
        TestPersonDelete(data: {id: "%s"}) {
            ok
        }
    }
    """
        % person_jane_main.id
    )
    gql_params = prepare_graphql_params(db=db, include_subscription=False, branch=default_branch)
    result = await graphql(
        schema=gql_params.schema,
        source=query,
        context_value=gql_params.context,
        root_value=None,
        variable_values={},
    )

    assert result.errors
    assert len(result.errors) == 1
    assert "Cannot delete. Node is linked to mandatory relationship" in result.errors[0].message
    assert f"{car_camry_main.id} at TestCar.owner" in result.errors[0].message
    assert result.data["TestPersonDelete"] is None

    assert await NodeManager.get_one(db=db, id=person_jane_main.id) is not None
