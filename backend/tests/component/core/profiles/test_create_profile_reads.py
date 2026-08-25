from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from infrahub.core.node import Node
from infrahub.core.node.create import create_node
from infrahub.core.query.relationship import RelationshipGetPeerQuery
from infrahub.core.registry import registry
from infrahub.core.schema import SchemaRoot
from tests.constants import TestKind
from tests.helpers.db_query_counter import CountingInfrahubDatabase
from tests.helpers.schema import CHILD, THING, load_schema

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.database import InfrahubDatabase


@pytest.fixture
async def schema(db: InfrahubDatabase, default_branch: Branch, register_core_models_schema: None) -> None:
    await load_schema(db=db, schema=SchemaRoot(nodes=[CHILD, THING]), branch_name=default_branch.name)


async def test_create_without_profiles_does_not_look_them_up(
    db: InfrahubDatabase, default_branch: Branch, schema: None
) -> None:
    child_schema = registry.schema.get_node_schema(name=TestKind.CHILD, branch=default_branch)
    counting_db = CountingInfrahubDatabase.from_db(db=db)

    child = await create_node(data={"name": "no-profile"}, db=counting_db, branch=default_branch, schema=child_schema)

    assert counting_db.count_for(RelationshipGetPeerQuery.name) == 0
    assert child.name.value == "no-profile"


async def test_create_with_profiles_still_applies_them(
    db: InfrahubDatabase, default_branch: Branch, schema: None
) -> None:
    profile_schema = registry.schema.get(name=f"Profile{TestKind.CHILD}", branch=default_branch)
    profile = await Node.init(db=db, schema=profile_schema, branch=default_branch)
    await profile.new(db=db, profile_name="from-profile", profile_priority=1000, name="profile-name")
    await profile.save(db=db)

    child_schema = registry.schema.get_node_schema(name=TestKind.CHILD, branch=default_branch)

    child = await create_node(data={"profiles": [profile.id]}, db=db, branch=default_branch, schema=child_schema)

    assert child.name.value == "profile-name"
    assert child.name.is_from_profile is True
