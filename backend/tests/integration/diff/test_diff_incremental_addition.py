from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import uuid4

import pytest

from infrahub.core.constants import (
    DiffAction,
    RelationshipCardinality,
)
from infrahub.core.constants.database import DatabaseEdgeType
from infrahub.core.diff.coordinator import DiffCoordinator
from infrahub.core.initialization import create_branch
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.core.timestamp import Timestamp
from infrahub.dependencies.registry import get_component_registry
from infrahub.services.adapters.cache.redis import RedisCache
from tests.constants import TestKind
from tests.helpers.schema import CAR_SCHEMA, load_schema
from tests.helpers.test_app import TestInfrahubApp

if TYPE_CHECKING:
    from infrahub_sdk import InfrahubClient

    from infrahub.core.branch import Branch
    from infrahub.core.diff.model.path import EnrichedDiffRoot
    from infrahub.database import InfrahubDatabase
    from tests.adapters.message_bus import BusSimulator

BRANCH_NAME = "branch1"
PROPOSED_CHANGE_NAME = "branch1-pc"


class TestDiffUpdateConflict(TestInfrahubApp):
    @pytest.fixture(scope="class")
    async def initial_dataset(
        self,
        db: InfrahubDatabase,
        default_branch,
        client: InfrahubClient,
        bus_simulator: BusSimulator,
    ) -> dict[str, Node]:
        await load_schema(db, schema=CAR_SCHEMA)
        doc_brown = await Node.init(schema=TestKind.PERSON, db=db)
        await doc_brown.new(db=db, name="Doc Brown", height=175)
        await doc_brown.save(db=db)
        marty = await Node.init(schema=TestKind.PERSON, db=db)
        await marty.new(db=db, name="Marty McFly", height=155)
        await marty.save(db=db)
        biff = await Node.init(schema=TestKind.PERSON, db=db)
        await biff.new(db=db, name="Biff... something", height=177)
        await biff.save(db=db)
        dmc = await Node.init(schema=TestKind.MANUFACTURER, db=db)
        await dmc.new(db=db, name="DMC")
        await dmc.save(db=db)
        delorean = await Node.init(schema=TestKind.CAR, db=db)
        await delorean.new(
            db=db,
            name="Delorean",
            color="Silver",
            description="time-travelling coupe",
            owner=doc_brown,
            manufacturer=dmc,
        )
        await delorean.save(db=db)
        await delorean.previous_owner.update(db=db, data={"id": doc_brown.id, "_relation__is_protected": True})  # type: ignore[attr-defined]
        await delorean.save(db=db)

        bus_simulator.service.cache = RedisCache()

        return {
            "doc_brown": doc_brown,
            "marty": marty,
            "biff": biff,
            "dmc": dmc,
            "delorean": delorean,
        }

    @pytest.fixture(scope="class")
    async def diff_branch(self, db: InfrahubDatabase, initial_dataset) -> Branch:
        return await create_branch(db=db, branch_name=BRANCH_NAME)

    @pytest.fixture(scope="class")
    async def diff_coordinator(self, db: InfrahubDatabase, diff_branch: Branch) -> DiffCoordinator:
        component_registry = get_component_registry()
        return await component_registry.get_component(DiffCoordinator, db=db, branch=diff_branch)

    @pytest.fixture(scope="class")
    async def data_01_remove_on_main(
        self,
        db: InfrahubDatabase,
        initial_dataset,
        default_branch: Branch,
        diff_branch: Branch,
    ) -> None:
        delorean_id = initial_dataset["delorean"].get_id()

        delorean_main = await NodeManager.get_one(db=db, branch=default_branch, id=delorean_id)
        await delorean_main.previous_owner.update(db=db, data=[None])
        await delorean_main.save(db=db)

    @pytest.fixture(scope="class")
    async def data_02_previous_owner_on_branch(
        self,
        db: InfrahubDatabase,
        initial_dataset,
        default_branch: Branch,
        diff_branch: Branch,
        data_01_remove_on_main,
    ) -> None:
        delorean = initial_dataset["delorean"]
        marty = initial_dataset["marty"]

        delorean_branch = await NodeManager.get_one(db=db, branch=diff_branch, id=delorean.get_id())
        await delorean_branch.previous_owner.update(
            db=db, data=[{"id": marty.get_id(), "_relation__is_protected": False}]
        )
        await delorean_branch.save(db=db)

    @pytest.fixture(scope="class")
    async def data_03_new_peer_on_main(
        self,
        db: InfrahubDatabase,
        initial_dataset,
        default_branch: Branch,
        diff_branch: Branch,
        data_02_previous_owner_on_branch,
    ) -> None:
        delorean = initial_dataset["delorean"]
        biff = initial_dataset["biff"]

        delorean_main = await NodeManager.get_one(db=db, branch=default_branch, id=delorean.get_id())
        await delorean_main.previous_owner.update(db=db, data=[{"id": biff.get_id(), "_relation__is_protected": True}])
        await delorean_main.save(db=db)

    @pytest.fixture(scope="class")
    async def data_04_update_previous_owner_protected_on_branch(
        self,
        db: InfrahubDatabase,
        initial_dataset,
        default_branch: Branch,
        diff_branch: Branch,
        data_03_new_peer_on_main,
    ) -> None:
        delorean = initial_dataset["delorean"]
        marty = initial_dataset["marty"]

        delorean_branch = await NodeManager.get_one(db=db, branch=diff_branch, id=delorean.get_id())
        await delorean_branch.previous_owner.update(
            db=db, data=[{"id": marty.get_id(), "_relation__is_protected": True}]
        )
        await delorean_branch.save(db=db)

    @pytest.fixture(scope="class")
    async def data_05_remove_previous_owner_on_branch(
        self,
        db: InfrahubDatabase,
        initial_dataset,
        default_branch: Branch,
        diff_branch: Branch,
        data_04_update_previous_owner_protected_on_branch,
    ) -> None:
        delorean = initial_dataset["delorean"]

        delorean_branch = await NodeManager.get_one(db=db, branch=diff_branch, id=delorean.get_id())
        await delorean_branch.previous_owner.update(db=db, data=[None])
        await delorean_branch.save(db=db)

    @pytest.fixture(scope="class")
    async def data_06_remove_previous_owner_on_main_again(
        self,
        db: InfrahubDatabase,
        initial_dataset,
        default_branch: Branch,
        diff_branch: Branch,
        data_05_remove_previous_owner_on_branch,
    ) -> None:
        delorean = initial_dataset["delorean"]

        delorean_main = await NodeManager.get_one(db=db, branch=default_branch, id=delorean.get_id())
        await delorean_main.previous_owner.update(db=db, data=[None])
        await delorean_main.save(db=db)

    async def test_remove_on_main(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        diff_branch: Branch,
        diff_coordinator: DiffCoordinator,
        data_01_remove_on_main,
    ) -> None:
        enriched_diff = await diff_coordinator.update_branch_diff(base_branch=default_branch, diff_branch=diff_branch)

        assert len(enriched_diff.nodes) == 0

    async def validate_diff_data_02(
        self,
        db: InfrahubDatabase,
        enriched_diff: EnrichedDiffRoot,
        initial_dataset: dict[str, Node],
    ):
        delorean = initial_dataset["delorean"]
        marty = initial_dataset["marty"]
        doc_brown = initial_dataset["doc_brown"]
        marty_label = await marty.render_display_label(db=db)
        delorean_label = await delorean.render_display_label(db=db)

        assert len(enriched_diff.nodes) == 1
        node = enriched_diff.nodes.pop()
        assert node.uuid == delorean.get_id()
        assert node.label == delorean_label
        assert node.action is DiffAction.UPDATED
        assert len(node.attributes) == 0
        assert len(node.relationships) == 1
        previous_owner_rel = node.relationships.pop()
        assert previous_owner_rel.name == "previous_owner"
        assert previous_owner_rel.action is DiffAction.UPDATED
        assert previous_owner_rel.cardinality is RelationshipCardinality.ONE
        assert len(previous_owner_rel.relationships) == 1
        rel_element = previous_owner_rel.relationships.pop()
        assert rel_element.peer_id == marty.get_id()
        assert rel_element.peer_label == marty_label
        assert rel_element.action is DiffAction.UPDATED
        assert rel_element.conflict
        assert rel_element.conflict.base_branch_action is DiffAction.REMOVED
        assert rel_element.conflict.base_branch_value is None
        assert rel_element.conflict.diff_branch_action is DiffAction.UPDATED
        assert rel_element.conflict.diff_branch_value == marty.get_id()
        properties_by_type = {p.property_type: p for p in rel_element.properties}
        # is_visible is still true, although on a different peeer
        assert set(properties_by_type.keys()) == {DatabaseEdgeType.IS_RELATED, DatabaseEdgeType.IS_PROTECTED}
        related_prop = properties_by_type[DatabaseEdgeType.IS_RELATED]
        assert related_prop.previous_value == doc_brown.get_id()
        assert related_prop.new_value == marty.get_id()
        assert related_prop.action is DiffAction.UPDATED
        assert related_prop.conflict is None
        protected_prop = properties_by_type[DatabaseEdgeType.IS_PROTECTED]
        assert protected_prop.previous_value == "True"
        assert protected_prop.new_value == "False"
        assert protected_prop.action is DiffAction.UPDATED
        assert protected_prop.conflict
        assert protected_prop.conflict.base_branch_action is DiffAction.REMOVED
        assert protected_prop.conflict.base_branch_value is None
        assert protected_prop.conflict.diff_branch_action is DiffAction.UPDATED
        assert protected_prop.conflict.diff_branch_value == "False"

    async def test_update_previous_owner_on_branch(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        diff_branch: Branch,
        diff_coordinator: DiffCoordinator,
        initial_dataset,
        data_02_previous_owner_on_branch,
    ) -> None:
        incremental_diff = await diff_coordinator.update_branch_diff(
            base_branch=default_branch, diff_branch=diff_branch
        )
        await self.validate_diff_data_02(db=db, enriched_diff=incremental_diff, initial_dataset=initial_dataset)
        full_diff = await diff_coordinator.create_or_update_arbitrary_timeframe_diff(
            base_branch=default_branch,
            diff_branch=diff_branch,
            from_time=incremental_diff.from_time,
            to_time=incremental_diff.to_time,
            name=str(uuid4),
        )
        await self.validate_diff_data_02(db=db, enriched_diff=full_diff, initial_dataset=initial_dataset)

    async def validate_diff_data_03(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        enriched_diff: EnrichedDiffRoot,
        initial_dataset: dict[str, Node],
    ):
        delorean = initial_dataset["delorean"]
        doc_brown = initial_dataset["doc_brown"]
        marty = initial_dataset["marty"]
        biff = initial_dataset["biff"]
        marty_label = await marty.render_display_label(db=db)
        delorean_main = await NodeManager.get_one(db=db, branch=default_branch, id=delorean.get_id())
        delorean_label = await delorean_main.render_display_label(db=db)

        assert len(enriched_diff.nodes) == 1
        node = enriched_diff.nodes.pop()
        assert node.uuid == delorean.get_id()
        assert node.label == delorean_label
        assert node.action is DiffAction.UPDATED
        assert len(node.attributes) == 0
        assert len(node.relationships) == 1
        previous_owner_rel = node.relationships.pop()
        assert previous_owner_rel.name == "previous_owner"
        assert previous_owner_rel.action is DiffAction.UPDATED
        assert previous_owner_rel.cardinality is RelationshipCardinality.ONE
        assert len(previous_owner_rel.relationships) == 1
        rel_element = previous_owner_rel.relationships.pop()
        assert rel_element.peer_id == marty.get_id()
        assert rel_element.peer_label == marty_label
        assert rel_element.action is DiffAction.UPDATED
        assert rel_element.conflict
        assert rel_element.conflict.base_branch_action is DiffAction.UPDATED
        assert rel_element.conflict.base_branch_value == biff.get_id()
        assert rel_element.conflict.diff_branch_action is DiffAction.UPDATED
        assert rel_element.conflict.diff_branch_value == marty.get_id()
        properties_by_type = {p.property_type: p for p in rel_element.properties}
        # is_visible is still true, although on a different peeer
        assert set(properties_by_type.keys()) == {DatabaseEdgeType.IS_RELATED, DatabaseEdgeType.IS_PROTECTED}
        related_prop = properties_by_type[DatabaseEdgeType.IS_RELATED]
        assert related_prop.previous_value == doc_brown.get_id()
        assert related_prop.new_value == marty.get_id()
        assert related_prop.action is DiffAction.UPDATED
        assert related_prop.conflict is None
        protected_prop = properties_by_type[DatabaseEdgeType.IS_PROTECTED]
        assert protected_prop.previous_value == "True"
        assert str(protected_prop.new_value) == "False"
        assert protected_prop.action is DiffAction.UPDATED
        assert protected_prop.conflict
        assert protected_prop.conflict.base_branch_action is DiffAction.UPDATED
        assert str(protected_prop.conflict.base_branch_value) == "True"
        assert protected_prop.conflict.diff_branch_action is DiffAction.UPDATED
        assert str(protected_prop.conflict.diff_branch_value) == "False"

    async def test_add_new_peer_on_main(
        self,
        db: InfrahubDatabase,
        initial_dataset,
        default_branch: Branch,
        diff_branch: Branch,
        diff_coordinator: DiffCoordinator,
        data_03_new_peer_on_main,
    ) -> None:
        incremental_diff = await diff_coordinator.update_branch_diff(
            base_branch=default_branch, diff_branch=diff_branch
        )
        await self.validate_diff_data_03(
            db=db, default_branch=default_branch, enriched_diff=incremental_diff, initial_dataset=initial_dataset
        )
        full_diff = await diff_coordinator.create_or_update_arbitrary_timeframe_diff(
            base_branch=default_branch,
            diff_branch=diff_branch,
            from_time=Timestamp(diff_branch.branched_from),
            to_time=Timestamp(),
            name=str(uuid4),
        )
        await self.validate_diff_data_03(
            db=db, default_branch=default_branch, enriched_diff=full_diff, initial_dataset=initial_dataset
        )

    async def validate_diff_data_04(
        self,
        db: InfrahubDatabase,
        enriched_diff: EnrichedDiffRoot,
        initial_dataset: dict[str, Node],
    ):
        delorean = initial_dataset["delorean"]
        marty = initial_dataset["marty"]
        doc_brown = initial_dataset["doc_brown"]
        biff = initial_dataset["biff"]
        marty_label = await marty.render_display_label(db=db)
        delorean_label = await delorean.render_display_label(db=db)

        assert len(enriched_diff.nodes) == 1
        node = enriched_diff.nodes.pop()
        assert node.uuid == delorean.get_id()
        assert node.label == delorean_label
        assert node.action is DiffAction.UPDATED
        assert len(node.attributes) == 0
        assert len(node.relationships) == 1
        previous_owner_rel = node.relationships.pop()
        assert previous_owner_rel.name == "previous_owner"
        assert previous_owner_rel.action is DiffAction.UPDATED
        assert previous_owner_rel.cardinality is RelationshipCardinality.ONE
        assert len(previous_owner_rel.relationships) == 1
        rel_element = previous_owner_rel.relationships.pop()
        assert rel_element.peer_id == marty.get_id()
        assert rel_element.peer_label == marty_label
        assert rel_element.action is DiffAction.UPDATED
        assert rel_element.conflict
        assert rel_element.conflict.base_branch_action is DiffAction.UPDATED
        assert rel_element.conflict.base_branch_value == biff.get_id()
        assert rel_element.conflict.diff_branch_action is DiffAction.UPDATED
        assert rel_element.conflict.diff_branch_value == marty.get_id()
        properties_by_type = {p.property_type: p for p in rel_element.properties}
        # is_visible is still true, although on a different peeer
        assert set(properties_by_type.keys()) == {DatabaseEdgeType.IS_RELATED, DatabaseEdgeType.IS_PROTECTED}
        related_prop = properties_by_type[DatabaseEdgeType.IS_RELATED]
        assert related_prop.previous_value == doc_brown.get_id()
        assert related_prop.new_value == marty.get_id()
        assert related_prop.action is DiffAction.UPDATED
        assert related_prop.conflict is None
        protected_prop = properties_by_type[DatabaseEdgeType.IS_PROTECTED]
        assert protected_prop.previous_value == "True"
        assert protected_prop.new_value == "True"
        assert protected_prop.action is DiffAction.UPDATED
        # no conflict b/c both have been updated to the same value
        assert protected_prop.conflict is None

    async def test_update_previous_owner_protected_on_branch(
        self,
        db: InfrahubDatabase,
        initial_dataset,
        default_branch: Branch,
        diff_branch: Branch,
        diff_coordinator: DiffCoordinator,
        data_04_update_previous_owner_protected_on_branch,
    ) -> None:
        incremental_diff = await diff_coordinator.update_branch_diff(
            base_branch=default_branch, diff_branch=diff_branch
        )
        await self.validate_diff_data_04(db=db, enriched_diff=incremental_diff, initial_dataset=initial_dataset)
        full_diff = await diff_coordinator.create_or_update_arbitrary_timeframe_diff(
            base_branch=default_branch,
            diff_branch=diff_branch,
            from_time=Timestamp(diff_branch.branched_from),
            to_time=Timestamp(),
            name=str(uuid4),
        )
        await self.validate_diff_data_04(db=db, enriched_diff=full_diff, initial_dataset=initial_dataset)

    async def validate_diff_data_05(
        self,
        db: InfrahubDatabase,
        enriched_diff: EnrichedDiffRoot,
        initial_dataset: dict[str, Node],
    ):
        delorean = initial_dataset["delorean"]
        doc_brown = initial_dataset["doc_brown"]
        biff = initial_dataset["biff"]
        doc_brown_label = await doc_brown.render_display_label(db=db)
        delorean_label = await delorean.render_display_label(db=db)

        assert len(enriched_diff.nodes) == 1
        node = enriched_diff.nodes.pop()
        assert node.uuid == delorean.get_id()
        assert node.label == delorean_label
        assert node.action is DiffAction.UPDATED
        assert len(node.attributes) == 0
        assert len(node.relationships) == 1
        previous_owner_rel = node.relationships.pop()
        assert previous_owner_rel.name == "previous_owner"
        assert previous_owner_rel.action is DiffAction.REMOVED
        assert previous_owner_rel.cardinality is RelationshipCardinality.ONE
        assert len(previous_owner_rel.relationships) == 1
        rel_element = previous_owner_rel.relationships.pop()
        # peer ID and label should point to latest pre-branch value on main b/c branch update has been removed
        assert rel_element.peer_id == doc_brown.get_id()
        assert rel_element.peer_label == doc_brown_label
        assert rel_element.action is DiffAction.REMOVED
        assert rel_element.conflict
        assert rel_element.conflict.base_branch_action is DiffAction.UPDATED
        assert rel_element.conflict.base_branch_value == biff.get_id()
        assert rel_element.conflict.diff_branch_action is DiffAction.REMOVED
        assert rel_element.conflict.diff_branch_value is None
        properties_by_type = {p.property_type: p for p in rel_element.properties}
        # is_visible is still true, although on a different peeer
        assert set(properties_by_type.keys()) == {
            DatabaseEdgeType.IS_RELATED,
            DatabaseEdgeType.IS_PROTECTED,
            DatabaseEdgeType.IS_VISIBLE,
        }
        related_prop = properties_by_type[DatabaseEdgeType.IS_RELATED]
        assert related_prop.previous_value == doc_brown.get_id()
        assert related_prop.new_value is None
        assert related_prop.action is DiffAction.REMOVED
        assert related_prop.conflict is None
        for prop_type in (DatabaseEdgeType.IS_PROTECTED, DatabaseEdgeType.IS_VISIBLE):
            protected_prop = properties_by_type[prop_type]
            assert protected_prop.previous_value == "True"
            assert protected_prop.new_value is None
            assert protected_prop.action is DiffAction.REMOVED
            assert protected_prop.conflict
            assert protected_prop.conflict.base_branch_action is DiffAction.UPDATED
            assert protected_prop.conflict.base_branch_value == "True"
            assert protected_prop.conflict.diff_branch_action is DiffAction.REMOVED
            assert protected_prop.conflict.diff_branch_value is None

    async def test_remove_previous_owner_on_branch(
        self,
        db: InfrahubDatabase,
        initial_dataset,
        default_branch: Branch,
        diff_branch: Branch,
        diff_coordinator: DiffCoordinator,
        data_05_remove_previous_owner_on_branch,
    ) -> None:
        incremental_diff = await diff_coordinator.update_branch_diff(
            base_branch=default_branch, diff_branch=diff_branch
        )
        await self.validate_diff_data_05(db=db, enriched_diff=incremental_diff, initial_dataset=initial_dataset)
        full_diff = await diff_coordinator.create_or_update_arbitrary_timeframe_diff(
            base_branch=default_branch,
            diff_branch=diff_branch,
            from_time=Timestamp(diff_branch.branched_from),
            to_time=Timestamp(),
            name=str(uuid4),
        )
        await self.validate_diff_data_05(db=db, enriched_diff=full_diff, initial_dataset=initial_dataset)

    async def validate_diff_data_06(
        self,
        db: InfrahubDatabase,
        enriched_diff: EnrichedDiffRoot,
        initial_dataset: dict[str, Node],
    ):
        delorean = initial_dataset["delorean"]
        doc_brown = initial_dataset["doc_brown"]
        doc_brown_label = await doc_brown.render_display_label(db=db)
        delorean_label = await delorean.render_display_label(db=db)

        assert len(enriched_diff.nodes) == 1
        node = enriched_diff.nodes.pop()
        assert node.uuid == delorean.get_id()
        assert node.label == delorean_label
        assert node.action is DiffAction.UPDATED
        assert len(node.attributes) == 0
        assert len(node.relationships) == 1
        previous_owner_rel = node.relationships.pop()
        assert previous_owner_rel.name == "previous_owner"
        assert previous_owner_rel.action is DiffAction.REMOVED
        assert previous_owner_rel.cardinality is RelationshipCardinality.ONE
        assert len(previous_owner_rel.relationships) == 1
        rel_element = previous_owner_rel.relationships.pop()
        # peer ID and label should point to latest pre-branch value on main b/c branch update has been removed
        assert rel_element.peer_id == doc_brown.get_id()
        assert rel_element.peer_label == doc_brown_label
        assert rel_element.action is DiffAction.REMOVED
        assert rel_element.conflict is None
        properties_by_type = {p.property_type: p for p in rel_element.properties}
        # is_visible is still true, although on a different peeer
        assert set(properties_by_type.keys()) == {
            DatabaseEdgeType.IS_RELATED,
            DatabaseEdgeType.IS_PROTECTED,
            DatabaseEdgeType.IS_VISIBLE,
        }
        related_prop = properties_by_type[DatabaseEdgeType.IS_RELATED]
        assert related_prop.previous_value == doc_brown.get_id()
        assert related_prop.new_value is None
        assert related_prop.action is DiffAction.REMOVED
        assert related_prop.conflict is None
        for prop_type in (DatabaseEdgeType.IS_PROTECTED, DatabaseEdgeType.IS_VISIBLE):
            protected_prop = properties_by_type[prop_type]
            assert protected_prop.previous_value == "True"
            assert protected_prop.new_value is None
            assert protected_prop.action is DiffAction.REMOVED
            assert protected_prop.conflict is None

    async def test_remove_previous_owner_on_main_again(
        self,
        db: InfrahubDatabase,
        initial_dataset,
        default_branch: Branch,
        diff_branch: Branch,
        diff_coordinator: DiffCoordinator,
        data_06_remove_previous_owner_on_main_again,
    ) -> None:
        incremental_diff = await diff_coordinator.update_branch_diff(
            base_branch=default_branch, diff_branch=diff_branch
        )
        await self.validate_diff_data_06(db=db, enriched_diff=incremental_diff, initial_dataset=initial_dataset)
        full_diff = await diff_coordinator.create_or_update_arbitrary_timeframe_diff(
            base_branch=default_branch,
            diff_branch=diff_branch,
            from_time=Timestamp(diff_branch.branched_from),
            to_time=Timestamp(),
            name=str(uuid4),
        )
        await self.validate_diff_data_06(db=db, enriched_diff=full_diff, initial_dataset=initial_dataset)
