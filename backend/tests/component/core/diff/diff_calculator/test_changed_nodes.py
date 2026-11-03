"""The changed-nodes queries list only nodes the field- and property-level paths queries can return paths for."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

import pytest

from infrahub.core import registry
from infrahub.core.constants import BranchSupportType, RelationshipCardinality, RelationshipDirection, SchemaPathType
from infrahub.core.initialization import create_branch
from infrahub.core.manager import NodeManager
from infrahub.core.migrations.schema.node_kind_update import NodeKindUpdateMigration
from infrahub.core.migrations.shared import MigrationInput
from infrahub.core.node import Node
from infrahub.core.path import SchemaPath
from infrahub.core.query.diff import DiffChangedNodesQuery, DiffFieldNodesQuery, DiffPropertyNodesQuery
from infrahub.core.schema import SchemaRoot
from infrahub.core.schema.attribute_schema import AttributeSchema
from infrahub.core.schema.node_schema import NodeSchema
from infrahub.core.schema.relationship_schema import RelationshipSchema
from infrahub.core.timestamp import Timestamp
from tests.conftest import do_car_person_schema_unregistered

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.core.schema.schema_branch import SchemaBranch
    from infrahub.database import InfrahubDatabase

LOCAL_NOTE_KIND = "TestingLocalNote"


@pytest.fixture
async def local_note_schema(db: InfrahubDatabase, default_branch: Branch, car_person_schema: SchemaBranch) -> None:
    """A branch-local kind, whose changes on a branch never enter a diff."""
    local_note = NodeSchema(
        name="LocalNote",
        namespace="Testing",
        branch=BranchSupportType.LOCAL,
        default_filter="name__value",
        attributes=[
            AttributeSchema(name="name", kind="Text", unique=True),
            AttributeSchema(name="text", kind="Text", optional=True),
        ],
    )
    registry.schema.register_schema(schema=SchemaRoot(nodes=[local_note]), branch=default_branch.name)


async def _changed_node_uuids(
    db: InfrahubDatabase, query_class: type[DiffChangedNodesQuery], base_branch: Branch, branch: Branch
) -> list[str]:
    query = await query_class.init(
        db=db,
        branch=branch,
        base_branch=base_branch,
        diff_branch_from_time=Timestamp(branch.created_at),
        diff_from=Timestamp(branch.created_at),
        diff_to=Timestamp(),
    )
    await query.execute(db=db)
    return query.get_node_uuids()


@pytest.mark.parametrize("query_class", [DiffFieldNodesQuery, DiffPropertyNodesQuery])
async def test_branch_local_changes_are_not_listed(
    db: InfrahubDatabase,
    default_branch: Branch,
    local_note_schema: None,
    query_class: type[DiffChangedNodesQuery],
) -> None:
    branch = await create_branch(db=db, branch_name="branch")
    note = await Node.init(db=db, schema=LOCAL_NOTE_KIND, branch=branch)
    await note.new(db=db, name="note-1", text="branch only")
    await note.save(db=db)

    assert await _changed_node_uuids(db=db, query_class=query_class, base_branch=default_branch, branch=branch) == []


@pytest.mark.parametrize("query_class", [DiffFieldNodesQuery, DiffPropertyNodesQuery])
async def test_branch_aware_changes_are_listed(
    db: InfrahubDatabase,
    default_branch: Branch,
    local_note_schema: None,
    query_class: type[DiffChangedNodesQuery],
) -> None:
    branch = await create_branch(db=db, branch_name="branch")
    note = await Node.init(db=db, schema=LOCAL_NOTE_KIND, branch=branch)
    await note.new(db=db, name="note-1", text="branch only")
    await note.save(db=db)
    person = await Node.init(db=db, schema="TestPerson", branch=branch)
    await person.new(db=db, name="Alice", height=170)
    await person.save(db=db)

    assert await _changed_node_uuids(db=db, query_class=query_class, base_branch=default_branch, branch=branch) == [
        person.id
    ]


MIRROR_KIND = "TestingMirror"


@dataclass
class ChangeHistory:
    """The branch, the node ids and the start time of each step of the scenario, in the order of the steps."""

    branch: Branch
    node_ids: dict[str, str]
    times: dict[str, Timestamp]

    def ids(self, *names: str) -> list[str]:
        return sorted(self.node_ids[name] for name in names)


@pytest.fixture(scope="class")
async def changed_nodes_schema(
    db: InfrahubDatabase,
    default_branch_scope_class: Branch,
    node_group_schema_scope_class: None,
    data_schema_scope_class: None,
) -> None:
    schema = do_car_person_schema_unregistered()
    person = schema.get(name="TestPerson")
    person.attributes.append(
        AttributeSchema(name="badge", kind="Number", optional=True, branch=BranchSupportType.AGNOSTIC)
    )
    person.relationships.append(
        RelationshipSchema(
            name="mentor",
            peer="TestPerson",
            cardinality=RelationshipCardinality.ONE,
            optional=True,
            identifier="person__mentor",
            direction=RelationshipDirection.OUTBOUND,
        )
    )
    mirror = NodeSchema(
        name="Mirror",
        namespace="Testing",
        branch=BranchSupportType.AGNOSTIC,
        default_filter="name__value",
        attributes=[
            AttributeSchema(name="name", kind="Text", unique=True, branch=BranchSupportType.AGNOSTIC),
            AttributeSchema(name="ref", kind="Text", branch=BranchSupportType.AWARE),
        ],
    )
    schema.nodes.append(mirror)
    registry.schema.register_schema(schema=schema, branch=default_branch_scope_class.name)


async def _create(db: InfrahubDatabase, branch: Branch, kind: str, at: Timestamp, **data: Any) -> Node:
    node = await Node.init(db=db, schema=kind, branch=branch)
    await node.new(db=db, **data)
    await node.save(db=db, at=at)
    return node


async def _get(db: InfrahubDatabase, branch: Branch, node_id: str) -> Node:
    return await NodeManager.get_one(db=db, branch=branch, id=node_id, raise_on_error=True)


@pytest.fixture(scope="class")
async def change_history(
    db: InfrahubDatabase, default_branch_scope_class: Branch, changed_nodes_schema: None
) -> ChangeHistory:
    """Start each step of the scenario at its own time, so that the window from one step to the next holds its changes only."""
    main = default_branch_scope_class
    setup_at = Timestamp()
    john = await _create(db, main, "TestPerson", setup_at, name="John", height=180, badge=1)
    jane = await _create(db, main, "TestPerson", setup_at, name="Jane", height=170)
    alfred = await _create(db, main, "TestPerson", setup_at, name="Alfred", height=160)
    albert = await _create(db, main, "TestPerson", setup_at, name="Albert", height=150)
    accord = await _create(db, main, "TestCar", setup_at, name="accord", owner=john)
    camry = await _create(db, main, "TestCar", setup_at, name="camry", owner=jane)
    civic = await _create(db, main, "TestCar", setup_at, name="civic", owner=alfred, driver=john)
    mirror = await _create(db, main, MIRROR_KIND, setup_at, name="mirror", ref="main")
    branch = await create_branch(db=db, branch_name="changes")

    node_ids = {
        "john": john.id,
        "jane": jane.id,
        "alfred": alfred.id,
        "albert": albert.id,
        "accord": accord.id,
        "camry": camry.id,
        "civic": civic.id,
        "mirror": mirror.id,
    }
    times: dict[str, Timestamp] = {}

    times["value"] = Timestamp()
    node = await _get(db, branch, jane.id)
    node.height.value = 155
    await node.save(db=db, at=times["value"])

    times["between_value_and_created"] = Timestamp()

    times["created"] = Timestamp()
    newman = await _create(db, branch, "TestPerson", times["created"], name="Newman", height=140)
    node_ids["newman"] = newman.id

    times["relationship_added"] = Timestamp()
    node = await _get(db, branch, accord.id)
    await node.driver.update(db=db, data=albert.id)
    await node.save(db=db, at=times["relationship_added"])

    times["relationship_removed"] = Timestamp()
    node = await _get(db, branch, civic.id)
    await node.driver.update(db=db, data=None)
    await node.save(db=db, at=times["relationship_removed"])

    times["same_kind_relationship_added"] = Timestamp()
    node = await _get(db, branch, albert.id)
    await node.mentor.update(db=db, data=jane.id)
    await node.save(db=db, at=times["same_kind_relationship_added"])

    times["attribute_source"] = Timestamp()
    node = await _get(db, branch, alfred.id)
    node.name.source = john
    await node.save(db=db, at=times["attribute_source"])

    times["attribute_owner"] = Timestamp()
    node = await _get(db, branch, albert.id)
    node.height.owner = jane
    await node.save(db=db, at=times["attribute_owner"])

    times["attribute_protected"] = Timestamp()
    node = await _get(db, branch, john.id)
    node.name.is_protected = True
    await node.save(db=db, at=times["attribute_protected"])

    times["relationship_protected"] = Timestamp()
    node = await _get(db, branch, camry.id)
    await node.owner.update(db=db, data={"id": jane.id, "_relation__is_protected": True})
    await node.save(db=db, at=times["relationship_protected"])

    times["relationship_source"] = Timestamp()
    node = await _get(db, branch, accord.id)
    await node.owner.update(db=db, data={"id": john.id, "_relation__source": alfred.id})
    await node.save(db=db, at=times["relationship_source"])

    times["relationship_owner"] = Timestamp()
    node = await _get(db, branch, civic.id)
    await node.owner.update(db=db, data={"id": alfred.id, "_relation__owner": jane.id})
    await node.save(db=db, at=times["relationship_owner"])

    times["agnostic_attribute"] = Timestamp()
    node = await _get(db, branch, john.id)
    node.badge.value = 2
    await node.save(db=db, at=times["agnostic_attribute"])

    times["aware_attribute_of_agnostic_node"] = Timestamp()
    node = await _get(db, branch, mirror.id)
    node.ref.value = "feature"
    await node.save(db=db, at=times["aware_attribute_of_agnostic_node"])

    times["node_deleted"] = Timestamp()
    node = await _get(db, branch, camry.id)
    await node.delete(db=db, at=times["node_deleted"])

    times["branch_node_deleted"] = Timestamp()
    node = await _get(db, branch, newman.id)
    await node.delete(db=db, at=times["branch_node_deleted"])

    times["value_changed_and_undone"] = Timestamp()
    node = await _get(db, branch, jane.id)
    node.height.value = 1
    await node.save(db=db, at=times["value_changed_and_undone"])
    node = await _get(db, branch, jane.id)
    node.height.value = 155
    await node.save(db=db)

    times["main_changes"] = Timestamp()
    node = await _get(db, main, alfred.id)
    node.height.value = 99
    await node.save(db=db, at=times["main_changes"])
    mainman = await _create(db, main, "TestPerson", times["main_changes"], name="Mainman", height=130)
    node = await _get(db, main, accord.id)
    await node.driver.update(db=db, data=jane.id)
    await node.save(db=db, at=times["main_changes"])
    node_ids["mainman"] = mainman.id

    times["end"] = Timestamp()
    return ChangeHistory(branch=branch, node_ids=node_ids, times=times)


@dataclass
class ChangedNodesCase:
    name: str
    from_step: str
    to_step: str | None
    expected_field_nodes: list[str]
    expected_property_nodes: list[str]
    on_default_branch: bool = False
    node_kinds: list[str] | None = None


def _next_step(history: ChangeHistory, step: str) -> str:
    steps = list(history.times)
    return steps[steps.index(step) + 1]


CHANGED_NODES_CASES: list[ChangedNodesCase] = [
    ChangedNodesCase(
        name="attribute_value_changed",
        from_step="value",
        to_step=None,
        expected_field_nodes=[],
        expected_property_nodes=["jane"],
    ),
    ChangedNodesCase(
        name="change_before_from_time_and_change_at_to_time",
        from_step="between_value_and_created",
        to_step=None,
        expected_field_nodes=[],
        expected_property_nodes=[],
    ),
    ChangedNodesCase(
        name="node_created",
        from_step="created",
        to_step=None,
        expected_field_nodes=["newman"],
        expected_property_nodes=["newman"],
    ),
    ChangedNodesCase(
        name="relationship_added_lists_both_peers",
        from_step="relationship_added",
        to_step=None,
        expected_field_nodes=["accord", "albert"],
        expected_property_nodes=["accord", "albert"],
    ),
    ChangedNodesCase(
        name="relationship_removed_lists_both_peers",
        from_step="relationship_removed",
        to_step=None,
        expected_field_nodes=["civic", "john"],
        expected_property_nodes=["civic", "john"],
    ),
    ChangedNodesCase(
        name="relationship_between_nodes_of_one_kind_added",
        from_step="same_kind_relationship_added",
        to_step=None,
        expected_field_nodes=["albert", "jane"],
        expected_property_nodes=["albert", "jane"],
    ),
    ChangedNodesCase(
        name="attribute_source_changed",
        from_step="attribute_source",
        to_step=None,
        expected_field_nodes=[],
        expected_property_nodes=["alfred"],
    ),
    ChangedNodesCase(
        name="attribute_owner_changed",
        from_step="attribute_owner",
        to_step=None,
        expected_field_nodes=[],
        expected_property_nodes=["albert"],
    ),
    ChangedNodesCase(
        name="attribute_is_protected_changed",
        from_step="attribute_protected",
        to_step=None,
        expected_field_nodes=[],
        expected_property_nodes=["john"],
    ),
    ChangedNodesCase(
        name="relationship_is_protected_changed",
        from_step="relationship_protected",
        to_step=None,
        expected_field_nodes=[],
        expected_property_nodes=["camry", "jane"],
    ),
    ChangedNodesCase(
        name="relationship_source_changed",
        from_step="relationship_source",
        to_step=None,
        expected_field_nodes=[],
        expected_property_nodes=["accord", "john"],
    ),
    ChangedNodesCase(
        name="relationship_owner_changed",
        from_step="relationship_owner",
        to_step=None,
        expected_field_nodes=[],
        expected_property_nodes=["alfred", "civic"],
    ),
    ChangedNodesCase(
        name="branch_agnostic_attribute_of_branch_aware_node_changed",
        from_step="agnostic_attribute",
        to_step=None,
        expected_field_nodes=[],
        expected_property_nodes=[],
    ),
    ChangedNodesCase(
        name="branch_aware_attribute_of_branch_agnostic_node_changed",
        from_step="aware_attribute_of_agnostic_node",
        to_step=None,
        expected_field_nodes=[],
        expected_property_nodes=["mirror"],
    ),
    ChangedNodesCase(
        name="node_created_on_default_branch_deleted",
        from_step="node_deleted",
        to_step=None,
        expected_field_nodes=["camry", "jane"],
        expected_property_nodes=["camry", "jane"],
    ),
    ChangedNodesCase(
        name="node_created_on_branch_deleted",
        from_step="branch_node_deleted",
        to_step=None,
        expected_field_nodes=["newman"],
        expected_property_nodes=["newman"],
    ),
    ChangedNodesCase(
        name="value_changed_and_changed_back",
        from_step="value_changed_and_undone",
        to_step=None,
        expected_field_nodes=[],
        expected_property_nodes=["jane"],
    ),
    ChangedNodesCase(
        name="default_branch_changes_not_listed_for_branch",
        from_step="main_changes",
        to_step=None,
        expected_field_nodes=[],
        expected_property_nodes=[],
    ),
    ChangedNodesCase(
        name="whole_branch",
        from_step="value",
        to_step="end",
        expected_field_nodes=["accord", "albert", "camry", "civic", "jane", "john", "newman"],
        expected_property_nodes=["accord", "albert", "alfred", "camry", "civic", "jane", "john", "mirror", "newman"],
    ),
    ChangedNodesCase(
        name="whole_branch_one_kind",
        from_step="value",
        to_step="end",
        node_kinds=["TestCar"],
        expected_field_nodes=["accord", "camry", "civic"],
        expected_property_nodes=["accord", "camry", "civic"],
    ),
    ChangedNodesCase(
        name="kind_changed_only_through_properties",
        from_step="attribute_source",
        to_step=None,
        node_kinds=["TestPerson"],
        expected_field_nodes=[],
        expected_property_nodes=["alfred"],
    ),
    ChangedNodesCase(
        name="kind_without_changes",
        from_step="attribute_source",
        to_step=None,
        node_kinds=["TestCar"],
        expected_field_nodes=[],
        expected_property_nodes=[],
    ),
    ChangedNodesCase(
        name="default_branch_as_diff_branch",
        from_step="main_changes",
        to_step=None,
        on_default_branch=True,
        expected_field_nodes=["accord", "jane", "mainman"],
        expected_property_nodes=["accord", "alfred", "jane", "mainman"],
    ),
    ChangedNodesCase(
        name="default_branch_as_diff_branch_ignores_branch_changes",
        from_step="value",
        to_step="main_changes",
        on_default_branch=True,
        expected_field_nodes=[],
        expected_property_nodes=[],
    ),
]


class TestChangedNodesTimeWindows:
    async def _list(
        self,
        db: InfrahubDatabase,
        query_class: type[DiffChangedNodesQuery],
        history: ChangeHistory,
        case: ChangedNodesCase,
        default_branch: Branch,
    ) -> list[str]:
        from_time = history.times[case.from_step]
        to_time = history.times[case.to_step or _next_step(history, case.from_step)]
        diff_branch = default_branch if case.on_default_branch else history.branch
        query = await query_class.init(
            db=db,
            branch=diff_branch,
            base_branch=default_branch,
            diff_branch_from_time=from_time if case.on_default_branch else Timestamp(diff_branch.get_branched_from()),
            diff_from=from_time,
            diff_to=to_time,
            node_kinds=case.node_kinds,
        )
        await query.execute(db=db)
        return sorted(query.get_node_uuids())

    async def test_same_kind_relationship_has_an_edge_to_a_node(
        self, db: InfrahubDatabase, change_history: ChangeHistory
    ) -> None:
        """The relationship between two nodes of one kind has an edge from the Relationship to a Node."""
        results = await db.execute_query(
            query="""
            MATCH (:Relationship)-[r:IS_RELATED {branch: $branch_name, from: $at}]->(n:Node)
            RETURN n.uuid AS uuid
            """,
            params={
                "branch_name": change_history.branch.name,
                "at": change_history.times["same_kind_relationship_added"].to_string(),
            },
        )
        assert [result["uuid"] for result in results] == [change_history.node_ids["jane"]]

    @pytest.mark.parametrize("case", CHANGED_NODES_CASES, ids=lambda case: case.name)
    async def test_changed_nodes(
        self,
        db: InfrahubDatabase,
        default_branch_scope_class: Branch,
        change_history: ChangeHistory,
        case: ChangedNodesCase,
    ) -> None:
        listed = {
            "field": await self._list(db, DiffFieldNodesQuery, change_history, case, default_branch_scope_class),
            "property": await self._list(db, DiffPropertyNodesQuery, change_history, case, default_branch_scope_class),
        }

        assert listed == {
            "field": change_history.ids(*case.expected_field_nodes),
            "property": change_history.ids(*case.expected_property_nodes),
        }


@dataclass
class MigratedKindCase:
    name: str
    query_class: type[DiffChangedNodesQuery]
    expected_cars: list[str]


MIGRATED_KIND_CASES: list[MigratedKindCase] = [
    MigratedKindCase(name="field_nodes", query_class=DiffFieldNodesQuery, expected_cars=["accord", "camry"]),
    MigratedKindCase(name="property_nodes", query_class=DiffPropertyNodesQuery, expected_cars=["accord"]),
]


@pytest.mark.parametrize("case", MIGRATED_KIND_CASES, ids=lambda case: case.name)
async def test_node_with_migrated_kind_is_listed_once(
    db: InfrahubDatabase,
    default_branch: Branch,
    car_accord_main: Node,
    car_camry_main: Node,
    case: MigratedKindCase,
) -> None:
    branch = await create_branch(db=db, branch_name="migrated-kind")
    schema = registry.schema.get_schema_branch(name=default_branch.name)
    car_schema = schema.get(name="TestCar")
    car_schema.name = "NewCar"
    car_schema.namespace = "Test2"
    registry.schema.set(name="Test2NewCar", schema=car_schema, branch=branch.name)
    migration = NodeKindUpdateMigration(
        previous_node_schema=schema.get(name="TestCar"),
        new_node_schema=car_schema,
        schema_path=SchemaPath(path_type=SchemaPathType.ATTRIBUTE, schema_kind="Test2NewCar", field_name="namespace"),
    )
    execution_result = await migration.execute(migration_input=MigrationInput(db=db), branch=branch)
    assert not execution_result.errors
    results = await db.execute_query(
        query="MATCH (n:Node {uuid: $uuid}) RETURN n.kind AS kind",
        params={"uuid": car_accord_main.id},
    )
    assert sorted(result["kind"] for result in results) == ["Test2NewCar", "TestCar"]

    migrated_accord = await _get(db, branch, car_accord_main.id)
    migrated_accord.color.value = "#123456"
    await migrated_accord.save(db=db)

    car_ids = {"accord": car_accord_main.id, "camry": car_camry_main.id}
    listed = await _changed_node_uuids(db=db, query_class=case.query_class, base_branch=default_branch, branch=branch)
    assert sorted(listed) == sorted(car_ids[name] for name in case.expected_cars)
