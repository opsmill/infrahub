from graphql import graphql

from infrahub.core.manager import NodeManager
from infrahub.graphql import generate_graphql_schema


async def test_create_simple_object(db, session, default_branch, register_core_models_schema):
    query = """
    mutation {
        node_schema_create(data: {
            name: { value: "device"},
            kind: {value: "Device"}
        }
        ) {
            ok
            object {
                id
            }
        }
    }
    """

    result = await graphql(
        schema=await generate_graphql_schema(session=session, include_subscription=False, branch=default_branch),
        source=query,
        context_value={"infrahub_session": session, "infrahub_database": db, "infrahub_branch": default_branch},
        root_value=None,
        variable_values={},
    )

    assert result.errors is None
    assert result.data["node_schema_create"]["ok"] is True
    assert len(result.data["node_schema_create"]["object"]["id"]) == 36  # lenght of an UUID

    device_schema = await NodeManager.get_one(id=result.data["node_schema_create"]["object"]["id"], session=session)
    assert device_schema.branch.value is True
