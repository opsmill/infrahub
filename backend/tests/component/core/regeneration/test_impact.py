from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest

from infrahub.core.constants import InfrahubKind
from infrahub.core.node import Node
from infrahub.core.regeneration.impact import get_field_level_impacted_subscribers
from infrahub.core.regeneration.models import TargetSelection
from tests.constants import TestKind
from tests.helpers.diff_summary import node_diff
from tests.helpers.schema import CAR_SCHEMA, load_schema
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

    async def test_related_node_change_selects_subscriber(
        self,
        dataset: dict[str, Any],
        default_branch: Branch,
        client: InfrahubClient,
    ) -> None:
        """A change to a field the query reads on a *related* node still selects the subscriber.

        The changed owner is not itself a query-group member, so it cannot be mapped back to a
        subscriber by membership lookup. Leaving the subscriber unselected would under-execute and ship
        a stale artifact, so the impact mapping has to widen instead of returning nothing.
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
        assert resolved == TargetSelection(ids=[dataset["subscriber_id"]], widened=True)
