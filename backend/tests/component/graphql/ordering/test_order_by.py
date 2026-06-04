from dataclasses import dataclass
from typing import Any

import pytest

from infrahub.core import registry
from infrahub.core.branch import Branch
from infrahub.core.node import Node
from infrahub.core.schema import NodeSchema
from infrahub.core.schema.schema_branch import SchemaBranch
from infrahub.database import InfrahubDatabase
from infrahub.graphql.initialization import prepare_graphql_params
from tests.conftest import do_car_person_schema_unregistered
from tests.helpers.graphql import graphql


@dataclass(frozen=True)
class OrderByCase:
    name: str
    order_by: list[str]
    expected_names: list[str]


@dataclass(frozen=True)
class OrderByErrorCase:
    name: str
    order_input: dict[str, Any]
    error_substring: str


class TestRootOrderByString:
    """Root-level GraphQL `order: {order_by: [...]}` against a single dataset."""

    @pytest.fixture(scope="class")
    async def dataset(
        self,
        db: InfrahubDatabase,
        default_branch_scope_class: Branch,
        criticality_schema_scope_class: NodeSchema,
    ) -> list[str]:
        names: list[str] = []
        for name, level in [("koala", 1), ("aardvark", 2), ("pangolin", 1), ("zebra", 2)]:
            node = await Node.init(db=db, schema=criticality_schema_scope_class)
            await node.new(db=db, name=name, level=level)
            await node.save(db=db)
            names.append(name)
        return names

    cases = [
        OrderByCase(
            name="attribute-asc",
            order_by=["name__value__asc"],
            expected_names=["aardvark", "koala", "pangolin", "zebra"],
        ),
        OrderByCase(
            name="attribute-desc",
            order_by=["name__value__desc"],
            expected_names=["zebra", "pangolin", "koala", "aardvark"],
        ),
        OrderByCase(
            name="attribute-default-direction",
            order_by=["name__value"],
            expected_names=["aardvark", "koala", "pangolin", "zebra"],
        ),
        OrderByCase(
            name="metadata-created-asc",
            order_by=["node_metadata__created_at__asc"],
            expected_names=["koala", "aardvark", "pangolin", "zebra"],
        ),
        OrderByCase(
            name="metadata-created-desc",
            order_by=["node_metadata__created_at__desc"],
            expected_names=["zebra", "pangolin", "aardvark", "koala"],
        ),
        OrderByCase(
            name="mixed-level-asc-then-name-desc",
            order_by=["level__value__asc", "name__value__desc"],
            expected_names=["pangolin", "koala", "zebra", "aardvark"],
        ),
    ]

    @pytest.mark.parametrize("case", cases, ids=lambda c: c.name)
    async def test_order_by_string(
        self,
        db: InfrahubDatabase,
        default_branch_scope_class: Branch,
        dataset: list[str],
        case: OrderByCase,
    ) -> None:
        query = """
        query($order: OrderInput) {
            TestCriticality(order: $order) {
                edges { node { name { value } } }
            }
        }
        """
        gql_params = await prepare_graphql_params(db=db, branch=default_branch_scope_class)
        result = await graphql(
            schema=gql_params.schema,
            source=query,
            context_value=gql_params.context,
            root_value=None,
            variable_values={"order": {"order_by": case.order_by}},
        )

        assert result.errors is None
        assert result.data
        names = [edge["node"]["name"]["value"] for edge in result.data["TestCriticality"]["edges"]]
        actual_in_dataset = [n for n in names if n in dataset]
        assert actual_in_dataset == case.expected_names

    error_cases = [
        OrderByErrorCase(
            name="unknown-field",
            order_input={"order_by": ["does_not_exist__value__asc"]},
            error_substring="attribute 'does_not_exist' not defined on this schema",
        ),
        OrderByErrorCase(
            name="invalid-direction-token",
            order_input={"order_by": ["name__value__bogus"]},
            error_substring="Direction must be 'asc' or 'desc'",
        ),
        OrderByErrorCase(
            name="missing-property-segment",
            order_input={"order_by": ["name__asc"]},
            error_substring="Property segment is missing",
        ),
        OrderByErrorCase(
            name="both-forms-set",
            order_input={"node_metadata": {"created_at": "ASC"}, "order_by": ["name__value"]},
            error_substring="Cannot combine 'node_metadata' and 'order_by'",
        ),
    ]

    @pytest.mark.parametrize("case", error_cases, ids=lambda c: c.name)
    async def test_order_by_string_validation_errors(
        self,
        db: InfrahubDatabase,
        default_branch_scope_class: Branch,
        dataset: list[str],
        case: OrderByErrorCase,
    ) -> None:
        query = """
        query($order: OrderInput) {
            TestCriticality(order: $order) {
                edges { node { name { value } } }
            }
        }
        """
        gql_params = await prepare_graphql_params(db=db, branch=default_branch_scope_class)
        result = await graphql(
            schema=gql_params.schema,
            source=query,
            context_value=gql_params.context,
            root_value=None,
            variable_values={"order": case.order_input},
        )

        assert result.errors is not None
        assert any(case.error_substring in str(err.message) for err in result.errors)


@dataclass(frozen=True)
class CarPersonDataset:
    owner_id: str
    car_names: list[str]


class TestManyRelationshipOrderByString:
    """Many-relationship GraphQL `order: {order_by: [...]}` against a single dataset."""

    @pytest.fixture(scope="class", autouse=True)
    async def _schema(
        self,
        db: InfrahubDatabase,
        default_branch_scope_class: Branch,
        register_core_models_schema_scope_class: SchemaBranch,
    ) -> SchemaBranch:
        return registry.schema.register_schema(
            schema=do_car_person_schema_unregistered(), branch=default_branch_scope_class.name
        )

    @pytest.fixture(scope="class")
    async def dataset(
        self,
        db: InfrahubDatabase,
        default_branch_scope_class: Branch,
        _schema: SchemaBranch,
    ) -> CarPersonDataset:
        car_schema = _schema.get_node(name="TestCar", duplicate=False)
        person_schema = _schema.get_node(name="TestPerson", duplicate=False)

        owner = await Node.init(db=db, schema=person_schema)
        await owner.new(db=db, name="fleet-owner")
        await owner.save(db=db)

        driver_charlie = await Node.init(db=db, schema=person_schema)
        await driver_charlie.new(db=db, name="charlie-driver")
        await driver_charlie.save(db=db)

        driver_alice = await Node.init(db=db, schema=person_schema)
        await driver_alice.new(db=db, name="alice-driver")
        await driver_alice.save(db=db)

        driver_bob = await Node.init(db=db, schema=person_schema)
        await driver_bob.new(db=db, name="bob-driver")
        await driver_bob.save(db=db)

        car_setups = [
            ("zeta-car", 4, driver_charlie),
            ("aardvark-car", 2, driver_alice),
            ("pangolin-car", 4, driver_bob),
        ]
        for car_name, nbr_seats, driver in car_setups:
            car = await Node.init(db=db, schema=car_schema)
            await car.new(db=db, name=car_name, nbr_seats=nbr_seats, is_electric=False, owner=owner, driver=driver)
            await car.save(db=db)

        default_branch_scope_class.update_schema_hash()
        return CarPersonDataset(owner_id=owner.id, car_names=[name for name, *_ in car_setups])

    cases = [
        OrderByCase(
            name="attribute-asc",
            order_by=["name__value__asc"],
            expected_names=["aardvark-car", "pangolin-car", "zeta-car"],
        ),
        OrderByCase(
            name="attribute-desc",
            order_by=["name__value__desc"],
            expected_names=["zeta-car", "pangolin-car", "aardvark-car"],
        ),
        OrderByCase(
            name="relationship-attribute-asc",
            order_by=["driver__name__value__asc"],
            expected_names=["aardvark-car", "pangolin-car", "zeta-car"],
        ),
        OrderByCase(
            name="relationship-attribute-desc",
            order_by=["driver__name__value__desc"],
            expected_names=["zeta-car", "pangolin-car", "aardvark-car"],
        ),
        OrderByCase(
            name="metadata-created-asc",
            order_by=["node_metadata__created_at__asc"],
            expected_names=["zeta-car", "aardvark-car", "pangolin-car"],
        ),
        OrderByCase(
            name="metadata-created-desc",
            order_by=["node_metadata__created_at__desc"],
            expected_names=["pangolin-car", "aardvark-car", "zeta-car"],
        ),
        OrderByCase(
            # nbr_seats: aardvark=2, zeta=4, pangolin=4; tiebreaker by name asc
            name="combo-nbr_seats-asc-then-name-asc",
            order_by=["nbr_seats__value__asc", "name__value__asc"],
            expected_names=["aardvark-car", "pangolin-car", "zeta-car"],
        ),
        OrderByCase(
            name="combo-nbr_seats-desc-then-name-desc",
            order_by=["nbr_seats__value__desc", "name__value__desc"],
            expected_names=["zeta-car", "pangolin-car", "aardvark-car"],
        ),
        OrderByCase(
            # Cross-kind combo: rel-attribute primary, metadata secondary.
            name="combo-driver-name-asc-then-created-desc",
            order_by=["driver__name__value__asc", "node_metadata__created_at__desc"],
            expected_names=["aardvark-car", "pangolin-car", "zeta-car"],
        ),
    ]

    @pytest.mark.parametrize("case", cases, ids=lambda c: c.name)
    async def test_order_by_string(
        self,
        db: InfrahubDatabase,
        default_branch_scope_class: Branch,
        dataset: CarPersonDataset,
        case: OrderByCase,
    ) -> None:
        query = """
        query($owner_id: ID!, $order: OrderInput) {
            TestPerson(ids: [$owner_id]) {
                edges {
                    node {
                        cars(order: $order) {
                            edges { node { name { value } } }
                        }
                    }
                }
            }
        }
        """
        gql_params = await prepare_graphql_params(db=db, branch=default_branch_scope_class)
        result = await graphql(
            schema=gql_params.schema,
            source=query,
            context_value=gql_params.context,
            root_value=None,
            variable_values={"owner_id": dataset.owner_id, "order": {"order_by": case.order_by}},
        )

        assert result.errors is None
        assert result.data
        cars_edges = result.data["TestPerson"]["edges"][0]["node"]["cars"]["edges"]
        names = [e["node"]["name"]["value"] for e in cars_edges]
        assert names == case.expected_names


class TestHierarchyOrderByString:
    """Hierarchical descendants `order: {order_by: [...]}` against a single dataset.

    The fixture assigns racks alternating `status` values (r1=online, r2=offline) while sites
    keep the default ("online"); combo cases below rely on that to exercise multi-key ordering
    with a real tiebreaker on the primary key.
    """

    cases = [
        OrderByCase(
            name="attribute-asc",
            order_by=["name__value__asc"],
            expected_names=["london", "london-r1", "london-r2", "paris", "paris-r1", "paris-r2"],
        ),
        OrderByCase(
            name="attribute-desc",
            order_by=["name__value__desc"],
            expected_names=["paris-r2", "paris-r1", "paris", "london-r2", "london-r1", "london"],
        ),
        OrderByCase(
            name="metadata-created-asc",
            order_by=["node_metadata__created_at__asc"],
            expected_names=["paris", "paris-r1", "paris-r2", "london", "london-r1", "london-r2"],
        ),
        OrderByCase(
            name="metadata-created-desc",
            order_by=["node_metadata__created_at__desc"],
            expected_names=["london-r2", "london-r1", "london", "paris-r2", "paris-r1", "paris"],
        ),
        OrderByCase(
            name="combo-status-asc-then-name-asc",
            order_by=["status__value__asc", "name__value__asc"],
            expected_names=["london-r2", "paris-r2", "london", "london-r1", "paris", "paris-r1"],
        ),
        OrderByCase(
            name="combo-status-desc-then-created-asc",
            order_by=["status__value__desc", "node_metadata__created_at__asc"],
            expected_names=["paris", "paris-r1", "london", "london-r1", "paris-r2", "london-r2"],
        ),
    ]

    @pytest.mark.parametrize("case", cases, ids=lambda c: c.name)
    async def test_descendants_order_by_string(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        hierarchical_location_data: dict[str, Node],
        case: OrderByCase,
    ) -> None:
        europe = hierarchical_location_data["europe"]
        query = """
        query($region_id: ID!, $order: OrderInput) {
            LocationRegion(ids: [$region_id]) {
                edges {
                    node {
                        descendants(order: $order) {
                            edges { node { name { value } } }
                        }
                    }
                }
            }
        }
        """
        gql_params = await prepare_graphql_params(db=db, branch=default_branch)
        result = await graphql(
            schema=gql_params.schema,
            source=query,
            context_value=gql_params.context,
            root_value=None,
            variable_values={"region_id": europe.id, "order": {"order_by": case.order_by}},
        )

        assert result.errors is None
        assert result.data
        descendants = result.data["LocationRegion"]["edges"][0]["node"]["descendants"]["edges"]
        names = [d["node"]["name"]["value"] for d in descendants]
        assert names == case.expected_names
