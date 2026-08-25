from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest

from infrahub.core.constants import InfrahubKind, RelationshipCardinality, RelationshipDirection
from infrahub.core.node import Node
from infrahub.core.regeneration.impact import get_field_level_impacted_subscribers
from infrahub.core.regeneration.models import TargetSelection
from infrahub.core.schema import AttributeSchema, GenericSchema, NodeSchema, RelationshipSchema, SchemaRoot
from tests.constants import TestKind
from tests.helpers.diff_summary import node_diff
from tests.helpers.schema import CAR_SCHEMA, load_schema
from tests.helpers.schema.tag import TAG
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
        assert resolved == TargetSelection(ids=[dataset["subscriber_id"]], widened=False)

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
        assert resolved == TargetSelection(ids=[dataset["subscriber_id"]], widened=False)

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
        assert resolved == TargetSelection(ids=[], widened=False)


# A rack reaches a card through a slot: ``slots`` peers the generic ``TestingSlot`` and ``card`` is a
# relationship defined on that generic. The card is therefore reached through a relationship whose
# owner is a generic -- the case that pins to the generic kind for the reverse traversal.
GENERIC_OWNER_SCHEMA = SchemaRoot(
    generics=[
        GenericSchema(
            name="Slot",
            namespace="Testing",
            attributes=[AttributeSchema(name="name", kind="Text")],
            relationships=[
                RelationshipSchema(
                    name="card",
                    peer="TestingCard",
                    identifier="slot__card",
                    cardinality=RelationshipCardinality.ONE,
                    optional=True,
                    direction=RelationshipDirection.OUTBOUND,
                )
            ],
        )
    ],
    nodes=[
        NodeSchema(
            name="Rack",
            namespace="Testing",
            attributes=[AttributeSchema(name="name", kind="Text", unique=True)],
            relationships=[
                RelationshipSchema(
                    name="slots",
                    peer="TestingSlot",
                    identifier="rack__slot",
                    cardinality=RelationshipCardinality.MANY,
                    optional=True,
                    direction=RelationshipDirection.OUTBOUND,
                )
            ],
        ),
        NodeSchema(name="PowerSlot", namespace="Testing", inherit_from=["TestingSlot"]),
        NodeSchema(
            name="Card",
            namespace="Testing",
            attributes=[AttributeSchema(name="name", kind="Text")],
        ),
        TAG,
    ],
)

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


class TestGenericOwnerFieldLevelImpact(TestInfrahubApp):
    """Narrow a change reached through a relationship whose owner is a generic.

    The query pins its root rack by id and reads ``name`` off a card reached through the rack's slots.
    The slot is a concrete ``TestingPowerSlot`` labelled with the ``TestingSlot`` generic, so the
    reverse traversal keyed on the generic label walks the card change back through the slot to the
    rack -- proving the generic-owner hop resolves to a subset of members rather than widening.
    """

    @pytest.fixture(scope="class")
    async def dataset(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        client: InfrahubClient,
    ) -> dict[str, Any]:
        await load_schema(db=db, schema=GENERIC_OWNER_SCHEMA, update_db=True)

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
        assert resolved == TargetSelection(ids=[dataset["subscriber_id"]], widened=False)
