"""A conversion moves the pool's IS_RESERVED edge onto the object that replaces the converted one."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from infrahub_sdk.convert_object_type import ConversionFieldInput

from infrahub.core import registry
from infrahub.core.constants import GLOBAL_BRANCH_NAME, InfrahubKind
from infrahub.core.convert_object_type.object_conversion import convert_object_type
from infrahub.core.initialization import create_branch
from infrahub.core.node import Node
from infrahub.core.node.resource_manager.number_pool import CoreNumberPool
from infrahub.core.query.resource_manager import PoolRecordProvenance
from infrahub.core.schema import AttributeSchema, GenericSchema, NodeSchema, SchemaRoot
from tests.helpers.agnostic_edges import (
    active_is_reserved_edges_on,
    open_is_reserved_edge_on,
    set_open_is_reserved_edge_provenance,
)
from tests.helpers.schema import load_schema

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.core.schema.schema_branch import SchemaBranch
    from infrahub.database import InfrahubDatabase

POOL_START = 1
POOL_END = 10
TRACKED_ATTRIBUTE_NAME = "ticket_id"

GENERIC_KIND = "TestingConvertbase"
SOURCE_KIND = "TestingConvertsource"
TARGET_KIND = "TestingConverttarget"

# The pool tracks the generic, so a conversion between the two kinds stays inside its scope.
CONVERT_BASE = GenericSchema(
    name="Convertbase",
    namespace="Testing",
    attributes=[
        AttributeSchema(name="title", kind="Text", optional=False),
        AttributeSchema(name=TRACKED_ATTRIBUTE_NAME, kind="Number", optional=True, unique=True),
    ],
)

CONVERT_SOURCE = NodeSchema(name="Convertsource", namespace="Testing", inherit_from=[GENERIC_KIND])

CONVERT_TARGET = NodeSchema(name="Converttarget", namespace="Testing", inherit_from=[GENERIC_KIND])

OUTSIDER_KIND = "TestingConvertoutsider"

# Carries the tracked attribute by name but inherits nothing, so the pool has no claim on it.
CONVERT_OUTSIDER = NodeSchema(
    name="Convertoutsider",
    namespace="Testing",
    attributes=[
        AttributeSchema(name="title", kind="Text", optional=False),
        AttributeSchema(name=TRACKED_ATTRIBUTE_NAME, kind="Number", optional=True),
    ],
)


@pytest.fixture
async def convert_pool(
    db: InfrahubDatabase, default_branch: Branch, register_core_models_schema: SchemaBranch
) -> CoreNumberPool:
    await load_schema(
        db=db,
        schema=SchemaRoot(generics=[CONVERT_BASE], nodes=[CONVERT_SOURCE, CONVERT_TARGET, CONVERT_OUTSIDER]),
    )
    registry.node[InfrahubKind.NUMBERPOOL] = CoreNumberPool
    pool = await CoreNumberPool.init(db=db, schema=InfrahubKind.NUMBERPOOL)
    await pool.new(
        db=db,
        name="convert-pool",
        node=GENERIC_KIND,
        node_attribute=TRACKED_ATTRIBUTE_NAME,
        start_range=POOL_START,
        end_range=POOL_END,
    )
    await pool.save(db=db)
    return pool


async def holder_holding_a_pooled_number(db: InfrahubDatabase, branch: Branch, pool: CoreNumberPool) -> Node:
    """An object of the tracked kind, holding a number the pool allocated and accounts for."""
    holder = await Node.init(db=db, schema=SOURCE_KIND, branch=branch)
    await holder.new(db=db, title="holder", ticket_id={"from_pool": {"id": pool.id}})
    await holder.save(db=db)
    return holder


async def convert_to(db: InfrahubDatabase, branch: Branch, node: Node, target_kind: str) -> Node:
    """Convert carrying the tracked attribute across as a plain value, so nothing re-allocates."""
    return await convert_object_type(
        node=node,
        target_schema=registry.schema.get_node_schema(name=target_kind, branch=branch),
        mapping={
            "title": ConversionFieldInput(source_field="title"),
            TRACKED_ATTRIBUTE_NAME: ConversionFieldInput(source_field=TRACKED_ATTRIBUTE_NAME),
        },
        branch=branch,
        db=db,
    )


async def test_converting_an_object_carries_its_is_reserved_edge_onto_the_replacement_intact(
    db: InfrahubDatabase, default_branch: Branch, convert_pool: CoreNumberPool
) -> None:
    """The pool keeps accounting for the number, through an IS_RESERVED edge that says what it said before.

    The IS_RESERVED edge's provenance is preserved.
    """
    holder = await holder_holding_a_pooled_number(db=db, branch=default_branch, pool=convert_pool)
    allocated = holder.get_attribute(TRACKED_ATTRIBUTE_NAME).value
    assert allocated == POOL_START
    assert await convert_pool.get_used(db=db, branch=default_branch) == [allocated]

    await set_open_is_reserved_edge_provenance(
        db=db,
        node_id=holder.get_id(),
        attribute_name=TRACKED_ATTRIBUTE_NAME,
        provenance=PoolRecordProvenance.PROVIDED.value,
    )

    converted = await convert_to(db=db, branch=default_branch, node=holder, target_kind=TARGET_KIND)

    assert converted.get_id() != holder.get_id()
    assert converted.get_attribute(TRACKED_ATTRIBUTE_NAME).value == allocated, (
        "the conversion carries the number across"
    )
    assert await convert_pool.get_used(db=db, branch=default_branch) == [allocated], (
        "the pool must still account for the number, now on the object the conversion produced"
    )
    assert await convert_pool.get_free(db=db, branch=default_branch) != allocated, (
        "a number an object still holds must never be offered again"
    )

    assert (
        await active_is_reserved_edges_on(
            db=db, node_id=holder.get_id(), attribute_name=TRACKED_ATTRIBUTE_NAME, open_only=True
        )
        == []
    ), "no branch predates the conversion, so the IS_RESERVED edge on the replaced object is closed"

    moved = await open_is_reserved_edge_on(db=db, node_id=converted.get_id(), attribute_name=TRACKED_ATTRIBUTE_NAME)
    assert moved["provenance"] == PoolRecordProvenance.PROVIDED.value, (
        "the move must carry the provenance across rather than assume the pool chose the number"
    )
    assert moved["identifier"] == converted.get_id()
    assert moved["branch"] == GLOBAL_BRANCH_NAME
    assert moved["status"] == "active"
    assert "to" not in moved, "a moved IS_RESERVED edge is open, whatever state the one it came from was in"


async def test_a_pool_does_not_follow_its_is_reserved_edge_onto_a_kind_it_does_not_track(
    db: InfrahubDatabase, default_branch: Branch, convert_pool: CoreNumberPool
) -> None:
    """A pool tracks a kind. Sharing an attribute name with some other kind is not a claim on it."""
    holder = await holder_holding_a_pooled_number(db=db, branch=default_branch, pool=convert_pool)
    allocated = holder.get_attribute(TRACKED_ATTRIBUTE_NAME).value
    assert await convert_pool.get_used(db=db, branch=default_branch) == [allocated]

    converted = await convert_to(db=db, branch=default_branch, node=holder, target_kind=OUTSIDER_KIND)

    assert converted.get_attribute(TRACKED_ATTRIBUTE_NAME).value == allocated, (
        "the conversion still carries the number across"
    )
    is_reserved_edges = await active_is_reserved_edges_on(
        db=db,
        node_id=converted.get_id(),
        attribute_name=TRACKED_ATTRIBUTE_NAME,
        pool_id=convert_pool.get_id(),
        open_only=True,
    )
    assert is_reserved_edges == [], "the pool must not account for an attribute of a kind it does not track"
    assert await convert_pool.get_used(db=db, branch=default_branch) == [], (
        "and the number it held is released rather than left charged to an object outside the pool"
    )


async def test_converting_an_object_on_a_branch_leaves_its_is_reserved_edge_open(
    db: InfrahubDatabase, default_branch: Branch, convert_pool: CoreNumberPool
) -> None:
    """The object is only replaced on the branch; on the default branch it still holds its number."""
    holder = await holder_holding_a_pooled_number(db=db, branch=default_branch, pool=convert_pool)
    allocated = holder.get_attribute(TRACKED_ATTRIBUTE_NAME).value
    assert await convert_pool.get_used(db=db, branch=default_branch) == [allocated]

    branch = await create_branch(db=db, branch_name="convert-on-a-branch")
    on_branch = await registry.manager.get_one(db=db, id=holder.get_id(), branch=branch, raise_on_error=True)
    converted = await convert_to(db=db, branch=branch, node=on_branch, target_kind=TARGET_KIND)

    kept = await open_is_reserved_edge_on(db=db, node_id=holder.get_id(), attribute_name=TRACKED_ATTRIBUTE_NAME)
    assert kept["identifier"] == holder.get_id(), (
        "the default branch's object still holds the number, so its IS_RESERVED edge must stay open"
    )
    moved = await open_is_reserved_edge_on(db=db, node_id=converted.get_id(), attribute_name=TRACKED_ATTRIBUTE_NAME)
    assert moved["identifier"] == converted.get_id()
    assert moved["branch"] == GLOBAL_BRANCH_NAME

    assert set(await convert_pool.get_used(db=db, branch=default_branch)) == {allocated}, (
        "the number stays used, held by the default branch's object and the branch's replacement"
    )
    assert await convert_pool.get_free(db=db, branch=default_branch) != allocated, (
        "a conversion on a branch must not offer the default branch's number again"
    )
