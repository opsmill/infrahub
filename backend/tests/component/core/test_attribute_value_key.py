from typing import Any

from infrahub.core.branch import Branch
from infrahub.core.graph.schema import get_attribute_value_key
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.core.schema import NodeSchema
from infrahub.database import InfrahubDatabase

VALUE_VERTICES_QUERY = """
MATCH (:Node {uuid: $node_id})-[:HAS_ATTRIBUTE]->(:Attribute {name: $attr_name})-[r:HAS_VALUE]->(av:AttributeValue)
RETURN elementId(av) AS value_id, av.value_key AS value_key, "AttributeValueIndexed" IN labels(av) AS is_indexed
ORDER BY r.from DESC
"""

# Larger than the 8167 bytes a RANGE index entry can hold.
VALUE_TOO_LARGE_TO_INDEX = "a" * 10_000


async def _value_vertices(db: InfrahubDatabase, node_id: str, attr_name: str) -> list[dict[str, Any]]:
    results = await db.execute_query(query=VALUE_VERTICES_QUERY, params={"node_id": node_id, "attr_name": attr_name})
    return [
        {"value_id": result["value_id"], "value_key": result["value_key"], "is_indexed": result["is_indexed"]}
        for result in results
    ]


async def _create(db: InfrahubDatabase, schema: NodeSchema, **values: Any) -> Node:
    node = await Node.init(db=db, schema=schema)
    await node.new(db=db, **values)
    await node.save(db=db)
    return node


async def test_equal_large_values_share_one_keyed_vertex(
    db: InfrahubDatabase, default_branch: Branch, all_attribute_types_schema: NodeSchema
) -> None:
    first = await _create(
        db=db,
        schema=all_attribute_types_schema,
        mytextarea=VALUE_TOO_LARGE_TO_INDEX,
        myjson={"value": {"id": "one"}},
        mystring="indexed",
    )
    second = await _create(
        db=db,
        schema=all_attribute_types_schema,
        mytextarea=VALUE_TOO_LARGE_TO_INDEX,
        myjson={"value": {"id": "one"}},
        mystring="indexed",
    )

    for attr_name, serialized in (("mytextarea", VALUE_TOO_LARGE_TO_INDEX), ("myjson", '{"id":"one"}')):
        first_values = await _value_vertices(db=db, node_id=first.id, attr_name=attr_name)
        second_values = await _value_vertices(db=db, node_id=second.id, attr_name=attr_name)
        assert first_values == second_values
        assert first_values == [
            {
                "value_id": first_values[0]["value_id"],
                "value_key": get_attribute_value_key(serialized),
                "is_indexed": False,
            }
        ]

    indexed_values = await _value_vertices(db=db, node_id=first.id, attr_name="mystring")
    assert indexed_values[0]["is_indexed"] is True
    assert indexed_values[0]["value_key"] is None

    fetched = await NodeManager.get_one(db=db, id=second.id, raise_on_error=True)
    assert fetched.get_attribute(name="mytextarea").value == VALUE_TOO_LARGE_TO_INDEX


async def test_update_reuses_the_keyed_vertex_of_an_equal_value(
    db: InfrahubDatabase, default_branch: Branch, all_attribute_types_schema: NodeSchema
) -> None:
    first = await _create(db=db, schema=all_attribute_types_schema, myjson={"value": {"id": "shared"}})
    second = await _create(db=db, schema=all_attribute_types_schema, myjson={"value": {"id": "other"}})

    second.get_attribute(name="myjson").value = {"id": "shared"}
    await second.save(db=db)

    first_values = await _value_vertices(db=db, node_id=first.id, attr_name="myjson")
    second_values = await _value_vertices(db=db, node_id=second.id, attr_name="myjson")
    assert second_values[0] == first_values[0]
    assert second_values[0]["value_key"] == get_attribute_value_key('{"id":"shared"}')


async def test_saving_an_unchanged_value_stored_without_key_keeps_it(
    db: InfrahubDatabase, default_branch: Branch, all_attribute_types_schema: NodeSchema
) -> None:
    node = await _create(db=db, schema=all_attribute_types_schema, mytextarea="stored before keys")
    await db.execute_query(
        query="""
        MATCH (:Node {uuid: $node_id})-[:HAS_ATTRIBUTE]->(:Attribute {name: "mytextarea"})-[:HAS_VALUE]->(av)
        REMOVE av.value_key
        """,
        params={"node_id": node.id},
    )

    fetched = await NodeManager.get_one(db=db, id=node.id, raise_on_error=True)
    await fetched.save(db=db)

    values = await _value_vertices(db=db, node_id=node.id, attr_name="mytextarea")
    assert len(values) == 1
    assert values[0]["value_key"] is None
