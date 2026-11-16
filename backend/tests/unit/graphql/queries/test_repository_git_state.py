from __future__ import annotations

from dataclasses import dataclass

import pytest

from infrahub.core.constants import RepositoryCommitState
from infrahub.graphql.queries.repository_git_state import ResolvedGitRef, _resolve_remote_branch

TRUNK = "trunk"


@dataclass
class RemoteBranchTestCase:
    name: str
    repository_default_branch: str | None
    infrahub_branch_name: str
    branch_is_synced_with_git: bool
    repository_is_staging: bool
    has_imported_commit: bool
    expected: ResolvedGitRef


REMOTE_BRANCH_TEST_CASES: list[RemoteBranchTestCase] = [
    RemoteBranchTestCase(
        name="no_default_branch_reads_no_ref_even_when_staging",
        repository_default_branch=None,
        infrahub_branch_name="branch2",
        branch_is_synced_with_git=False,
        repository_is_staging=True,
        has_imported_commit=True,
        expected=ResolvedGitRef(git_ref=None),
    ),
    RemoteBranchTestCase(
        name="staging_branch_reads_the_trunk_without_a_commit",
        repository_default_branch=TRUNK,
        infrahub_branch_name="branch2",
        branch_is_synced_with_git=False,
        repository_is_staging=True,
        has_imported_commit=False,
        expected=ResolvedGitRef(git_ref=TRUNK),
    ),
    RemoteBranchTestCase(
        name="staging_branch_synced_with_git_reads_the_trunk",
        repository_default_branch=TRUNK,
        infrahub_branch_name="branch2",
        branch_is_synced_with_git=True,
        repository_is_staging=True,
        has_imported_commit=True,
        expected=ResolvedGitRef(git_ref=TRUNK),
    ),
    RemoteBranchTestCase(
        name="branch_not_synced_with_git_reads_the_trunk_without_imports",
        repository_default_branch=TRUNK,
        infrahub_branch_name="branch2",
        branch_is_synced_with_git=False,
        repository_is_staging=False,
        has_imported_commit=True,
        expected=ResolvedGitRef(git_ref=TRUNK, reads_trunk_without_imports=True),
    ),
    RemoteBranchTestCase(
        name="branch_not_synced_with_git_without_a_commit_reads_no_ref",
        repository_default_branch=TRUNK,
        infrahub_branch_name="branch2",
        branch_is_synced_with_git=False,
        repository_is_staging=False,
        has_imported_commit=False,
        expected=ResolvedGitRef(git_ref=None),
    ),
    RemoteBranchTestCase(
        name="branch_synced_with_git_reads_its_own_name",
        repository_default_branch=TRUNK,
        infrahub_branch_name="branch2",
        branch_is_synced_with_git=True,
        repository_is_staging=False,
        has_imported_commit=True,
        expected=ResolvedGitRef(git_ref="branch2"),
    ),
    RemoteBranchTestCase(
        name="default_branch_reads_the_trunk_with_imports",
        repository_default_branch=TRUNK,
        infrahub_branch_name="main",
        branch_is_synced_with_git=False,
        repository_is_staging=False,
        has_imported_commit=True,
        expected=ResolvedGitRef(git_ref=TRUNK),
    ),
]


@pytest.mark.parametrize(
    "test_case",
    [pytest.param(tc, id=tc.name) for tc in REMOTE_BRANCH_TEST_CASES],
)
def test_resolve_remote_branch(test_case: RemoteBranchTestCase) -> None:
    assert (
        _resolve_remote_branch(
            repository_default_branch=test_case.repository_default_branch,
            infrahub_branch_name=test_case.infrahub_branch_name,
            branch_is_synced_with_git=test_case.branch_is_synced_with_git,
            repository_is_staging=test_case.repository_is_staging,
            has_imported_commit=test_case.has_imported_commit,
        )
        == test_case.expected
    )


@dataclass
class StateOnBranchTestCase:
    name: str
    reads_trunk_without_imports: bool
    expected: dict[RepositoryCommitState, RepositoryCommitState]


STATE_ON_BRANCH_TEST_CASES: list[StateOnBranchTestCase] = [
    StateOnBranchTestCase(
        name="reads_trunk_without_imports",
        reads_trunk_without_imports=True,
        expected={
            RepositoryCommitState.HEAD: RepositoryCommitState.HEAD,
            RepositoryCommitState.IMPORTED: RepositoryCommitState.IMPORTED,
            RepositoryCommitState.PENDING: RepositoryCommitState.NOT_ON_BRANCH,
            RepositoryCommitState.HISTORY: RepositoryCommitState.HISTORY,
            RepositoryCommitState.UNRELATED: RepositoryCommitState.UNRELATED,
        },
    ),
    StateOnBranchTestCase(
        name="receives_imports",
        reads_trunk_without_imports=False,
        expected={
            RepositoryCommitState.HEAD: RepositoryCommitState.HEAD,
            RepositoryCommitState.IMPORTED: RepositoryCommitState.IMPORTED,
            RepositoryCommitState.PENDING: RepositoryCommitState.PENDING,
            RepositoryCommitState.HISTORY: RepositoryCommitState.HISTORY,
            RepositoryCommitState.UNRELATED: RepositoryCommitState.UNRELATED,
        },
    ),
]


@pytest.mark.parametrize(
    "test_case",
    [pytest.param(tc, id=tc.name) for tc in STATE_ON_BRANCH_TEST_CASES],
)
def test_state_on_branch(test_case: StateOnBranchTestCase) -> None:
    resolved = ResolvedGitRef(git_ref=TRUNK, reads_trunk_without_imports=test_case.reads_trunk_without_imports)

    assert {state: resolved.state_on_branch(state=state) for state in test_case.expected} == test_case.expected
