"""Sequential relationship property updates across two diff passes.

A branch updates one property on a relationship, runs ``update_branch_diff``,
then updates a different property on the same relationship and runs
``update_branch_diff`` again. The merge should see the accumulated enriched
diff and apply both property changes to the default branch.

Covers regression where a second pass of ``update_branch_diff`` could drop the
first pass's property change.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from infrahub.core import registry
from infrahub.core.constants import MetadataOptions
from infrahub.core.initialization import create_branch
from infrahub.core.manager import NodeManager
from infrahub.core.timestamp import Timestamp
from tests.helpers.db_validation import verify_graph

from .conftest import get_diff_coordinator, get_diff_merger

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.core.node import Node
    from infrahub.database import InfrahubDatabase


async def test_sequential_rel_property_updates(
    db: InfrahubDatabase,
    default_branch: Branch,
    person_john_main: Node,
    person_alfred_main: Node,
    car_accord_main: Node,
    car_camry_main: Node,
) -> None:
    before_test_start = Timestamp()
    original_car_created_at = car_accord_main._get_created_at()
    original_car_created_by = car_accord_main._get_created_by()

    branch = await create_branch(db=db, branch_name="sequential-rel-props")

    # Pass 1: set owner.is_protected=True, run update_branch_diff.
    car_branch = await NodeManager.get_one(db=db, branch=branch, id=car_accord_main.id)
    await car_branch.owner.update(db=db, data={"id": person_john_main.id, "_relation__is_protected": True})
    await car_branch.save(db=db, user_id="branch-user-one")

    coordinator = await get_diff_coordinator(db=db, branch=branch)
    await coordinator.update_branch_diff(base_branch=default_branch, diff_branch=branch)

    # Pass 2: set owner.source=car_camry on the same rel, run update_branch_diff again.
    car_branch = await NodeManager.get_one(db=db, branch=branch, id=car_accord_main.id)
    await car_branch.owner.update(db=db, data={"id": person_john_main.id, "_relation__source": car_camry_main.id})
    await car_branch.save(db=db, user_id="branch-user-two")

    await coordinator.update_branch_diff(base_branch=default_branch, diff_branch=branch)

    merger = await get_diff_merger(db=db, branch=branch)
    merge_at = Timestamp()
    await merger.merge_graph(at=merge_at)

    # Both property changes should have landed on default. Use two fetches:
    # peer-valued properties (source_id) require prefetch_relationships=False;
    # timestamps require prefetch_relationships=True.
    merged_car_no_prefetch = await NodeManager.get_one(db=db, branch=default_branch, id=car_accord_main.id)
    owner_rel = await merged_car_no_prefetch.owner.get(db=db)
    assert owner_rel.peer_id == person_john_main.id
    assert owner_rel.is_protected is True
    owner_source = await owner_rel.get_source(db=db)
    assert owner_source is not None
    assert owner_source.id == car_camry_main.id

    # Verify the two saves produced one rel on merge (not a duplicate).
    person_schema = registry.schema.get(name="TestPerson", duplicate=False)
    cars_rel_schema = person_schema.get_relationship(name="cars")
    john_car_count = await NodeManager.count_peers(
        db=db,
        ids=[person_john_main.id],
        source_kind="TestPerson",
        filters={},
        schema=cars_rel_schema,
        branch=default_branch,
    )
    assert john_car_count == 1

    merged_car_with_metadata = await NodeManager.get_one(
        db=db,
        branch=default_branch,
        id=car_accord_main.id,
        include_metadata=MetadataOptions.USER_TIMESTAMPS,
        prefetch_relationships=True,
    )
    owner_rel_meta = await merged_car_with_metadata.owner.get(db=db)
    assert merged_car_with_metadata._get_created_at() == original_car_created_at
    assert merged_car_with_metadata._get_created_by() == original_car_created_by
    assert merged_car_with_metadata._get_updated_at() == merge_at
    assert merged_car_with_metadata._get_updated_by() == "branch-user-two"
    assert owner_rel_meta._get_updated_at() == merge_at
    assert owner_rel_meta._get_updated_by() == "branch-user-two"

    await verify_graph(db=db)

    # Rollback reverts both property changes.
    await merger.rollback(at=merge_at)
    rolled_back_car = await NodeManager.get_one(db=db, branch=default_branch, id=car_accord_main.id)
    rolled_back_owner = await rolled_back_car.owner.get(db=db)
    assert rolled_back_owner.peer_id == person_john_main.id
    assert rolled_back_owner.is_protected is False
    rolled_back_source = await rolled_back_owner.get_source(db=db)
    assert rolled_back_source is None

    rolled_back_car_meta = await NodeManager.get_one(
        db=db,
        branch=default_branch,
        id=car_accord_main.id,
        include_metadata=MetadataOptions.USER_TIMESTAMPS,
        prefetch_relationships=True,
    )
    rolled_back_owner_meta = await rolled_back_car_meta.owner.get(db=db)
    assert rolled_back_car_meta._get_updated_at() < before_test_start
    assert rolled_back_owner_meta._get_updated_at() < before_test_start
    await verify_graph(db=db)
