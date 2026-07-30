"""Merge-time uniqueness validation when only some changed fields participate in the constraint.

The check is scoped to the nodes whose changed field participates in the kind's uniqueness, so a
diff mixing a participating and a non-participating change must still reach the participating one.
Both branches here change data only, keeping the node-scoped path in play — a branch that also
carries a schema change is validated against the whole population instead.
"""

from __future__ import annotations

import copy
from typing import TYPE_CHECKING

import pytest
from infrahub_sdk.exceptions import GraphQLError

from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from tests.constants import TestKind
from tests.helpers.schema import CAR_SCHEMA, load_schema
from tests.helpers.test_app import TestInfrahubApp

if TYPE_CHECKING:
    from infrahub_sdk import InfrahubClient

    from infrahub.core.branch import Branch
    from infrahub.core.schema import SchemaRoot
    from infrahub.database import InfrahubDatabase
    from tests.adapters.message_bus import BusSimulator

BLOCKED_BRANCH = "uniqueness_scoping_relationship"
CLEAN_BRANCH = "uniqueness_scoping_unrelated"

BRANCH_MERGE_MUTATION = """
mutation($branch: String!) {
    BranchMerge(data: { name: $branch }) {
        ok
    }
}
"""


async def _get_car(db: InfrahubDatabase, car_id: str, branch: Branch | str) -> Node:
    return await NodeManager.get_one(db=db, id=car_id, branch=branch, kind=TestKind.CAR, raise_on_error=True)


class TestMergeUniquenessFieldScoping(TestInfrahubApp):
    @pytest.fixture(scope="class")
    def car_schema_unique_owner_name(self) -> SchemaRoot:
        """Cars made unique by their owner together with their name.

        "owner" is a relationship and "name__value" an attribute, so a change to either half
        implicates the constraint while "color"/"description" changes cannot.
        """
        schema = copy.deepcopy(CAR_SCHEMA)
        car = next(node for node in schema.nodes if node.kind == TestKind.CAR)
        car.uniqueness_constraints = [["owner", "name__value"]]
        return schema

    @pytest.fixture(scope="class")
    async def initial_dataset(
        self,
        db: InfrahubDatabase,
        initialize_registry: None,
        client: InfrahubClient,
        bus_simulator: BusSimulator,
        prefect_test_fixture: None,
        car_schema_unique_owner_name: SchemaRoot,
    ) -> dict[str, str]:
        """Two cars named "civic" kept distinct only by their owner, plus an unrelated "accord"."""
        await load_schema(db, schema=car_schema_unique_owner_name)

        john = await Node.init(schema=TestKind.PERSON, db=db)
        await john.new(db=db, name="John", height=175)
        await john.save(db=db)
        jane = await Node.init(schema=TestKind.PERSON, db=db)
        await jane.new(db=db, name="Jane", height=165)
        await jane.save(db=db)
        honda = await Node.init(schema=TestKind.MANUFACTURER, db=db)
        await honda.new(db=db, name="honda")
        await honda.save(db=db)

        civic_john = await Node.init(schema=TestKind.CAR, db=db)
        await civic_john.new(db=db, name="civic", color="blue", owner=john, manufacturer=honda)
        await civic_john.save(db=db)
        civic_jane = await Node.init(schema=TestKind.CAR, db=db)
        await civic_jane.new(db=db, name="civic", color="red", owner=jane, manufacturer=honda)
        await civic_jane.save(db=db)
        accord_john = await Node.init(schema=TestKind.CAR, db=db)
        await accord_john.new(db=db, name="accord", color="green", owner=john, manufacturer=honda)
        await accord_john.save(db=db)

        return {
            "john": john.id,
            "jane": jane.id,
            "civic_john": civic_john.id,
            "civic_jane": civic_jane.id,
            "accord_john": accord_john.id,
        }

    async def test_participating_relationship_change_blocks_merge(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        initial_dataset: dict[str, str],
        client: InfrahubClient,
    ) -> None:
        """A re-owned car collides on (owner, name) even though no node changed the name attribute.

        The branch also changes another car's color, a field no constraint group reads, so the
        participating change is the relationship one and it is the only reason to validate.
        """
        await client.branch.create(branch_name=BLOCKED_BRANCH)

        civic_jane_branch = await _get_car(db=db, car_id=initial_dataset["civic_jane"], branch=BLOCKED_BRANCH)
        await civic_jane_branch.get_relationship("owner").update(db=db, data=initial_dataset["john"])
        await civic_jane_branch.save(db=db)
        accord_branch = await _get_car(db=db, car_id=initial_dataset["accord_john"], branch=BLOCKED_BRANCH)
        accord_branch.get_attribute("color").value = "black"
        await accord_branch.save(db=db)

        with pytest.raises(GraphQLError) as exc:
            await client.execute_graphql(query=BRANCH_MERGE_MUTATION, variables={"branch": BLOCKED_BRANCH})

        message = exc.value.message
        civic_john_branch = await _get_car(db=db, car_id=initial_dataset["civic_john"], branch=BLOCKED_BRANCH)
        for car in (civic_jane_branch, civic_john_branch):
            display_label = await car.get_display_label(db=db)
            assert (
                f"Node-level 'uniqueness_constraints' constraint violation on schema '{TestKind.CAR}'."
                f" Node ({display_label}) is not compliant."
            ) in message
        # the car whose only change is a non-participating field is never implicated
        assert await accord_branch.get_display_label(db=db) not in message

        # main keeps both owners, so it never holds two cars named "civic" with the same owner
        civic_jane_main = await _get_car(db=db, car_id=initial_dataset["civic_jane"], branch=default_branch)
        owner_main = await civic_jane_main.get_relationship("owner").get_peer(db=db, raise_on_error=True)
        assert owner_main.id == initial_dataset["jane"]
        accord_main = await _get_car(db=db, car_id=initial_dataset["accord_john"], branch=default_branch)
        assert accord_main.get_attribute("color").value == "green"

    async def test_non_participating_change_alone_merges(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        initial_dataset: dict[str, str],
        client: InfrahubClient,
    ) -> None:
        """A branch touching only a field outside every constraint group merges without a violation."""
        await client.branch.create(branch_name=CLEAN_BRANCH)

        civic_john_branch = await _get_car(db=db, car_id=initial_dataset["civic_john"], branch=CLEAN_BRANCH)
        civic_john_branch.get_attribute("description").value = "the blue one"
        await civic_john_branch.save(db=db)

        await client.execute_graphql(query=BRANCH_MERGE_MUTATION, variables={"branch": CLEAN_BRANCH})

        civic_john_main = await _get_car(db=db, car_id=initial_dataset["civic_john"], branch=default_branch)
        assert civic_john_main.get_attribute("description").value == "the blue one"
