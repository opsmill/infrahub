"""A recompute must not fail on a schema its worker has not loaded yet."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from infrahub.computed_attribute.tasks import process_transform
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


class TestPythonSchemaConvergence(ScopedRecomputeTestBase):
    WORKFLOW = COMPUTED_ATTRIBUTE_PROCESS_TRANSFORM

    @pytest.fixture(scope="class")
    async def transform_dataset(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        client: InfrahubClient,
        admin_account: CoreAccount,
    ) -> str:
        """One transform reading TestCar.name, and one car that a submission can name."""
        await create_transform01(db=db, branch_name=default_branch.name)
        await load_schema(db=db, schema=CAR_PERSON_PYTHON_SCHEMA, update_db=True)

        owner = await Node.init(db=db, schema="TestPerson")
        await owner.new(db=db, name="convergence-owner")
        await owner.save(db=db)
        car = await Node.init(db=db, schema="TestCar")
        await car.new(db=db, name="convergence-car", owner=owner)
        await car.save(db=db)
        return car.id

    async def test_a_kind_the_schema_does_not_carry_ends_the_run_quietly(
        self,
        transform_dataset: str,
        default_branch: Branch,
        admin_account: CoreAccount,
    ) -> None:
        """A submission naming an unknown kind waits for the workers to agree, looks again, then stops.

        It used to raise on the first lookup, which failed the flow run and dropped every node in
        the batch.
        """
        await process_transform(
            branch_name=default_branch.name,
            node_kind="TestNeverExisted",
            computed_attribute_name="computed_desc_python",
            computed_attribute_kind="TestNeverExisted",
            context=self._context(admin_account, default_branch),
            object_ids=[transform_dataset],
        )

    async def test_an_attribute_the_schema_does_not_carry_ends_the_run_quietly(
        self,
        transform_dataset: str,
        default_branch: Branch,
        admin_account: CoreAccount,
    ) -> None:
        """Same for a known kind whose named attribute is gone: a stale submission, not an error."""
        await process_transform(
            branch_name=default_branch.name,
            node_kind="TestCar",
            computed_attribute_name="never_existed",
            computed_attribute_kind="TestCar",
            context=self._context(admin_account, default_branch),
            object_ids=[transform_dataset],
        )
