from dataclasses import dataclass
from unittest.mock import AsyncMock

import pytest

from infrahub.core.branch import Branch
from infrahub.core.constants import MetadataOptions
from infrahub.core.diff.coordinator import DiffCoordinator
from infrahub.core.diff.data_check_synchronizer import DiffDataCheckSynchronizer
from infrahub.core.diff.merger.merger import DiffMerger
from infrahub.core.manager import NodeManager
from infrahub.core.metadata.model import MetadataQueryOptions
from infrahub.core.node import Node
from infrahub.core.registry import registry
from infrahub.core.relationship.model import Relationship
from infrahub.core.schema.schema_branch import SchemaBranch
from infrahub.database import InfrahubDatabase
from infrahub.dependencies.registry import get_component_registry
from tests.conftest import do_car_person_schema_unregistered


@dataclass
class _RelMetadataCase:
    name: str
    flags: MetadataOptions
    expect_is_protected_populated: bool
    expect_source_populated: bool
    expect_owner_populated: bool
    expect_timestamps_populated: bool


_REL_METADATA_CASES = [
    _RelMetadataCase(
        name="none",
        flags=MetadataOptions.NONE,
        expect_is_protected_populated=False,
        expect_source_populated=False,
        expect_owner_populated=False,
        expect_timestamps_populated=False,
    ),
    _RelMetadataCase(
        name="is-protected-only",
        flags=MetadataOptions.IS_PROTECTED,
        expect_is_protected_populated=True,
        expect_source_populated=False,
        expect_owner_populated=False,
        expect_timestamps_populated=False,
    ),
    _RelMetadataCase(
        name="source-only",
        flags=MetadataOptions.SOURCE,
        expect_is_protected_populated=False,
        expect_source_populated=True,
        expect_owner_populated=False,
        expect_timestamps_populated=False,
    ),
    _RelMetadataCase(
        name="owner-only",
        flags=MetadataOptions.OWNER,
        expect_is_protected_populated=False,
        expect_source_populated=False,
        expect_owner_populated=True,
        expect_timestamps_populated=False,
    ),
    _RelMetadataCase(
        name="linked-nodes",
        flags=MetadataOptions.LINKED_NODES,
        expect_is_protected_populated=False,
        expect_source_populated=True,
        expect_owner_populated=True,
        expect_timestamps_populated=False,
    ),
    _RelMetadataCase(
        name="user-timestamps",
        flags=MetadataOptions.USER_TIMESTAMPS,
        expect_is_protected_populated=False,
        expect_source_populated=False,
        expect_owner_populated=False,
        expect_timestamps_populated=True,
    ),
    _RelMetadataCase(
        name="all",
        flags=MetadataOptions.IS_PROTECTED | MetadataOptions.LINKED_NODES | MetadataOptions.USER_TIMESTAMPS,
        expect_is_protected_populated=True,
        expect_source_populated=True,
        expect_owner_populated=True,
        expect_timestamps_populated=True,
    ),
]


class TestGetManyPrefetchRelationshipMetadataFiltering:
    """`include_metadata` selectively populates relationship metadata under prefetch"""

    @pytest.fixture(scope="class", autouse=True)
    async def _schema(self, db: InfrahubDatabase, default_branch_scope_class: Branch) -> SchemaBranch:
        return registry.schema.register_schema(
            schema=do_car_person_schema_unregistered(), branch=default_branch_scope_class.name
        )

    @pytest.fixture(scope="class")
    async def fixture_data(
        self, db: InfrahubDatabase, default_branch_scope_class: Branch, _schema: SchemaBranch
    ) -> dict[str, Node]:
        owner_node = await Node.init(db=db, schema="TestPerson")
        await owner_node.new(db=db, name="Owner", height=180)
        await owner_node.save(db=db)

        source_node = await Node.init(db=db, schema="TestPerson")
        await source_node.new(db=db, name="Source", height=170)
        await source_node.save(db=db)

        driver = await Node.init(db=db, schema="TestPerson")
        await driver.new(db=db, name="Driver", height=190)
        await driver.save(db=db)

        car = await Node.init(db=db, schema="TestCar")
        await car.new(
            db=db,
            name="volt",
            nbr_seats=4,
            is_electric=True,
            owner={
                "id": driver.id,
                "_relation__is_protected": True,
                "_relation__source": source_node.id,
                "_relation__owner": owner_node.id,
            },
        )
        await car.save(db=db)
        return {"car": car, "driver": driver, "source": source_node, "owner": owner_node}

    @pytest.mark.parametrize("case", [pytest.param(c, id=c.name) for c in _REL_METADATA_CASES])
    async def test_get_many_prefetch_metadata_filtering(
        self,
        db: InfrahubDatabase,
        default_branch_scope_class: Branch,
        fixture_data: dict[str, Node],
        case: _RelMetadataCase,
    ) -> None:
        car = fixture_data["car"]
        driver = fixture_data["driver"]
        source_node = fixture_data["source"]
        owner_node = fixture_data["owner"]

        nodes = await NodeManager.get_many(
            db=db,
            ids=[car.id],
            prefetch_relationships=True,
            include_metadata=MetadataQueryOptions(relationship_level=case.flags),
        )

        assert car.id in nodes
        rel = await nodes[car.id].get_relationship("owner").get(db=db)
        assert rel is not None
        assert isinstance(rel, Relationship)
        assert rel.peer_id == driver.id

        # is_protected: defaults to False on FlagPropertyMixin; we set it to True
        if case.expect_is_protected_populated:
            assert rel.is_protected is True
        else:
            assert rel.is_protected is False

        if case.expect_source_populated:
            assert rel.source_id == source_node.id
        else:
            assert rel.source_id is None

        if case.expect_owner_populated:
            assert rel.owner_id == owner_node.id
        else:
            assert rel.owner_id is None

        if case.expect_timestamps_populated:
            assert rel._get_updated_at() is not None
            assert rel._get_updated_by() is not None
            assert rel._get_created_at() is not None
            assert rel._get_created_by() is not None
        else:
            assert rel._get_updated_at() is None
            assert rel._get_updated_by() is None
            assert rel._get_created_at() is None
            assert rel._get_created_by() is None


class TestGetManyPrefetchRelationshipMetadataCleared:
    """Cleared LINKED_NODES values must surface as None under prefetch.

    Two paths exercise the same prefetch query: clearing on the same branch where
    the relationship was created, and clearing on a feature branch and merging back.
    """

    @pytest.fixture(autouse=True)
    async def _schema(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        register_core_models_schema: SchemaBranch,
    ) -> SchemaBranch:
        return registry.schema.register_schema(schema=do_car_person_schema_unregistered(), branch=default_branch.name)

    async def _get_diff_coordinator(self, db: InfrahubDatabase, branch: Branch) -> DiffCoordinator:
        component_registry = get_component_registry()
        diff_coordinator = await component_registry.get_component(DiffCoordinator, db=db, branch=branch)
        diff_coordinator.data_check_synchronizer = AsyncMock(spec=DiffDataCheckSynchronizer)
        return diff_coordinator

    async def _get_diff_merger(self, db: InfrahubDatabase, branch: Branch) -> DiffMerger:
        component_registry = get_component_registry()
        return await component_registry.get_component(DiffMerger, db=db, branch=branch)

    async def _build_car(self, db: InfrahubDatabase, branch: Branch) -> dict[str, Node]:
        owner_person = await Node.init(db=db, schema="TestPerson", branch=branch)
        await owner_person.new(db=db, name="Owner", height=180)
        await owner_person.save(db=db)

        source_person = await Node.init(db=db, schema="TestPerson", branch=branch)
        await source_person.new(db=db, name="Source", height=170)
        await source_person.save(db=db)

        driver = await Node.init(db=db, schema="TestPerson", branch=branch)
        await driver.new(db=db, name="Driver", height=190)
        await driver.save(db=db)

        car = await Node.init(db=db, schema="TestCar", branch=branch)
        await car.new(
            db=db,
            name="volt",
            nbr_seats=4,
            is_electric=True,
            owner={
                "id": driver.id,
                "_relation__source": source_person.id,
                "_relation__owner": owner_person.id,
            },
        )
        await car.save(db=db)
        return {"car": car, "driver": driver, "source": source_person, "owner": owner_person}

    async def _assert_cleared(self, db: InfrahubDatabase, branch: Branch, car_id: str, driver_id: str) -> None:
        nodes = await NodeManager.get_many(
            db=db,
            ids=[car_id],
            branch=branch,
            prefetch_relationships=True,
            include_metadata=MetadataQueryOptions(relationship_level=MetadataOptions.LINKED_NODES),
        )
        rel = await nodes[car_id].get_relationship("owner").get(db=db)
        assert isinstance(rel, Relationship)
        assert rel.peer_id == driver_id
        assert rel.source_id is None
        assert rel.owner_id is None

    async def test_cleared_source_owner_same_branch(self, db: InfrahubDatabase, default_branch: Branch) -> None:
        fixture = await self._build_car(db=db, branch=default_branch)
        car = fixture["car"]
        driver = fixture["driver"]

        car_reloaded = await NodeManager.get_one(db=db, branch=default_branch, id=car.id)
        owner_rel = (await car_reloaded.get_relationship("owner").get_relationships(db=db))[0]
        owner_rel.clear_source()
        owner_rel.clear_owner()
        await car_reloaded.save(db=db)

        await self._assert_cleared(db=db, branch=default_branch, car_id=car.id, driver_id=driver.id)
