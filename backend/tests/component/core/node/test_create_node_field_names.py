from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from infrahub.core import registry
from infrahub.core.manager import NodeManager
from infrahub.core.node.create import create_node
from infrahub.core.schema import AttributeSchema, NodeSchema, SchemaRoot
from tests.helpers.agnostic_edges import TEST_ACTOR_ID

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.database import InfrahubDatabase


@pytest.fixture
async def stuff_schema_with_creation_parameter_names(db: InfrahubDatabase, default_branch: Branch) -> SchemaRoot:
    """Schema whose attributes share their names with the parameters that create a node."""
    schema = SchemaRoot(
        nodes=[
            NodeSchema(
                name="Stuff",
                namespace="Random",
                attributes=[
                    AttributeSchema(name="user_id", kind="Text"),
                    AttributeSchema(name="pool_applier", kind="Text"),
                ],
            ),
        ],
    )
    registry.schema.register_schema(schema=schema, branch=default_branch.name)
    return schema


async def test_create_node_saves_attributes_named_like_creation_parameters(
    db: InfrahubDatabase, default_branch: Branch, stuff_schema_with_creation_parameter_names: SchemaRoot
) -> None:
    stuff_schema = registry.schema.get_node_schema(name="RandomStuff", branch=default_branch)

    created = await create_node(
        data={"user_id": "jdoe", "pool_applier": "manual"},
        db=db,
        branch=default_branch,
        schema=stuff_schema,
        user_id=TEST_ACTOR_ID,
    )

    stored = await NodeManager.get_one(db=db, id=created.get_id(), branch=default_branch)
    assert stored is not None
    assert [stored.get_attribute(name=name).value for name in ("user_id", "pool_applier")] == ["jdoe", "manual"]
    assert created._get_created_by() == TEST_ACTOR_ID
