"""Fixtures for the branch-agnostic repair migration.

No current code path produces the shapes under test, so they are built with raw Cypher and read back
edge by edge rather than through the node manager, which would hide the states being pinned down.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import pytest
from rich.console import Console

from infrahub.core import registry
from infrahub.core.constants import GLOBAL_BRANCH_NAME
from infrahub.core.migrations.graph.m077_retire_agnostic_property_edges import Migration077
from infrahub.core.migrations.shared import MigrationInput, MigrationResult
from tests.helpers.schema.agnostic_retirement import AGNOSTIC_RETIREMENT_SCHEMA

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.core.timestamp import Timestamp
    from infrahub.database import InfrahubDatabase


@dataclass(frozen=True)
class MigrationRun:
    """One run of the repair migration, with the console output it produced."""

    result: MigrationResult

    output: str
    """Everything the migration logged, so the reported counts can be asserted on."""

    at: Timestamp
    """The run's own time, which a close falls back to when the graph records no other."""


@pytest.fixture
async def agnostic_schema(db: InfrahubDatabase, default_branch: Branch) -> None:
    registry.schema.register_schema(schema=AGNOSTIC_RETIREMENT_SCHEMA, branch=default_branch.name)


async def run_migration(db: InfrahubDatabase) -> MigrationRun:
    console = Console(record=True, width=250)
    migration = Migration077()
    migration_input = MigrationInput(db=db, console=console)
    result = await migration.execute(migration_input=migration_input)
    validation = await migration.validate_migration(db=db)
    assert not validation.errors
    return MigrationRun(result=result, output=console.export_text(), at=migration_input.at)


async def detach_node_vertices(db: InfrahubDatabase, node_ids: list[str]) -> None:
    """Remove the node vertices outright, leaving their field vertices pointing at nothing.

    This is what a branch deletion predating the agnostic-peer cleanup left behind.
    """
    await db.execute_query(
        query="MATCH (n:Node) WHERE n.uuid IN $node_ids DETACH DELETE n",
        params={"node_ids": node_ids},
    )


async def detached_field_uuids(db: InfrahubDatabase) -> set[str]:
    """The uuids of every attribute and relationship vertex with no linked node vertex."""
    results = await db.execute_query(
        query="""
        MATCH (field:Attribute|Relationship)
        WHERE NOT EXISTS { MATCH (:Node)-[:HAS_ATTRIBUTE|IS_RELATED]-(field) }
        RETURN field.uuid AS uuid
        """,
    )
    return {result["uuid"] for result in results}


async def field_vertex_exists(db: InfrahubDatabase, vertex_uuid: str) -> bool:
    results = await db.execute_query(
        query="""
        MATCH (field:Attribute|Relationship {uuid: $vertex_uuid})
        RETURN count(field) AS vertex_count
        """,
        params={"vertex_uuid": vertex_uuid},
    )
    return results[0]["vertex_count"] > 0


async def attribute_value_count(db: InfrahubDatabase) -> int:
    results = await db.execute_query(query="MATCH (v:AttributeValue) RETURN count(v) AS value_count")
    return results[0]["value_count"]


async def close_global_owning_edge(db: InfrahubDatabase, field_uuid: str, at: Timestamp) -> None:
    """Close the field vertex's open global owning edge, leaving its property edges untouched.

    Object deletion used to leave exactly this shape behind.
    """
    results = await db.execute_query(
        query="""
        MATCH (:Node)-[owning:HAS_ATTRIBUTE|IS_RELATED]-(field:Attribute|Relationship {uuid: $field_uuid})
        WHERE owning.branch = $global_branch
          AND owning.status = "active"
          AND owning.to IS NULL
        SET owning.to = $at
        RETURN count(owning) AS closed
        """,
        params={"field_uuid": field_uuid, "global_branch": GLOBAL_BRANCH_NAME, "at": at.to_string()},
    )
    assert results[0]["closed"] > 0


async def close_global_property_edges(db: InfrahubDatabase, field_uuid: str, at: Timestamp) -> None:
    """Close every open global edge of the field vertex except its owning edges."""
    results = await db.execute_query(
        query="""
        MATCH (field {uuid: $field_uuid})-[property_edge]-()
        WHERE (field:Attribute|Relationship)
          AND NOT type(property_edge) IN ["HAS_ATTRIBUTE", "IS_RELATED"]
          AND property_edge.branch = $global_branch
          AND property_edge.status = "active"
          AND property_edge.to IS NULL
        SET property_edge.to = $at
        RETURN count(property_edge) AS closed
        """,
        params={"field_uuid": field_uuid, "global_branch": GLOBAL_BRANCH_NAME, "at": at.to_string()},
    )
    assert results[0]["closed"] > 0


async def close_one_relationship_arm(db: InfrahubDatabase, field_uuid: str, peer_id: str, at: Timestamp) -> None:
    """Close the global `IS_RELATED` edge reaching one peer, leaving the other arm open.

    A kind-update migration leaves this shape behind: one arm closed as the peer vertex is
    superseded, the other still open.
    """
    results = await db.execute_query(
        query="""
        MATCH (:Node {uuid: $peer_id})-[arm:IS_RELATED]-(field:Relationship {uuid: $field_uuid})
        WHERE arm.branch = $global_branch
          AND arm.status = "active"
          AND arm.to IS NULL
        SET arm.to = $at
        RETURN count(arm) AS closed
        """,
        params={
            "field_uuid": field_uuid,
            "peer_id": peer_id,
            "global_branch": GLOBAL_BRANCH_NAME,
            "at": at.to_string(),
        },
    )
    assert results[0]["closed"] == 1


async def remove_existence_edges(db: InfrahubDatabase, node_id: str) -> None:
    """Strip the node's existence edges outright, leaving the node vertex and its fields in place.

    Nothing then records when its fields stopped being readable, so no retirement time is derivable
    for them.
    """
    results = await db.execute_query(
        query="""
        MATCH (:Node {uuid: $node_id})-[existence:IS_PART_OF]->(:Root)
        DELETE existence
        RETURN count(existence) AS removed
        """,
        params={"node_id": node_id},
    )
    assert results[0]["removed"] > 0


async def value_vertex_ids(db: InfrahubDatabase, node_id: str, attribute_name: str) -> set[str]:
    """The internal identities of the value vertices the node's attribute points at.

    Internal identity rather than a property, so two attributes carrying equal values are only
    reported as sharing when they genuinely point at one vertex.
    """
    results = await db.execute_query(
        query="""
        MATCH (:Node {uuid: $node_id})-[:HAS_ATTRIBUTE]->(a:Attribute {name: $attribute_name})
        MATCH (a)-[:HAS_VALUE]->(value:AttributeValue)
        RETURN DISTINCT elementId(value) AS value_id
        """,
        params={"node_id": node_id, "attribute_name": attribute_name},
    )
    return {result["value_id"] for result in results}


async def duplicate_node_vertex(db: InfrahubDatabase, node_id: str, at: Timestamp) -> None:
    """Copy the node vertex the way a kind or inheritance change does, leaving two vertices on one uuid.

    The copy takes over every active outbound edge and the original keeps a `deleted` mirror of each,
    so the field vertices end up shared between a stale owner and the live one that supersedes it.
    """
    results = await db.execute_query(
        query="""
        MATCH (original:Node {uuid: $node_id})
        WITH original LIMIT 1
        CREATE (copy:Node)
        SET copy = properties(original)
        SET copy:$(labels(original))
        WITH original, copy
        CALL (original, copy) {
            MATCH (original)-[edge]->(peer)
            WHERE edge.status = "active" AND edge.to IS NULL
            CREATE (copy)-[copied_edge:$(type(edge))]->(peer)
            SET copied_edge = properties(edge)
            SET copied_edge.from = $at
            CREATE (original)-[superseded_edge:$(type(edge))]->(peer)
            SET superseded_edge = properties(edge)
            SET superseded_edge.from = $at
            SET superseded_edge.status = "deleted"
            RETURN count(edge) AS copied_count
        }
        RETURN copied_count
        """,
        params={"node_id": node_id, "at": at.to_string()},
    )
    assert results[0]["copied_count"] > 0
