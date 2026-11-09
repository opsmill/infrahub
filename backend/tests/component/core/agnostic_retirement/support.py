"""Shared drivers and failure doubles for the branch-agnostic retirement suite.

Branch-agnostic fields on branch-aware objects are released only when they cannot be read from any
branch. Each test module in this package covers one enforcement point of that rule, and every
assertion reads the edges directly rather than going through the node manager: the subject is which
edges carry a `to` timestamp and which do not, and a read through the manager would hide the very
states the tests exist to pin down. Where a branch is expected to go on reading the object, the
manager is used as well, because that is the claim being made.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any
from unittest.mock import AsyncMock

from infrahub.core.diff.coordinator import DiffCoordinator
from infrahub.core.diff.data_check_synchronizer import DiffDataCheckSynchronizer
from infrahub.core.diff.merger.merger import DiffMerger
from infrahub.core.diff.repository.repository import DiffRepository
from infrahub.core.manager import NodeManager
from infrahub.core.query.branch_agnostic_retirement import RetireBranchAgnosticFieldsQuery
from infrahub.core.query.node_agnostic_retirement import RetireNodeAgnosticFieldsQuery
from infrahub.database import InfrahubDatabase, InfrahubDatabaseMode
from infrahub.dependencies.registry import get_component_registry
from tests.helpers.agnostic_edges import TEST_ACTOR_ID

if TYPE_CHECKING:
    from neo4j import Record

    from infrahub.core.branch import Branch
    from infrahub.core.diff.model.path import EnrichedDiffRoot
    from infrahub.core.query import QueryType
    from infrahub.core.timestamp import Timestamp


class RetirementFailureError(Exception):
    """Stands in for whatever the retirement run could fail with."""


class FailingRetirementDatabase(InfrahubDatabase):
    """Database that fails the branch-agnostic retirement query and passes every other query through.

    A real database is what makes the claim testable: the deletion's own writes have to reach the
    transaction so that the rollback has something to undo.
    """

    failing_query_name: str = RetireNodeAgnosticFieldsQuery.name

    @classmethod
    def from_db(cls, db: InfrahubDatabase) -> FailingRetirementDatabase:
        return cls(
            mode=InfrahubDatabaseMode.DRIVER,
            driver=db._driver,
            db_type=db.db_type,
            default_neo4j_runtime=db.default_neo4j_runtime,
            queries_names_to_config=db.queries_names_to_config,
        )

    async def execute_query_with_metadata(
        self,
        query: str,
        params: dict[str, Any] | None = None,
        name: str = "undefined",
        context: dict[str, str] | None = None,
        type: QueryType | None = None,
        timeout_seconds: float | None = None,
    ) -> tuple[list[Record], dict[str, Any]]:
        if name == self.failing_query_name:
            raise RetirementFailureError("the retirement run could not complete")
        return await super().execute_query_with_metadata(
            query=query, params=params, name=name, context=context, type=type, timeout_seconds=timeout_seconds
        )


class FailingBranchRetirementDatabase(FailingRetirementDatabase):
    """Fails the branch-deletion retirement query instead of the node-deletion one."""

    failing_query_name = RetireBranchAgnosticFieldsQuery.name


async def delete_node(
    db: InfrahubDatabase, node_id: str, branch: Branch, at: Timestamp, user_id: str = TEST_ACTOR_ID
) -> None:
    to_delete = await NodeManager.get_one(db=db, id=node_id, branch=branch, raise_on_error=True)
    await to_delete.delete(db=db, at=at, user_id=user_id)


async def update_branch_diff(db: InfrahubDatabase, default_branch: Branch, branch: Branch) -> EnrichedDiffRoot:
    """Recompute the branch's tracked diff and return the enriched branch-side diff root."""
    component_registry = get_component_registry()
    diff_coordinator = await component_registry.get_component(DiffCoordinator, db=db, branch=branch)
    diff_coordinator.data_check_synchronizer = AsyncMock(spec=DiffDataCheckSynchronizer)
    metadata = await diff_coordinator.update_branch_diff(base_branch=default_branch, diff_branch=branch)
    diff_repository = await component_registry.get_component(DiffRepository, db=db, branch=default_branch)
    return await diff_repository.get_one(diff_branch_name=metadata.diff_branch_name, diff_id=metadata.uuid)


async def merge_branch(db: InfrahubDatabase, default_branch: Branch, branch: Branch, at: Timestamp) -> None:
    """Merge the branch's graph into the default branch, the way the merge flow drives it."""
    await update_branch_diff(db=db, default_branch=default_branch, branch=branch)
    component_registry = get_component_registry()
    diff_merger = await component_registry.get_component(DiffMerger, db=db, branch=branch)
    await diff_merger.merge_graph(at=at, user_id=TEST_ACTOR_ID)
