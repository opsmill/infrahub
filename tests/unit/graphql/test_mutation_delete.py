import graphene
import pytest
from graphql import graphql

from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.graphql import get_gql_mutation, get_gql_query


async def test_delete_object(db, session, default_branch, car_person_schema):

    obj1 = await Node.init(session=session, schema="Person")
    await obj1.new(session=session, name="John", height=180)
    await obj1.save(session=session)
    obj2 = await Node.init(session=session, schema="Person")
    await obj2.new(session=session, name="Jim", height=160)
    await obj2.save(session=session)
    obj3 = await Node.init(session=session, schema="Person")
    await obj3.new(session=session, name="Joe", height=170)
    await obj3.save(session=session)

    query = (
        """
    mutation {
        person_delete(data: {id: "%s"}) {
            ok
        }
    }
    """
        % obj1.id
    )
    result = await graphql(
        graphene.Schema(
            query=await get_gql_query(session=session),
            mutation=await get_gql_mutation(session=session),
            auto_camelcase=False,
        ).graphql_schema,
        source=query,
        context_value={"infrahub_session": session, "infrahub_database": db},
        root_value=None,
        variable_values={},
    )

    assert result.errors is None
    assert result.data["person_delete"]["ok"] is True

    assert not await NodeManager.get_one(session=session, id=obj1.id)
