from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from infrahub import lock
from infrahub.core import registry
from infrahub.core.branch import Branch
from infrahub.core.constants import (
    DiffAction,
    HashableModelState,
    InfrahubKind,
    RelationshipCardinality,
    RelationshipKind,
)
from infrahub.core.constants.database import DatabaseEdgeType
from infrahub.core.diff.model.path import BranchTrackingId, FrozenTrackingId
from infrahub.core.diff.repository.repository import DiffRepository
from infrahub.core.initialization import create_branch
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.core.schema import RelationshipSchema, SchemaRoot
from infrahub.core.timestamp import Timestamp
from infrahub.dependencies.registry import get_component_registry
from tests.constants import TestKind
from tests.helpers.schema import CAR_SCHEMA, load_schema
from tests.helpers.schema.location import CONTINENT, LOCATION
from tests.helpers.test_app import TestInfrahubApp

if TYPE_CHECKING:
    from infrahub_sdk import InfrahubClient

    from infrahub.database import InfrahubDatabase
    from tests.adapters.message_bus import BusSimulator


DIFF_UPDATE_QUERY = """
mutation DiffUpdate($branch_name: String!, $wait_for_completion: Boolean) {
    DiffUpdate(data: { branch: $branch_name, wait_for_completion: $wait_for_completion }) {
        ok
    }
}
"""

BRANCH_MERGE = """
mutation($branch: String!) {
    BranchMerge(data: { name: $branch }) {
        ok
    }
}
"""

CONFLICT_SELECTION_QUERY = """
mutation ResolveDiffConflict($conflict_id: String!, $selected_branch: ConflictSelection!) {
    ResolveDiffConflict(data: { conflict_id: $conflict_id, selected_branch: $selected_branch }) {
        ok
    }
}
"""

BRANCH_REBASE = """
mutation($branch: String!) {
    BranchRebase(data: { name: $branch }) {
        ok
    }
}
"""


class TestDiffRebase(TestInfrahubApp):
    @pytest.fixture(scope="class", autouse=True)
    def initialize_lock(self) -> None:
        lock.initialize_lock(local_only=True)

    @pytest.fixture(scope="class")
    def main_schema_root(self) -> SchemaRoot:
        main_schema_root = CAR_SCHEMA.model_copy()
        # add a Node and relationship to delete later
        main_schema_root.generics.append(LOCATION)
        continent_schema = CONTINENT.model_copy()
        continent_schema.children = None
        continent_schema.parent = None
        main_schema_root.nodes.append(continent_schema)
        manufacturer_schema = main_schema_root.get(TestKind.MANUFACTURER)
        manufacturer_schema.generate_profile = False
        manufacturer_schema.relationships.append(
            RelationshipSchema(
                name="continents",
                kind=RelationshipKind.GENERIC,
                peer=TestKind.CONTINENT,
                cardinality=RelationshipCardinality.MANY,
                identifier="continent__manufacturer",
            )
        )
        return main_schema_root

    @pytest.fixture(scope="class")
    async def initial_dataset(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        main_schema_root: SchemaRoot,
        client: InfrahubClient,
        bus_simulator: BusSimulator,
    ) -> dict[str, Node]:
        await load_schema(db, schema=main_schema_root, update_db=True)
        antarctica = await Node.init(schema=TestKind.CONTINENT, db=db)
        await antarctica.new(db=db, name="Antarctica", shortname="ANT")
        await antarctica.save(db=db)
        john = await Node.init(schema=TestKind.PERSON, db=db)
        await john.new(db=db, name="John", height=175, description="The famous Joe Doe")
        await john.save(db=db)
        kara = await Node.init(schema=TestKind.PERSON, db=db)
        await kara.new(db=db, name="Kara Thrace", height=165, description="Starbuck")
        await kara.save(db=db)
        murphy = await Node.init(schema=TestKind.PERSON, db=db)
        await murphy.new(db=db, name="Alex Murphy", height=185, description="Robocop")
        await murphy.save(db=db)
        koenigsegg = await Node.init(schema=TestKind.MANUFACTURER, db=db)
        await koenigsegg.new(db=db, name="Koenigsegg", customers=[john])
        await koenigsegg.save(db=db)
        omnicorp = await Node.init(schema=TestKind.MANUFACTURER, db=db)
        await omnicorp.new(db=db, name="Omnicorp", customers=[murphy], continents=[antarctica])
        await omnicorp.save(db=db)
        cyberdyne = await Node.init(schema=TestKind.MANUFACTURER, db=db)
        await cyberdyne.new(db=db, name="Cyberdyne")
        await cyberdyne.save(db=db)
        people = await Node.init(schema=InfrahubKind.STANDARDGROUP, db=db)
        await people.new(db=db, name="people", members=[john])
        await people.save(db=db)

        jesko = await Node.init(schema=TestKind.CAR, db=db)
        await jesko.new(
            db=db,
            name="Jesko",
            color="Red",
            description="A limited production mid-engine sports car",
            owner=john,
            manufacturer=koenigsegg,
        )
        await jesko.save(db=db)
        t_800 = await Node.init(schema=TestKind.CAR, db=db)
        await t_800.new(
            db=db,
            name="Cyberdyne systems model 101",
            color="Chrome",
            description="killing machine with secret heart of gold",
            owner=john,
            manufacturer=cyberdyne,
        )
        await t_800.save(db=db)
        ed_209 = await Node.init(schema=TestKind.CAR, db=db)
        await ed_209.new(
            db=db,
            name="ED-209",
            color="Chrome",
            description="still working on doing stairs",
            owner=john,
            manufacturer=omnicorp,
        )
        await ed_209.save(db=db)

        return {
            "antarctica": antarctica,
            "john": john,
            "kara": kara,
            "murphy": murphy,
            "koenigsegg": koenigsegg,
            "omnicorp": omnicorp,
            "cyberdyne": cyberdyne,
            "people": people,
            "jesko": jesko,
            "t_800": t_800,
            "ed_209": ed_209,
        }

    @pytest.fixture(scope="class")
    async def branch_1(self, db: InfrahubDatabase) -> Branch:
        return await create_branch(branch_name="branch_1", db=db)

    @pytest.fixture(scope="class")
    async def branch_2(self, db: InfrahubDatabase) -> Branch:
        return await create_branch(branch_name="branch_2", db=db)

    @pytest.fixture(scope="class")
    async def branch_3(self, db: InfrahubDatabase) -> Branch:
        return await create_branch(branch_name="branch_3", db=db)

    @pytest.fixture(scope="class")
    async def diff_repository(self, db: InfrahubDatabase, default_branch: Branch) -> DiffRepository:
        component_registry = get_component_registry()
        return await component_registry.get_component(DiffRepository, db=db, branch=default_branch)

    @pytest.fixture(scope="class")
    async def add_branch_1_changes(
        self,
        db: InfrahubDatabase,
        client: InfrahubClient,
        default_branch: Branch,
        initial_dataset: dict[str, Node],
        branch_1: Branch,
    ) -> None:
        kara_id = initial_dataset["kara"].id
        kara_branch_1 = await NodeManager.get_one(db=db, id=kara_id, branch=branch_1)
        kara_branch_1.description.value = "branch-1-description"
        await kara_branch_1.save(db=db)
        jesko_id = initial_dataset["jesko"].id
        cyberdyne_id = initial_dataset["cyberdyne"].id
        jesko_branch_1 = await NodeManager.get_one(db=db, id=jesko_id, branch=branch_1)
        await jesko_branch_1.manufacturer.update(db=db, data=cyberdyne_id)
        await jesko_branch_1.save(db=db)

        result = await client.execute_graphql(query=DIFF_UPDATE_QUERY, variables={"branch_name": branch_1.name})
        assert result["DiffUpdate"]["ok"]

    @pytest.fixture(scope="class")
    async def add_branch_2_changes(
        self,
        db: InfrahubDatabase,
        client: InfrahubClient,
        default_branch: Branch,
        initial_dataset: dict[str, Node],
        branch_2: Branch,
    ) -> None:
        kara_id = initial_dataset["kara"].id
        kara_branch_2 = await NodeManager.get_one(db=db, id=kara_id, branch=branch_2)
        kara_branch_2.description.value = "branch-2-description"
        await kara_branch_2.save(db=db)
        jesko_id = initial_dataset["jesko"].id
        omnicorp_id = initial_dataset["omnicorp"].id
        jesko_branch_2 = await NodeManager.get_one(db=db, id=jesko_id, branch=branch_2)
        await jesko_branch_2.manufacturer.update(db=db, data=omnicorp_id)
        await jesko_branch_2.save(db=db)

        result = await client.execute_graphql(query=DIFF_UPDATE_QUERY, variables={"branch_name": branch_2.name})
        assert result["DiffUpdate"]["ok"]

    @pytest.fixture(scope="class")
    async def add_branch_3_changes(
        self,
        db: InfrahubDatabase,
        client: InfrahubClient,
        default_branch: Branch,
        initial_dataset: dict[str, Node],
        branch_3: Branch,
    ) -> None:
        antarctica_id = initial_dataset["antarctica"].id
        antarctica_branch_1 = await NodeManager.get_one(db=db, id=antarctica_id, branch=branch_3)
        await antarctica_branch_1.delete(db=db)

        # delete a node schema with a relationship
        branch_3_schema = await registry.schema.load_schema_from_db(db=db, branch=branch_3.name)

        continent_schema = branch_3_schema.get(name=TestKind.CONTINENT, duplicate=True)
        continent_schema.state = HashableModelState.ABSENT
        manufacturer_schema = branch_3_schema.get(name=TestKind.MANUFACTURER, duplicate=True)
        manufactuer_continent_rel = manufacturer_schema.get_relationship("continents")
        manufactuer_continent_rel.state = HashableModelState.ABSENT
        schemas_to_load = {"version": "1.0", "nodes": [continent_schema.model_dump(), manufacturer_schema.model_dump()]}
        response = await client.schema.load(schemas=[schemas_to_load], branch=branch_3.name, wait_until_converged=True)
        assert not response.errors
        assert response.schema_updated

        retrieved_branch_3_schema = await registry.schema.load_schema_from_db(db=db, branch=branch_3.name)
        assert not retrieved_branch_3_schema.has(name=TestKind.CONTINENT)
        manufacturer_schema = retrieved_branch_3_schema.get(name=TestKind.MANUFACTURER)
        assert "continents" not in manufacturer_schema.relationship_names

    async def test_no_conflicts_before_merge(
        self,
        db: InfrahubDatabase,
        initial_dataset: dict[str, Node],
        add_branch_1_changes: None,
        add_branch_2_changes: None,
        branch_1: Branch,
        branch_2: Branch,
        diff_repository: DiffRepository,
    ) -> None:
        kara_id = initial_dataset["kara"].id
        jesko_id = initial_dataset["jesko"].id
        koenigsegg_id = initial_dataset["koenigsegg"].id
        cyberdyne_id = initial_dataset["cyberdyne"].id
        omnicorp_id = initial_dataset["omnicorp"].id

        branch_1_diff = await diff_repository.get_one(
            diff_branch_name=branch_1.name, tracking_id=BranchTrackingId(name=branch_1.name)
        )
        branch_2_diff = await diff_repository.get_one(
            diff_branch_name=branch_2.name, tracking_id=BranchTrackingId(name=branch_2.name)
        )
        for new_desc_value, new_peer_id, branch_diff in [
            ("branch-1-description", cyberdyne_id, branch_1_diff),
            ("branch-2-description", omnicorp_id, branch_2_diff),
        ]:
            assert len(branch_diff.nodes) == 4
            nodes_by_id = {n.uuid: n for n in branch_diff.nodes}
            assert set(nodes_by_id.keys()) == {kara_id, jesko_id, koenigsegg_id, new_peer_id}
            kara_node = nodes_by_id[kara_id]
            assert len(kara_node.attributes) == 1
            description_attr = kara_node.attributes.pop()
            assert description_attr.name == "description"
            assert len(description_attr.properties) == 1
            value_prop = description_attr.properties.pop()
            assert value_prop.action is DiffAction.UPDATED
            assert value_prop.property_type is DatabaseEdgeType.HAS_VALUE
            assert value_prop.previous_value == "Starbuck"
            assert value_prop.new_value == new_desc_value
            assert value_prop.conflict is None
            jesko_node = nodes_by_id[jesko_id]
            assert len(jesko_node.relationships) == 1
            manufacturer_rel = jesko_node.relationships.pop()
            assert manufacturer_rel.name == "manufacturer"
            assert len(manufacturer_rel.relationships) == 1
            manufacturer_element = manufacturer_rel.relationships.pop()
            assert manufacturer_element.peer_id == new_peer_id
            assert manufacturer_element.action is DiffAction.UPDATED
            assert manufacturer_element.conflict is None
            properties_by_type = {p.property_type: p for p in manufacturer_element.properties}
            assert set(properties_by_type.keys()) == {
                DatabaseEdgeType.IS_RELATED,
                DatabaseEdgeType.IS_PROTECTED,
            }
            related_prop = properties_by_type[DatabaseEdgeType.IS_RELATED]
            assert related_prop.action is DiffAction.UPDATED
            assert related_prop.previous_value == koenigsegg_id
            assert related_prop.new_value == new_peer_id
            assert related_prop.conflict is None
            prop_type, value = (DatabaseEdgeType.IS_PROTECTED, "False")
            diff_prop = properties_by_type[prop_type]
            assert diff_prop.action is DiffAction.UNCHANGED
            assert diff_prop.previous_value == diff_prop.new_value == value
            for manufacturer_id, expected_action in (
                (koenigsegg_id, DiffAction.REMOVED),
                (new_peer_id, DiffAction.ADDED),
            ):
                manufacturer_node = nodes_by_id[manufacturer_id]
                assert len(manufacturer_node.relationships) == 1
                cars_rel = manufacturer_node.relationships.pop()
                assert cars_rel.name == "cars"
                assert cars_rel.action is DiffAction.UPDATED
                assert len(cars_rel.relationships) == 1
                cars_element = cars_rel.relationships.pop()
                assert cars_element.peer_id == jesko_id
                assert cars_element.action is expected_action
                assert cars_element.conflict is None
                properties_by_type = {p.property_type: p for p in cars_element.properties}
                assert set(properties_by_type.keys()) == {
                    DatabaseEdgeType.IS_RELATED,
                    DatabaseEdgeType.IS_PROTECTED,
                }
                for property_type, check_value in (
                    (DatabaseEdgeType.IS_RELATED, jesko_id),
                    (DatabaseEdgeType.IS_PROTECTED, "False"),
                ):
                    prop_diff = properties_by_type[property_type]
                    assert prop_diff.action is expected_action
                    assert prop_diff.previous_value == (check_value if expected_action is DiffAction.REMOVED else None)
                    assert prop_diff.new_value == (check_value if expected_action is DiffAction.ADDED else None)
                    assert prop_diff.conflict is None

    async def test_merge_causes_diff_update(
        self,
        db: InfrahubDatabase,
        client: InfrahubClient,
        initial_dataset: dict[str, Node],
        add_branch_1_changes: None,
        branch_1: Branch,
        branch_2: Branch,
        diff_repository: DiffRepository,
    ) -> None:
        kara_id = initial_dataset["kara"].id
        jesko_id = initial_dataset["jesko"].id
        koenigsegg_id = initial_dataset["koenigsegg"].id
        cyberdyne_id = initial_dataset["cyberdyne"].id
        omnicorp_id = initial_dataset["omnicorp"].id
        before_merge = Timestamp()

        result = await client.execute_graphql(query=BRANCH_MERGE, variables={"branch": branch_1.name})
        assert result["BranchMerge"]["ok"]

        branch_2_diff = await diff_repository.get_one(
            diff_branch_name=branch_2.name, tracking_id=BranchTrackingId(name=branch_2.name)
        )

        assert len(branch_2_diff.nodes) == 4
        assert branch_2_diff.to_time > before_merge
        nodes_by_id = {n.uuid: n for n in branch_2_diff.nodes}
        kara_node = nodes_by_id[kara_id]
        assert len(kara_node.attributes) == 1
        description_attr = kara_node.attributes.pop()
        assert description_attr.name == "description"
        assert len(description_attr.properties) == 1
        value_prop = description_attr.properties.pop()
        assert value_prop.property_type is DatabaseEdgeType.HAS_VALUE
        assert value_prop.previous_value == "Starbuck"
        assert value_prop.new_value == "branch-2-description"
        assert value_prop.conflict
        assert value_prop.conflict.base_branch_action is DiffAction.UPDATED
        assert value_prop.conflict.base_branch_value == "branch-1-description"
        assert value_prop.conflict.diff_branch_action is DiffAction.UPDATED
        assert value_prop.conflict.diff_branch_value == "branch-2-description"
        jesko_node = nodes_by_id[jesko_id]
        assert len(jesko_node.relationships) == 1
        manufacturer_rel = jesko_node.relationships.pop()
        assert manufacturer_rel.name == "manufacturer"
        assert len(manufacturer_rel.relationships) == 1
        manufacturer_element = manufacturer_rel.relationships.pop()
        assert manufacturer_element.peer_id == omnicorp_id
        assert manufacturer_element.action is DiffAction.UPDATED
        assert manufacturer_element.conflict
        assert manufacturer_element.conflict.base_branch_action is DiffAction.UPDATED
        assert manufacturer_element.conflict.base_branch_value == cyberdyne_id
        assert manufacturer_element.conflict.diff_branch_action is DiffAction.UPDATED
        assert manufacturer_element.conflict.diff_branch_value == omnicorp_id
        properties_by_type = {p.property_type: p for p in manufacturer_element.properties}
        assert set(properties_by_type.keys()) == {
            DatabaseEdgeType.IS_RELATED,
            DatabaseEdgeType.IS_PROTECTED,
        }
        related_prop = properties_by_type[DatabaseEdgeType.IS_RELATED]
        assert related_prop.property_type is DatabaseEdgeType.IS_RELATED
        assert related_prop.action is DiffAction.UPDATED
        assert related_prop.previous_value == koenigsegg_id
        assert related_prop.new_value == omnicorp_id
        assert related_prop.conflict is None
        for prop_type, value in ((DatabaseEdgeType.IS_PROTECTED, "False"),):
            diff_prop = properties_by_type[prop_type]
            assert diff_prop.action is DiffAction.UNCHANGED
            assert diff_prop.previous_value == diff_prop.new_value == value
        for manufacturer_id, expected_action in ((koenigsegg_id, DiffAction.REMOVED), (omnicorp_id, DiffAction.ADDED)):
            manufacturer_node = nodes_by_id[manufacturer_id]
            assert len(manufacturer_node.relationships) == 1
            cars_rel = manufacturer_node.relationships.pop()
            assert cars_rel.name == "cars"
            assert cars_rel.action is DiffAction.UPDATED
            assert len(cars_rel.relationships) == 1
            cars_element = cars_rel.relationships.pop()
            assert cars_element.peer_id == jesko_id
            assert cars_element.action is expected_action
            assert cars_element.conflict is None
            properties_by_type = {p.property_type: p for p in cars_element.properties}
            assert set(properties_by_type.keys()) == {
                DatabaseEdgeType.IS_RELATED,
                DatabaseEdgeType.IS_PROTECTED,
            }
            for property_type, check_value in (
                (DatabaseEdgeType.IS_RELATED, jesko_id),
                (DatabaseEdgeType.IS_PROTECTED, "False"),
            ):
                prop_diff = properties_by_type[property_type]
                assert prop_diff.action is expected_action
                assert prop_diff.previous_value == (check_value if expected_action is DiffAction.REMOVED else None)
                assert prop_diff.new_value == (check_value if expected_action is DiffAction.ADDED else None)
                assert prop_diff.conflict is None

        # Verify that branch_1's diffs are frozen after merge
        branch_1_frozen_metadata = await diff_repository.get_roots_metadata(
            diff_branch_names=[branch_1.name, "main"],
            tracking_id=FrozenTrackingId(name=branch_1.name),
            exclude_merged=False,
        )
        assert len(branch_1_frozen_metadata) == 2, "Merged branch should have 2 frozen diff roots (branch + base)"
        for m in branch_1_frozen_metadata:
            assert m.is_frozen is True
            assert isinstance(m.tracking_id, FrozenTrackingId)
            assert m.tracking_id.name == branch_1.name

        # Original BranchTrackingId should no longer find branch_1 diffs
        branch_1_active_metadata = await diff_repository.get_roots_metadata(
            diff_branch_names=[branch_1.name],
            tracking_id=BranchTrackingId(name=branch_1.name),
            exclude_merged=False,
        )
        assert len(branch_1_active_metadata) == 0, "Merged branch should have no active branch-tracking diffs"

    async def test_resolve_conflict(
        self,
        db: InfrahubDatabase,
        branch_2: Branch,
        initial_dataset: dict[str, Node],
    ) -> None:
        kara_id = initial_dataset["kara"].id
        jesko_id = initial_dataset["jesko"].id
        cyberdyne_id = initial_dataset["cyberdyne"].id

        kara_main = await NodeManager.get_one(db=db, id=kara_id)
        kara_main.description.value = "branch-2-description"
        await kara_main.save(db=db)

        jesko_branch = await NodeManager.get_one(db=db, branch=branch_2, id=jesko_id)
        await jesko_branch.manufacturer.update(db=db, data=cyberdyne_id)
        await jesko_branch.save(db=db)

    async def test_rebase_causes_diff_recalculation(
        self,
        db: InfrahubDatabase,
        client: InfrahubClient,
        initial_dataset: dict[str, Node],
        branch_2: Branch,
        diff_repository: DiffRepository,
    ) -> None:
        jesko_id = initial_dataset["jesko"].id
        koenigsegg_id = initial_dataset["koenigsegg"].id
        cyberdyne_id = initial_dataset["cyberdyne"].id
        before_rebase = Timestamp()

        result = await client.execute_graphql(query=BRANCH_REBASE, variables={"branch": branch_2.name})
        assert result["BranchRebase"]["ok"]

        branch_2_diff = await diff_repository.get_one(
            diff_branch_name=branch_2.name, tracking_id=BranchTrackingId(name=branch_2.name)
        )

        assert len(branch_2_diff.nodes) == 3
        assert branch_2_diff.to_time > before_rebase
        nodes_by_id = {n.uuid: n for n in branch_2_diff.nodes}
        assert set(nodes_by_id.keys()) == {jesko_id, cyberdyne_id, koenigsegg_id}
        jesko_node = nodes_by_id[jesko_id]
        assert len(jesko_node.relationships) == 1
        manufacturer_rel = jesko_node.relationships.pop()
        assert manufacturer_rel.name == "manufacturer"
        assert len(manufacturer_rel.relationships) == 1
        manufacturer_element = manufacturer_rel.relationships.pop()
        assert manufacturer_element.peer_id == cyberdyne_id
        assert manufacturer_element.action is DiffAction.UPDATED
        assert manufacturer_element.conflict is None
        properties_by_type = {p.property_type: p for p in manufacturer_element.properties}
        assert set(properties_by_type.keys()) == {
            DatabaseEdgeType.IS_RELATED,
            DatabaseEdgeType.IS_PROTECTED,
        }
        related_prop = properties_by_type[DatabaseEdgeType.IS_RELATED]
        assert related_prop.property_type is DatabaseEdgeType.IS_RELATED
        assert related_prop.action is DiffAction.UPDATED
        assert related_prop.previous_value == koenigsegg_id
        assert related_prop.new_value == cyberdyne_id
        assert related_prop.conflict is None
        for prop_type, value in ((DatabaseEdgeType.IS_PROTECTED, "False"),):
            diff_prop = properties_by_type[prop_type]
            assert diff_prop.action is DiffAction.UNCHANGED
            assert diff_prop.previous_value == diff_prop.new_value == value
        for manufacturer_id, expected_action in ((koenigsegg_id, DiffAction.REMOVED), (cyberdyne_id, DiffAction.ADDED)):
            manufacturer_node = nodes_by_id[manufacturer_id]
            assert len(manufacturer_node.relationships) == 1
            cars_rel = manufacturer_node.relationships.pop()
            assert cars_rel.name == "cars"
            assert cars_rel.action is DiffAction.UPDATED
            assert len(cars_rel.relationships) == 1
            cars_element = cars_rel.relationships.pop()
            assert cars_element.peer_id == jesko_id
            assert cars_element.action is expected_action
            assert cars_element.conflict is None
            properties_by_type = {p.property_type: p for p in cars_element.properties}
            assert set(properties_by_type.keys()) == {
                DatabaseEdgeType.IS_RELATED,
                DatabaseEdgeType.IS_PROTECTED,
            }
            for property_type, check_value in (
                (DatabaseEdgeType.IS_RELATED, jesko_id),
                (DatabaseEdgeType.IS_PROTECTED, "False"),
            ):
                prop_diff = properties_by_type[property_type]
                assert prop_diff.action is expected_action
                assert prop_diff.previous_value == (check_value if expected_action is DiffAction.REMOVED else None)
                assert prop_diff.new_value == (check_value if expected_action is DiffAction.ADDED else None)
                assert prop_diff.conflict is None

    async def test_merge_branch(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        initial_dataset: dict[str, Node],
        client: InfrahubClient,
        branch_3: Branch,
        add_branch_3_changes: None,
    ) -> None:
        antarctica_id = initial_dataset["antarctica"].id

        # add a node on main
        main_jeb = await Node.init(db=db, branch=default_branch, schema=TestKind.PERSON)
        await main_jeb.new(db=db, name="Jeb", height=160)
        await main_jeb.save(db=db)

        # check schema is correct on branch_3
        branch_3_schema = await registry.schema.load_schema_from_db(db=db, branch=branch_3.name)
        assert not branch_3_schema.has(name=TestKind.CONTINENT)
        manufacturer_schema = branch_3_schema.get(name=TestKind.MANUFACTURER)
        assert "continents" not in manufacturer_schema.relationship_names

        # merge branch_3
        result = await client.execute_graphql(query=BRANCH_MERGE, variables={"branch": branch_3.name})
        assert result["BranchMerge"]["ok"]

        # check schema is correct on default_branch
        main_schema = await registry.schema.load_schema_from_db(db=db, branch=default_branch.name)
        assert not main_schema.has(name=TestKind.CONTINENT)
        manufacturer_schema = main_schema.get(name=TestKind.MANUFACTURER)
        assert "continents" not in manufacturer_schema.relationship_names
        no_antartica = await NodeManager.get_one(db=db, id=antarctica_id, branch=default_branch)
        assert no_antartica is None

    async def test_rebase_branch(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        initial_dataset: dict[str, Node],
        client: InfrahubClient,
    ) -> None:
        rebase_branch = await create_branch(branch_name="rebase_test_branch", db=db)

        # add a node on main after branch creation
        main_person = await Node.init(db=db, branch=default_branch, schema=TestKind.PERSON)
        await main_person.new(db=db, name="RebaseTestPerson", height=170)
        await main_person.save(db=db)

        # verify the node is NOT on the branch yet
        branch_person_before = await NodeManager.get_one(db=db, id=main_person.id, branch=rebase_branch)
        assert branch_person_before is None

        # rebase the branch
        result = await client.execute_graphql(query=BRANCH_REBASE, variables={"branch": rebase_branch.name})
        assert result["BranchRebase"]["ok"]

        # check the branch is updated with the new node
        rebase_branch = await Branch.get_by_name(db=db, name=rebase_branch.name)
        branch_person_after = await NodeManager.get_one(db=db, id=main_person.id, branch=rebase_branch)
        assert branch_person_after is not None
        assert branch_person_after.name.value == "RebaseTestPerson"
        assert branch_person_after.height.value == 170
