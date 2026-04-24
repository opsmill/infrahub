"""Branch-local (``BranchSupportType.LOCAL``) nodes do not merge to the default branch."""

import pytest

from infrahub.core import registry
from infrahub.core.branch import Branch
from infrahub.core.constants import DiffAction, MetadataOptions
from infrahub.core.diff.repository.repository import DiffRepository
from infrahub.core.initialization import create_branch
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.core.schema.schema_branch import SchemaBranch
from infrahub.core.timestamp import Timestamp
from infrahub.database import InfrahubDatabase
from tests.helpers.db_validation import verify_graph

from ..get_one_node import get_one_diff_node
from .conftest import get_diff_coordinator, get_diff_merger


async def test_local_and_aware_nodes_added_on_branch(
    db: InfrahubDatabase,
    default_branch: Branch,
    diff_repository: DiffRepository,
    car_person_schema_branch_local: SchemaBranch,
) -> None:
    branch2 = await create_branch(db=db, branch_name="branch2")
    person = await Node.init(db=db, schema="TestPerson", branch=branch2)
    await person.new(db=db, name="Guy", height=180)
    await person.save(db=db, user_id="branch-user-person")
    car = await Node.init(db=db, schema="TestCar", branch=branch2)
    await car.new(db=db, name="camry", owner=person.id)
    before_car_create = Timestamp()
    await car.save(db=db, user_id="branch-user-car")
    after_car_create = Timestamp()

    diff_coordinator = await get_diff_coordinator(db=db, branch=branch2)
    enriched_diff_metadata = await diff_coordinator.update_branch_diff(base_branch=default_branch, diff_branch=branch2)
    enriched_diff = await diff_repository.get_one(
        diff_branch_name=enriched_diff_metadata.diff_branch_name, diff_id=enriched_diff_metadata.uuid
    )
    diff_person = get_one_diff_node(diff_root=enriched_diff, node_uuid=person.id)
    assert diff_person.action is DiffAction.ADDED
    # validate car is not in the diff
    with pytest.raises(ValueError, match=r"No nodes found"):
        get_one_diff_node(diff_root=enriched_diff, node_uuid=car.id)

    diff_merger = await get_diff_merger(db=db, branch=branch2)
    merge_at = Timestamp()
    await diff_merger.merge_graph(at=merge_at)

    # validate person update on main with metadata
    updated_person = await NodeManager.get_one(db=db, id=person.id, include_metadata=MetadataOptions.USER_TIMESTAMPS)
    assert updated_person.height.value == 180
    assert updated_person.name.value == "Guy"
    # Person Node metadata - created on branch, merged to main
    assert updated_person._get_created_at() == merge_at
    assert updated_person._get_created_by() == "branch-user-person"
    assert updated_person._get_updated_at() == merge_at
    assert updated_person._get_updated_by() == "branch-user-person"
    # Person Attribute metadata
    assert updated_person.name._get_created_at() == merge_at
    assert updated_person.name._get_created_by() == "branch-user-person"
    assert updated_person.name._get_updated_at() == merge_at
    assert updated_person.name._get_updated_by() == "branch-user-person"
    assert updated_person.height._get_created_at() == merge_at
    assert updated_person.height._get_created_by() == "branch-user-person"
    assert updated_person.height._get_updated_at() == merge_at
    assert updated_person.height._get_updated_by() == "branch-user-person"
    # validate car (branch=local) not merged to main
    updated_car = await NodeManager.get_one(db=db, id=car.id)
    assert updated_car is None
    person_schema = registry.schema.get(name="TestPerson", duplicate=False)
    cars_rel_schema = person_schema.get_relationship(name="cars")
    cars_rels = await NodeManager.query_peers(
        db=db, ids=[person.id], source_kind="TestPerson", schema=cars_rel_schema, filters={}, fetch_peers=True
    )
    assert len(cars_rels) == 0
    car_schema = registry.schema.get(name="TestCar", duplicate=False)
    owner_rel_schema = car_schema.get_relationship(name="owner")
    owner_rels = await NodeManager.query_peers(
        db=db, ids=[car.id], source_kind="TestCar", schema=owner_rel_schema, filters={}, fetch_peers=True
    )
    assert len(owner_rels) == 0
    # validate relationship still exists on branch
    cars_rels = await NodeManager.query_peers(
        db=db,
        branch=branch2,
        ids=[person.id],
        source_kind="TestPerson",
        schema=cars_rel_schema,
        filters={},
        fetch_peers=True,
    )
    assert len(cars_rels) == 1
    assert cars_rels[0].peer_id == car.id
    owner_rels = await NodeManager.query_peers(
        db=db,
        branch=branch2,
        ids=[car.id],
        source_kind="TestCar",
        schema=owner_rel_schema,
        filters={},
        fetch_peers=True,
        include_metadata=MetadataOptions.USER_TIMESTAMPS,
    )
    assert len(owner_rels) == 1
    assert owner_rels[0].peer_id == person.id
    assert before_car_create < owner_rels[0]._get_created_at() < after_car_create
    assert owner_rels[0]._get_created_by() == "branch-user-car"
    assert before_car_create < owner_rels[0]._get_updated_at() < after_car_create
    assert owner_rels[0]._get_updated_by() == "branch-user-car"
    await verify_graph(db=db)
