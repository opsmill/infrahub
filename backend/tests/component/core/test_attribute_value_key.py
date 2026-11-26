import re
from dataclasses import dataclass
from typing import Any

from infrahub.core import registry
from infrahub.core.branch import Branch
from infrahub.core.constants import BranchSupportType, SchemaPathType
from infrahub.core.graph.schema import get_attribute_value_key
from infrahub.core.manager import NodeManager
from infrahub.core.migrations.query.attribute_add import AttributeAddQuery
from infrahub.core.migrations.schema.attribute_kind_update import (
    AttributeKindUpdateMigration,
    AttributeKindUpdateMigrationQuery,
)
from infrahub.core.migrations.shared import MigrationInput
from infrahub.core.node import Node
from infrahub.core.path import SchemaPath
from infrahub.core.query import Query
from infrahub.core.query.attribute import AttributeUpdateValueQuery
from infrahub.core.query.node import NodeCreateAllQuery
from infrahub.core.schema import NodeSchema
from infrahub.core.timestamp import Timestamp
from infrahub.database import InfrahubDatabase
from infrahub.database.validation import verify_graph
from tests.helpers.query_plan import explain_plan_operators

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


async def test_create_links_one_value_when_equal_keyed_values_are_duplicated(
    db: InfrahubDatabase, default_branch: Branch, all_attribute_types_schema: NodeSchema
) -> None:
    first = await _create(db=db, schema=all_attribute_types_schema, mytextarea="duplicated")
    # Concurrent writes can leave two equal values, and the upgrade then gives both the same key.
    await db.execute_query(
        query="""
        MATCH (:Node {uuid: $node_id})-[:HAS_ATTRIBUTE]->(:Attribute {name: "mytextarea"})-[:HAS_VALUE]->(av)
        CREATE (copy:AttributeValue)
        SET copy = properties(av)
        """,
        params={"node_id": first.id},
    )

    second = await _create(db=db, schema=all_attribute_types_schema, mytextarea="duplicated")

    await verify_graph(db=db)
    results = await db.execute_query(
        query="""
        MATCH (:Node {uuid: $node_id})-[:HAS_ATTRIBUTE]->(attr:Attribute {name: "mytextarea"})-[:HAS_VALUE]->(av)
        RETURN count(DISTINCT attr) AS attributes, count(av) AS values
        """,
        params={"node_id": second.id},
    )
    assert (results[0]["attributes"], results[0]["values"]) == (1, 1)

    fetched = await NodeManager.get_one(db=db, id=second.id, raise_on_error=True)
    assert fetched.get_attribute(name="mytextarea").value == "duplicated"


async def test_saving_an_unchanged_value_stored_before_a_memgraph_upgrade_keeps_it(
    db: InfrahubDatabase, default_branch: Branch, all_attribute_types_schema: NodeSchema
) -> None:
    node = await _create(db=db, schema=all_attribute_types_schema, mytextarea="stored before keys")
    # The upgrade keys the stored values only on Neo4j, so this state exists only on Memgraph.
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


# Reads through AttributeValueIndexed are left out, as indexed kinds find their values through that label's index.
VALUE_READ = re.compile(r":(AttributeValue\b\S*)")
KEY_SEEK = "NodeIndexSeek AttributeValue(value_key)"


def _value_reads(plan_operators: list[str], read_suffix: str) -> list[str]:
    reads = []
    for operator in plan_operators:
        operator_type, _, details = operator.partition(": ")
        operator_type = operator_type.removesuffix("@neo4j")
        if operator_type.endswith(read_suffix) and (match := VALUE_READ.search(details)):
            reads.append(f"{operator_type} {match.group(1)}")
    return reads


@dataclass
class _PlannedValueReads:
    # A scan of every vertex or of every attribute value costs as much as the database holds, whatever the write.
    full_scans: list[str]
    seeks: list[str]


async def _planned_value_reads(db: InfrahubDatabase, query: Query) -> _PlannedValueReads:
    plan_operators = await explain_plan_operators(db=db, query=query)
    every_vertex = [operator for operator in plan_operators if operator.startswith("AllNodesScan")]
    return _PlannedValueReads(
        full_scans=every_vertex + _value_reads(plan_operators=plan_operators, read_suffix="Scan"),
        seeks=_value_reads(plan_operators=plan_operators, read_suffix="Seek"),
    )


async def test_large_value_lookups_seek_the_key_index(
    db: InfrahubDatabase, default_branch: Branch, all_attribute_types_schema: NodeSchema
) -> None:
    node = await _create(db=db, schema=all_attribute_types_schema, mystring="indexed", mytextarea="stored")

    new_node = await Node.init(db=db, schema=all_attribute_types_schema)
    await new_node.new(db=db, mytextarea="created", myjson={"value": {"id": "created"}})
    create_query = await NodeCreateAllQuery.init(db=db, node=new_node, at=Timestamp())

    textarea = node.get_attribute(name="mytextarea")
    textarea.value = "updated"
    update_query = await AttributeUpdateValueQuery.init(db=db, attr=textarea)

    add_query = await AttributeAddQuery.init(
        db=db,
        branch=default_branch,
        node_kinds=[all_attribute_types_schema.kind],
        attribute_name="added",
        attribute_kind="TextArea",
        branch_support=BranchSupportType.AWARE.value,
        default_value="added value",
    )

    schema = registry.schema.get_schema_branch(name=default_branch.name)
    new_schema = schema.duplicate().get(name=all_attribute_types_schema.kind)
    new_schema.get_attribute(name="mystring").kind = "TextArea"
    migration = AttributeKindUpdateMigration(
        previous_node_schema=schema.get(name=all_attribute_types_schema.kind),
        new_node_schema=new_schema,
        schema_path=SchemaPath(
            path_type=SchemaPathType.ATTRIBUTE, schema_kind=all_attribute_types_schema.kind, field_name="mystring"
        ),
    )
    kind_query = await migration.build_query(
        migration_query=AttributeKindUpdateMigrationQuery, migration_input=MigrationInput(db=db), branch=default_branch
    )

    one_seek = _PlannedValueReads(full_scans=[], seeks=[KEY_SEEK])
    assert await _planned_value_reads(db=db, query=create_query) == one_seek
    assert await _planned_value_reads(db=db, query=update_query) == one_seek
    assert await _planned_value_reads(db=db, query=add_query) == one_seek
    # One lookup creates the missing values, the second links each attribute to its value.
    assert await _planned_value_reads(db=db, query=kind_query) == _PlannedValueReads(
        full_scans=[], seeks=[KEY_SEEK, KEY_SEEK]
    )
