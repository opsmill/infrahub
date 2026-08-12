from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from infrahub.core import registry
from infrahub.core.node.create import create_node
from infrahub.core.schema import AttributeSchema, NodeSchema, RelationshipSchema, SchemaRoot
from infrahub.exceptions import HFIDViolatedError, ValidationError
from tests.helpers.schema_builders import computed_jinja2_attr

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.database import InfrahubDatabase


@pytest.fixture
async def stuff_schema_computed_hfid(db: InfrahubDatabase, default_branch: Branch) -> SchemaRoot:
    """Schema where the human-friendly id is a required computed attribute derived from a local attribute."""
    schema = SchemaRoot(
        nodes=[
            NodeSchema(
                name="Stuff",
                namespace="Random",
                human_friendly_id=["name__value"],
                attributes=[
                    computed_jinja2_attr(name="name", template="{{ description__value | upper }}-STUFF"),
                    AttributeSchema(name="description", kind="Text"),
                ],
            ),
        ],
    )
    registry.schema.register_schema(schema=schema, branch=default_branch.name)
    return schema


@pytest.fixture
async def stuff_schema_computed_from_relationship(db: InfrahubDatabase, default_branch: Branch) -> SchemaRoot:
    """Schema where the unique computed attribute is derived from an attribute on a peer relationship."""
    schema = SchemaRoot(
        nodes=[
            NodeSchema(
                name="Stuff",
                namespace="Random",
                human_friendly_id=["name__value"],
                attributes=[computed_jinja2_attr(name="name", template="{{ owner__name__value | upper }}")],
                relationships=[
                    RelationshipSchema(name="owner", peer="RandomOwner", optional=False, cardinality="one"),
                ],
            ),
            NodeSchema(
                name="Owner",
                namespace="Random",
                attributes=[AttributeSchema(name="name", kind="Text", unique=True)],
            ),
        ],
    )
    registry.schema.register_schema(schema=schema, branch=default_branch.name)
    return schema


@pytest.fixture
async def stuff_schema_computed_secondary_unique(db: InfrahubDatabase, default_branch: Branch) -> SchemaRoot:
    """Schema where a unique computed attribute exists alongside a separate, non-computed human-friendly id."""
    schema = SchemaRoot(
        nodes=[
            NodeSchema(
                name="Stuff",
                namespace="Random",
                human_friendly_id=["name__value"],
                attributes=[
                    AttributeSchema(name="name", kind="Text", unique=True),
                    computed_jinja2_attr(name="code", template="{{ description__value | upper }}"),
                    AttributeSchema(name="description", kind="Text"),
                ],
            ),
        ],
    )
    registry.schema.register_schema(schema=schema, branch=default_branch.name)
    return schema


async def test_create_node_rejects_duplicate_computed_hfid(
    db: InfrahubDatabase, default_branch: Branch, stuff_schema_computed_hfid: SchemaRoot
) -> None:
    stuff_schema = registry.schema.get_node_schema(name="RandomStuff", branch=default_branch)

    first = await create_node(data={"description": "widget"}, db=db, branch=default_branch, schema=stuff_schema)
    assert first.name.value == "WIDGET-STUFF"

    with pytest.raises(
        HFIDViolatedError, match=r"Violates uniqueness constraint 'name' \(computed from: description\)"
    ):
        await create_node(data={"description": "widget"}, db=db, branch=default_branch, schema=stuff_schema)


async def test_violation_message_lists_relationship_peer_attribute(
    db: InfrahubDatabase, default_branch: Branch, stuff_schema_computed_from_relationship: SchemaRoot
) -> None:
    stuff_schema = registry.schema.get_node_schema(name="RandomStuff", branch=default_branch)
    owner_schema = registry.schema.get_node_schema(name="RandomOwner", branch=default_branch)

    alice = await create_node(data={"name": "alice"}, db=db, branch=default_branch, schema=owner_schema)
    first = await create_node(data={"owner": {"id": alice.id}}, db=db, branch=default_branch, schema=stuff_schema)
    assert first.name.value == "ALICE"

    with pytest.raises(
        HFIDViolatedError, match=r"Violates uniqueness constraint 'name' \(computed from: owner\.name\)"
    ):
        await create_node(data={"owner": {"id": alice.id}}, db=db, branch=default_branch, schema=stuff_schema)


async def test_create_node_rejects_duplicate_computed_secondary_unique(
    db: InfrahubDatabase,
    default_branch: Branch,
    stuff_schema_computed_secondary_unique: SchemaRoot,
) -> None:
    stuff_schema = registry.schema.get_node_schema(name="RandomStuff", branch=default_branch)

    first = await create_node(
        data={"name": "alpha", "description": "widget"}, db=db, branch=default_branch, schema=stuff_schema
    )
    assert first.code.value == "WIDGET"

    with pytest.raises(
        ValidationError, match=r"Violates uniqueness constraint 'code' \(computed from: description\)"
    ) as exc_info:
        await create_node(
            data={"name": "beta", "description": "widget"}, db=db, branch=default_branch, schema=stuff_schema
        )
    assert not isinstance(exc_info.value, HFIDViolatedError)
