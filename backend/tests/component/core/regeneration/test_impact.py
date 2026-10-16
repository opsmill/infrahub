from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest

from infrahub.core.constants import InfrahubKind
from infrahub.core.node import Node
from infrahub.core.regeneration.impact import get_field_level_impacted_subscribers
from infrahub.core.regeneration.models import TargetSelection, Widening, WideningReason
from tests.constants import TestKind
from tests.helpers.diff_summary import node_diff
from tests.helpers.schema import CAR_SCHEMA, RACK_SCHEMA, load_schema
from tests.helpers.test_app import TestInfrahubApp

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

# The car is the group member; the tag stands in for an artifact or generator definition. The impact
# mapping reads only the subscriber's id and typename, so a plain kind keeps the fixture free of the
# transformation and repository wiring a real definition would demand.
SUBSCRIBER_KIND = TestKind.TAG


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


# The root car is pinned by id, and the query reads the names of every car of its owner: a car is read
# both at the root and through the ``owner`` and ``cars`` relationships.
QUERY_CAR_WITH_ITS_OWNER_CARS = """
query GetImpactCarWithOwnerCars($ids: [ID!]!) {
    TestingCar(ids: $ids) {
        edges {
            node {
                name { value }
                owner { node { cars { edges { node { name { value } } } } } }
            }
        }
    }
}
"""

# The root car is pinned by id, and the query reads the names of the cars its previous owner owns. A car
# without a previous owner is reached back through no relationship, so only its root read selects it.
QUERY_CAR_WITH_ITS_PREVIOUS_OWNER_CARS = """
query GetImpactCarWithPreviousOwnerCars($ids: [ID!]!) {
    TestingCar(ids: $ids) {
        edges {
            node {
                name { value }
                previous_owner { node { cars { edges { node { name { value } } } } } }
            }
        }
    }
}
"""


class TestRootAndRelationshipReadImpact(TestInfrahubApp):
    """Narrow a change on a kind the query reads both at its root and through a relationship.

    Two owners: the first owns the first car, a group member, and a second car that is no member; the
    second owner owns the third car, the member of another group.
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

        owner = await Node.init(db=db, schema=TestKind.PERSON)
        await owner.new(db=db, name="owner-1")
        await owner.save(db=db)

        other_owner = await Node.init(db=db, schema=TestKind.PERSON)
        await other_owner.new(db=db, name="owner-2")
        await other_owner.save(db=db)

        cars = []
        for name, car_owner in (("car-1", owner), ("car-2", owner), ("car-3", other_owner)):
            car = await Node.init(db=db, schema=TestKind.CAR)
            await car.new(db=db, name=name, color="red", owner=car_owner, manufacturer=manufacturer)
            await car.save(db=db)
            cars.append(car)
        first_car, second_car, third_car = cars

        stored_query = await Node.init(db=db, schema=InfrahubKind.GRAPHQLQUERY)
        await stored_query.new(
            db=db,
            name="GetImpactCarWithOwnerCars",
            query=QUERY_CAR_WITH_ITS_OWNER_CARS,
            models=[TestKind.CAR, TestKind.PERSON],
        )
        await stored_query.save(db=db)

        subscribers = []
        for member, name in ((first_car, "first-car-artifact"), (third_car, "third-car-artifact")):
            subscriber = await Node.init(db=db, schema=TestKind.TAG)
            await subscriber.new(db=db, name=name)
            await subscriber.save(db=db)
            group = await Node.init(db=db, schema=InfrahubKind.GRAPHQLQUERYGROUP)
            await group.new(
                db=db, name=f"{name}-targets", query=stored_query, members=[member], subscribers=[subscriber]
            )
            await group.save(db=db)
            subscribers.append(subscriber)
        first_subscriber, third_subscriber = subscribers

        return {
            "first_car_id": first_car.id,
            "second_car_id": second_car.id,
            "third_car_id": third_car.id,
            "first_subscriber_id": first_subscriber.id,
            "third_subscriber_id": third_subscriber.id,
        }

    async def _resolve(
        self,
        *,
        dataset: dict[str, Any],
        default_branch: Branch,
        client: InfrahubClient,
        car_id: str,
        query: str = QUERY_CAR_WITH_ITS_OWNER_CARS,
    ) -> TargetSelection:
        return await get_field_level_impacted_subscribers(
            query_payload=query,
            diff_summary=[
                node_diff(node_id=car_id, kind=TestKind.CAR, branch=default_branch.name, field_names=["name"])
            ],
            query_branch=default_branch.name,
            subscriber_kind=SUBSCRIBER_KIND,
            every_target=[dataset["first_subscriber_id"], dataset["third_subscriber_id"]],
            client=client,
        )

    async def test_change_on_a_car_read_only_through_the_relationship_selects_the_reading_member(
        self,
        dataset: dict[str, Any],
        default_branch: Branch,
        client: InfrahubClient,
    ) -> None:
        """The second car is no group member: its change walks back through its owner to the first car."""
        resolved = await self._resolve(
            dataset=dataset, default_branch=default_branch, client=client, car_id=dataset["second_car_id"]
        )

        assert resolved == TargetSelection(ids=[dataset["first_subscriber_id"]])

    async def test_change_on_a_car_read_at_the_root_selects_its_own_member(
        self,
        dataset: dict[str, Any],
        default_branch: Branch,
        client: InfrahubClient,
    ) -> None:
        """The third car is the root of its own group and shares no owner with the first car."""
        resolved = await self._resolve(
            dataset=dataset, default_branch=default_branch, client=client, car_id=dataset["third_car_id"]
        )

        assert resolved == TargetSelection(ids=[dataset["third_subscriber_id"]])

    async def test_change_on_a_car_no_relationship_reaches_back_selects_its_own_member(
        self,
        dataset: dict[str, Any],
        default_branch: Branch,
        client: InfrahubClient,
    ) -> None:
        """The first car has no previous owner, so walking the relationship back from it reaches no member."""
        resolved = await self._resolve(
            dataset=dataset,
            default_branch=default_branch,
            client=client,
            car_id=dataset["first_car_id"],
            query=QUERY_CAR_WITH_ITS_PREVIOUS_OWNER_CARS,
        )

        assert resolved == TargetSelection(ids=[dataset["first_subscriber_id"]])


QUERY_RACK_WITH_CARD = """
query GetImpactRack($ids: [ID!]!) {
    TestingRack(ids: $ids) {
        edges {
            node {
                name { value }
                slots { edges { node {
                    card { node { name { value } } }
                } } }
            }
        }
    }
}
"""

# The slot names are read only inside a fragment on the ``TestingSlot`` generic, while a change to a slot is
# reported under its concrete ``TestingPowerSlot`` kind.
QUERY_RACK_WITH_SLOT_NAMES_ON_THE_GENERIC = """
query GetImpactRackSlotNames($ids: [ID!]!) {
    TestingRack(ids: $ids) {
        edges {
            node {
                name { value }
                slots { edges { node {
                    ... on TestingSlot { name { value } }
                } } }
            }
        }
    }
}
"""

# The card is read inside a fragment on the concrete ``TestingPowerSlot`` kind.
QUERY_RACK_WITH_CARD_THROUGH_A_FRAGMENT = """
query GetImpactRackThroughFragment($ids: [ID!]!) {
    TestingRack(ids: $ids) {
        edges {
            node {
                name { value }
                slots { edges { node {
                    ... on TestingPowerSlot { card { node { name { value } } } }
                } } }
            }
        }
    }
}
"""


class TestGenericOwnerFieldLevelImpact(TestInfrahubApp):
    """Narrow a change reached through a relationship whose owner is a generic.

    The query pins its root rack by id and reads ``name`` off a card reached through the rack's slots.
    The slot is a concrete ``TestingPowerSlot`` labelled with the ``TestingSlot`` generic, so the
    reverse traversal keyed on the generic label walks the card change back through the slot to the
    rack.
    """

    @pytest.fixture(scope="class")
    async def dataset(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        client: InfrahubClient,
    ) -> dict[str, Any]:
        await load_schema(db=db, schema=RACK_SCHEMA, update_db=True)

        card = await Node.init(db=db, schema="TestingCard")
        await card.new(db=db, name="card-1")
        await card.save(db=db)

        slot = await Node.init(db=db, schema="TestingPowerSlot")
        await slot.new(db=db, name="slot-1", card=card)
        await slot.save(db=db)

        rack = await Node.init(db=db, schema="TestingRack")
        await rack.new(db=db, name="rack-1", slots=[slot])
        await rack.save(db=db)

        # A second rack with its own slot and card: the reverse traversal must reach only the rack that
        # owns the changed card, never every member of the group.
        other_card = await Node.init(db=db, schema="TestingCard")
        await other_card.new(db=db, name="card-2")
        await other_card.save(db=db)

        other_slot = await Node.init(db=db, schema="TestingPowerSlot")
        await other_slot.new(db=db, name="slot-2", card=other_card)
        await other_slot.save(db=db)

        other_rack = await Node.init(db=db, schema="TestingRack")
        await other_rack.new(db=db, name="rack-2", slots=[other_slot])
        await other_rack.save(db=db)

        subscriber = await Node.init(db=db, schema=TestKind.TAG)
        await subscriber.new(db=db, name="rack-artifact")
        await subscriber.save(db=db)

        other_subscriber = await Node.init(db=db, schema=TestKind.TAG)
        await other_subscriber.new(db=db, name="other-rack-artifact")
        await other_subscriber.save(db=db)

        stored_query = await Node.init(db=db, schema=InfrahubKind.GRAPHQLQUERY)
        await stored_query.new(
            db=db, name="GetImpactRack", query=QUERY_RACK_WITH_CARD, models=["TestingRack", "TestingCard"]
        )
        await stored_query.save(db=db)

        # Each rack stands for a separate definition, so it gets its own group with its own subscriber.
        # Subscribers resolve per group, so narrowing to one rack must return only that rack's group's
        # subscriber -- the other rack's subscriber proves the traversal did not widen.
        query_group = await Node.init(db=db, schema=InfrahubKind.GRAPHQLQUERYGROUP)
        await query_group.new(
            db=db, name="rack-impact-targets", query=stored_query, members=[rack], subscribers=[subscriber]
        )
        await query_group.save(db=db)

        other_group = await Node.init(db=db, schema=InfrahubKind.GRAPHQLQUERYGROUP)
        await other_group.new(
            db=db,
            name="other-rack-impact-targets",
            query=stored_query,
            members=[other_rack],
            subscribers=[other_subscriber],
        )
        await other_group.save(db=db)

        return {
            "rack_id": rack.id,
            "other_rack_id": other_rack.id,
            "slot_id": slot.id,
            "card_id": card.id,
            "subscriber_id": subscriber.id,
            "other_subscriber_id": other_subscriber.id,
        }

    async def test_generic_owner_reached_change_narrows_to_the_owning_member(
        self,
        dataset: dict[str, Any],
        default_branch: Branch,
        client: InfrahubClient,
    ) -> None:
        """A change on a card reached through a generic-owned relationship narrows to its rack alone.

        Both racks are members of the group, so a widen would return both subscribers. The reverse
        traversal keyed on the generic slot label reaches only the slot holding the changed card, and
        through it only the owning rack, so a single subscriber comes back.
        """
        resolved = await get_field_level_impacted_subscribers(
            query_payload=QUERY_RACK_WITH_CARD,
            diff_summary=[
                node_diff(
                    node_id=dataset["card_id"],
                    kind="TestingCard",
                    branch=default_branch.name,
                    field_names=["name"],
                )
            ],
            query_branch=default_branch.name,
            subscriber_kind=TestKind.TAG,
            every_target=[dataset["subscriber_id"], dataset["other_subscriber_id"]],
            client=client,
        )
        assert resolved == TargetSelection(ids=[dataset["subscriber_id"]])

    async def test_change_to_a_field_read_through_a_fragment_on_a_generic_narrows_to_the_owning_member(
        self,
        dataset: dict[str, Any],
        default_branch: Branch,
        client: InfrahubClient,
    ) -> None:
        """A change to a slot name read inside a fragment on the slot generic selects the owning rack.

        The query reads ``name`` off the ``TestingSlot`` generic, and the diff reports the change under the
        concrete ``TestingPowerSlot`` kind: the change is a read of the implementation, mapped back to
        the rack holding the slot.
        """
        resolved = await get_field_level_impacted_subscribers(
            query_payload=QUERY_RACK_WITH_SLOT_NAMES_ON_THE_GENERIC,
            diff_summary=[
                node_diff(
                    node_id=dataset["slot_id"],
                    kind="TestingPowerSlot",
                    branch=default_branch.name,
                    field_names=["name"],
                )
            ],
            query_branch=default_branch.name,
            subscriber_kind=TestKind.TAG,
            every_target=[dataset["subscriber_id"], dataset["other_subscriber_id"]],
            client=client,
        )
        assert resolved == TargetSelection(ids=[dataset["subscriber_id"]])

    async def test_change_reached_through_a_fragment_narrows_to_the_owning_member(
        self,
        dataset: dict[str, Any],
        default_branch: Branch,
        client: InfrahubClient,
    ) -> None:
        """A change on a card read inside a fragment on the slot kind narrows to its rack alone.

        The fragment narrows the slot's type without reaching another node, so the reverse traversal
        walks the card back through the slot to the rack holding it, as it does without the fragment.
        """
        resolved = await get_field_level_impacted_subscribers(
            query_payload=QUERY_RACK_WITH_CARD_THROUGH_A_FRAGMENT,
            diff_summary=[
                node_diff(
                    node_id=dataset["card_id"],
                    kind="TestingCard",
                    branch=default_branch.name,
                    field_names=["name"],
                )
            ],
            query_branch=default_branch.name,
            subscriber_kind=TestKind.TAG,
            every_target=[dataset["subscriber_id"], dataset["other_subscriber_id"]],
            client=client,
        )
        assert resolved == TargetSelection(ids=[dataset["subscriber_id"]])
