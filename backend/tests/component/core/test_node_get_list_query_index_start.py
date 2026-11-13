from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

import pytest

from infrahub.core.initialization import create_branch
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.core.query.index_start import IndexStart, NodeGetListIndexStartQuery, find_index_start
from infrahub.core.query.node import NodeGetListQuery
from infrahub.core.schema import AttributeSchema
from infrahub.core.timestamp import Timestamp

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.core.schema.schema_branch import SchemaBranch
    from infrahub.database import InfrahubDatabase

MAIN = "main"
BRANCH = "branch2"
FLEET_CAR_COUNT = 9
PERSONS_SHARING_A_CAR_VALUE = 8


@dataclass
class IndexStartData:
    main: Branch
    branch: Branch
    before_changes: Timestamp
    """After every node exists on main, before any of them is renamed, deleted or changed on the branch."""
    car_ids: dict[str, str]
    """Keyed by the name each car was created with."""
    person_ids: dict[str, str]

    def get_branch(self, name: str) -> Branch:
        return self.main if name == MAIN else self.branch

    def resolve_filters(self, filters: dict[str, Any]) -> dict[str, Any]:
        """Replace the person names of the relationship filters and the car names of `ids` with node ids."""
        resolved: dict[str, Any] = {}
        for key, value in filters.items():
            if key == "ids":
                resolved[key] = [self.car_ids[name] for name in value]
            elif key.endswith("__ids"):
                resolved[key] = [self.person_ids[name] for name in value]
            elif key.endswith("__id"):
                resolved[key] = self.person_ids[value]
            else:
                resolved[key] = value
        return resolved

    def car_names(self, node_ids: list[str]) -> list[str]:
        names_by_id = {car_id: name for name, car_id in self.car_ids.items()}
        return sorted(names_by_id[node_id] for node_id in node_ids)


@pytest.fixture(scope="class")
async def index_start_data(
    db: InfrahubDatabase, default_branch_scope_class: Branch, car_person_schema_scope_class: SchemaBranch
) -> IndexStartData:
    """Cars whose filters reach few or many edges, then changes on main and on a branch.

    On main:
    - john owns car-0 and car-1, jane owns car-2, fleet owns car-3 to car-11
    - car-0 and car-1 have 2 seats, a value that many persons hold as their height; the other cars have 4
    - car-0 is the only car with a color of its own, a transmission and the electric flag
    - after `before_changes`, car-1 is renamed to car-1-renamed and car-3 is deleted

    On the branch:
    - car-2 gets 2 seats, car-4 is deleted, car-5 moves from fleet to jane
    - car-branch is created with 6 seats and john as owner
    """
    person_ids: dict[str, str] = {}
    persons: dict[str, Node] = {}
    for name in ("john", "jane", "fleet"):
        person = await Node.init(db=db, schema="TestPerson", branch=default_branch_scope_class)
        await person.new(db=db, name=name, height=180)
        await person.save(db=db)
        persons[name] = person
        person_ids[name] = person.id
    for idx in range(PERSONS_SHARING_A_CAR_VALUE):
        person = await Node.init(db=db, schema="TestPerson", branch=default_branch_scope_class)
        await person.new(db=db, name=f"short-{idx}", height=2)
        await person.save(db=db)

    car_ids: dict[str, str] = {}
    owners = ["john", "john", "jane"] + ["fleet"] * FLEET_CAR_COUNT
    for idx, owner in enumerate(owners):
        car = await Node.init(db=db, schema="TestCar", branch=default_branch_scope_class)
        details: dict[str, Any] = {"name": f"car-{idx}", "nbr_seats": 2 if idx < 2 else 4, "owner": persons[owner]}
        if idx == 0:
            details |= {"color": "#111111", "transmission": "manual", "is_electric": True}
        await car.new(db=db, **details)
        await car.save(db=db)
        car_ids[f"car-{idx}"] = car.id

    before_changes = Timestamp()

    renamed = await NodeManager.get_one(db=db, id=car_ids["car-1"], branch=default_branch_scope_class)
    assert renamed
    renamed.name.value = "car-1-renamed"
    await renamed.save(db=db)
    deleted = await NodeManager.get_one(db=db, id=car_ids["car-3"], branch=default_branch_scope_class)
    assert deleted
    await deleted.delete(db=db)

    branch = await create_branch(branch_name=BRANCH, db=db)
    changed = await NodeManager.get_one(db=db, id=car_ids["car-2"], branch=branch)
    assert changed
    changed.nbr_seats.value = 2
    await changed.save(db=db)
    deleted_on_branch = await NodeManager.get_one(db=db, id=car_ids["car-4"], branch=branch)
    assert deleted_on_branch
    await deleted_on_branch.delete(db=db)
    moved = await NodeManager.get_one(db=db, id=car_ids["car-5"], branch=branch)
    assert moved
    await moved.owner.update(db=db, data=persons["jane"])
    await moved.save(db=db)
    created_on_branch = await Node.init(db=db, schema="TestCar", branch=branch)
    await created_on_branch.new(db=db, name="car-branch", nbr_seats=6, owner=persons["john"])
    await created_on_branch.save(db=db)
    car_ids["car-branch"] = created_on_branch.id

    return IndexStartData(
        main=default_branch_scope_class,
        branch=branch,
        before_changes=before_changes,
        car_ids=car_ids,
        person_ids=person_ids,
    )


@dataclass
class ListResultTestCase:
    name: str
    filters: dict[str, Any]
    """Relationship filters name the persons, the test replaces the names with ids."""
    expected: list[str]
    """The names the cars were created with."""
    branch: str = MAIN
    at_before_changes: bool = False
    partial_match: bool = False


LIST_RESULT_TEST_CASES: list[ListResultTestCase] = [
    ListResultTestCase(name="value_of_one_node", filters={"name__value": "car-0"}, expected=["car-0"]),
    ListResultTestCase(
        name="values_with_one_that_no_node_holds",
        filters={"name__values": ["car-0", "car-2", "missing"]},
        expected=["car-0", "car-2"],
    ),
    ListResultTestCase(name="value_that_no_node_holds", filters={"name__value": "missing"}, expected=[]),
    ListResultTestCase(name="empty_list_of_values", filters={"name__values": []}, expected=[]),
    ListResultTestCase(name="boolean_value", filters={"is_electric__value": True}, expected=["car-0"]),
    ListResultTestCase(name="enum_value", filters={"transmission__value": "manual"}, expected=["car-0"]),
    ListResultTestCase(name="new_value_of_renamed_node", filters={"name__value": "car-1-renamed"}, expected=["car-1"]),
    ListResultTestCase(name="old_value_of_renamed_node", filters={"name__value": "car-1"}, expected=[]),
    ListResultTestCase(
        name="old_value_of_renamed_node_before_the_rename",
        filters={"name__value": "car-1"},
        expected=["car-1"],
        at_before_changes=True,
    ),
    ListResultTestCase(name="deleted_node", filters={"name__value": "car-3"}, expected=[]),
    ListResultTestCase(
        name="deleted_node_before_the_delete",
        filters={"name__value": "car-3"},
        expected=["car-3"],
        at_before_changes=True,
    ),
    ListResultTestCase(
        name="value_that_another_kind_holds_more_often",
        filters={"nbr_seats__value": 2},
        expected=["car-0", "car-1"],
    ),
    ListResultTestCase(
        name="value_that_most_nodes_hold",
        filters={"nbr_seats__value": 4},
        expected=["car-2", *[f"car-{idx}" for idx in range(4, 12)]],
    ),
    ListResultTestCase(name="value_held_only_on_another_branch", filters={"nbr_seats__value": 6}, expected=[]),
    ListResultTestCase(
        name="value_of_node_created_on_branch",
        filters={"nbr_seats__value": 6},
        expected=["car-branch"],
        branch=BRANCH,
    ),
    ListResultTestCase(
        name="value_set_on_branch",
        filters={"nbr_seats__value": 2},
        expected=["car-0", "car-1", "car-2"],
        branch=BRANCH,
    ),
    ListResultTestCase(
        name="value_replaced_on_branch",
        filters={"nbr_seats__value": 4},
        expected=[f"car-{idx}" for idx in range(5, 12)],
        branch=BRANCH,
    ),
    ListResultTestCase(name="node_deleted_on_branch", filters={"name__value": "car-4"}, expected=[], branch=BRANCH),
    ListResultTestCase(name="node_deleted_on_another_branch", filters={"name__value": "car-4"}, expected=["car-4"]),
    ListResultTestCase(name="peer_ids", filters={"owner__ids": ["john"]}, expected=["car-0", "car-1"]),
    ListResultTestCase(
        name="peer_ids_on_branch",
        filters={"owner__ids": ["john"]},
        expected=["car-0", "car-1", "car-branch"],
        branch=BRANCH,
    ),
    ListResultTestCase(name="peer_id", filters={"owner__id": "jane"}, expected=["car-2"]),
    ListResultTestCase(
        name="peer_id_with_relationship_added_on_branch",
        filters={"owner__id": "jane"},
        expected=["car-2", "car-5"],
        branch=BRANCH,
    ),
    ListResultTestCase(
        name="several_peer_ids",
        filters={"owner__ids": ["john", "jane"]},
        expected=["car-0", "car-1", "car-2"],
    ),
    ListResultTestCase(name="empty_list_of_peer_ids", filters={"owner__ids": []}, expected=[]),
    ListResultTestCase(
        name="peer_with_most_nodes",
        filters={"owner__ids": ["fleet"]},
        expected=[f"car-{idx}" for idx in range(4, 12)],
    ),
    ListResultTestCase(
        name="peer_with_relationship_removed_on_branch",
        filters={"owner__ids": ["fleet"]},
        expected=[f"car-{idx}" for idx in range(6, 12)],
        branch=BRANCH,
    ),
    ListResultTestCase(
        name="peer_ids_and_value",
        filters={"owner__ids": ["john"], "name__value": "car-0"},
        expected=["car-0"],
    ),
    ListResultTestCase(
        name="peer_ids_and_value_of_another_node",
        filters={"owner__ids": ["fleet"], "color__value": "#111111"},
        expected=[],
    ),
    ListResultTestCase(
        name="peer_ids_and_value_changed_on_branch",
        filters={"owner__ids": ["jane"], "nbr_seats__value": 4},
        expected=["car-5"],
        branch=BRANCH,
    ),
    ListResultTestCase(
        name="peer_ids_and_partial_value",
        filters={"owner__ids": ["john"], "name__value": "renamed"},
        expected=["car-1"],
        partial_match=True,
    ),
    ListResultTestCase(
        name="value_and_peer_attribute",
        filters={"color__value": "#111111", "owner__name__value": "john"},
        expected=["car-0"],
    ),
]


@dataclass
class IndexStartSelectionTestCase:
    name: str
    filters: dict[str, Any]
    """Relationship filters name the persons, the test replaces the names with ids."""
    expected: str | None
    """The filter the list query enters from, None when it reads every node of the kind."""


INDEX_START_SELECTION_TEST_CASES: list[IndexStartSelectionTestCase] = [
    IndexStartSelectionTestCase(name="value_of_one_node", filters={"name__value": "car-0"}, expected="name__value"),
    IndexStartSelectionTestCase(
        name="values_of_two_nodes", filters={"name__values": ["car-0", "car-2"]}, expected="name__values"
    ),
    IndexStartSelectionTestCase(
        name="value_that_no_node_holds", filters={"name__value": "missing"}, expected="name__value"
    ),
    IndexStartSelectionTestCase(name="value_that_most_nodes_hold", filters={"nbr_seats__value": 4}, expected=None),
    IndexStartSelectionTestCase(
        name="value_that_another_kind_holds_more_often", filters={"nbr_seats__value": 2}, expected=None
    ),
    IndexStartSelectionTestCase(name="peer_with_few_nodes", filters={"owner__ids": ["jane"]}, expected="owner__ids"),
    IndexStartSelectionTestCase(name="peer_id_with_few_nodes", filters={"owner__id": "john"}, expected="owner__id"),
    IndexStartSelectionTestCase(name="peer_with_most_nodes", filters={"owner__ids": ["fleet"]}, expected=None),
    IndexStartSelectionTestCase(
        name="peers_that_have_most_nodes_together", filters={"owner__ids": ["john", "jane", "fleet"]}, expected=None
    ),
    IndexStartSelectionTestCase(
        name="filter_with_fewest_edges_listed_last",
        filters={"owner__ids": ["john"], "name__value": "car-0"},
        expected="name__value",
    ),
    IndexStartSelectionTestCase(
        name="filter_with_fewest_edges_listed_first",
        filters={"name__value": "car-0", "owner__ids": ["john"]},
        expected="name__value",
    ),
    IndexStartSelectionTestCase(
        name="one_filter_with_few_edges_among_two",
        filters={"nbr_seats__value": 4, "owner__ids": ["jane"]},
        expected="owner__ids",
    ),
]


@dataclass
class QueryTextTestCase:
    name: str
    filters: dict[str, Any]
    """Relationship filters name the persons and `ids` names the cars, the test replaces the names with ids."""
    expected: list[str]
    """The lines the text of the list query starts with."""
    branch: str = MAIN


QUERY_TEXT_TEST_CASES: list[QueryTextTestCase] = [
    QueryTextTestCase(
        name="value_of_one_node",
        filters={"name__value": "car-0"},
        expected=[
            "MATCH (av:AttributeValueIndexed { value: $filter1_value })",
            "WITH collect(av) AS index_start_vertices",
            "UNWIND index_start_vertices AS av",
            "MATCH (n:TestCar)-[:HAS_ATTRIBUTE]-(i:Attribute { name: $filter1_name })-[:HAS_VALUE]-(av)",
            "WITH DISTINCT n",
            "MATCH (root:Root)<-[r:IS_PART_OF]-(n)",
        ],
    ),
    QueryTextTestCase(
        name="values_of_two_nodes",
        filters={"name__values": ["car-0", "car-2"]},
        expected=[
            "MATCH (av:AttributeValueIndexed)",
            "WHERE av.value IN $filter1_value",
            "WITH collect(av) AS index_start_vertices",
            "UNWIND index_start_vertices AS av",
            "MATCH (n:TestCar)-[:HAS_ATTRIBUTE]-(i:Attribute { name: $filter1_name })-[:HAS_VALUE]-(av)",
            "WITH DISTINCT n",
            "MATCH (root:Root)<-[r:IS_PART_OF]-(n)",
        ],
    ),
    QueryTextTestCase(
        name="peer_id_with_few_nodes",
        filters={"owner__id": "john"},
        expected=[
            "MATCH (peer:Node { uuid: $filter1_peer_id })",
            "WITH collect(peer) AS index_start_vertices",
            "UNWIND index_start_vertices AS peer",
            "MATCH (n:TestCar)-[r1:IS_RELATED]->(rl:Relationship { name: $filter1_rel_name })-[r2:IS_RELATED]->(peer)",
            "WITH DISTINCT n",
            "MATCH (root:Root)<-[r:IS_PART_OF]-(n)",
        ],
    ),
    QueryTextTestCase(
        name="peer_with_few_nodes_on_branch",
        filters={"owner__ids": ["jane"]},
        expected=[
            "MATCH (peer:Node)",
            "WHERE peer.uuid IN $filter1_peer_ids",
            "WITH collect(peer) AS index_start_vertices",
            "UNWIND index_start_vertices AS peer",
            "MATCH (n:TestCar)-[r1:IS_RELATED]->(rl:Relationship { name: $filter1_rel_name })-[r2:IS_RELATED]->(peer)",
            "WITH DISTINCT n",
            "CALL (n) {",
        ],
        branch=BRANCH,
    ),
    QueryTextTestCase(
        name="filter_with_fewest_edges_listed_last",
        filters={"owner__ids": ["john"], "name__value": "car-0"},
        expected=[
            "MATCH (av:AttributeValueIndexed { value: $filter2_value })",
            "WITH collect(av) AS index_start_vertices",
            "UNWIND index_start_vertices AS av",
            "MATCH (n:TestCar)-[:HAS_ATTRIBUTE]-(i:Attribute { name: $filter2_name })-[:HAS_VALUE]-(av)",
            "WITH DISTINCT n",
            "MATCH (root:Root)<-[r:IS_PART_OF]-(n)",
        ],
    ),
    QueryTextTestCase(
        name="value_listed_after_metadata_filter",
        filters={"node_metadata__created_at__before": "2100-01-01T00:00:00.000000Z", "name__value": "car-0"},
        expected=[
            "MATCH (av:AttributeValueIndexed { value: $filter2_value })",
            "WITH collect(av) AS index_start_vertices",
            "UNWIND index_start_vertices AS av",
            "MATCH (n:TestCar)-[:HAS_ATTRIBUTE]-(i:Attribute { name: $filter2_name })-[:HAS_VALUE]-(av)",
            "WITH DISTINCT n",
            "MATCH (root:Root)<-[r:IS_PART_OF]-(n)",
        ],
    ),
    QueryTextTestCase(
        name="value_that_most_nodes_hold",
        filters={"nbr_seats__value": 4},
        expected=["MATCH (root:Root)<-[r:IS_PART_OF]-(n:TestCar)"],
    ),
    QueryTextTestCase(
        name="value_that_most_nodes_hold_on_branch",
        filters={"nbr_seats__value": 4},
        expected=["MATCH (n:TestCar)", "CALL (n) {"],
        branch=BRANCH,
    ),
    QueryTextTestCase(
        name="value_of_one_node_with_node_ids",
        filters={"ids": ["car-0", "car-2"], "name__value": "car-0"},
        expected=["MATCH (root:Root)<-[r:IS_PART_OF]-(n:Node:TestCar)"],
    ),
]


@dataclass
class NoIndexStartTestCase:
    name: str
    field_name: str
    filter_name: str
    filter_value: Any
    partial_match: bool = False
    attribute: AttributeSchema | None = None
    """Used in place of the field of the car schema."""


NO_INDEX_START_TEST_CASES: list[NoIndexStartTestCase] = [
    NoIndexStartTestCase(
        name="partial_match", field_name="name", filter_name="value", filter_value="car", partial_match=True
    ),
    NoIndexStartTestCase(name="null_check", field_name="color", filter_name="isnull", filter_value=True),
    NoIndexStartTestCase(name="no_value", field_name="name", filter_name="value", filter_value=None),
    NoIndexStartTestCase(name="protected_flag", field_name="name", filter_name="is_protected", filter_value=True),
    NoIndexStartTestCase(name="source_of_value", field_name="name", filter_name="source__id", filter_value="abc"),
    NoIndexStartTestCase(
        name="list_attribute",
        field_name="tags",
        filter_name="value",
        filter_value="blue",
        attribute=AttributeSchema(name="tags", kind="List"),
    ),
    NoIndexStartTestCase(
        name="attribute_without_value_index",
        field_name="notes",
        filter_name="value",
        filter_value="blue",
        attribute=AttributeSchema(name="notes", kind="TextArea"),
    ),
    NoIndexStartTestCase(name="peer_attribute", field_name="owner", filter_name="name__value", filter_value="john"),
    NoIndexStartTestCase(name="peer_null_check", field_name="owner", filter_name="isnull", filter_value=False),
    NoIndexStartTestCase(name="peer_ids_without_value", field_name="owner", filter_name="ids", filter_value=None),
]


class TestNodeGetListQueryIndexStart:
    @pytest.mark.parametrize("test_case", [pytest.param(tc, id=tc.name) for tc in LIST_RESULT_TEST_CASES])
    async def test_list_and_count(
        self, db: InfrahubDatabase, index_start_data: IndexStartData, test_case: ListResultTestCase
    ) -> None:
        branch = index_start_data.get_branch(name=test_case.branch)
        query = await NodeGetListQuery.init(
            db=db,
            branch=branch,
            schema=db.schema.get_node_schema(name="TestCar", branch=branch),
            filters=index_start_data.resolve_filters(filters=test_case.filters),
            partial_match=test_case.partial_match,
            at=index_start_data.before_changes if test_case.at_before_changes else None,
        )
        await query.execute(db=db)

        assert index_start_data.car_names(node_ids=query.get_node_ids()) == sorted(test_case.expected)
        assert await query.count(db=db) == len(test_case.expected)

    async def test_limit_and_offset(self, db: InfrahubDatabase, index_start_data: IndexStartData) -> None:
        owned_by_john = sorted(index_start_data.car_ids[name] for name in ("car-0", "car-1", "car-branch"))

        query = await NodeGetListQuery.init(
            db=db,
            branch=index_start_data.branch,
            schema=db.schema.get_node_schema(name="TestCar", branch=index_start_data.branch),
            filters={"owner__ids": [index_start_data.person_ids["john"]]},
            limit=2,
            offset=1,
        )
        await query.execute(db=db)

        assert query.get_node_ids() == owned_by_john[1:]

    async def test_list_read_one_row_at_a_time(
        self, db: InfrahubDatabase, index_start_data: IndexStartData, query_limit_of_one: None
    ) -> None:
        query = await NodeGetListQuery.init(
            db=db,
            branch=index_start_data.branch,
            schema=db.schema.get_node_schema(name="TestCar", branch=index_start_data.branch),
            filters={"owner__ids": [index_start_data.person_ids["john"]]},
        )
        await query.execute(db=db)

        assert index_start_data.car_names(node_ids=query.get_node_ids()) == ["car-0", "car-1", "car-branch"]

    @pytest.mark.parametrize("test_case", [pytest.param(tc, id=tc.name) for tc in QUERY_TEXT_TEST_CASES])
    async def test_query_text(
        self, db: InfrahubDatabase, index_start_data: IndexStartData, test_case: QueryTextTestCase
    ) -> None:
        branch = index_start_data.get_branch(name=test_case.branch)
        query = await NodeGetListQuery.init(
            db=db,
            branch=branch,
            schema=db.schema.get_node_schema(name="TestCar", branch=branch),
            filters=index_start_data.resolve_filters(filters=test_case.filters),
        )

        assert query.get_query().splitlines()[: len(test_case.expected)] == test_case.expected

    @pytest.mark.parametrize("test_case", [pytest.param(tc, id=tc.name) for tc in INDEX_START_SELECTION_TEST_CASES])
    async def test_selected_index_start(
        self, db: InfrahubDatabase, index_start_data: IndexStartData, test_case: IndexStartSelectionTestCase
    ) -> None:
        schema = db.schema.get_node_schema(name="TestCar", branch=index_start_data.main)
        filter_by_position: dict[int, str] = {}
        index_starts: list[IndexStart] = []
        filters = index_start_data.resolve_filters(filters=test_case.filters)
        for position, (filter_key, filter_value) in enumerate(filters.items(), start=1):
            field_name, filter_name = filter_key.split("__", maxsplit=1)
            index_start = await find_index_start(
                db=db,
                field=schema.get_field(name=field_name),
                name=field_name,
                filter_name=filter_name,
                filter_value=filter_value,
                branch=index_start_data.main,
                partial_match=False,
                subquery_idx=position,
                position=position,
            )
            assert index_start
            index_starts.append(index_start)
            filter_by_position[position] = filter_key

        query = NodeGetListIndexStartQuery(node_kind="TestCar", index_starts=index_starts)
        await query.execute(db=db)
        selected = query.get_selected_index_start()

        assert (filter_by_position[selected.position] if selected else None) == test_case.expected

    @pytest.mark.parametrize("test_case", [pytest.param(tc, id=tc.name) for tc in NO_INDEX_START_TEST_CASES])
    async def test_filter_without_index_start(
        self, db: InfrahubDatabase, index_start_data: IndexStartData, test_case: NoIndexStartTestCase
    ) -> None:
        schema = db.schema.get_node_schema(name="TestCar", branch=index_start_data.main)

        index_start = await find_index_start(
            db=db,
            field=test_case.attribute or schema.get_field(name=test_case.field_name),
            name=test_case.field_name,
            filter_name=test_case.filter_name,
            filter_value=test_case.filter_value,
            branch=index_start_data.main,
            partial_match=test_case.partial_match,
            subquery_idx=1,
            position=1,
        )

        assert index_start is None
