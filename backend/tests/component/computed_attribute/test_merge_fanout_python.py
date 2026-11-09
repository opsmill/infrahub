"""Measure the node fan-out of a Python computed-attribute recompute.

On merge/rebase a Python computed attribute is refreshed by dispatching one
recompute per affected attribute, which then resolves the nodes to process. This
records how many nodes that resolution selects. Today it selects every node of
the kind regardless of how many changed; once the recompute is scoped to the
changed nodes the same test pins the affected-only count.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from infrahub.computed_attribute.tasks import trigger_update_python_computed_attributes
from infrahub.core.node import Node
from infrahub.workflows.catalogue import COMPUTED_ATTRIBUTE_PROCESS_TRANSFORM
from tests.component.computed_attribute._base import (
    CAR_PERSON_PYTHON_SCHEMA,
    ScopedRecomputeTestBase,
    create_transform01,
)
from tests.helpers.schema import load_schema

if TYPE_CHECKING:
    from infrahub_sdk import InfrahubClient

    from infrahub.core.branch import Branch
    from infrahub.core.protocols import CoreAccount
    from infrahub.database import InfrahubDatabase
    from tests.adapters.workflow import WorkflowRecorder

CAR_COUNT = 5


class TestMergeFanoutPython(ScopedRecomputeTestBase):
    # The fan-out is dispatched as one process-transform per chunk of node ids.
    WORKFLOW = COMPUTED_ATTRIBUTE_PROCESS_TRANSFORM

    @pytest.fixture(scope="class")
    async def transform_dataset(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        client: InfrahubClient,
        admin_account: CoreAccount,
    ) -> set[str]:
        """One transform reading TestCar.name, plus CAR_COUNT cars owned by one person.

        Returns the ids of every car, so the test can compare the fan-out against the
        full population of the kind.
        """
        await create_transform01(db=db, branch_name=default_branch.name)

        await load_schema(db=db, schema=CAR_PERSON_PYTHON_SCHEMA, update_db=True)

        owner = await Node.init(db=db, schema="TestPerson")
        await owner.new(db=db, name="owner01")
        await owner.save(db=db)

        car_ids: set[str] = set()
        for index in range(CAR_COUNT):
            car = await Node.init(db=db, schema="TestCar")
            await car.new(db=db, name=f"car{index}", owner=owner)
            await car.save(db=db)
            car_ids.add(car.id)

        return car_ids

    def _fanned_out_ids(self, recorder: WorkflowRecorder) -> set[str]:
        ids: set[str] = set()
        for call in recorder.get_submit_calls_for(self.WORKFLOW):
            ids.update(call["parameters"].get("object_ids") or [])
        return ids

    async def test_recompute_fans_out_to_every_node_of_the_kind(
        self,
        transform_dataset: set[str],
        workflow_recorder: WorkflowRecorder,
        default_branch: Branch,
        admin_account: CoreAccount,
    ) -> None:
        car_ids = transform_dataset

        await trigger_update_python_computed_attributes(
            branch_name=default_branch.name,
            computed_attribute_name="computed_desc_python",
            computed_attribute_kind="TestCar",
            context=self._context(admin_account, default_branch),
        )

        assert self._fanned_out_ids(workflow_recorder) == car_ids
