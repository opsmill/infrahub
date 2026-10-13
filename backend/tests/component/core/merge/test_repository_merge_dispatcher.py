"""Which repositories take part in the Git merge of a branch, and the commit each side of the merge records."""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime
from functools import partial
from typing import TYPE_CHECKING, Any
from uuid import uuid4

import pytest

from infrahub import lock
from infrahub.auth.session import AccountSession
from infrahub.auth.types import AuthType
from infrahub.context import InfrahubContext
from infrahub.core.constants import InfrahubKind, RepositoryInternalStatus
from infrahub.core.initialization import create_branch
from infrahub.core.manager import NodeManager
from infrahub.core.merge.repository_merge_dispatcher import RepositoryMergeDispatcher, list_git_merge_targets
from infrahub.core.node import Node
from infrahub.git.merge_readiness import GitMergeTarget
from infrahub.git.models import GitRepositoryMerge
from infrahub.git.writeback.models import PendingMerge
from infrahub.git.writeback.store import WritebackIntentStore
from infrahub.workflows.catalogue import GIT_REPOSITORIES_MERGE
from tests.adapters.workflow import WorkflowRecorder

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.core.schema.schema_branch import SchemaBranch
    from infrahub.database import InfrahubDatabase

LOGGER_NAME = "tests.repository_merge_dispatcher"
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


def build_dispatcher(
    db: InfrahubDatabase,
    source_branch: Branch,
    default_branch: Branch,
    workflow: WorkflowRecorder,
    logger: logging.Logger | None = None,
) -> RepositoryMergeDispatcher:
    return RepositoryMergeDispatcher(
        db=db,
        source_branch=source_branch,
        destination_branch=default_branch,
        workflow=workflow,
        state_for_session=lambda session: WritebackIntentStore(
            db=session, lock_registry=lock.registry, default_branch=default_branch, clock=partial(datetime.now, UTC)
        ),
        sleep=asyncio.sleep,
        logger=logger,
    )


def build_context(default_branch: Branch) -> InfrahubContext:
    return InfrahubContext.init(
        branch=default_branch, account=AccountSession(account_id=str(uuid4()), auth_type=AuthType.NONE)
    )


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
            nothing_to_merge=False,
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

    await build_dispatcher(
        db=db, source_branch=feature, default_branch=default_branch, workflow=workflow
    ).merge_core_repositories(context=build_context(default_branch=default_branch))

    [submitted] = [call["parameters"]["model"] for call in workflow.get_submit_calls_for(GIT_REPOSITORIES_MERGE)]
    assert submitted.pending_merge is not None
    assert submitted == GitRepositoryMerge(
        repository_id=repository.id,
        repository_name="active-repo",
        internal_status=RepositoryInternalStatus.ACTIVE.value,
        source_branch="feature",
        destination_branch=default_branch.name,
        destination_branch_id=str(default_branch.get_uuid()),
        repository_kind=InfrahubKind.REPOSITORY,
        source_commit=BRANCH_COMMIT,
        pending_merge=PendingMerge(
            entry_id=submitted.pending_merge.entry_id,
            source_branch="feature",
            source_git_branch="feature",
            source_commit=BRANCH_COMMIT,
            merged_at=submitted.pending_merge.merged_at,
        ),
        pending_merge_enqueued=True,
    )


async def test_a_repository_whose_branch_records_the_trunk_commit_gets_no_git_merge(
    db: InfrahubDatabase,
    default_branch: Branch,
    register_core_models_schema: SchemaBranch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Both branches record the same commit, or neither records one, so the Git merge has nothing to push."""
    changed = await create_repository(db=db, name="changed-repo", commit=TRUNK_COMMIT)
    unchanged = await create_repository(db=db, name="unchanged-repo", commit=TRUNK_COMMIT)
    await create_repository(db=db, name="never-cloned-repo")
    staging = await create_repository(db=db, name="staging-repo", commit=TRUNK_COMMIT)
    feature = await create_feature_branch(db=db, sync_with_git=True)
    await update_on_branch(db=db, repository=changed, branch=feature, commit=BRANCH_COMMIT)
    await update_on_branch(db=db, repository=unchanged, branch=feature, commit=TRUNK_COMMIT)
    await update_on_branch(
        db=db, repository=staging, branch=feature, internal_status=RepositoryInternalStatus.STAGING.value
    )
    workflow = WorkflowRecorder()
    caplog.set_level(logging.INFO, logger=LOGGER_NAME)

    await build_dispatcher(
        db=db,
        source_branch=feature,
        default_branch=default_branch,
        workflow=workflow,
        logger=logging.getLogger(LOGGER_NAME),
    ).merge_core_repositories(context=build_context(default_branch=default_branch))

    assert sorted(record.getMessage() for record in caplog.records if record.name == LOGGER_NAME) == [
        "The merge of branch feature changes no content of repository never-cloned-repo, so nothing is pushed to "
        "its remote.",
        "The merge of branch feature changes no content of repository unchanged-repo, so nothing is pushed to its "
        "remote.",
        "The merge of branch feature waits for its push to repository changed-repo.",
    ]
    assert sorted(
        call["parameters"]["model"].repository_name for call in workflow.get_submit_calls_for(GIT_REPOSITORIES_MERGE)
    ) == ["changed-repo", "staging-repo"]
    assert {
        target.name: target.nothing_to_merge for target in await list_git_merge_targets(db=db, source_branch=feature)
    } == {"changed-repo": False, "never-cloned-repo": True, "unchanged-repo": True}


@pytest.mark.parametrize("commit", [BRANCH_COMMIT, "b1a2c3d"], ids=["full-commit-id", "short-commit-id"])
async def test_the_git_merge_of_a_read_only_repository_carries_the_ref_and_commit_of_the_branch(
    db: InfrahubDatabase, default_branch: Branch, register_core_models_schema: SchemaBranch, commit: str
) -> None:
    """The source branch can be deleted before the Git merge runs, so the merge must not read it again.

    The merge copies the commit as the branch stores it, whatever its form.
    """
    repository = await Node.init(db=db, schema=InfrahubKind.READONLYREPOSITORY)
    await repository.new(
        db=db,
        name="read-only-repo",
        location="https://git.example.com/read-only-repo.git",
        ref="main",
        commit=TRUNK_COMMIT,
    )
    await repository.save(db=db)
    feature = await create_feature_branch(db=db, sync_with_git=True)
    await update_on_branch(db=db, repository=repository, branch=feature, ref="v2", commit=commit)
    workflow = WorkflowRecorder()

    await build_dispatcher(
        db=db, source_branch=feature, default_branch=default_branch, workflow=workflow
    ).merge_core_read_only_repositories()

    assert [call["parameters"] for call in workflow.get_submit_calls_for(GIT_REPOSITORIES_MERGE)] == [
        {
            "model": GitRepositoryMerge(
                repository_id=repository.id,
                repository_name="read-only-repo",
                internal_status=RepositoryInternalStatus.INACTIVE.value,
                source_branch="feature",
                destination_branch=default_branch.name,
                destination_branch_id=str(default_branch.get_uuid()),
                repository_kind=InfrahubKind.READONLYREPOSITORY,
                source_commit=commit,
                source_ref="v2",
            )
        }
    ]
