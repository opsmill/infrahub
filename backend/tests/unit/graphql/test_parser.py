from graphql import graphql

from infrahub.core.branch import Branch
from infrahub.core.node import Node
from infrahub.database import InfrahubDatabase
from infrahub.graphql import prepare_graphql_params


async def test_simple_directive(db: InfrahubDatabase, default_branch: Branch, criticality_schema):
    obj1 = await Node.init(db=db, schema=criticality_schema)
    await obj1.new(db=db, name="low", level=4)
    await obj1.save(db=db)
    obj2 = await Node.init(db=db, schema=criticality_schema)
    await obj2.new(db=db, name="medium", level=3, description="My desc", color="#333333")
    await obj2.save(db=db)

    query = """
    query {
        TestCriticality {
            count
            edges {
                node @expand {
                    id
                }
            }
        }
    }
    """

    gql_params = prepare_graphql_params(
        db=db, include_mutation=False, include_subscription=False, branch=default_branch
    )
    result = await graphql(
        schema=gql_params.schema,
        source=query,
        context_value=gql_params.context,
        root_value=None,
        variable_values={},
    )

    assert result.errors is None
    assert result.data
    assert result.data["TestCriticality"]["count"] == 2
    assert len(result.data["TestCriticality"]["edges"]) == 2
    assert gql_params.context.related_node_ids == {obj1.id, obj2.id}
    assert {
        "node": {
            "id": obj1.id,
            "__typename": "TestCriticality",
            "name": {"value": "low"},
            "label": {"value": "Low"},
            "level": {"value": 4},
            "color": {"value": "#444444"},
            "mylist": {"value": ["one", "two"]},
            "is_true": {"value": True},
            "is_false": {"value": False},
            "json_no_default": {"value": None},
            "json_default": {"value": {"value": "bob"}},
            "description": {"value": None},
            "status": {"value": None},
        }
    } in result.data["TestCriticality"]["edges"]


async def test_directive_exclude(db: InfrahubDatabase, default_branch: Branch, criticality_schema):
    obj1 = await Node.init(db=db, schema=criticality_schema)
    await obj1.new(db=db, name="low", level=4)
    await obj1.save(db=db)
    obj2 = await Node.init(db=db, schema=criticality_schema)
    await obj2.new(db=db, name="medium", level=3, description="My desc", color="#333333")
    await obj2.save(db=db)

    query = """
    query {
        TestCriticality {
            count
            edges {
                node @expand(exclude: ["color", "mylist"]) {
                    id
                }
            }
        }
    }
    """

    gql_params = prepare_graphql_params(
        db=db, include_mutation=False, include_subscription=False, branch=default_branch
    )
    result = await graphql(
        schema=gql_params.schema,
        source=query,
        context_value=gql_params.context,
        root_value=None,
        variable_values={},
    )

    assert result.errors is None
    assert result.data
    assert result.data["TestCriticality"]["count"] == 2
    assert len(result.data["TestCriticality"]["edges"]) == 2
    assert gql_params.context.related_node_ids == {obj1.id, obj2.id}
    assert {
        "node": {
            "id": obj1.id,
            "__typename": "TestCriticality",
            "name": {"value": "low"},
            "label": {"value": "Low"},
            "level": {"value": 4},
            "is_true": {"value": True},
            "is_false": {"value": False},
            "json_no_default": {"value": None},
            "json_default": {"value": {"value": "bob"}},
            "description": {"value": None},
            "status": {"value": None},
        }
    } in result.data["TestCriticality"]["edges"]
