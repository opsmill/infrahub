from unittest.mock import AsyncMock

import pytest

from infrahub.core import registry
from infrahub.core.branch import Branch
from infrahub.core.constants import (
    DiffAction,
    MetadataOptions,
)
from infrahub.core.diff.coordinator import DiffCoordinator
from infrahub.core.diff.data_check_synchronizer import DiffDataCheckSynchronizer
from infrahub.core.diff.merger.merger import DiffMerger
from infrahub.core.diff.repository.repository import DiffRepository
from infrahub.core.initialization import create_branch
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.core.schema.schema_branch import SchemaBranch
from infrahub.core.timestamp import Timestamp
from infrahub.database import InfrahubDatabase
from infrahub.dependencies.registry import get_component_registry
from tests.helpers.db_validation import verify_graph

from ..get_one_node import get_one_diff_node


class TestAgnosticNodeMerge:
    @pytest.fixture(autouse=True)
    async def _setup_core_schema(self, register_core_models_schema: SchemaBranch) -> None:
        return

    @pytest.fixture
    async def diff_repository(self, db: InfrahubDatabase, default_branch: Branch) -> DiffRepository:
        component_registry = get_component_registry()
        return await component_registry.get_component(DiffRepository, db=db, branch=default_branch)

    async def _get_diff_coordinator(self, db: InfrahubDatabase, branch: Branch) -> DiffCoordinator:
        component_registry = get_component_registry()
        diff_coordinator = await component_registry.get_component(DiffCoordinator, db=db, branch=branch)
        diff_coordinator.data_check_synchronizer = AsyncMock(spec=DiffDataCheckSynchronizer)
        return diff_coordinator

    async def _get_diff_merger(self, db: InfrahubDatabase, branch: Branch) -> DiffMerger:
        component_registry = get_component_registry()
        return await component_registry.get_component(DiffMerger, db=db, branch=branch)

    async def test_agnostic_and_aware_nodes_added_on_branch(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        diff_repository: DiffRepository,
        car_person_schema_global: None,
    ) -> None:
        branch2 = await create_branch(db=db, branch_name="branch2")
        person = await Node.init(db=db, schema="TestPerson", branch=branch2)
        await person.new(db=db, name="Guy", height=180)
        before_person_create = Timestamp()
        await person.save(db=db, user_id="branch-user-person")
        after_person_create = Timestamp()
        car = await Node.init(db=db, schema="TestCar", branch=branch2)
        await car.new(db=db, name="camry", nbr_seats=3, is_electric=False, owner=person.id)
        before_car_create = Timestamp()
        await car.save(db=db, user_id="branch-user-car")
        after_car_create = Timestamp()

        diff_coordinator = await self._get_diff_coordinator(db=db, branch=branch2)
        enriched_diff_metadata = await diff_coordinator.update_branch_diff(
            base_branch=default_branch, diff_branch=branch2
        )
        enriched_diff = await diff_repository.get_one(
            diff_branch_name=enriched_diff_metadata.diff_branch_name, diff_id=enriched_diff_metadata.uuid
        )
        diff_person = get_one_diff_node(diff_root=enriched_diff, node_uuid=person.id)
        assert diff_person.action is DiffAction.UPDATED
        diff_car = get_one_diff_node(diff_root=enriched_diff, node_uuid=car.id)
        assert diff_car.action is DiffAction.ADDED

        diff_merger = await self._get_diff_merger(db=db, branch=branch2)
        merge_at = Timestamp()
        await diff_merger.merge_graph(at=merge_at)

        # validate person (agnostic) exists on main with metadata
        updated_person = await NodeManager.get_one(
            db=db, id=person.id, include_metadata=MetadataOptions.USER_TIMESTAMPS, prefetch_relationships=True
        )
        assert updated_person.height.value == 180
        assert updated_person.name.value == "Guy"
        # Person Node metadata - updated_at reflects merge (relationship added)
        assert before_person_create < updated_person._get_created_at() < after_person_create
        assert updated_person._get_created_by() == "branch-user-person"
        assert updated_person._get_updated_at() == merge_at
        assert updated_person._get_updated_by() == "branch-user-car"

        cars_rels = await updated_person.cars.get_relationships(db=db)
        assert len(cars_rels) == 1
        assert cars_rels[0].peer_id == car.id
        # Person cars relationship metadata
        assert cars_rels[0]._get_created_at() == merge_at
        assert cars_rels[0]._get_created_by() == "branch-user-car"
        assert cars_rels[0]._get_updated_at() == merge_at
        assert cars_rels[0]._get_updated_by() == "branch-user-car"

        # validate car merged to main with metadata
        updated_car = await NodeManager.get_one(
            db=db, id=car.id, include_metadata=MetadataOptions.USER_TIMESTAMPS, prefetch_relationships=True
        )
        assert updated_car.name.value == "camry"
        assert updated_car.nbr_seats.value == 3
        assert updated_car.is_electric.value is False
        owner_rel = await updated_car.owner.get(db=db)
        assert owner_rel.peer_id == person.id
        # Car Node metadata - created on branch, merged to main
        assert updated_car._get_created_at() == merge_at
        assert updated_car._get_created_by() == "branch-user-car"
        assert updated_car._get_updated_at() == merge_at
        assert updated_car._get_updated_by() == "branch-user-car"
        # Car owner relationship metadata
        assert owner_rel._get_created_at() == merge_at
        assert owner_rel._get_created_by() == "branch-user-car"
        assert owner_rel._get_updated_at() == merge_at
        assert owner_rel._get_updated_by() == "branch-user-car"
        # Car Attribute metadata
        assert updated_car.name._get_created_at() == merge_at
        assert updated_car.name._get_created_by() == "branch-user-car"

        # validate relationships on default branch
        person_schema = registry.schema.get(name="TestPerson", duplicate=False)
        cars_rel_schema = person_schema.get_relationship(name="cars")
        cars_rels = await NodeManager.query_peers(
            db=db,
            ids=[person.id],
            source_kind="TestPerson",
            schema=cars_rel_schema,
            filters={},
            fetch_peers=True,
            include_metadata=MetadataOptions.USER_TIMESTAMPS,
        )
        assert len(cars_rels) == 1
        assert cars_rels[0].peer_id == car.id
        assert cars_rels[0]._get_created_at() == merge_at
        assert cars_rels[0]._get_created_by() == "branch-user-car"
        assert cars_rels[0]._get_updated_at() == merge_at
        assert cars_rels[0]._get_updated_by() == "branch-user-car"

        car_schema = registry.schema.get(name="TestCar", duplicate=False)
        owner_rel_schema = car_schema.get_relationship(name="owner")
        owner_rels = await NodeManager.query_peers(
            db=db,
            ids=[car.id],
            source_kind="TestCar",
            schema=owner_rel_schema,
            filters={},
            fetch_peers=True,
            include_metadata=MetadataOptions.USER_TIMESTAMPS,
        )
        assert len(owner_rels) == 1
        assert owner_rels[0].peer_id == person.id
        assert owner_rels[0]._get_created_at() == merge_at
        assert owner_rels[0]._get_created_by() == "branch-user-car"
        assert owner_rels[0]._get_updated_at() == merge_at
        assert owner_rels[0]._get_updated_by() == "branch-user-car"

        # validate relationship still exists on branch
        cars_rels = await NodeManager.query_peers(
            db=db,
            branch=branch2,
            ids=[person.id],
            source_kind="TestPerson",
            schema=cars_rel_schema,
            filters={},
            fetch_peers=True,
            include_metadata=MetadataOptions.USER_TIMESTAMPS,
        )
        assert len(cars_rels) == 1
        assert cars_rels[0].peer_id == car.id
        assert before_car_create < cars_rels[0]._get_created_at() < after_car_create
        assert cars_rels[0]._get_created_by() == "branch-user-car"
        assert before_car_create < cars_rels[0]._get_updated_at() < after_car_create
        assert cars_rels[0]._get_updated_by() == "branch-user-car"

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
