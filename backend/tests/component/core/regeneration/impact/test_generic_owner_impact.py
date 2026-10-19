from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest

from infrahub.core.constants import InfrahubKind
from infrahub.core.node import Node
from infrahub.core.regeneration.impact import get_field_level_impacted_subscribers
from infrahub.core.regeneration.models import TargetSelection
from tests.constants import TestKind
from tests.helpers.diff_summary import node_diff
from tests.helpers.schema import RACK_SCHEMA, load_schema
from tests.helpers.test_app import TestInfrahubApp

from .helpers import query_report

if TYPE_CHECKING:
    from infrahub_sdk.client import InfrahubClient

    from infrahub.core.branch import Branch
    from infrahub.database import InfrahubDatabase

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
            query_report=query_report(QUERY_RACK_WITH_CARD, default_branch),
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
            query_report=query_report(QUERY_RACK_WITH_SLOT_NAMES_ON_THE_GENERIC, default_branch),
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
            query_report=query_report(QUERY_RACK_WITH_CARD_THROUGH_A_FRAGMENT, default_branch),
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
