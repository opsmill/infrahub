"""Diff-and-merge coverage for the AGNOSTIC node + AWARE attribute scenario.

Mirrors the real CoreReadOnlyRepository schema shape (AGNOSTIC node with
AWARE ref/commit attributes). The node exists on default before the branch
is created; the AWARE attribute is updated on the branch; after the merge,
the default branch must reflect the value set on the branch.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import AsyncMock

import pytest

from infrahub.core.constants import DiffAction
from infrahub.core.diff.coordinator import DiffCoordinator
from infrahub.core.diff.data_check_synchronizer import DiffDataCheckSynchronizer
from infrahub.core.diff.merger.merger import DiffMerger
from infrahub.core.diff.repository.repository import DiffRepository
from infrahub.core.initialization import create_branch
from infrahub.core.manager import NodeManager
from infrahub.core.timestamp import Timestamp
from infrahub.dependencies.registry import get_component_registry
from tests.helpers.db_validation import verify_no_duplicate_paths

from .get_one_node import get_one_diff_node

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.core.node import Node
    from infrahub.core.schema.schema_branch import SchemaBranch
    from infrahub.database import InfrahubDatabase


class TestDiffAndMergeAgnosticNodeAwareAttr:
    @pytest.fixture(autouse=True)
    async def _setup_core_schema(self, register_core_models_schema: SchemaBranch) -> None:
        return

    @pytest.fixture
    async def diff_repository(self, db: InfrahubDatabase, default_branch: Branch) -> DiffRepository:
        component_registry = get_component_registry()
        return await component_registry.get_component(DiffRepository, db=db, branch=default_branch)

    async def _get_diff_coordinator(self, db: InfrahubDatabase, branch: Branch) -> DiffCoordinator:
        component_registry = get_component_registry()
        diff_coordinator = await component_registry.get_component(DiffCoordinator, db=db, branch=branch)
        diff_coordinator.data_check_synchronizer = AsyncMock(spec=DiffDataCheckSynchronizer)
        return diff_coordinator

    async def _get_diff_merger(self, db: InfrahubDatabase, branch: Branch) -> DiffMerger:
        component_registry = get_component_registry()
        return await component_registry.get_component(DiffMerger, db=db, branch=branch)

    async def test_merge_aware_attribute_update_on_agnostic_node(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        diff_repository: DiffRepository,
        repo_mirror_main: Node,
    ) -> None:
        """Update an AWARE attribute on a branch and verify the merged value.

        appears on default after merge_graph.

        """
        branch = await create_branch(db=db, branch_name="repo_mirror_merge_branch")
        repo_on_branch = await NodeManager.get_one(db=db, branch=branch, id=repo_mirror_main.id)
        new_commit = "b" * 40
        repo_on_branch.get_attribute("ref").value = "feature"
        repo_on_branch.get_attribute("commit").value = new_commit
        await repo_on_branch.save(db=db, user_id="branch-user")

        diff_coordinator = await self._get_diff_coordinator(db=db, branch=branch)
        enriched_diff_metadata = await diff_coordinator.update_branch_diff(
            base_branch=default_branch, diff_branch=branch
        )
        enriched_diff = await diff_repository.get_one(
            diff_branch_name=enriched_diff_metadata.diff_branch_name, diff_id=enriched_diff_metadata.uuid
        )
        diff_node = get_one_diff_node(diff_root=enriched_diff, node_uuid=repo_mirror_main.id)
        assert diff_node.action is DiffAction.UPDATED

        diff_merger = await self._get_diff_merger(db=db, branch=branch)
        merge_at = Timestamp()
        await diff_merger.merge_graph(at=merge_at)

        # On default branch, the AGNOSTIC node's AWARE attributes must reflect the branch values.
        updated_repo = await NodeManager.get_one(db=db, branch=default_branch, id=repo_mirror_main.id)
        assert updated_repo.get_attribute("name").value == "mirror-1", (
            "AGNOSTIC attribute should be unchanged after the merge"
        )
        assert updated_repo.get_attribute("commit").value == new_commit, (
            f"AWARE attribute on AGNOSTIC node should reflect branch value '{new_commit}' "
            f"after merge, got '{updated_repo.get_attribute('commit').value}'"
        )
        assert updated_repo.get_attribute("ref").value == "feature", (
            "AWARE attribute on AGNOSTIC node should reflect branch value 'feature' "
            f"after merge, got '{updated_repo.get_attribute('ref').value}'"
        )

        await verify_no_duplicate_paths(db=db)
