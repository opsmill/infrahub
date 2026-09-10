"""What the live query automation dispatches when a node one of its queries reads changes.

The flow resolves its targets from query-group membership, so the groups are real nodes here:
one per query, with the changed node as a member and the reader as a subscriber.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

import pytest

from infrahub.computed_attribute.tasks import query_transform_targets
from infrahub.core.constants import InfrahubKind, RelationshipCardinality
from infrahub.core.node import Node
from infrahub.core.schema import AttributeSchema, NodeSchema, RelationshipSchema, SchemaRoot
from infrahub.core.schema.computed_attribute import ComputedAttribute, ComputedAttributeKind
from infrahub.workflows.catalogue import COMPUTED_ATTRIBUTE_PROCESS_TRANSFORM
from tests.component.computed_attribute._base import ScopedRecomputeTestBase
from tests.helpers.schema import load_schema

if TYPE_CHECKING:
    from infrahub_sdk import InfrahubClient

    from infrahub.core.branch import Branch
    from infrahub.core.protocols import CoreAccount
    from infrahub.database import InfrahubDatabase
    from tests.adapters.workflow import WorkflowRecorder


# Two attributes on TestCar fed by two transforms, and one on TestPerson that reads a car. The two
# TestCar queries read the same field, so the query a group belongs to is the only thing that can
# tell their readers apart. Only the TestPerson query reads TestCar.name.
QUERY_OWN = "query CarOwn($id: ID!) { TestCar(ids: [$id]) { edges { node { nbr_seats { value } } } } }"
QUERY_OTHER = "query CarOther($id: ID!) { TestCar(ids: [$id]) { edges { node { nbr_seats { value } } } } }"
QUERY_PEER = "query CarName($id: ID!) { TestCar(ids: [$id]) { edges { node { name { value } } } } }"

CAR_PERSON_TWO_QUERY_SCHEMA = SchemaRoot(
    nodes=[
        NodeSchema(
            name="Car",
            namespace="Test",
            attributes=[
                AttributeSchema(name="name", kind="Text", unique=True),
                AttributeSchema(name="nbr_seats", kind="Number", optional=True),
                AttributeSchema(
                    name="computed_own",
                    kind="Text",
                    read_only=True,
                    optional=True,
                    computed_attribute=ComputedAttribute(
                        kind=ComputedAttributeKind.TRANSFORM_PYTHON,
                        transform="transform_own",
                    ),
                ),
                AttributeSchema(
                    name="computed_other",
                    kind="Text",
                    read_only=True,
                    optional=True,
                    computed_attribute=ComputedAttribute(
                        kind=ComputedAttributeKind.TRANSFORM_PYTHON,
                        transform="transform_other",
                    ),
                ),
            ],
            relationships=[
                RelationshipSchema(
                    name="owner",
                    peer="TestPerson",
                    optional=False,
                    cardinality=RelationshipCardinality.ONE,
                ),
            ],
        ),
        NodeSchema(
            name="Person",
            namespace="Test",
            attributes=[
                AttributeSchema(name="name", kind="Text", unique=True),
                AttributeSchema(
                    name="computed_peer",
                    kind="Text",
                    read_only=True,
                    optional=True,
                    computed_attribute=ComputedAttribute(
                        kind=ComputedAttributeKind.TRANSFORM_PYTHON,
                        transform="transform_peer",
                    ),
                ),
            ],
            relationships=[
                RelationshipSchema(name="cars", peer="TestCar", cardinality=RelationshipCardinality.MANY),
            ],
        ),
    ]
)


@dataclass
class WideDispatchCase:
    """An automation the flow cannot narrow, and which therefore has to cover everything."""

    name: str
    graphql_query_id: str | None
    transform_name: str | None


WIDE_DISPATCH_CASES = [
    WideDispatchCase(name="an_automation_stored_before_the_narrowing", graphql_query_id=None, transform_name=None),
    WideDispatchCase(
        name="a_transform_the_schema_no_longer_feeds_from",
        graphql_query_id=None,
        transform_name="transform_retired",
    ),
]


class TestQueryTransformTargets(ScopedRecomputeTestBase):
    WORKFLOW = COMPUTED_ATTRIBUTE_PROCESS_TRANSFORM

    @pytest.fixture(scope="class")
    async def dataset(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        client: InfrahubClient,
        admin_account: CoreAccount,
    ) -> dict[str, Any]:
        """Three transforms, two cars, one person, and the four query groups they subscribed to."""
        repository = await Node.init(db=db, schema=InfrahubKind.READONLYREPOSITORY)
        await repository.new(db=db, name="repo01", ref=default_branch.name, commit="commit01", location="location01")
        await repository.save(db=db)

        queries: dict[str, Node] = {}
        for query_name, query_body, transform_name in (
            ("query_own", QUERY_OWN, "transform_own"),
            ("query_other", QUERY_OTHER, "transform_other"),
            ("query_peer", QUERY_PEER, "transform_peer"),
        ):
            query = await Node.init(db=db, schema=InfrahubKind.GRAPHQLQUERY)
            await query.new(db=db, name=query_name, query=query_body, models=["TestCar", "TestPerson"])
            await query.save(db=db)
            queries[query_name] = query

            transform = await Node.init(db=db, schema=InfrahubKind.TRANSFORMPYTHON)
            await transform.new(
                db=db,
                name=transform_name,
                file_path="transform.py",
                class_name="Transform",
                query=query,
                repository=repository,
            )
            await transform.save(db=db)

        await load_schema(db=db, schema=CAR_PERSON_TWO_QUERY_SCHEMA, update_db=True)

        person = await Node.init(db=db, schema="TestPerson")
        await person.new(db=db, name="owner01")
        await person.save(db=db)

        cars: list[Node] = []
        for index in range(2):
            car = await Node.init(db=db, schema="TestCar")
            await car.new(db=db, name=f"car{index}", owner=person)
            await car.save(db=db)
            cars.append(car)

        # The person is read by both TestCar queries, each one by a different car.
        await self._create_group(
            db=db, name="group_own_of_person", query=queries["query_own"], members=[person], subscribers=[cars[0]]
        )
        await self._create_group(
            db=db, name="group_other_of_person", query=queries["query_other"], members=[person], subscribers=[cars[1]]
        )
        # The first car computed its own attribute, and the person read that car's name.
        await self._create_group(
            db=db, name="group_own_of_car", query=queries["query_own"], members=[cars[0]], subscribers=[cars[0]]
        )
        await self._create_group(
            db=db, name="group_peer_of_car", query=queries["query_peer"], members=[cars[0]], subscribers=[person]
        )

        return {"person": person, "cars": cars, "queries": queries}

    @staticmethod
    async def _create_group(
        *, db: InfrahubDatabase, name: str, query: Node, members: list[Node], subscribers: list[Node]
    ) -> Node:
        group = await Node.init(db=db, schema=InfrahubKind.GRAPHQLQUERYGROUP)
        await group.new(db=db, name=name, group_type="internal", query=query, members=members, subscribers=subscribers)
        await group.save(db=db)
        return group

    def _submissions(self, recorder: WorkflowRecorder) -> dict[tuple[str, str], list[str]]:
        submitted: dict[tuple[str, str], list[str]] = {}
        for call in recorder.get_submit_calls_for(self.WORKFLOW):
            key = (call["parameters"]["node_kind"], call["parameters"]["computed_attribute_name"])
            submitted.setdefault(key, []).extend(call["parameters"]["object_ids"])
        return {key: sorted(ids) for key, ids in submitted.items()}

    async def test_only_the_matching_query_feeds_its_own_attribute(
        self,
        dataset: dict[str, Any],
        workflow_recorder: WorkflowRecorder,
        default_branch: Branch,
        admin_account: CoreAccount,
    ) -> None:
        """Two attributes on one kind, fed by two queries: a change selects one of them.

        Both cars subscribe to a group holding the person, so both are reported. Only the car that
        read the person through this automation's query can have a value that moved.
        """
        person = dataset["person"]

        await query_transform_targets(
            branch_name=default_branch.name,
            node_kind="TestPerson",
            object_id=person.id,
            context=self._context(admin_account, default_branch),
            graphql_query_id=dataset["queries"]["query_own"].id,
            transform_name="transform_own",
        )

        assert self._submissions(workflow_recorder) == {("TestCar", "computed_own"): [dataset["cars"][0].id]}

    async def test_the_changed_node_is_left_out_when_its_own_query_did_not_match(
        self,
        dataset: dict[str, Any],
        workflow_recorder: WorkflowRecorder,
        default_branch: Branch,
        admin_account: CoreAccount,
    ) -> None:
        """A renamed car is not recomputed when nothing that reads its name feeds it.

        The car subscribes to its own group, whose query reads ``nbr_seats``. Only the person's
        query reads the name, so the rename reaches the person and stops there.
        """
        car = dataset["cars"][0]

        await query_transform_targets(
            branch_name=default_branch.name,
            node_kind="TestCar",
            object_id=car.id,
            context=self._context(admin_account, default_branch),
            graphql_query_id=dataset["queries"]["query_peer"].id,
            transform_name="transform_peer",
        )

        assert self._submissions(workflow_recorder) == {("TestPerson", "computed_peer"): [dataset["person"].id]}

    @pytest.mark.parametrize("case", WIDE_DISPATCH_CASES, ids=lambda case: case.name)
    async def test_an_automation_that_cannot_be_narrowed_keeps_the_wide_dispatch(
        self,
        case: WideDispatchCase,
        dataset: dict[str, Any],
        workflow_recorder: WorkflowRecorder,
        default_branch: Branch,
        admin_account: CoreAccount,
    ) -> None:
        """Every group holding the changed node answers, and every attribute of their kinds runs.

        Narrowing to nothing would leave those values stale, so an automation the schema cannot
        explain has to fall back to the widest dispatch.
        """
        car = dataset["cars"][0]

        await query_transform_targets(
            branch_name=default_branch.name,
            node_kind="TestCar",
            object_id=car.id,
            context=self._context(admin_account, default_branch),
            graphql_query_id=case.graphql_query_id,
            transform_name=case.transform_name,
        )

        assert self._submissions(workflow_recorder) == {
            ("TestCar", "computed_own"): [car.id],
            ("TestCar", "computed_other"): [car.id],
            ("TestPerson", "computed_peer"): [dataset["person"].id],
        }
