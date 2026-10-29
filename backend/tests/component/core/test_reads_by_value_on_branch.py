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
from infrahub.core.query.node import NodeGetByHFIDQuery, NodeGetListQuery
from infrahub.core.schema import SchemaRoot
from infrahub.graphql.initialization import prepare_graphql_params
from tests.constants import TestKind
from tests.helpers.graphql import graphql
from tests.helpers.schema import CAR_SCHEMA, TICKET, load_schema
from tests.helpers.schema.agnostic_retirement import AGNOSTIC_RETIREMENT_SCHEMA, GADGET_KIND, WIDGET_KIND

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
        name="attribute_owner",
        kind=TestKind.CAR,
        filters={"color__owner__id": "alice"},
        expected_on_default={"car-red"},
        expected_on_branch=set(),
    ),
    ValueFilterCase(
        name="attribute_owner_set_on_the_branch",
        kind=TestKind.CAR,
        filters={"color__owner__id": "carol"},
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
            "car-red": {
                "color": {"value": "red", "source": ids["alice"], "owner": ids["alice"]},
                "description": "fast",
                "owner": "alice",
            },
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
        await _update(
            db, branch, ids["car-red"], color={"value": "blue", "source": ids["carol"], "owner": ids["carol"]}
        )
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

    async def test_branch_agnostic_lookup_by_hfid_finds_the_default_branch_value(
        self, db: InfrahubDatabase, default_branch_scope_class: Branch, dataset: BranchDataset
    ) -> None:
        node = await NodeManager.get_one_by_hfid(
            db=db, hfid=["t-old", "1"], kind=TestKind.TICKET, branch=default_branch_scope_class, branch_agnostic=True
        )

        assert node
        assert node.id == dataset.ids["ticket"]

    async def test_branch_agnostic_filter_finds_the_default_branch_value(
        self, db: InfrahubDatabase, default_branch_scope_class: Branch, dataset: BranchDataset
    ) -> None:
        nodes = await NodeManager.query(
            db=db,
            schema=TestKind.CAR,
            branch=default_branch_scope_class,
            filters={"color__value": "red"},
            branch_agnostic=True,
        )

        assert dataset.keys([node.id for node in nodes]) == {"car-red", "car-ruby", "car-scarlet", "car-coral"}

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
        nodes = hierarchical_location_data_scope_class
        branch = await create_branch(db=db, branch_name="hierarchy-by-value")
        await _update(db, branch, nodes["paris-r1"].id, status={"value": "offline"})
        await _update(db, branch, nodes["chicago"].id, name={"value": "chi-town"})
        moved_rack = await NodeManager.get_one(db=db, id=nodes["paris-r2"].id, branch=branch, raise_on_error=True)
        await moved_rack.parent.update(db=db, data=nodes["london"].id)
        await moved_rack.save(db=db)
        return HierarchyDataset(branch=branch, nodes=nodes)

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

    async def test_filter_through_the_parent_relationship(
        self, db: InfrahubDatabase, default_branch_scope_class: Branch, dataset: HierarchyDataset
    ) -> None:
        names_by_id = {node.id: name for name, node in dataset.nodes.items()}
        found: dict[tuple[str, str], set[str]] = {}
        for branch in (default_branch_scope_class, dataset.branch):
            for parent_name in ("paris", "chicago", "chi-town", "europe"):
                racks = await NodeManager.query(
                    db=db, schema="LocationRack", branch=branch, filters={"parent__name__value": parent_name}
                )
                found[branch.name, parent_name] = {names_by_id[rack.id] for rack in racks}

        assert found == {
            (default_branch_scope_class.name, "paris"): {"paris-r1", "paris-r2"},
            (default_branch_scope_class.name, "chicago"): {"chicago-r1", "chicago-r2"},
            (default_branch_scope_class.name, "chi-town"): set(),
            (default_branch_scope_class.name, "europe"): {"paris-r1", "paris-r2", "london-r1", "london-r2"},
            (dataset.branch.name, "paris"): {"paris-r1"},
            (dataset.branch.name, "chicago"): set(),
            (dataset.branch.name, "chi-town"): {"chicago-r1", "chicago-r2"},
            (dataset.branch.name, "europe"): {"paris-r1", "paris-r2", "london-r1", "london-r2"},
        }

    async def test_branch_agnostic_filter_through_the_parent_relationship(
        self, db: InfrahubDatabase, default_branch_scope_class: Branch, dataset: HierarchyDataset
    ) -> None:
        names_by_id = {node.id: name for name, node in dataset.nodes.items()}
        rack_schema = db.schema.get(name="LocationRack", branch=default_branch_scope_class)
        found: dict[str, set[str]] = {}
        for parent_name in ("paris", "london", "chicago", "chi-town"):
            query = await NodeGetListQuery.init(
                db=db,
                branch=default_branch_scope_class,
                schema=rack_schema,
                filters={"parent__name__value": parent_name},
                branch_agnostic=True,
            )
            await query.execute(db=db)
            found[parent_name] = {names_by_id[node_id] for node_id in query.get_node_ids()}

        assert found == {
            "paris": {"paris-r1", "paris-r2"},
            "london": {"london-r1", "london-r2", "paris-r2"},
            "chicago": {"chicago-r1", "chicago-r2"},
            "chi-town": {"chicago-r1", "chicago-r2"},
        }


class TestBranchAgnosticLookupByHFID:
    """A branch-agnostic HFID lookup returns a node whose HFID is the active value on any branch."""

    @pytest.fixture(scope="class")
    async def dataset(
        self,
        db: InfrahubDatabase,
        default_branch_scope_class: Branch,
        register_core_models_schema_scope_class: SchemaBranch,
    ) -> BranchDataset:
        await load_schema(db=db, schema=SchemaRoot(nodes=[TICKET]))

        ids: dict[str, str] = {}
        for key, title, ticket_id in (
            ("renamed-before-branching", "b-old", 11),
            ("renamed-on-default", "a-old", 12),
            ("deleted-on-default", "d-old", 13),
            ("renamed-on-branch", "c-old", 14),
        ):
            ticket = await Node.init(db=db, schema=TestKind.TICKET)
            await ticket.new(db=db, title=title, ticket_id=ticket_id)
            await ticket.save(db=db)
            ids[key] = ticket.id

        await _update(db, default_branch_scope_class, ids["renamed-before-branching"], title={"value": "b-new"})
        branch = await create_branch(db=db, branch_name="agnostic-hfid")
        await _update(db, default_branch_scope_class, ids["renamed-on-default"], title={"value": "a-new"})
        deleted = await NodeManager.get_one(
            db=db, id=ids["deleted-on-default"], branch=default_branch_scope_class, raise_on_error=True
        )
        await deleted.delete(db=db)
        await _update(db, branch, ids["renamed-on-branch"], title={"value": "c-new"})

        return BranchDataset(branch=branch, ids=ids)

    async def test_lookup_finds_a_value_active_on_any_branch(
        self, db: InfrahubDatabase, default_branch_scope_class: Branch, dataset: BranchDataset
    ) -> None:
        hfids = {
            "b-old": ["b-old", "11"],
            "b-new": ["b-new", "11"],
            "a-old": ["a-old", "12"],
            "a-new": ["a-new", "12"],
            "d-old": ["d-old", "13"],
            "c-old": ["c-old", "14"],
            "c-new": ["c-new", "14"],
        }
        found: dict[str, set[str]] = {}
        for title, hfid in hfids.items():
            query = await NodeGetByHFIDQuery.init(
                db=db, branch=default_branch_scope_class, node_kind=TestKind.TICKET, hfids=[hfid], branch_agnostic=True
            )
            await query.execute(db=db)
            found[title] = dataset.keys(query.get_node_uuids())

        assert found == {
            "b-old": set(),
            "b-new": {"renamed-before-branching"},
            "a-old": {"renamed-on-default"},
            "a-new": {"renamed-on-default"},
            "d-old": {"deleted-on-default"},
            "c-old": {"renamed-on-branch"},
            "c-new": {"renamed-on-branch"},
        }

    async def test_filter_finds_a_value_latest_on_any_branch(
        self, db: InfrahubDatabase, default_branch_scope_class: Branch, dataset: BranchDataset
    ) -> None:
        ticket_schema = db.schema.get(name=TestKind.TICKET, branch=default_branch_scope_class)
        found: dict[str, set[str]] = {}
        for title in ("b-old", "b-new", "a-old", "a-new", "c-old", "c-new"):
            query = await NodeGetListQuery.init(
                db=db,
                branch=default_branch_scope_class,
                schema=ticket_schema,
                filters={"title__value": title},
                branch_agnostic=True,
            )
            await query.execute(db=db)
            found[title] = dataset.keys(query.get_node_ids())

        assert found == {
            "b-old": set(),
            "b-new": {"renamed-before-branching"},
            "a-old": {"renamed-on-default"},
            "a-new": {"renamed-on-default"},
            "c-old": {"renamed-on-branch"},
            "c-new": {"renamed-on-branch"},
        }


class TestBranchAgnosticPeerFilter:
    """A branch-agnostic read of a relationship keeps a peer whose filtered value is the latest value on any branch."""

    @pytest.fixture(scope="class")
    async def dataset(
        self,
        db: InfrahubDatabase,
        default_branch_scope_class: Branch,
        register_core_models_schema_scope_class: SchemaBranch,
    ) -> BranchDataset:
        await load_schema(db=db, schema=AGNOSTIC_RETIREMENT_SCHEMA)

        ids: dict[str, str] = {}
        for serial, (key, name) in enumerate(
            (
                ("renamed-before-branching", "b-old"),
                ("renamed-on-default", "a-old"),
                ("renamed-on-branch", "c-old"),
            )
        ):
            gadget = await Node.init(db=db, schema=GADGET_KIND)
            await gadget.new(db=db, name=name)
            await gadget.save(db=db)
            ids[key] = gadget.id
            widget = await Node.init(db=db, schema=WIDGET_KIND)
            await widget.new(db=db, name=f"widget-{name}", serial=serial, gadget=gadget)
            await widget.save(db=db)
            ids[f"widget-{key}"] = widget.id

        await _update(db, default_branch_scope_class, ids["renamed-before-branching"], name={"value": "b-new"})
        branch = await create_branch(db=db, branch_name="agnostic-peer-filter")
        await _update(db, default_branch_scope_class, ids["renamed-on-default"], name={"value": "a-new"})
        await _update(db, branch, ids["renamed-on-branch"], name={"value": "c-new"})

        return BranchDataset(branch=branch, ids=ids)

    async def test_peer_filter_finds_a_value_latest_on_any_branch(
        self, db: InfrahubDatabase, default_branch_scope_class: Branch, dataset: BranchDataset
    ) -> None:
        widget_schema = db.schema.get(name=WIDGET_KIND, branch=default_branch_scope_class)
        widget_ids = [node_id for key, node_id in dataset.ids.items() if key.startswith("widget-")]
        found: dict[str, set[str]] = {}
        for name in ("b-old", "b-new", "a-old", "a-new", "c-old", "c-new"):
            peers = await NodeManager.query_peers(
                db=db,
                ids=widget_ids,
                source_kind=WIDGET_KIND,
                schema=widget_schema.get_relationship(name="gadget"),
                filters={"gadget__name__value": name},
                branch=default_branch_scope_class,
                branch_agnostic=True,
            )
            found[name] = dataset.keys([peer.get_peer_id() for peer in peers])

        assert found == {
            "b-old": set(),
            "b-new": {"renamed-before-branching"},
            "a-old": {"renamed-on-default"},
            "a-new": {"renamed-on-default"},
            "c-old": {"renamed-on-branch"},
            "c-new": {"renamed-on-branch"},
        }
