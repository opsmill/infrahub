from uuid import UUID

import pytest

from infrahub.core import registry
from infrahub.core.branch import Branch
from infrahub.core.initialization import first_time_initialization, get_root_node, reset_deployment_id
from infrahub.core.preferences.repository import PreferenceRepository
from infrahub.core.schema import SchemaRoot, core_models, internal_schema
from infrahub.core.schema.definitions.deprecated import deprecated_models
from infrahub.database import InfrahubDatabase


async def test_first_time_initialization(db: InfrahubDatabase, default_branch: Branch) -> None:
    await first_time_initialization(db=db)
    assert True


async def test_first_time_initialization_converges_core_schema(db: InfrahubDatabase, default_branch: Branch) -> None:
    """A fresh installation must persist the schema shape the upgrade flow builds as its candidate.

    The candidate includes the deprecated overlay, so the core-schema diff starts out empty.
    """
    await first_time_initialization(db=db)

    branch_schema = await registry.schema.load_schema_from_db(db=db, branch=default_branch)
    candidate_schema = branch_schema.duplicate()
    candidate_schema.load_schema(schema=SchemaRoot(**internal_schema))
    candidate_schema.load_schema(schema=SchemaRoot(**core_models))
    candidate_schema.load_schema(schema=SchemaRoot(**deprecated_models))
    candidate_schema.process()

    assert branch_schema.diff(other=candidate_schema).all == []


async def test_first_time_initialization_does_not_seed_preferences(
    db: InfrahubDatabase, delete_all_nodes_in_db: None
) -> None:
    """A fresh install seeds NO preference row.

    Preferences reads never create, and there is no init seed — a Preference row exists only after
    the first write.
    """
    # delete_all_nodes_in_db leaves a truly empty graph, so first_time_initialization runs against
    # a fresh install and builds its own Root.
    await first_time_initialization(db=db)

    assert await PreferenceRepository(db=db).get_all() == []


async def test_first_time_initialization_converges_core_schema(db: InfrahubDatabase, default_branch: Branch) -> None:
    """A fresh installation must persist the schema shape the upgrade flow builds as its candidate.

    The candidate includes the deprecated overlay, so the core-schema diff starts out empty.
    """
    await first_time_initialization(db=db)

    branch_schema = await registry.schema.load_schema_from_db(db=db, branch=default_branch)
    candidate_schema = branch_schema.duplicate()
    candidate_schema.load_schema(schema=SchemaRoot(**internal_schema))
    candidate_schema.load_schema(schema=SchemaRoot(**core_models))
    candidate_schema.load_schema(schema=SchemaRoot(**deprecated_models))
    candidate_schema.process()

    assert branch_schema.diff(other=candidate_schema).all == []


async def test_reset_deployment_id_generates_new_uuid(db: InfrahubDatabase, default_branch: Branch) -> None:
    root_before = await get_root_node(db=db)
    original = str(root_before.get_uuid())

    old_uuid, new_uuid = await reset_deployment_id(db=db)

    assert old_uuid == original
    assert new_uuid != original
    UUID(new_uuid)

    root_after = await get_root_node(db=db)
    assert str(root_after.get_uuid()) == new_uuid


async def test_reset_deployment_id_with_explicit_value(db: InfrahubDatabase, default_branch: Branch) -> None:
    explicit = "11111111-2222-3333-4444-555555555555"

    _, new_uuid = await reset_deployment_id(db=db, new_uuid=explicit)

    assert new_uuid == explicit
    root_after = await get_root_node(db=db)
    assert str(root_after.get_uuid()) == explicit


async def test_reset_deployment_id_rejects_unchanged_value(db: InfrahubDatabase, default_branch: Branch) -> None:
    root = await get_root_node(db=db)
    current = str(root.get_uuid())

    with pytest.raises(ValueError, match="must be different"):
        await reset_deployment_id(db=db, new_uuid=current)
