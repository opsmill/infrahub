"""Which repositories take part in the Git merge of a branch, and the commit each side of the merge records."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from infrahub.core.constants import InfrahubKind, RepositoryInternalStatus
from infrahub.core.initialization import create_branch
from infrahub.core.manager import NodeManager
from infrahub.core.merge.repository_merge_dispatcher import RepositoryMergeDispatcher, list_git_merge_targets
from infrahub.core.node import Node
from infrahub.git.merge_readiness import GitMergeTarget
from infrahub.git.models import GitRepositoryMerge
from infrahub.workflows.catalogue import GIT_REPOSITORIES_MERGE
from tests.adapters.workflow import WorkflowRecorder

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.core.schema.schema_branch import SchemaBranch
    from infrahub.database import InfrahubDatabase

TRUNK_COMMIT = "a" * 40
BRANCH_COMMIT = "b" * 40


async def create_repository(db: InfrahubDatabase, name: str, **values: Any) -> Node:
    """Create an active repository, as the add flow leaves it once the first import succeeded."""
    repository = await Node.init(db=db, schema=InfrahubKind.REPOSITORY)
    values.setdefault("internal_status", RepositoryInternalStatus.ACTIVE.value)
    await repository.new(db=db, name=name, location=f"https://git.example.com/{name}.git", **values)
    await repository.save(db=db)
    return repository


async def update_on_branch(db: InfrahubDatabase, repository: Node, branch: Branch, **values: str) -> None:
    on_branch = await NodeManager.get_one(db=db, id=repository.id, branch=branch, raise_on_error=True)
    for name, value in values.items():
        getattr(on_branch, name).value = value
    await on_branch.save(db=db)


async def create_feature_branch(db: InfrahubDatabase, sync_with_git: bool) -> Branch:
    branch = await create_branch(branch_name="feature", db=db)
    branch.sync_with_git = sync_with_git
    await branch.save(db=db)
    return branch


async def test_only_the_active_repositories_of_the_branch_are_git_merge_targets(
    db: InfrahubDatabase, default_branch: Branch, register_core_models_schema: SchemaBranch
) -> None:
    active = await create_repository(db=db, name="active-repo", default_branch="develop", commit=TRUNK_COMMIT)
    staging = await create_repository(db=db, name="staging-repo", commit=TRUNK_COMMIT)
    await create_repository(db=db, name="inactive-repo", internal_status=RepositoryInternalStatus.INACTIVE.value)
    feature = await create_feature_branch(db=db, sync_with_git=True)
    await update_on_branch(db=db, repository=active, branch=feature, commit=BRANCH_COMMIT)
    await update_on_branch(
        db=db, repository=staging, branch=feature, internal_status=RepositoryInternalStatus.STAGING.value
    )

    targets = await list_git_merge_targets(db=db, source_branch=feature)

    assert targets == [
        GitMergeTarget(
            name="active-repo",
            location="https://git.example.com/active-repo.git",
            remote_source_branch="feature",
            remote_trunk="develop",
            source_commit=BRANCH_COMMIT,
            destination_commit=TRUNK_COMMIT,
        )
    ]


async def test_a_branch_not_synced_with_git_has_no_git_merge_target(
    db: InfrahubDatabase, default_branch: Branch, register_core_models_schema: SchemaBranch
) -> None:
    await create_repository(db=db, name="active-repo", commit=TRUNK_COMMIT)
    feature = await create_feature_branch(db=db, sync_with_git=False)

    assert await list_git_merge_targets(db=db, source_branch=feature) == []


async def test_the_git_merge_carries_the_commits_the_graph_records_at_dispatch(
    db: InfrahubDatabase, default_branch: Branch, register_core_models_schema: SchemaBranch
) -> None:
    """The source branch can be deleted before the Git merge runs, so the merge must not read it again."""
    repository = await create_repository(db=db, name="active-repo", commit=TRUNK_COMMIT)
    feature = await create_feature_branch(db=db, sync_with_git=True)
    await update_on_branch(db=db, repository=repository, branch=feature, commit=BRANCH_COMMIT)
    workflow = WorkflowRecorder()

    await RepositoryMergeDispatcher(
        db=db, source_branch=feature, destination_branch=default_branch, workflow=workflow
    ).merge_core_repositories()

    assert [call["parameters"] for call in workflow.get_submit_calls_for(GIT_REPOSITORIES_MERGE)] == [
        {
            "model": GitRepositoryMerge(
                repository_id=repository.id,
                repository_name="active-repo",
                internal_status=RepositoryInternalStatus.ACTIVE.value,
                source_branch="feature",
                destination_branch=default_branch.name,
                destination_branch_id=str(default_branch.get_uuid()),
                repository_kind=InfrahubKind.REPOSITORY,
                source_commit=BRANCH_COMMIT,
            )
        }
    ]
