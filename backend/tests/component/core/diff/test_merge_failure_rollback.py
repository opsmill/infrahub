"""A merge rollback requested before the merge ever wrote anything must leave the graph untouched."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from infrahub.core.diff.merger.exclusion_plan import MergeExclusionPlanBuilder
from infrahub.core.diff.merger.merger import DiffMerger
from infrahub.core.diff.repository.repository import DiffRepository
from infrahub.core.initialization import create_branch
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.core.rollback import GraphRollbacker
from infrahub.core.timestamp import Timestamp
from infrahub.dependencies.registry import get_component_registry

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.core.schema.schema_branch import SchemaBranch
    from infrahub.database import InfrahubDatabase


class TestRollbackBeforeMergeIsNoop:
    @pytest.fixture(scope="class", autouse=True)
    async def _schema(
        self,
        register_core_models_schema_scope_class: SchemaBranch,
        car_person_schema_scope_class: SchemaBranch,
    ) -> None:
        return

    async def test_rollback_before_merge_is_a_noop(
        self,
        db: InfrahubDatabase,
        default_branch_scope_class: Branch,
    ) -> None:
        at_existing = Timestamp()
        bystander = await Node.init(db=db, schema="TestPerson", branch=default_branch_scope_class)
        await bystander.new(db=db, name="Bystander", height=180)
        await bystander.save(db=db, at=at_existing)

        branch = await create_branch(branch_name="merge-fail-rollback", db=db)
        component_registry = get_component_registry()
        diff_repository = await component_registry.get_component(DiffRepository, db=db, branch=branch)
        diff_merger = DiffMerger(
            db=db,
            source_branch=branch,
            destination_branch=default_branch_scope_class,
            diff_repository=diff_repository,
            exclusion_plan_builder=MergeExclusionPlanBuilder(),
            rollbacker=GraphRollbacker(db=db),
        )

        await diff_merger.rollback(merge_started_at=at_existing)

        bystander_after = await NodeManager.get_one(db=db, id=bystander.id, branch=default_branch_scope_class)
        assert bystander_after is not None, "Rollback before any merge must not delete data at the given timestamp"
        assert bystander_after.get_attribute("name").value == "Bystander"
