from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from infrahub.core.constants import MetadataOptions
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.core.node.create import create_node
from infrahub.core.query.relationship import RelationshipGetPeerQuery
from infrahub.core.registry import registry
from infrahub.core.schema import SchemaRoot
from infrahub.profiles.node_applier import NodeProfilesApplier
from tests.constants import TestKind
from tests.helpers.db_query_counter import CountingInfrahubDatabase
from tests.helpers.schema import CHILD, DEVICE_SCHEMA, THING, load_schema

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.database import InfrahubDatabase


@pytest.fixture
async def schema(db: InfrahubDatabase, default_branch: Branch, register_core_models_schema: None) -> None:
    await load_schema(db=db, schema=SchemaRoot(nodes=[CHILD, THING]), branch_name=default_branch.name)


@pytest.fixture
async def device_schema(db: InfrahubDatabase, default_branch: Branch, register_core_models_schema: None) -> None:
    await load_schema(db=db, schema=DEVICE_SCHEMA, branch_name=default_branch.name)


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

    reloaded = await NodeManager.get_one(
        db=db, id=child.id, branch=default_branch, include_metadata=MetadataOptions.SOURCE, raise_on_error=True
    )
    assert reloaded.name.value == "profile-name"
    assert reloaded.name.is_from_profile is True
    assert reloaded.name.source_id == profile.id
    assert {rel.peer_id for rel in await reloaded.profiles.get_relationships(db=db)} == {profile.id}


async def test_create_from_a_template_applies_the_profiles_it_carries(
    db: InfrahubDatabase, default_branch: Branch, device_schema: None
) -> None:
    """The template names the profiles, not the payload, and the node still gets their current values."""
    profile_schema = registry.schema.get(name=f"Profile{TestKind.DEVICE}", branch=default_branch)
    profile = await Node.init(db=db, schema=profile_schema, branch=default_branch)
    await profile.new(db=db, profile_name="from-profile", profile_priority=1000, part_number="from-profile")
    await profile.save(db=db)

    template_schema = registry.schema.get(name=f"Template{TestKind.DEVICE}", branch=default_branch)
    template = await Node.init(db=db, schema=template_schema, branch=default_branch)
    await template.new(
        db=db,
        template_name="with-profile",
        manufacturer="Acme",
        weight=1,
        airflow="Passive",
        profiles=[profile.id],
    )
    await template.save(db=db)
    await NodeProfilesApplier(db=db, branch=default_branch).apply_profiles(node=template)
    await template.save(db=db)
    assert template.part_number.value == "from-profile"

    # The profile moves on after the template took its values from it.
    profile.part_number.value = "profile-updated"
    await profile.save(db=db)

    node_schema = registry.schema.get_node_schema(name=TestKind.DEVICE, branch=default_branch)
    device = await create_node(
        data={"name": "from-template", "object_template": {"id": template.id}},
        db=db,
        branch=default_branch,
        schema=node_schema,
    )

    assert device.part_number.value == "profile-updated"
    assert device.part_number.is_from_profile is True
    assert device.part_number.source_id == profile.id

    reloaded = await NodeManager.get_one(
        db=db, id=device.id, branch=default_branch, include_metadata=MetadataOptions.SOURCE, raise_on_error=True
    )
    assert reloaded.part_number.value == "profile-updated"
    assert reloaded.part_number.is_from_profile is True
    assert reloaded.part_number.source_id == profile.id
    assert {rel.peer_id for rel in await reloaded.profiles.get_relationships(db=db)} == {profile.id}
