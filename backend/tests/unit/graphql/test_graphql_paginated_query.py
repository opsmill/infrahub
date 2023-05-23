from graphql import graphql

from infrahub.core import registry
from infrahub.core.branch import Branch
from infrahub.core.node import Node
from infrahub.core.schema import NodeSchema
from infrahub.graphql import generate_graphql_paginated_schema


async def test_simple_query(db, session, default_branch: Branch, criticality_schema):
    obj1 = await Node.init(session=session, schema=criticality_schema)
    await obj1.new(session=session, name="low", level=4)
    await obj1.save(session=session)
    obj2 = await Node.init(session=session, schema=criticality_schema)
    await obj2.new(session=session, name="medium", level=3, description="My desc", color="#333333")
    await obj2.save(session=session)

    query = """
    query {
        criticality {
            count
            edges {
                node {
                    name {
                        value
                     }
                }
            }
        }
    }
    """
    result = await graphql(
        await generate_graphql_paginated_schema(
            session=session, include_mutation=False, include_subscription=False, branch=default_branch
        ),
        source=query,
        context_value={"infrahub_session": session, "infrahub_database": db, "infrahub_branch": default_branch},
        root_value=None,
        variable_values={},
    )

    assert result.errors is None
    assert result.data["criticality"]["count"] == 2
    assert len(result.data["criticality"]["edges"]) == 2


async def test_simple_query_with_offset_and_limit(db, session, default_branch: Branch, criticality_schema):
    obj1 = await Node.init(session=session, schema=criticality_schema)
    await obj1.new(session=session, name="low", level=4)
    await obj1.save(session=session)
    obj2 = await Node.init(session=session, schema=criticality_schema)
    await obj2.new(session=session, name="medium", level=3, description="My desc", color="#333333")
    await obj2.save(session=session)

    query = """
    query {
        criticality(offset: 0, limit:1) {
            count
            edges {
                node {
                    name {
                        value
                     }
                }
            }
        }
    }
    """
    result = await graphql(
        await generate_graphql_paginated_schema(
            session=session, include_mutation=False, include_subscription=False, branch=default_branch
        ),
        source=query,
        context_value={"infrahub_session": session, "infrahub_database": db, "infrahub_branch": default_branch},
        root_value=None,
        variable_values={},
    )

    assert result.errors is None
    assert result.data["criticality"]["count"] == 2
    assert len(result.data["criticality"]["edges"]) == 1


async def test_display_label_one_item(db, session, default_branch: Branch, data_schema):
    SCHEMA = {
        "name": "criticality",
        "kind": "Criticality",
        "display_labels": ["label__value"],
        "branch": True,
        "attributes": [
            {"name": "name", "kind": "Text", "unique": True},
            {"name": "label", "kind": "Text", "optional": True},
        ],
    }

    schema = NodeSchema(**SCHEMA)
    registry.set_schema(name=schema.kind, schema=schema)

    obj1 = await Node.init(session=session, schema=schema)
    await obj1.new(session=session, name="low")
    await obj1.save(session=session)

    query = """
    query {
        criticality {
            edges {
                node {
                    id
                    display_label
                }
            }
        }
    }
    """
    result = await graphql(
        await generate_graphql_paginated_schema(
            branch=default_branch, session=session, include_mutation=False, include_subscription=False
        ),
        source=query,
        context_value={"infrahub_session": session, "infrahub_database": db, "infrahub_branch": default_branch},
        root_value=None,
        variable_values={},
    )

    assert result.errors is None
    assert len(result.data["criticality"]["edges"]) == 1
    assert result.data["criticality"]["edges"][0]["node"]["display_label"] == "Low"
