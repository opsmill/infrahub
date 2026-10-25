from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

import pytest

from infrahub.constants.enums import OrderDirection
from infrahub.core.constants import RelationshipHierarchyDirection
from infrahub.core.initialization import create_branch
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.core.order import OrderByEntry, OrderModel
from infrahub.core.schema import SchemaRoot
from infrahub.graphql.initialization import prepare_graphql_params
from tests.constants import TestKind
from tests.helpers.graphql import graphql
from tests.helpers.schema import CAR_SCHEMA, TICKET, load_schema

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.core.schema.schema_branch import SchemaBranch
    from infrahub.database import InfrahubDatabase


@dataclass(frozen=True)
class BranchDataset:
    branch: Branch
    ids: dict[str, str]

    def keys(self, node_ids: list[str]) -> set[str]:
        keys_by_id = {node_id: key for key, node_id in self.ids.items()}
        return {keys_by_id[node_id] for node_id in node_ids}


async def _update(db: InfrahubDatabase, branch: Branch, node_id: str, **changes: Any) -> None:
    node = await NodeManager.get_one(db=db, id=node_id, branch=branch, raise_on_error=True)
    for attribute_name, attribute_changes in changes.items():
        attribute = getattr(node, attribute_name)
        for property_name, property_value in attribute_changes.items():
            setattr(attribute, property_name, property_value)
    await node.save(db=db)


@dataclass(frozen=True, kw_only=True)
class ValueFilterCase:
    name: str
    kind: str
    filters: dict[str, Any]
    expected_on_default: set[str]
    expected_on_branch: set[str]
    partial_match: bool = False


VALUE_FILTER_CASES = [
    ValueFilterCase(
        name="value",
        kind=TestKind.CAR,
        filters={"color__value": "red"},
        expected_on_default={"car-red", "car-ruby", "car-scarlet", "car-coral"},
        expected_on_branch={"car-ruby", "car-coral"},
    ),
    ValueFilterCase(
        name="value_set_on_the_branch",
        kind=TestKind.CAR,
        filters={"color__value": "blue"},
        expected_on_default=set(),
        expected_on_branch={"car-red", "car-scarlet"},
    ),
    ValueFilterCase(
        name="values",
        kind=TestKind.CAR,
        filters={"color__values": ["red"]},
        expected_on_default={"car-red", "car-ruby", "car-scarlet", "car-coral"},
        expected_on_branch={"car-ruby", "car-coral"},
    ),
    ValueFilterCase(
        name="partial_match",
        kind=TestKind.CAR,
        filters={"color__value": "ed"},
        partial_match=True,
        expected_on_default={"car-red", "car-ruby", "car-scarlet", "car-coral"},
        expected_on_branch={"car-ruby", "car-coral"},
    ),
    ValueFilterCase(
        name="any_attribute_keeps_the_other_attributes",
        kind=TestKind.CAR,
        filters={"any__value": "red"},
        expected_on_default={"car-red", "car-ruby", "car-scarlet", "car-coral"},
        expected_on_branch={"car-ruby", "car-scarlet", "car-coral"},
    ),
    ValueFilterCase(
        name="flag",
        kind=TestKind.CAR,
        filters={"color__is_protected": False},
        expected_on_default={"car-red", "car-ruby", "car-scarlet", "car-green", "car-coral"},
        expected_on_branch={"car-red", "car-ruby", "car-scarlet", "car-coral"},
    ),
    ValueFilterCase(
        name="flag_set_on_the_branch",
        kind=TestKind.CAR,
        filters={"color__is_protected": True},
        expected_on_default=set(),
        expected_on_branch={"car-green"},
    ),
    ValueFilterCase(
        name="source",
        kind=TestKind.CAR,
        filters={"color__source__id": "alice"},
        expected_on_default={"car-red"},
        expected_on_branch=set(),
    ),
    ValueFilterCase(
        name="source_set_on_the_branch",
        kind=TestKind.CAR,
        filters={"color__source__id": "carol"},
        expected_on_default=set(),
        expected_on_branch={"car-red"},
    ),
    ValueFilterCase(
        name="peer_attribute",
        kind=TestKind.CAR,
        filters={"owner__name__value": "bob"},
        expected_on_default={"car-scarlet"},
        expected_on_branch=set(),
    ),
    ValueFilterCase(
        name="peer_attribute_set_on_the_branch",
        kind=TestKind.CAR,
        filters={"owner__name__value": "robert"},
        expected_on_default=set(),
        expected_on_branch={"car-scarlet"},
    ),
    ValueFilterCase(
        name="any_of_several_peers",
        kind=TestKind.PERSON,
        filters={"cars__color__value": "red"},
        expected_on_default={"alice", "bob", "carol"},
        expected_on_branch={"alice", "carol"},
    ),
    ValueFilterCase(
        name="isnull",
        kind=TestKind.CAR,
        filters={"description__isnull": True},
        expected_on_default={"car-ruby", "car-green", "car-coral"},
        expected_on_branch={"car-ruby", "car-green"},
    ),
    ValueFilterCase(
        name="peer_ids",
        kind=TestKind.CAR,
        filters={"owner__ids": ["alice"]},
        expected_on_default={"car-red", "car-ruby"},
        expected_on_branch={"car-red", "car-ruby"},
    ),
]


class TestReadsByValueOnBranch:
    """On a branch, reads that select nodes by value compare the value the branch shows for each node."""

    @pytest.fixture(scope="class")
    async def dataset(
        self,
        db: InfrahubDatabase,
        default_branch_scope_class: Branch,
        register_core_models_schema_scope_class: SchemaBranch,
    ) -> BranchDataset:
        await load_schema(db=db, schema=CAR_SCHEMA)
        await load_schema(db=db, schema=SchemaRoot(nodes=[TICKET]))

        ids: dict[str, str] = {}
        maker = await Node.init(db=db, schema=TestKind.MANUFACTURER)
        await maker.new(db=db, name="maker")
        await maker.save(db=db)
        for name in ("alice", "bob", "carol"):
            person = await Node.init(db=db, schema=TestKind.PERSON)
            await person.new(db=db, name=name)
            await person.save(db=db)
            ids[name] = person.id

        cars: dict[str, dict[str, Any]] = {
            "car-red": {"color": {"value": "red", "source": ids["alice"]}, "description": "fast", "owner": "alice"},
            "car-ruby": {"color": "red", "owner": "alice"},
            "car-scarlet": {"color": "red", "description": "red", "owner": "bob"},
            "car-green": {"color": "green", "owner": "carol"},
            "car-coral": {"color": "red", "owner": "carol"},
        }
        for name, values in cars.items():
            car = await Node.init(db=db, schema=TestKind.CAR)
            await car.new(
                db=db,
                name=name,
                manufacturer=maker,
                **{key: ids[value] if key == "owner" else value for key, value in values.items()},
            )
            await car.save(db=db)
            ids[name] = car.id

        ticket = await Node.init(db=db, schema=TestKind.TICKET)
        await ticket.new(db=db, title="t-old", ticket_id=1)
        await ticket.save(db=db)
        ids["ticket"] = ticket.id

        branch = await create_branch(db=db, branch_name="reads-by-value")
        await _update(db, branch, ids["car-red"], color={"value": "blue", "source": ids["carol"]})
        await _update(db, branch, ids["car-scarlet"], color={"value": "blue"})
        await _update(db, branch, ids["car-green"], color={"is_protected": True}, name={"value": "car-teal"})
        await _update(db, branch, ids["car-coral"], color={"value": "blue"}, description={"value": "shiny"})
        await _update(db, branch, ids["car-coral"], color={"value": "red"})
        await _update(db, branch, ids["bob"], name={"value": "robert"})
        await _update(db, branch, ids["ticket"], title={"value": "t-new"})

        return BranchDataset(branch=branch, ids=ids)

    def _resolve_filters(self, dataset: BranchDataset, filters: dict[str, Any]) -> dict[str, Any]:
        resolved: dict[str, Any] = {}
        for key, value in filters.items():
            if key.endswith("__id"):
                resolved[key] = dataset.ids[value]
            elif key.endswith("__ids"):
                resolved[key] = [dataset.ids[item] for item in value]
            else:
                resolved[key] = value
        return resolved

    @pytest.mark.parametrize("case", VALUE_FILTER_CASES, ids=lambda case: case.name)
    async def test_node_list_filter(
        self, db: InfrahubDatabase, default_branch_scope_class: Branch, dataset: BranchDataset, case: ValueFilterCase
    ) -> None:
        filters = self._resolve_filters(dataset=dataset, filters=case.filters)
        for branch, expected in (
            (default_branch_scope_class, case.expected_on_default),
            (dataset.branch, case.expected_on_branch),
        ):
            nodes = await NodeManager.query(
                db=db, schema=case.kind, branch=branch, filters=filters, partial_match=case.partial_match
            )
            count = await NodeManager.count(
                db=db, schema=case.kind, branch=branch, filters=filters, partial_match=case.partial_match
            )

            assert (branch.name, dataset.keys([node.id for node in nodes])) == (branch.name, expected)
            assert (branch.name, count) == (branch.name, len(expected))

    async def test_filter_and_order_on_the_same_attribute(self, db: InfrahubDatabase, dataset: BranchDataset) -> None:
        nodes = await NodeManager.query(
            db=db,
            schema=TestKind.CAR,
            branch=dataset.branch,
            filters={"color__values": ["red", "green"]},
            order=OrderModel(
                by=(
                    OrderByEntry(field="color__value", direction=OrderDirection.ASC),
                    OrderByEntry(field="name__value", direction=OrderDirection.ASC),
                )
            ),
        )

        assert [dataset.keys([node.id]).pop() for node in nodes] == ["car-green", "car-coral", "car-ruby"]

    async def test_relationship_read_with_a_filter(
        self, db: InfrahubDatabase, default_branch_scope_class: Branch, dataset: BranchDataset
    ) -> None:
        person_schema = db.schema.get(name=TestKind.PERSON, branch=dataset.branch)
        found: dict[tuple[str, str], set[str]] = {}
        for branch in (default_branch_scope_class, dataset.branch):
            for color in ("red", "blue"):
                peers = await NodeManager.query_peers(
                    db=db,
                    ids=[dataset.ids["alice"]],
                    source_kind=TestKind.PERSON,
                    schema=person_schema.get_relationship(name="cars"),
                    filters={"cars__color__value": color},
                    branch=branch,
                )
                found[branch.name, color] = dataset.keys([peer.peer_id for peer in peers])

        assert found == {
            (default_branch_scope_class.name, "red"): {"car-red", "car-ruby"},
            (default_branch_scope_class.name, "blue"): set(),
            (dataset.branch.name, "red"): {"car-ruby"},
            (dataset.branch.name, "blue"): {"car-red"},
        }

    async def test_graphql_reads_with_a_filter(self, db: InfrahubDatabase, dataset: BranchDataset) -> None:
        query = """
        query ($person: ID!) {
            TestingCar(color__value: "red") { count edges { node { id } } }
            TestingPerson(ids: [$person]) { edges { node { cars(color__value: "red") { count edges { node { id } } } } } }
        }
        """
        gql_params = await prepare_graphql_params(db=db, branch=dataset.branch)
        result = await graphql(
            schema=gql_params.schema,
            source=query,
            context_value=gql_params.context,
            root_value=None,
            variable_values={"person": dataset.ids["alice"]},
        )

        assert result.errors is None
        assert result.data
        cars = result.data["TestingCar"]
        alice_cars = result.data["TestingPerson"]["edges"][0]["node"]["cars"]
        assert cars["count"] == 2
        assert dataset.keys([edge["node"]["id"] for edge in cars["edges"]]) == {"car-ruby", "car-coral"}
        assert alice_cars["count"] == 1
        assert dataset.keys([edge["node"]["id"] for edge in alice_cars["edges"]]) == {"car-ruby"}

    async def test_lookup_by_default_filter(
        self, db: InfrahubDatabase, default_branch_scope_class: Branch, dataset: BranchDataset
    ) -> None:
        on_default = await NodeManager.get_one_by_default_filter(
            db=db, id="car-green", kind=TestKind.CAR, branch=default_branch_scope_class
        )
        old_name_on_branch = await NodeManager.get_one_by_default_filter(
            db=db, id="car-green", kind=TestKind.CAR, branch=dataset.branch
        )
        new_name_on_branch = await NodeManager.get_one_by_default_filter(
            db=db, id="car-teal", kind=TestKind.CAR, branch=dataset.branch
        )

        assert on_default
        assert on_default.id == dataset.ids["car-green"]
        assert old_name_on_branch is None
        assert new_name_on_branch
        assert new_name_on_branch.id == dataset.ids["car-green"]

    async def test_lookup_by_hfid(
        self, db: InfrahubDatabase, default_branch_scope_class: Branch, dataset: BranchDataset
    ) -> None:
        found: dict[tuple[str, str], str | None] = {}
        for branch in (default_branch_scope_class, dataset.branch):
            for title in ("t-old", "t-new"):
                node = await NodeManager.get_one_by_hfid(db=db, hfid=[title, "1"], kind=TestKind.TICKET, branch=branch)
                found[branch.name, title] = node.id if node else None

        assert found == {
            (default_branch_scope_class.name, "t-old"): dataset.ids["ticket"],
            (default_branch_scope_class.name, "t-new"): None,
            (dataset.branch.name, "t-old"): None,
            (dataset.branch.name, "t-new"): dataset.ids["ticket"],
        }

    @pytest.mark.parametrize("case_sensitive", [True, False], ids=["case_sensitive", "case_insensitive"])
    async def test_search(
        self, db: InfrahubDatabase, default_branch_scope_class: Branch, dataset: BranchDataset, case_sensitive: bool
    ) -> None:
        query = """
        query ($q: String!, $case_sensitive: Boolean!) {
            InfrahubSearchAnywhere(q: $q, partial_match: false, case_sensitive: $case_sensitive) {
                edges { node { id } }
            }
        }
        """
        found: dict[tuple[str, str], set[str]] = {}
        for branch in (default_branch_scope_class, dataset.branch):
            gql_params = await prepare_graphql_params(db=db, branch=branch)
            for title in ("t-old", "t-new"):
                result = await graphql(
                    schema=gql_params.schema,
                    source=query,
                    context_value=gql_params.context,
                    root_value=None,
                    variable_values={"q": title, "case_sensitive": case_sensitive},
                )
                assert result.errors is None
                assert result.data
                edges = result.data["InfrahubSearchAnywhere"]["edges"]
                found[branch.name, title] = dataset.keys([edge["node"]["id"] for edge in edges])

        assert found == {
            (default_branch_scope_class.name, "t-old"): {"ticket"},
            (default_branch_scope_class.name, "t-new"): set(),
            (dataset.branch.name, "t-old"): set(),
            (dataset.branch.name, "t-new"): {"ticket"},
        }


@dataclass(frozen=True)
class HierarchyDataset:
    branch: Branch
    nodes: dict[str, Node] = field(default_factory=dict)


class TestHierarchyReadByValueOnBranch:
    @pytest.fixture(scope="class")
    async def dataset(
        self, db: InfrahubDatabase, hierarchical_location_data_scope_class: dict[str, Node]
    ) -> HierarchyDataset:
        branch = await create_branch(db=db, branch_name="hierarchy-by-value")
        await _update(db, branch, hierarchical_location_data_scope_class["paris-r1"].id, status={"value": "offline"})
        return HierarchyDataset(branch=branch, nodes=hierarchical_location_data_scope_class)

    async def test_descendants_filtered_by_value(
        self, db: InfrahubDatabase, default_branch_scope_class: Branch, dataset: HierarchyDataset
    ) -> None:
        names_by_id = {node.id: name for name, node in dataset.nodes.items()}
        region_schema = db.schema.get(name="LocationRegion", branch=dataset.branch)
        found: dict[str, set[str]] = {}
        for branch in (default_branch_scope_class, dataset.branch):
            descendants = await NodeManager.query_hierarchy(
                db=db,
                id=dataset.nodes["europe"].id,
                direction=RelationshipHierarchyDirection.DESCENDANTS,
                node_schema=region_schema,
                filters={"descendants__status__value": "online"},
                branch=branch,
            )
            found[branch.name] = {names_by_id[node_id] for node_id in descendants}

        assert found == {
            default_branch_scope_class.name: {"paris", "london", "paris-r1", "london-r1"},
            dataset.branch.name: {"paris", "london", "london-r1"},
        }
