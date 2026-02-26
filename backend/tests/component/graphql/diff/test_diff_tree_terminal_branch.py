from unittest.mock import AsyncMock

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


@pytest.fixture
async def diff_branch(db: InfrahubDatabase, default_branch: Branch) -> Branch:
    return await create_branch(db=db, branch_name="branch")


@pytest.fixture
async def diff_repository(db: InfrahubDatabase, diff_branch: Branch) -> DiffRepository:
    component_registry = get_component_registry()
    return await component_registry.get_component(DiffRepository, db=db, branch=diff_branch)


@pytest.fixture
async def diff_coordinator(db: InfrahubDatabase, diff_branch: Branch) -> DiffCoordinator:
    component_registry = get_component_registry()
    coordinator = await component_registry.get_component(DiffCoordinator, db=db, branch=diff_branch)
    coordinator.data_check_synchronizer = AsyncMock(spec=DiffDataCheckSynchronizer)
    coordinator.data_check_synchronizer.synchronize.return_value = []
    return coordinator


async def _merge_branch(db: InfrahubDatabase, diff_branch: Branch, diff_repository: DiffRepository) -> None:
    """Simulate the merge process: mark tracking IDs as merged and set branch status."""
    await diff_repository.mark_tracking_ids_merged(tracking_ids=[BranchTrackingId(name=diff_branch.name)])
    diff_branch.status = BranchStatus.MERGED
    await diff_branch.save(db=db)
    registry.branch[diff_branch.name] = diff_branch


async def test_diff_tree_merged_branch_returns_stored_diff(
    db: InfrahubDatabase,
    default_branch: Branch,
    criticality_schema: NodeSchema,
    criticality_low: Node,
    diff_branch: Branch,
    diff_coordinator: DiffCoordinator,
    diff_repository: DiffRepository,
) -> None:
    """DiffTree query on a merged branch should return the stored BranchTrackingId diff."""
    branch_crit = await NodeManager.get_one(db=db, id=criticality_low.id, branch=diff_branch)
    branch_crit.color.value = "#abcdef"
    await branch_crit.save(db=db)

    await diff_coordinator.update_branch_diff(base_branch=default_branch, diff_branch=diff_branch)
    await _merge_branch(db=db, diff_branch=diff_branch, diff_repository=diff_repository)

    default_branch.update_schema_hash()
    params = await prepare_graphql_params(db=db, branch=default_branch)
    result = await graphql(
        schema=params.schema,
        source=DIFF_TREE_QUERY,
        context_value=params.context,
        root_value=None,
        variable_values={"branch": diff_branch.name},
    )

    assert result.errors is None
    assert result.data
    diff_tree = result.data["DiffTree"]
    assert diff_tree is not None
    assert diff_tree["base_branch"] == default_branch.name
    assert diff_tree["diff_branch"] == diff_branch.name
    assert diff_tree["num_updated"] == 1
    assert len(diff_tree["nodes"]) == 1
    node = diff_tree["nodes"][0]
    assert node["uuid"] == criticality_low.id
    assert node["status"] == "UPDATED"


async def test_diff_tree_merged_branch_honors_explicit_time_filters(
    db: InfrahubDatabase,
    default_branch: Branch,
    criticality_schema: NodeSchema,
    criticality_low: Node,
    diff_branch: Branch,
    diff_coordinator: DiffCoordinator,
    diff_repository: DiffRepository,
) -> None:
    """Explicit time filters should be honored even for merged branches."""
    branch_crit = await NodeManager.get_one(db=db, id=criticality_low.id, branch=diff_branch)
    branch_crit.color.value = "#abcdef"
    await branch_crit.save(db=db)

    await diff_coordinator.update_branch_diff(base_branch=default_branch, diff_branch=diff_branch)
    await _merge_branch(db=db, diff_branch=diff_branch, diff_repository=diff_repository)

    # Use a time range far in the future - no diff covers this range
    far_future = "2099-01-01T00:00:00Z"
    farther_future = "2099-12-31T23:59:59Z"

    default_branch.update_schema_hash()
    params = await prepare_graphql_params(db=db, branch=default_branch)
    result = await graphql(
        schema=params.schema,
        source=DIFF_TREE_QUERY_WITH_TIME_FILTERS,
        context_value=params.context,
        root_value=None,
        variable_values={
            "branch": diff_branch.name,
            "from_time": far_future,
            "to_time": farther_future,
        },
    )

    assert result.errors is None
    assert result.data
    assert result.data["DiffTree"] is None


async def test_diff_tree_summary_merged_branch(
    db: InfrahubDatabase,
    default_branch: Branch,
    criticality_schema: NodeSchema,
    criticality_low: Node,
    diff_branch: Branch,
    diff_coordinator: DiffCoordinator,
    diff_repository: DiffRepository,
) -> None:
    """DiffTreeSummary query on a merged branch should return the stored summary."""
    branch_crit = await NodeManager.get_one(db=db, id=criticality_low.id, branch=diff_branch)
    branch_crit.color.value = "#abcdef"
    await branch_crit.save(db=db)

    await diff_coordinator.update_branch_diff(base_branch=default_branch, diff_branch=diff_branch)
    await _merge_branch(db=db, diff_branch=diff_branch, diff_repository=diff_repository)

    default_branch.update_schema_hash()
    params = await prepare_graphql_params(db=db, branch=default_branch)
    result = await graphql(
        schema=params.schema,
        source=DIFF_TREE_SUMMARY_QUERY,
        context_value=params.context,
        root_value=None,
        variable_values={"branch": diff_branch.name},
    )

    assert result.errors is None
    assert result.data
    summary = result.data["DiffTreeSummary"]
    assert summary is not None
    assert summary["base_branch"] == default_branch.name
    assert summary["diff_branch"] == diff_branch.name
    assert summary["num_updated"] == 1


async def test_diff_update_mutation_on_merged_branch(
    db: InfrahubDatabase,
    default_branch: Branch,
    criticality_low: Node,
    diff_branch: Branch,
    diff_coordinator: DiffCoordinator,
    diff_repository: DiffRepository,
) -> None:
    """DiffUpdate mutation on a merged branch should succeed without recalculating."""
    branch_crit = await NodeManager.get_one(db=db, id=criticality_low.id, branch=diff_branch)
    branch_crit.color.value = "#abcdef"
    await branch_crit.save(db=db)

    await diff_coordinator.update_branch_diff(base_branch=default_branch, diff_branch=diff_branch)
    await _merge_branch(db=db, diff_branch=diff_branch, diff_repository=diff_repository)

    # capture diff metadata before the mutation
    pre_metadata = await diff_repository.get_roots_metadata(
        diff_branch_names=[diff_branch.name],
        tracking_id=BranchTrackingId(name=diff_branch.name),
        exclude_merged=False,
    )
    assert len(pre_metadata) == 1

    default_branch.update_schema_hash()
    params = await prepare_graphql_params(db=db, branch=default_branch)
    result = await graphql(
        schema=params.schema,
        source=DIFF_UPDATE_MUTATION,
        context_value=params.context,
        root_value=None,
        variable_values={"branch": diff_branch.name},
    )

    assert result.errors is None
    assert result.data
    assert result.data["DiffUpdate"]["ok"] is True

    # verify diff timestamps are unchanged after update
    post_metadata = await diff_repository.get_roots_metadata(
        diff_branch_names=[diff_branch.name],
        tracking_id=BranchTrackingId(name=diff_branch.name),
        exclude_merged=False,
    )
    assert len(post_metadata) == 1
    assert post_metadata[0].uuid == pre_metadata[0].uuid
    assert post_metadata[0].from_time == pre_metadata[0].from_time
    assert post_metadata[0].to_time == pre_metadata[0].to_time
