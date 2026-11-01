from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import pytest

from infrahub.core import registry
from infrahub.core.constants import InfrahubKind
from infrahub.core.regeneration.models import PeerFilters, ReachedPath, RelationshipHop, RelationshipRead
from infrahub.graphql.analyzer import InfrahubGraphQLQueryAnalyzer
from infrahub.graphql.initialization import prepare_graphql_params
from tests.constants import TestKind
from tests.helpers.schema import CAR_SCHEMA, DEVICE_SCHEMA, load_schema
from tests.helpers.test_app import TestInfrahubApp

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.database import InfrahubDatabase
    from infrahub.graphql.analyzer import GraphQLQueryReport


@dataclass(frozen=True)
class QueryCase:
    name: str
    query: str


SINGLE_HOP = """
query { TestingCar { edges { node { owner { node { name { value } } } } } } }
"""

# The car reads its owner's name through two distinct relationships, so the owner kind is reached by
# two chains and both are kept.
TWO_RELATIONSHIPS_TO_THE_SAME_KIND = """
query {
    TestingCar {
        edges { node {
            owner { node { name { value } } }
            previous_owner { node { name { value } } }
        } }
    }
}
"""

# The owner kind is read both at a root query and through the car's owner relationship.
ROOT_AND_TRAVERSED = """
query {
    TestingCar { edges { node { owner { node { name { value } } } } } }
    TestingPerson { edges { node { name { value } } } }
}
"""

# Each query reads an account inside a fragment under the metadata of a field, not on the node the field
# belongs to: no relationship leads from the car to the account, so a change to it cannot be traced back.
ACCOUNT_IN_A_FRAGMENT_UNDER_FIELD_METADATA = [
    QueryCase(
        name="attribute_source",
        query="""
query { TestingCar { edges { node {
    name { value source { ... on CoreAccount { name { value } } } }
} } } }
""",
    ),
    QueryCase(
        name="attribute_owner",
        query="""
query { TestingCar { edges { node {
    name { value owner { ... on CoreAccount { name { value } } } }
} } } }
""",
    ),
    QueryCase(
        name="relationship_property_source",
        query="""
query { TestingCar { edges { node {
    owner { node { name { value } } properties { source { ... on CoreAccount { name { value } } } } }
} } } }
""",
    ),
]

# The interface generic is the query root and reads its device, a relationship every implementation carries.
DEVICE_OF_A_GENERIC_ROOT = """
query { TestingInterface { edges { node { device { node { name { value } } } } } } }
"""

# The device reaches its interfaces through a relationship whose peer is a generic, so the change is
# resolved to each concrete interface kind.
GENERIC_PEER = """
query { TestingDevice { edges { node { interfaces { edges { node { name { value } } } } } } } }
"""

# The SFP is reached through a relationship that only the physical interface has, so the query selects
# it inside a fragment on that kind.
SFP_INSIDE_AN_INLINE_FRAGMENT = """
query {
    TestingDevice { edges { node {
        interfaces { edges { node {
            ... on TestingPhysicalInterface { sfp { node { serial_number { value } } } }
        } } }
    } } }
}
"""

SFP_INSIDE_A_NAMED_FRAGMENT = """
fragment PhysicalInterfaceSfp on TestingPhysicalInterface { sfp { node { serial_number { value } } } }

query {
    TestingDevice { edges { node {
        interfaces { edges { node { ...PhysicalInterfaceSfp } } }
    } } }
}
"""

SFP_INSIDE_A_SPREAD_IN_AN_INLINE_FRAGMENT = """
fragment PhysicalInterfaceSfp on TestingPhysicalInterface { sfp { node { serial_number { value } } } }

query {
    TestingDevice { edges { node {
        interfaces { edges { node {
            ... on TestingPhysicalInterface { ...PhysicalInterfaceSfp }
        } } }
    } } }
}
"""

SFP_INSIDE_A_SPREAD_IN_A_NAMED_FRAGMENT = """
fragment PhysicalInterfaceSfp on TestingPhysicalInterface { sfp { node { serial_number { value } } } }
fragment InterfaceSfp on TestingPhysicalInterface { ...PhysicalInterfaceSfp }

query {
    TestingDevice { edges { node {
        interfaces { edges { node { ...InterfaceSfp } } }
    } } }
}
"""

SFP_INSIDE_NESTED_INLINE_FRAGMENTS = """
query {
    TestingDevice { edges { node {
        interfaces { edges { node {
            ... on TestingInterface { ... on TestingPhysicalInterface { sfp { node { serial_number { value } } } } }
        } } }
    } } }
}
"""

# The interface generic is the query root, and the SFP is read inside a fragment on one implementation.
SFP_INSIDE_A_FRAGMENT_ON_A_GENERIC_ROOT = """
query {
    TestingInterface { edges { node {
        ... on TestingPhysicalInterface { sfp { node { serial_number { value } } } }
    } } }
}
"""

# One named fragment spread both under the device's interfaces and under an interface root.
SFP_SPREAD_AT_TWO_PLACES = """
fragment PhysicalInterfaceSfp on TestingPhysicalInterface { sfp { node { serial_number { value } } } }

query {
    TestingDevice { edges { node {
        interfaces { edges { node { ...PhysicalInterfaceSfp } } }
    } } }
    TestingInterface { edges { node { ...PhysicalInterfaceSfp } } }
}
"""

SFP_FRAGMENT_QUERIES = [
    QueryCase(name="inline_fragment", query=SFP_INSIDE_AN_INLINE_FRAGMENT),
    QueryCase(name="named_fragment", query=SFP_INSIDE_A_NAMED_FRAGMENT),
    QueryCase(name="spread_in_an_inline_fragment", query=SFP_INSIDE_A_SPREAD_IN_AN_INLINE_FRAGMENT),
    QueryCase(name="spread_in_a_named_fragment", query=SFP_INSIDE_A_SPREAD_IN_A_NAMED_FRAGMENT),
    QueryCase(name="nested_inline_fragments", query=SFP_INSIDE_NESTED_INLINE_FRAGMENTS),
]


# Each query spreads a fragment that is not defined, which GraphQL validation reports; the reads around
# the spread are still analyzed.
SFP_BESIDE_A_SPREAD_OF_AN_UNDEFINED_FRAGMENT = [
    QueryCase(
        name="spread_in_an_inline_fragment",
        query="""
query { TestingDevice { edges { node { interfaces { edges { node {
    ... on TestingPhysicalInterface { sfp { node { serial_number { value } } } ...DoesNotExist }
} } } } } } }
""",
    ),
    QueryCase(
        name="spread_under_a_field",
        query="""
query { TestingDevice { edges { node { interfaces { edges { node {
    ... on TestingPhysicalInterface { sfp { node { serial_number { value } } } }
    ...DoesNotExist
} } } } } } }
""",
    ),
]


async def _query_report(db: InfrahubDatabase, branch: Branch, query: str) -> GraphQLQueryReport:
    schema_branch = registry.schema.get_schema_branch(name=branch.name)
    gql_params = await prepare_graphql_params(db=db, branch=branch)
    return InfrahubGraphQLQueryAnalyzer(
        query=query, schema=gql_params.schema, branch=branch, schema_branch=schema_branch
    ).query_report


async def _reached_paths(db: InfrahubDatabase, branch: Branch, query: str) -> dict[str, tuple[ReachedPath, ...]]:
    return (await _query_report(db, branch, query)).relationship_reached_paths_by_kind


class TestReachedPathsFromQueryCarSchema(TestInfrahubApp):
    @pytest.fixture(scope="class")
    async def car_schema(self, db: InfrahubDatabase, default_branch: Branch) -> None:
        await load_schema(db=db, schema=CAR_SCHEMA, update_db=True)

    async def test_single_hop_query_narrows_to_the_owner(
        self, db: InfrahubDatabase, default_branch: Branch, car_schema: None
    ) -> None:
        owner = registry.schema.get(name=TestKind.CAR, branch=default_branch).get_relationship("owner")
        assert owner.identifier is not None

        result = await _reached_paths(db, default_branch, SINGLE_HOP)

        assert result == {
            TestKind.PERSON: (
                ReachedPath(
                    hops=(
                        RelationshipHop(
                            node_kind=TestKind.CAR,
                            relationship_identifier=owner.identifier,
                            relationship_direction=owner.direction,
                        ),
                    )
                ),
            )
        }

    async def test_a_kind_reached_by_two_relationships_keeps_both(
        self, db: InfrahubDatabase, default_branch: Branch, car_schema: None
    ) -> None:
        car = registry.schema.get(name=TestKind.CAR, branch=default_branch)
        owner = car.get_relationship("owner")
        assert owner.identifier is not None
        previous_owner = car.get_relationship("previous_owner")
        assert previous_owner.identifier is not None

        result = await _reached_paths(db, default_branch, TWO_RELATIONSHIPS_TO_THE_SAME_KIND)

        assert result.keys() == {TestKind.PERSON}
        assert set(result[TestKind.PERSON]) == {
            ReachedPath(
                hops=(
                    RelationshipHop(
                        node_kind=TestKind.CAR,
                        relationship_identifier=owner.identifier,
                        relationship_direction=owner.direction,
                    ),
                )
            ),
            ReachedPath(
                hops=(
                    RelationshipHop(
                        node_kind=TestKind.CAR,
                        relationship_identifier=previous_owner.identifier,
                        relationship_direction=previous_owner.direction,
                    ),
                )
            ),
        }

    async def test_a_kind_read_at_a_root_and_through_a_relationship_keeps_an_empty_chain_besides_its_chain(
        self, db: InfrahubDatabase, default_branch: Branch, car_schema: None
    ) -> None:
        owner = registry.schema.get(name=TestKind.CAR, branch=default_branch).get_relationship("owner")
        assert owner.identifier is not None

        result = await _reached_paths(db, default_branch, ROOT_AND_TRAVERSED)

        assert result == {
            TestKind.PERSON: (
                ReachedPath(hops=()),
                ReachedPath(
                    hops=(
                        RelationshipHop(
                            node_kind=TestKind.CAR,
                            relationship_identifier=owner.identifier,
                            relationship_direction=owner.direction,
                        ),
                    )
                ),
            )
        }

    @pytest.mark.parametrize("case", ACCOUNT_IN_A_FRAGMENT_UNDER_FIELD_METADATA, ids=lambda case: case.name)
    async def test_a_kind_read_in_a_fragment_under_field_metadata_gets_no_chain(
        self, db: InfrahubDatabase, default_branch: Branch, car_schema: None, case: QueryCase
    ) -> None:
        report = await _query_report(db, default_branch, case.query)

        assert InfrahubKind.ACCOUNT in report.traversed_kinds
        assert InfrahubKind.ACCOUNT not in report.relationship_reached_paths_by_kind


class TestReachedPathsFromQueryDeviceSchema(TestInfrahubApp):
    @pytest.fixture(scope="class")
    async def device_schema(self, db: InfrahubDatabase, default_branch: Branch) -> None:
        await load_schema(db=db, schema=DEVICE_SCHEMA, update_db=True)

    async def test_generic_peer_resolves_to_its_concrete_implementations(
        self, db: InfrahubDatabase, default_branch: Branch, device_schema: None
    ) -> None:
        device = registry.schema.get(name=TestKind.DEVICE, branch=default_branch)
        interfaces = device.get_relationship("interfaces")
        assert interfaces.identifier is not None

        result = await _reached_paths(db, default_branch, GENERIC_PEER)

        interface_chain = ReachedPath(
            hops=(
                RelationshipHop(
                    node_kind=TestKind.DEVICE,
                    relationship_identifier=interfaces.identifier,
                    relationship_direction=interfaces.direction,
                ),
            )
        )
        assert result == {
            TestKind.PHYSICAL_INTERFACE: (interface_chain,),
            TestKind.VIRTUAL_INTERFACE: (interface_chain,),
        }

    async def test_a_read_on_a_generic_root_is_recorded_once_per_implementation(
        self, db: InfrahubDatabase, default_branch: Branch, device_schema: None
    ) -> None:
        device = registry.schema.get(name=TestKind.PHYSICAL_INTERFACE, branch=default_branch).get_relationship("device")
        assert device.identifier is not None

        report = await _query_report(db, default_branch, DEVICE_OF_A_GENERIC_ROOT)

        assert report.relationship_reads == tuple(
            RelationshipRead(
                owner_kind=owner_kind,
                relationship_name="device",
                relationship_identifier=device.identifier,
                relationship_direction=device.direction,
                peer_kinds=frozenset({TestKind.DEVICE}),
                peer_filters=None,
            )
            for owner_kind in (TestKind.PHYSICAL_INTERFACE, TestKind.VIRTUAL_INTERFACE)
        )

    @pytest.mark.parametrize("case", SFP_FRAGMENT_QUERIES, ids=lambda case: case.name)
    async def test_a_field_read_inside_a_fragment_is_in_the_read_set(
        self, db: InfrahubDatabase, default_branch: Branch, device_schema: None, case: QueryCase
    ) -> None:
        report = await _query_report(db, default_branch, case.query)

        assert report.requested_read[TestKind.SFP].attributes == {"serial_number"}

    @pytest.mark.parametrize("case", SFP_BESIDE_A_SPREAD_OF_AN_UNDEFINED_FRAGMENT, ids=lambda case: case.name)
    async def test_a_spread_of_an_undefined_fragment_is_skipped(
        self, db: InfrahubDatabase, default_branch: Branch, device_schema: None, case: QueryCase
    ) -> None:
        report = await _query_report(db, default_branch, case.query)

        assert report.requested_read[TestKind.SFP].attributes == {"serial_number"}

    @pytest.mark.parametrize("case", SFP_FRAGMENT_QUERIES, ids=lambda case: case.name)
    async def test_a_kind_reached_through_a_fragment_keeps_the_chain_through_it(
        self, db: InfrahubDatabase, default_branch: Branch, device_schema: None, case: QueryCase
    ) -> None:
        device = registry.schema.get(name=TestKind.DEVICE, branch=default_branch)
        interfaces = device.get_relationship("interfaces")
        assert interfaces.identifier is not None
        physical_interface = registry.schema.get(name=TestKind.PHYSICAL_INTERFACE, branch=default_branch)
        sfp = physical_interface.get_relationship("sfp")
        assert sfp.identifier is not None

        result = await _reached_paths(db, default_branch, case.query)

        interfaces_hop = RelationshipHop(
            node_kind=TestKind.DEVICE,
            relationship_identifier=interfaces.identifier,
            relationship_direction=interfaces.direction,
        )
        sfp_hop = RelationshipHop(
            node_kind=TestKind.PHYSICAL_INTERFACE,
            relationship_identifier=sfp.identifier,
            relationship_direction=sfp.direction,
        )
        interface_chain = ReachedPath(hops=(interfaces_hop,))
        sfp_chain = ReachedPath(hops=(sfp_hop, interfaces_hop))
        assert result == {
            TestKind.PHYSICAL_INTERFACE: (interface_chain,),
            TestKind.VIRTUAL_INTERFACE: (interface_chain,),
            TestKind.SFP: (sfp_chain,),
        }

    async def test_a_fragment_on_an_implementation_of_a_generic_root_reaches_from_the_root(
        self, db: InfrahubDatabase, default_branch: Branch, device_schema: None
    ) -> None:
        physical_interface = registry.schema.get(name=TestKind.PHYSICAL_INTERFACE, branch=default_branch)
        sfp = physical_interface.get_relationship("sfp")
        assert sfp.identifier is not None

        result = await _reached_paths(db, default_branch, SFP_INSIDE_A_FRAGMENT_ON_A_GENERIC_ROOT)

        sfp_hop = RelationshipHop(
            node_kind=TestKind.PHYSICAL_INTERFACE,
            relationship_identifier=sfp.identifier,
            relationship_direction=sfp.direction,
        )
        assert result == {
            TestKind.PHYSICAL_INTERFACE: (ReachedPath(hops=()),),
            TestKind.SFP: (ReachedPath(hops=(sfp_hop,)),),
        }

    async def test_a_named_fragment_spread_at_two_places_keeps_a_chain_for_each(
        self, db: InfrahubDatabase, default_branch: Branch, device_schema: None
    ) -> None:
        device = registry.schema.get(name=TestKind.DEVICE, branch=default_branch)
        interfaces = device.get_relationship("interfaces")
        assert interfaces.identifier is not None
        physical_interface = registry.schema.get(name=TestKind.PHYSICAL_INTERFACE, branch=default_branch)
        sfp = physical_interface.get_relationship("sfp")
        assert sfp.identifier is not None

        result = await _reached_paths(db, default_branch, SFP_SPREAD_AT_TWO_PLACES)

        interfaces_hop = RelationshipHop(
            node_kind=TestKind.DEVICE,
            relationship_identifier=interfaces.identifier,
            relationship_direction=interfaces.direction,
        )
        sfp_hop = RelationshipHop(
            node_kind=TestKind.PHYSICAL_INTERFACE,
            relationship_identifier=sfp.identifier,
            relationship_direction=sfp.direction,
        )
        assert set(result[TestKind.SFP]) == {
            ReachedPath(hops=(sfp_hop,)),
            ReachedPath(hops=(sfp_hop, interfaces_hop)),
        }


def _red_cars_of_the_manufacturer(arguments: str) -> str:
    return (
        "query ($ids: [ID!]!, $color: String) {"
        " TestingCar(ids: $ids) { edges { node {"
        f" manufacturer {{ node {{ cars({arguments}) {{ edges {{ node {{ name {{ value }} }} }} }} }} }}"
        " } } } }"
    )


def _cars(*filters: tuple[str, str | tuple[str, ...]]) -> PeerFilters:
    return PeerFilters(relationship_name="cars", filters=tuple(filters))


@dataclass(frozen=True, kw_only=True)
class PeerFilterCase:
    name: str
    arguments: str
    expected: PeerFilters | None


PEER_FILTER_CASES = [
    PeerFilterCase(
        name="a_constant_value_filter_is_recorded",
        arguments='color__value: "red"',
        expected=_cars(("cars__color__value", "red")),
    ),
    PeerFilterCase(
        name="a_constant_values_filter_keeps_every_accepted_value",
        arguments='color__values: ["red", "blue"]',
        expected=_cars(("cars__color__values", ("red", "blue"))),
    ),
    PeerFilterCase(
        name="several_filters_are_recorded_together",
        arguments='color__value: "red", name__values: ["car-1"]',
        expected=_cars(("cars__color__value", "red"), ("cars__name__values", ("car-1",))),
    ),
    PeerFilterCase(
        name="an_ids_filter_is_recorded",
        arguments='ids: ["car-1-id"]',
        expected=_cars(("cars__ids", ("car-1-id",))),
    ),
    PeerFilterCase(name="a_filter_from_a_variable_is_left_out", arguments="color__value: $color", expected=None),
    PeerFilterCase(
        name="a_list_holding_a_variable_is_left_out", arguments='color__values: ["red", $color]', expected=None
    ),
    PeerFilterCase(name="an_empty_filter_value_is_left_out", arguments='color__value: ""', expected=None),
    PeerFilterCase(
        name="a_filter_on_a_related_node_is_left_out", arguments='owner__name__value: "alice"', expected=None
    ),
    PeerFilterCase(name="a_read_without_a_filter_records_none", arguments="limit: 5", expected=None),
]


class TestPeerFiltersFromQueryCarSchema(TestInfrahubApp):
    @pytest.fixture(scope="class")
    async def car_schema(self, db: InfrahubDatabase, default_branch: Branch) -> None:
        await load_schema(db=db, schema=CAR_SCHEMA, update_db=True)

    @pytest.mark.parametrize("case", PEER_FILTER_CASES, ids=lambda case: case.name)
    async def test_the_filters_of_a_relationship_read(
        self, db: InfrahubDatabase, default_branch: Branch, car_schema: None, case: PeerFilterCase
    ) -> None:
        report = await _query_report(db, default_branch, _red_cars_of_the_manufacturer(case.arguments))

        manufacturer = registry.schema.get(name=TestKind.MANUFACTURER, branch=default_branch).get_relationship("cars")
        car_manufacturer = registry.schema.get(name=TestKind.CAR, branch=default_branch).get_relationship(
            "manufacturer"
        )
        assert manufacturer.identifier is not None
        assert car_manufacturer.identifier is not None
        assert report.relationship_reads == (
            RelationshipRead(
                owner_kind=TestKind.CAR,
                relationship_name="manufacturer",
                relationship_identifier=car_manufacturer.identifier,
                relationship_direction=car_manufacturer.direction,
                peer_kinds=frozenset({TestKind.MANUFACTURER}),
                peer_filters=None,
            ),
            RelationshipRead(
                owner_kind=TestKind.MANUFACTURER,
                relationship_name="cars",
                relationship_identifier=manufacturer.identifier,
                relationship_direction=manufacturer.direction,
                peer_kinds=frozenset({TestKind.CAR}),
                peer_filters=case.expected,
            ),
        )
        assert report.relationship_reached_paths_by_kind[TestKind.CAR] == (
            ReachedPath(hops=()),
            ReachedPath(
                hops=(
                    RelationshipHop(
                        node_kind=TestKind.MANUFACTURER,
                        relationship_identifier=manufacturer.identifier,
                        relationship_direction=manufacturer.direction,
                        peer_filters=case.expected,
                    ),
                    RelationshipHop(
                        node_kind=TestKind.CAR,
                        relationship_identifier=car_manufacturer.identifier,
                        relationship_direction=car_manufacturer.direction,
                    ),
                )
            ),
        )
