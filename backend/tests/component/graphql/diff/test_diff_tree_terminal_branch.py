from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from infrahub.core import registry
from infrahub.core.branch import Branch
from infrahub.core.branch.enums import BranchStatus
from infrahub.core.diff.coordinator import DiffCoordinator
from infrahub.core.diff.data_check_synchronizer import DiffDataCheckSynchronizer
from infrahub.core.diff.model.path import BranchTrackingId
from infrahub.core.diff.repository.repository import DiffRepository
from infrahub.core.initialization import create_branch
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.core.schema import NodeSchema
from infrahub.database import InfrahubDatabase
from infrahub.dependencies.registry import get_component_registry
from infrahub.graphql.initialization import prepare_graphql_params
from tests.helpers.graphql import graphql

DIFF_TREE_QUERY = """
query GetDiffTree($branch: String){
    DiffTree (branch: $branch) {
        base_branch
        diff_branch
        from_time
        to_time
        num_added
        num_removed
        num_updated
        num_conflicts
        nodes {
            uuid
            kind
            label
            status
            attributes {
                name
                status
                properties {
                    property_type
                    previous_value
                    new_value
                    status
                }
            }
        }
    }
}
"""

DIFF_TREE_QUERY_WITH_TIME_FILTERS = """
query GetDiffTree($branch: String, $from_time: DateTime, $to_time: DateTime){
    DiffTree (branch: $branch, from_time: $from_time, to_time: $to_time) {
        base_branch
        diff_branch
        num_added
        num_removed
        num_updated
        nodes {
            uuid
            kind
            label
            status
        }
    }
}
"""

DIFF_TREE_QUERY_BY_PROPOSED_CHANGE = """
query ($branch: String, $proposed_change_id: String){
    DiffTree (branch: $branch, proposed_change_id: $proposed_change_id) {
        nodes {
            uuid
            kind
            label
            status
        }
    }
}
"""

DIFF_TREE_SUMMARY_QUERY = """
query GetDiffTreeSummary($branch: String){
    DiffTreeSummary (branch: $branch) {
        base_branch
        diff_branch
        num_added
        num_removed
        num_updated
        num_conflicts
        num_unchanged
    }
}
"""

DIFF_TREE_SUMMARY_QUERY_BY_PROPOSED_CHANGE = """
query ($branch: String, $proposed_change_id: String){
    DiffTreeSummary (branch: $branch, proposed_change_id: $proposed_change_id) {
        base_branch
        diff_branch
        num_added
        num_removed
        num_updated
        num_conflicts
        num_unchanged
    }
}
"""

DIFF_UPDATE_MUTATION = """
mutation($branch: String!) {
    DiffUpdate(
        data: { branch: $branch },
        wait_until_completion: true
    ) {
        ok
    }
}
"""


class TestDiffTreeTerminalBranch:
    """Tests for DiffTree queries on merged and deleted branches.

    Uses class-scoped fixtures to set up the database, schema, and diff data once,
    then runs tests sequentially. Tests are ordered so that earlier tests verify
    behavior on a merged (but still registered) branch, and later tests simulate
    branch deletion from the registry.
    """

    @pytest.fixture(scope="class")
    async def diff_branch(self, db: InfrahubDatabase, default_branch_scope_class: Branch) -> Branch:
        return await create_branch(db=db, branch_name="branch")

    @pytest.fixture(scope="class")
    async def diff_repository(self, db: InfrahubDatabase, diff_branch: Branch) -> DiffRepository:
        component_registry = get_component_registry()
        return await component_registry.get_component(DiffRepository, db=db, branch=diff_branch)

    @pytest.fixture(scope="class")
    async def diff_coordinator(self, db: InfrahubDatabase, diff_branch: Branch) -> DiffCoordinator:
        component_registry = get_component_registry()
        coordinator = await component_registry.get_component(DiffCoordinator, db=db, branch=diff_branch)
        coordinator.data_check_synchronizer = AsyncMock(spec=DiffDataCheckSynchronizer)
        coordinator.data_check_synchronizer.synchronize.return_value = []
        return coordinator

    @pytest.fixture(scope="class")
    async def criticality_low(self, db: InfrahubDatabase, criticality_schema_scope_class: NodeSchema) -> Node:
        obj = await Node.init(db=db, schema=criticality_schema_scope_class)
        await obj.new(db=db, name="low", level=4)
        await obj.save(db=db)
        return obj

    @pytest.fixture(scope="class")
    async def proposed_change_id(self, db: InfrahubDatabase) -> str:
        """Make a mock Proposed Change"""
        pc_id = str(uuid4())
        await db.execute_query(query="CREATE (pc:Node {uuid: $uuid})", params={"uuid": pc_id})
        return pc_id

    @pytest.fixture(scope="class")
    async def diff_ready(
        self,
        db: InfrahubDatabase,
        default_branch_scope_class: Branch,
        criticality_low: Node,
        diff_branch: Branch,
        diff_coordinator: DiffCoordinator,
        diff_repository: DiffRepository,
        proposed_change_id: str,
    ) -> dict:
        """Set up the diff: make a change on the branch, create and link the diff."""
        branch_crit = await NodeManager.get_one(db=db, id=criticality_low.id, branch=diff_branch)
        branch_crit.color.value = "#abcdef"
        await branch_crit.save(db=db)

        enriched_diff_metadata = await diff_coordinator.update_branch_diff(
            base_branch=default_branch_scope_class, diff_branch=diff_branch
        )

        await diff_repository.link_to_proposed_change(
            diff_uuids=[enriched_diff_metadata.uuid],
            proposed_change_id=proposed_change_id,
        )

        return {"diff_uuid": enriched_diff_metadata.uuid}

    @pytest.fixture(scope="class")
    async def merged_branch(
        self,
        db: InfrahubDatabase,
        diff_branch: Branch,
        diff_repository: DiffRepository,
        diff_ready: dict,
    ) -> Branch:
        """Simulate the merge process: mark tracking IDs as merged and set branch status."""
        await diff_repository.mark_tracking_ids_merged(tracking_ids=[BranchTrackingId(name=diff_branch.name)])
        diff_branch.status = BranchStatus.MERGED
        await diff_branch.save(db=db)
        registry.branch[diff_branch.name] = diff_branch
        return diff_branch

    # -------------------------------------------------------------------------
    # Tests on a merged branch (still in the registry)
    # -------------------------------------------------------------------------

    async def test_diff_tree_merged_branch_returns_stored_diff(
        self,
        db: InfrahubDatabase,
        default_branch_scope_class: Branch,
        criticality_low: Node,
        merged_branch: Branch,
    ) -> None:
        """DiffTree query on a merged branch should return the stored BranchTrackingId diff."""
        default_branch_scope_class.update_schema_hash()
        params = await prepare_graphql_params(db=db, branch=default_branch_scope_class)
        result = await graphql(
            schema=params.schema,
            source=DIFF_TREE_QUERY,
            context_value=params.context,
            root_value=None,
            variable_values={"branch": merged_branch.name},
        )

        assert result.errors is None
        assert result.data
        diff_tree = result.data["DiffTree"]
        assert diff_tree is not None
        assert diff_tree["base_branch"] == default_branch_scope_class.name
        assert diff_tree["diff_branch"] == merged_branch.name
        assert diff_tree["num_updated"] == 1
        assert len(diff_tree["nodes"]) == 1
        node = diff_tree["nodes"][0]
        assert node["uuid"] == criticality_low.id
        assert node["status"] == "UPDATED"

    async def test_diff_tree_merged_branch_honors_explicit_time_filters(
        self,
        db: InfrahubDatabase,
        default_branch_scope_class: Branch,
        merged_branch: Branch,
    ) -> None:
        """Explicit time filters should be honored even for merged branches."""
        far_future = "2099-01-01T00:00:00Z"
        farther_future = "2099-12-31T23:59:59Z"

        default_branch_scope_class.update_schema_hash()
        params = await prepare_graphql_params(db=db, branch=default_branch_scope_class)
        result = await graphql(
            schema=params.schema,
            source=DIFF_TREE_QUERY_WITH_TIME_FILTERS,
            context_value=params.context,
            root_value=None,
            variable_values={
                "branch": merged_branch.name,
                "from_time": far_future,
                "to_time": farther_future,
            },
        )

        assert result.errors is None
        assert result.data
        assert result.data["DiffTree"] is None

    async def test_diff_tree_summary_merged_branch(
        self,
        db: InfrahubDatabase,
        default_branch_scope_class: Branch,
        merged_branch: Branch,
    ) -> None:
        """DiffTreeSummary query on a merged branch should return the stored summary."""
        default_branch_scope_class.update_schema_hash()
        params = await prepare_graphql_params(db=db, branch=default_branch_scope_class)
        result = await graphql(
            schema=params.schema,
            source=DIFF_TREE_SUMMARY_QUERY,
            context_value=params.context,
            root_value=None,
            variable_values={"branch": merged_branch.name},
        )

        assert result.errors is None
        assert result.data
        summary = result.data["DiffTreeSummary"]
        assert summary is not None
        assert summary["base_branch"] == default_branch_scope_class.name
        assert summary["diff_branch"] == merged_branch.name
        assert summary["num_updated"] == 1

    async def test_diff_update_mutation_on_merged_branch(
        self,
        db: InfrahubDatabase,
        default_branch_scope_class: Branch,
        merged_branch: Branch,
        diff_repository: DiffRepository,
    ) -> None:
        """DiffUpdate mutation on a merged branch should succeed without recalculating."""
        pre_metadata = await diff_repository.get_roots_metadata(
            diff_branch_names=[merged_branch.name],
            tracking_id=BranchTrackingId(name=merged_branch.name),
            exclude_merged=False,
        )
        assert len(pre_metadata) == 1

        default_branch_scope_class.update_schema_hash()
        params = await prepare_graphql_params(db=db, branch=default_branch_scope_class)
        result = await graphql(
            schema=params.schema,
            source=DIFF_UPDATE_MUTATION,
            context_value=params.context,
            root_value=None,
            variable_values={"branch": merged_branch.name},
        )

        assert result.errors is None
        assert result.data
        assert result.data["DiffUpdate"]["ok"] is True

        post_metadata = await diff_repository.get_roots_metadata(
            diff_branch_names=[merged_branch.name],
            tracking_id=BranchTrackingId(name=merged_branch.name),
            exclude_merged=False,
        )
        assert len(post_metadata) == 1
        assert post_metadata[0].uuid == pre_metadata[0].uuid
        assert post_metadata[0].from_time == pre_metadata[0].from_time
        assert post_metadata[0].to_time == pre_metadata[0].to_time

    async def test_diff_tree_merged_branch_with_proposed_change_id(
        self,
        db: InfrahubDatabase,
        default_branch_scope_class: Branch,
        criticality_low: Node,
        merged_branch: Branch,
        proposed_change_id: str,
    ) -> None:
        """DiffTree with branch + proposed_change_id should return the linked diff on a merged branch."""
        default_branch_scope_class.update_schema_hash()
        params = await prepare_graphql_params(db=db, branch=default_branch_scope_class)
        result = await graphql(
            schema=params.schema,
            source=DIFF_TREE_QUERY_BY_PROPOSED_CHANGE,
            context_value=params.context,
            root_value=None,
            variable_values={"branch": merged_branch.name, "proposed_change_id": proposed_change_id},
        )

        assert result.errors is None
        assert result.data
        diff_tree = result.data["DiffTree"]
        assert diff_tree is not None
        assert len(diff_tree["nodes"]) == 1
        assert diff_tree["nodes"][0]["uuid"] == criticality_low.id

    async def test_diff_tree_summary_merged_branch_with_proposed_change_id(
        self,
        db: InfrahubDatabase,
        default_branch_scope_class: Branch,
        merged_branch: Branch,
        proposed_change_id: str,
    ) -> None:
        """DiffTreeSummary with branch + proposed_change_id should return the linked summary on a merged branch."""
        default_branch_scope_class.update_schema_hash()
        params = await prepare_graphql_params(db=db, branch=default_branch_scope_class)
        result = await graphql(
            schema=params.schema,
            source=DIFF_TREE_SUMMARY_QUERY_BY_PROPOSED_CHANGE,
            context_value=params.context,
            root_value=None,
            variable_values={"branch": merged_branch.name, "proposed_change_id": proposed_change_id},
        )

        assert result.errors is None
        assert result.data
        summary = result.data["DiffTreeSummary"]
        assert summary is not None
        assert summary["num_updated"] == 1

    # -------------------------------------------------------------------------
    # Tests on a deleted branch (removed from registry and DB)
    # -------------------------------------------------------------------------

    @pytest.fixture(scope="class")
    async def deleted_branch(
        self,
        db: InfrahubDatabase,
        merged_branch: Branch,
    ) -> Branch:
        """Delete the branch and remove it from registry"""
        await merged_branch.delete(db=db)
        registry.branch.pop(merged_branch.name, None)
        return merged_branch

    async def test_diff_tree_deleted_branch_with_proposed_change_id(
        self,
        db: InfrahubDatabase,
        default_branch_scope_class: Branch,
        criticality_low: Node,
        deleted_branch: Branch,
        proposed_change_id: str,
    ) -> None:
        """DiffTree with branch + proposed_change_id should work after the branch is deleted"""
        default_branch_scope_class.update_schema_hash()
        params = await prepare_graphql_params(db=db, branch=default_branch_scope_class)
        result = await graphql(
            schema=params.schema,
            source=DIFF_TREE_QUERY_BY_PROPOSED_CHANGE,
            context_value=params.context,
            root_value=None,
            variable_values={"branch": deleted_branch.name, "proposed_change_id": proposed_change_id},
        )

        assert result.errors is None, (
            f"Expected no errors querying diff for deleted branch with proposed_change_id, got: {result.errors}"
        )
        diff_tree = result.data["DiffTree"]
        assert diff_tree is not None
        assert len(diff_tree["nodes"]) == 1
        assert diff_tree["nodes"][0]["uuid"] == criticality_low.id
        assert diff_tree["nodes"][0]["status"] == "UPDATED"

    async def test_diff_tree_summary_deleted_branch_with_proposed_change_id(
        self,
        db: InfrahubDatabase,
        default_branch_scope_class: Branch,
        deleted_branch: Branch,
        proposed_change_id: str,
    ) -> None:
        """DiffTreeSummary with branch + proposed_change_id should work after the branch is deleted"""
        default_branch_scope_class.update_schema_hash()
        params = await prepare_graphql_params(db=db, branch=default_branch_scope_class)
        result = await graphql(
            schema=params.schema,
            source=DIFF_TREE_SUMMARY_QUERY_BY_PROPOSED_CHANGE,
            context_value=params.context,
            root_value=None,
            variable_values={"branch": deleted_branch.name, "proposed_change_id": proposed_change_id},
        )

        assert result.errors is None, (
            f"Expected no errors querying diff summary for deleted branch with proposed_change_id, got: {result.errors}"
        )
        summary = result.data["DiffTreeSummary"]
        assert summary is not None
        assert summary["num_updated"] == 1
        assert summary["num_added"] == 0
        assert summary["num_removed"] == 0
