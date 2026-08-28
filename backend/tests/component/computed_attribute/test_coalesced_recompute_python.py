"""The coalesced merge and rebase pass covers Python computed attributes.

These run the real sources behind the derivation: the read sets come from the analyzed transform
queries in the database, and the readers come from the query-group subscribers through the API
client. What is pinned here is the count and the shape of the submissions the pass produces, one
per affected attribute instead of one per changed node.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from typing import TYPE_CHECKING, Generator

import pytest

from infrahub import config
from infrahub.core.constants import ComputedAttributeKind, InfrahubKind
from infrahub.core.manager import NodeManager
from infrahub.core.merge.python_target_sources import build_python_target_deriver
from infrahub.core.merge.recompute_coalescing import (
    CoalescedRecomputeBuilder,
    CoalescedRecomputeSubmitter,
    MergeChange,
    MergeRecomputeCoordinator,
)
from infrahub.core.node import Node
from infrahub.core.registry import registry
from infrahub.core.schema.computed_attribute import ComputedAttribute
from infrahub.workflows.catalogue import (
    COMPUTED_ATTRIBUTE_PROCESS_TRANSFORM,
    TRIGGER_UPDATE_PYTHON_COMPUTED_ATTRIBUTES,
)
from tests.component.computed_attribute._base import (
    CAR_PERSON_PYTHON_SCHEMA,
    ScopedRecomputeTestBase,
    create_transform01,
)
from tests.helpers.schema import load_schema

if TYPE_CHECKING:
    from collections.abc import Iterable

    from infrahub_sdk import InfrahubClient

    from infrahub.core.branch import Branch
    from infrahub.core.protocols import CoreAccount
    from infrahub.core.schema import SchemaRoot
    from infrahub.database import InfrahubDatabase
    from tests.adapters.workflow import WorkflowRecorder

CAR_KIND = "TestCar"
PERSON_KIND = "TestPerson"
NAME_ATTRIBUTE = "computed_desc_python"
OWNER_ATTRIBUTE = "computed_desc_python_owner"

# Stands for a target the pass could not narrow, so every node of the kind is refreshed.
WHOLE_KIND = "whole-kind"

# The owner is read across the relationship, so a change on the person selects the cars, while a
# change on a field neither query reads selects nothing.
QUERY_OWNER = "query { TestCar { edges { node { name { value } owner { node { name { value } } } } } } }"


def _schema_with_an_owner_reading_transform() -> SchemaRoot:
    """The car/person Python schema, with the second attribute fed by the owner-reading transform.

    The owner relationship is optional here so that a test can delete a person while its cars
    survive, which is the shape a merged peer deletion takes.
    """
    schema = deepcopy(CAR_PERSON_PYTHON_SCHEMA)
    car = next(node for node in schema.nodes if node.kind == CAR_KIND)
    car.get_relationship(name="owner").optional = True
    attribute = car.get_attribute(name="computed_desc_python_opaque")
    attribute.name = OWNER_ATTRIBUTE
    attribute.computed_attribute = ComputedAttribute(
        kind=ComputedAttributeKind.TRANSFORM_PYTHON, transform="transform_owner"
    )
    return schema


@dataclass
class PythonRecomputeDataset:
    """Two cars owned by one person, both subscribed to the owner-reading transform's query."""

    car_ids: list[str]
    person_id: str


async def _seed(db: InfrahubDatabase, branch: Branch) -> PythonRecomputeDataset:
    repo = await create_transform01(db=db, branch_name=branch.name)

    query_owner = await Node.init(db=db, schema=InfrahubKind.GRAPHQLQUERY)
    await query_owner.new(db=db, name="query_owner", query=QUERY_OWNER, models=[CAR_KIND, PERSON_KIND])
    await query_owner.save(db=db)

    transform_owner = await Node.init(db=db, schema=InfrahubKind.TRANSFORMPYTHON)
    await transform_owner.new(
        db=db,
        name="transform_owner",
        file_path="transform.py",
        class_name="Transform",
        query=query_owner,
        repository=repo,
    )
    await transform_owner.save(db=db)

    await load_schema(db=db, schema=_schema_with_an_owner_reading_transform(), update_db=True)

    person = await Node.init(db=db, schema=PERSON_KIND)
    await person.new(db=db, name="owner01")
    await person.save(db=db)

    cars: list[Node] = []
    for index in range(2):
        car = await Node.init(db=db, schema=CAR_KIND)
        await car.new(db=db, name=f"car{index}", owner=person)
        await car.save(db=db)
        cars.append(car)

    # One group per query, holding every node the query returned as a member and every node that
    # computed through it as a subscriber: what a recompute of both cars leaves behind.
    group = await Node.init(db=db, schema=InfrahubKind.GRAPHQLQUERYGROUP)
    await group.new(db=db, name="query_owner", query=query_owner, members=[*cars, person], subscribers=cars)
    await group.save(db=db)

    return PythonRecomputeDataset(car_ids=[car.id for car in cars], person_id=person.id)


class CoalescedPythonTestBase(ScopedRecomputeTestBase):
    """Runs the coalesced pass with the switch on and reports the submissions it produced."""

    WORKFLOW = COMPUTED_ATTRIBUTE_PROCESS_TRANSFORM

    @pytest.fixture(autouse=True)
    def coalesce_python_switch(self) -> Generator[None, None, None]:
        original = config.SETTINGS.main.coalesce_python_recompute_after_merge
        config.SETTINGS.main.coalesce_python_recompute_after_merge = True
        yield
        config.SETTINGS.main.coalesce_python_recompute_after_merge = original

    async def _run_pass(
        self,
        *,
        db: InfrahubDatabase,
        recorder: WorkflowRecorder,
        default_branch: Branch,
        admin_account: CoreAccount,
        changes: Iterable[MergeChange],
    ) -> dict[str, list[str] | str]:
        coordinator = MergeRecomputeCoordinator(
            builder=CoalescedRecomputeBuilder(
                schema_branch=registry.schema.get_schema_branch(name=default_branch.name)
            ),
            submitter=CoalescedRecomputeSubmitter(workflow=recorder),
            python_deriver=await build_python_target_deriver(db=db),
        )

        await coordinator.run(
            changes=changes,
            branch=default_branch.name,
            context=self._context(admin_account, default_branch),
        )

        submissions: dict[str, list[str] | str] = {}
        for call in recorder.get_submit_calls_for(COMPUTED_ATTRIBUTE_PROCESS_TRANSFORM):
            attribute_name = call["parameters"]["computed_attribute_name"]
            assert attribute_name not in submissions, f"{attribute_name} was submitted more than once"
            assert call["parameters"]["coalesced"] is True
            assert call["parameters"]["node_kind"] == CAR_KIND
            submissions[attribute_name] = sorted(call["parameters"]["object_ids"])
        # A widened target goes to the whole-kind fan-out instead, and must not read as a skip.
        for call in recorder.get_submit_calls_for(TRIGGER_UPDATE_PYTHON_COMPUTED_ATTRIBUTES):
            attribute_name = call["parameters"]["computed_attribute_name"]
            assert attribute_name not in submissions, f"{attribute_name} was submitted more than once"
            assert call["parameters"]["coalesced"] is True
            submissions[attribute_name] = WHOLE_KIND
        return submissions


class TestCoalescedRecomputePython(CoalescedPythonTestBase):
    @pytest.fixture(scope="class")
    async def dataset(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        client: InfrahubClient,
        admin_account: CoreAccount,
    ) -> PythonRecomputeDataset:
        return await _seed(db=db, branch=default_branch)

    async def test_created_nodes_submit_one_recompute_per_attribute(
        self,
        dataset: PythonRecomputeDataset,
        db: InfrahubDatabase,
        workflow_recorder: WorkflowRecorder,
        default_branch: Branch,
        admin_account: CoreAccount,
    ) -> None:
        """Two created cars are one submission per attribute, not one per node."""
        submissions = await self._run_pass(
            db=db,
            recorder=workflow_recorder,
            default_branch=default_branch,
            admin_account=admin_account,
            changes=[MergeChange(node_id=car_id, kind=CAR_KIND, action="created") for car_id in dataset.car_ids],
        )

        assert submissions == {
            NAME_ATTRIBUTE: sorted(dataset.car_ids),
            OWNER_ATTRIBUTE: sorted(dataset.car_ids),
        }

    async def test_a_change_to_an_unread_field_submits_nothing(
        self,
        dataset: PythonRecomputeDataset,
        db: InfrahubDatabase,
        workflow_recorder: WorkflowRecorder,
        default_branch: Branch,
        admin_account: CoreAccount,
    ) -> None:
        """Neither transform query reads the seat count, so the merge of one refreshes nothing."""
        submissions = await self._run_pass(
            db=db,
            recorder=workflow_recorder,
            default_branch=default_branch,
            admin_account=admin_account,
            changes=[
                MergeChange(
                    node_id=dataset.car_ids[0],
                    kind=CAR_KIND,
                    action="updated",
                    changed_fields=frozenset({"nbr_seats"}),
                )
            ],
        )

        assert submissions == {}

    async def test_a_change_to_a_read_relationship_selects_only_the_attribute_reading_it(
        self,
        dataset: PythonRecomputeDataset,
        db: InfrahubDatabase,
        workflow_recorder: WorkflowRecorder,
        default_branch: Branch,
        admin_account: CoreAccount,
    ) -> None:
        """Only the owner-reading query has the relationship in its read set.

        Both cars come back, since one group holds the members of every node that computed through
        that query: the narrowing is per attribute, not per subscriber.
        """
        submissions = await self._run_pass(
            db=db,
            recorder=workflow_recorder,
            default_branch=default_branch,
            admin_account=admin_account,
            changes=[
                MergeChange(
                    node_id=dataset.car_ids[0],
                    kind=CAR_KIND,
                    action="updated",
                    changed_fields=frozenset({"owner"}),
                )
            ],
        )

        assert submissions == {OWNER_ATTRIBUTE: sorted(dataset.car_ids)}

    async def test_a_peer_change_selects_its_readers_through_the_query_group(
        self,
        dataset: PythonRecomputeDataset,
        db: InfrahubDatabase,
        workflow_recorder: WorkflowRecorder,
        default_branch: Branch,
        admin_account: CoreAccount,
    ) -> None:
        """Only the attribute whose query reads the owner is refreshed, over both subscribed cars."""
        submissions = await self._run_pass(
            db=db,
            recorder=workflow_recorder,
            default_branch=default_branch,
            admin_account=admin_account,
            changes=[
                MergeChange(
                    node_id=dataset.person_id,
                    kind=PERSON_KIND,
                    action="updated",
                    changed_fields=frozenset({"name"}),
                )
            ],
        )

        assert submissions == {OWNER_ATTRIBUTE: sorted(dataset.car_ids)}


class TestCoalescedRecomputePythonDeletedPeer(CoalescedPythonTestBase):
    """A merged peer deletion still refreshes the readers of that peer.

    The reverse lookup cannot see a deleted node: its group membership closed with it. The readers
    are carried by their own relationship update instead, which the change set of the merge holds.
    """

    @pytest.fixture(scope="class")
    async def deleted_peer_dataset(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        client: InfrahubClient,
        admin_account: CoreAccount,
    ) -> PythonRecomputeDataset:
        dataset = await _seed(db=db, branch=default_branch)
        person = await NodeManager.get_one(db=db, id=dataset.person_id, raise_on_error=True)
        await person.delete(db=db)
        return dataset

    async def test_the_readers_are_refreshed_by_their_own_relationship_update(
        self,
        deleted_peer_dataset: PythonRecomputeDataset,
        db: InfrahubDatabase,
        workflow_recorder: WorkflowRecorder,
        default_branch: Branch,
        admin_account: CoreAccount,
    ) -> None:
        submissions = await self._run_pass(
            db=db,
            recorder=workflow_recorder,
            default_branch=default_branch,
            admin_account=admin_account,
            changes=[
                MergeChange(node_id=deleted_peer_dataset.person_id, kind=PERSON_KIND, action="deleted"),
                *[
                    MergeChange(node_id=car_id, kind=CAR_KIND, action="updated", changed_fields=frozenset({"owner"}))
                    for car_id in deleted_peer_dataset.car_ids
                ],
            ],
        )

        assert submissions == {OWNER_ATTRIBUTE: sorted(deleted_peer_dataset.car_ids)}
