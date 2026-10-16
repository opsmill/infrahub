from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest

from infrahub.core.constants import InfrahubKind
from infrahub.core.node import Node
from infrahub.core.regeneration.impact import get_field_level_impacted_subscribers
from infrahub.core.regeneration.models import TargetSelection, Widening, WideningReason
from tests.constants import TestKind
from tests.helpers.diff_summary import node_diff
from tests.helpers.schema import CAR_SCHEMA, load_schema
from tests.helpers.test_app import TestInfrahubApp

from .helpers import SUBSCRIBER_KIND

if TYPE_CHECKING:
    from infrahub_sdk.client import InfrahubClient
    from infrahub_sdk.diff import NodeDiff

    from infrahub.core.branch import Branch
    from infrahub.database import InfrahubDatabase

# The root query pins a single car by ``ids``, so the query analyzer reports unique targets and the
# impact mapping takes its narrowing path. The query also reads ``name`` off the car's owner, a kind
# reached by traversing a relationship: a change there has no query-group membership to map back to.
QUERY_CAR_WITH_OWNER = """
query GetImpactCar($ids: [ID!]!) {
    TestingCar(ids: $ids) {
        edges {
            node {
                name { value }
                owner { node { name { value } } }
            }
        }
    }
}
"""

# The query reads only the car's ``display_label``, a computed value built from the car's own
# ``name`` and ``color``. A change to ``name`` moves the label but is reported under ``name``, which
# an exact-name match against the read set never sees.
QUERY_CAR_DISPLAY_LABEL = """
query GetImpactCarLabel($ids: [ID!]!) {
    TestingCar(ids: $ids) {
        edges {
            node {
                display_label
            }
        }
    }
}
"""

# The cars are selected by their owner's name, a filter argument the query never reads back: which cars
# answer the query moves when a car's ``owner`` relationship changes.
QUERY_CARS_BY_OWNER_NAME = """
query GetImpactCarsByOwner($owner: String!) {
    TestingCar(owner__name__value: $owner) {
        edges {
            node {
                name { value }
            }
        }
    }
}
"""

# ``any__value`` matches a car on any of its attributes, so a change to an attribute the query never
# reads can still move which cars answer it.
QUERY_CARS_BY_ANY_VALUE = """
query GetImpactCarsByAnyValue($value: String!) {
    TestingCar(any__value: $value) {
        edges {
            node {
                name { value }
            }
        }
    }
}
"""


class TestFieldLevelImpact(TestInfrahubApp):
    """Map a data change onto the query-group subscribers that must be regenerated.

    The query pins its root car by id and reads ``name`` off that car's owner. The query group tracks
    the car as its member and the tag as its subscriber, mirroring how a definition's target group is
    recorded in production.

    Only the wiring is covered here: that the real query analysis classifies the owner as traversed,
    and that a narrowed routing resolves group members to subscribers of the requested kind. The
    routing rule itself is pinned by the classifier's unit tests, which need no database.
    """

    @pytest.fixture(scope="class")
    async def dataset(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        client: InfrahubClient,
    ) -> dict[str, Any]:
        await load_schema(db=db, schema=CAR_SCHEMA, update_db=True)

        manufacturer = await Node.init(db=db, schema=TestKind.MANUFACTURER)
        await manufacturer.new(db=db, name="maker")
        await manufacturer.save(db=db)

        person = await Node.init(db=db, schema=TestKind.PERSON)
        await person.new(db=db, name="owner-1", height=180)
        await person.save(db=db)

        car = await Node.init(db=db, schema=TestKind.CAR)
        await car.new(db=db, name="car-1", color="red", owner=person, manufacturer=manufacturer)
        await car.save(db=db)

        subscriber = await Node.init(db=db, schema=TestKind.TAG)
        await subscriber.new(db=db, name="car-artifact")
        await subscriber.save(db=db)

        # A second subscriber of a different kind on the same group: only the requested kind may
        # come back, so an unrelated definition tracking the same targets is never regenerated.
        other_kind_subscriber = await Node.init(db=db, schema=TestKind.MANUFACTURER)
        await other_kind_subscriber.new(db=db, name="not-a-subscriber-kind")
        await other_kind_subscriber.save(db=db)

        stored_query = await Node.init(db=db, schema=InfrahubKind.GRAPHQLQUERY)
        await stored_query.new(
            db=db, name="GetImpactCar", query=QUERY_CAR_WITH_OWNER, models=[TestKind.CAR, TestKind.PERSON]
        )
        await stored_query.save(db=db)

        query_group = await Node.init(db=db, schema=InfrahubKind.GRAPHQLQUERYGROUP)
        await query_group.new(
            db=db,
            name="impact-targets",
            query=stored_query,
            members=[car],
            subscribers=[subscriber, other_kind_subscriber],
        )
        await query_group.save(db=db)

        return {
            "car_id": car.id,
            "person_id": person.id,
            "subscriber_id": subscriber.id,
            "other_kind_subscriber_id": other_kind_subscriber.id,
        }

    async def _resolve(
        self,
        *,
        dataset: dict[str, Any],
        default_branch: Branch,
        client: InfrahubClient,
        diff_summary: list[NodeDiff],
    ) -> TargetSelection:
        return await get_field_level_impacted_subscribers(
            query_payload=QUERY_CAR_WITH_OWNER,
            diff_summary=diff_summary,
            query_branch=default_branch.name,
            subscriber_kind=SUBSCRIBER_KIND,
            every_target=[dataset["subscriber_id"]],
            client=client,
        )

    async def test_root_node_change_selects_subscriber(
        self,
        dataset: dict[str, Any],
        default_branch: Branch,
        client: InfrahubClient,
    ) -> None:
        """A change on the group member resolves to that member's subscriber of the requested kind.

        The group also carries a subscriber of another kind, which must not come back: a narrowed
        routing regenerates the definitions it was asked about and nothing else.
        """
        resolved = await self._resolve(
            dataset=dataset,
            default_branch=default_branch,
            client=client,
            diff_summary=[
                node_diff(
                    node_id=dataset["car_id"],
                    kind=TestKind.CAR,
                    branch=default_branch.name,
                    field_names=["name"],
                )
            ],
        )
        assert resolved == TargetSelection(ids=[dataset["subscriber_id"]])

    async def test_display_label_backing_change_selects_subscriber(
        self,
        dataset: dict[str, Any],
        default_branch: Branch,
        client: InfrahubClient,
    ) -> None:
        """A change to a backing field that moves a read display_label selects the subscriber.

        The query reads only the car's display_label; the diff reports the backing ``name``. An
        exact-name match would drop it and leave the artifact stale. The label is built from the
        car's own attributes, so the routing narrows to the car's subscriber rather than widening.
        """
        resolved = await get_field_level_impacted_subscribers(
            query_payload=QUERY_CAR_DISPLAY_LABEL,
            diff_summary=[
                node_diff(
                    node_id=dataset["car_id"],
                    kind=TestKind.CAR,
                    branch=default_branch.name,
                    field_names=["name"],
                )
            ],
            query_branch=default_branch.name,
            subscriber_kind=SUBSCRIBER_KIND,
            every_target=[dataset["subscriber_id"]],
            client=client,
        )
        assert resolved == TargetSelection(ids=[dataset["subscriber_id"]])

    async def test_related_node_change_narrows_to_the_owning_member(
        self,
        dataset: dict[str, Any],
        default_branch: Branch,
        client: InfrahubClient,
    ) -> None:
        """A change to a field the query reads on a *related* node narrows to the members owning it.

        The changed owner is not itself a query-group member, so the relationship the query traverses
        to reach it is walked back to the cars pointing at that owner, and only their subscribers are
        selected -- not every member of the definition.
        """
        resolved = await self._resolve(
            dataset=dataset,
            default_branch=default_branch,
            client=client,
            diff_summary=[
                node_diff(
                    node_id=dataset["person_id"],
                    kind=TestKind.PERSON,
                    branch=default_branch.name,
                    field_names=["name"],
                )
            ],
        )
        assert resolved == TargetSelection(ids=[dataset["subscriber_id"]])

    async def test_unread_related_field_change_selects_nothing(
        self,
        dataset: dict[str, Any],
        default_branch: Branch,
        client: InfrahubClient,
    ) -> None:
        """A change to a related field the query does not read resolves to no subscriber.

        Field-level precision holds through the relationship: only a change to a field the query
        actually reads off the owner can implicate the cars that read it.
        """
        resolved = await self._resolve(
            dataset=dataset,
            default_branch=default_branch,
            client=client,
            diff_summary=[
                node_diff(
                    node_id=dataset["person_id"],
                    kind=TestKind.PERSON,
                    branch=default_branch.name,
                    field_names=["height"],
                )
            ],
        )
        assert resolved == TargetSelection(ids=[])

    async def test_change_to_a_filtered_relationship_selects_every_target(
        self,
        dataset: dict[str, Any],
        default_branch: Branch,
        client: InfrahubClient,
    ) -> None:
        """A change to a relationship the query filters on selects every target.

        The query selects cars by their owner's name and reads only the car's ``name``. Moving a car to
        another owner changes which cars answer the query for both owners, so every target has to run
        even though no field the query reads back changed.
        """
        resolved = await get_field_level_impacted_subscribers(
            query_payload=QUERY_CARS_BY_OWNER_NAME,
            diff_summary=[
                node_diff(
                    node_id=dataset["car_id"],
                    kind=TestKind.CAR,
                    branch=default_branch.name,
                    field_names=["owner"],
                    element_type="RELATIONSHIP_ONE",
                )
            ],
            query_branch=default_branch.name,
            subscriber_kind=SUBSCRIBER_KIND,
            every_target=[dataset["subscriber_id"]],
            client=client,
        )
        assert resolved == TargetSelection(
            ids=[dataset["subscriber_id"]],
            widening=Widening(reason=WideningReason.NON_UNIQUE_TARGETS),
        )

    async def test_change_to_an_attribute_matched_by_any_value_selects_every_target(
        self,
        dataset: dict[str, Any],
        default_branch: Branch,
        client: InfrahubClient,
    ) -> None:
        """A change to any attribute selects every target when the query filters on ``any__value``.

        The query reads only the car's ``name``, but its filter matches on every attribute, so a
        change to ``color`` can move which cars answer the query.
        """
        resolved = await get_field_level_impacted_subscribers(
            query_payload=QUERY_CARS_BY_ANY_VALUE,
            diff_summary=[
                node_diff(
                    node_id=dataset["car_id"],
                    kind=TestKind.CAR,
                    branch=default_branch.name,
                    field_names=["color"],
                )
            ],
            query_branch=default_branch.name,
            subscriber_kind=SUBSCRIBER_KIND,
            every_target=[dataset["subscriber_id"]],
            client=client,
        )
        assert resolved == TargetSelection(
            ids=[dataset["subscriber_id"]],
            widening=Widening(reason=WideningReason.NON_UNIQUE_TARGETS),
        )
