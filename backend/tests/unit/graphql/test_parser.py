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
                    level {
                        __typename
                    }
                    label {
                        value
                    }
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
            "level": {"value": 4, "__typename": "NumberAttribute"},
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


async def test_directive_merge_fields(
    db: InfrahubDatabase, default_branch: Branch, register_core_models_schema, person_tag_schema, first_account
):
    """This test validates that the @expand directive doesn't override the source field under username."""
    p1 = await Node.init(db=db, schema="TestPerson")
    await p1.new(db=db, firstname="John", lastname="Doe", _source=first_account)
    await p1.save(db=db)

    query = """
    query {
        TestPerson {
            edges {
                node @expand {
                    id
                    firstname {
                        source {
                            id
                        }
                    }
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
    assert len(result.data["TestPerson"]["edges"]) == 1
    assert result.data["TestPerson"]["edges"][0] == {
        "node": {
            "id": p1.id,
            "firstname": {"source": {"id": first_account.id}, "value": "John"},
            "__typename": "TestPerson",
            "lastname": {"value": "Doe"},
        }
    }
