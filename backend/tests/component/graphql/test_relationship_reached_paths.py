from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from infrahub.core import registry
from infrahub.core.regeneration.models import ReachedPath, RelationshipHop
from infrahub.core.schema import GenericSchema
from infrahub.graphql.analyzer import InfrahubGraphQLQueryAnalyzer
from infrahub.graphql.initialization import prepare_graphql_params
from tests.constants import TestKind
from tests.helpers.schema import CAR_SCHEMA, DEVICE_SCHEMA, load_schema
from tests.helpers.test_app import TestInfrahubApp

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.database import InfrahubDatabase

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


async def _reached_paths(db: InfrahubDatabase, branch: Branch, query: str) -> dict[str, tuple[ReachedPath, ...]]:
    schema_branch = registry.schema.get_schema_branch(name=branch.name)
    gql_params = await prepare_graphql_params(db=db, branch=branch)
    report = InfrahubGraphQLQueryAnalyzer(
        query=query, schema=gql_params.schema, branch=branch, schema_branch=schema_branch
    ).query_report
    return report.relationship_reached_paths_by_kind


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
        interface_generic = registry.schema.get(name=TestKind.INTERFACE, branch=default_branch)
        assert isinstance(interface_generic, GenericSchema)

        result = await _reached_paths(db, default_branch, GENERIC_PEER)

        chain = ReachedPath(
            hops=(
                RelationshipHop(
                    node_kind=TestKind.DEVICE,
                    relationship_identifier=interfaces.identifier,
                    relationship_direction=interfaces.direction,
                ),
            )
        )
        assert result == dict.fromkeys(interface_generic.used_by, (chain,))

    @pytest.mark.parametrize(
        "query",
        [
            pytest.param(SFP_INSIDE_AN_INLINE_FRAGMENT, id="inline_fragment"),
            pytest.param(SFP_INSIDE_A_NAMED_FRAGMENT, id="named_fragment"),
        ],
    )
    async def test_a_kind_reached_through_a_fragment_keeps_the_chain_through_it(
        self, db: InfrahubDatabase, default_branch: Branch, device_schema: None, query: str
    ) -> None:
        device = registry.schema.get(name=TestKind.DEVICE, branch=default_branch)
        interfaces = device.get_relationship("interfaces")
        assert interfaces.identifier is not None
        physical_interface = registry.schema.get(name=TestKind.PHYSICAL_INTERFACE, branch=default_branch)
        sfp = physical_interface.get_relationship("sfp")
        assert sfp.identifier is not None
        interface_generic = registry.schema.get(name=TestKind.INTERFACE, branch=default_branch)
        assert isinstance(interface_generic, GenericSchema)

        result = await _reached_paths(db, default_branch, query)

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
        assert result == {
            **dict.fromkeys(interface_generic.used_by, (ReachedPath(hops=(interfaces_hop,)),)),
            TestKind.SFP: (ReachedPath(hops=(sfp_hop, interfaces_hop)),),
        }
