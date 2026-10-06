"""How a merge brings its two branches onto their remote heads, or refuses when the graph lacks a rewrite."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import TYPE_CHECKING

import pytest
from infrahub_sdk.uuidt import UUIDT

from infrahub import config
from infrahub.core.registry import registry
from infrahub.exceptions import RepositoryDivergentHistoryError, RepositoryError
from tests.adapters.repository_record_store import FailingGraphCommitReader, InMemoryGraphCommitReader
from tests.helpers.git import GraphRecordingClient, LocalRemote, clone_repository

if TYPE_CHECKING:
    from pathlib import Path

    from infrahub.git.divergence.protocols import GraphCommitReader
    from infrahub.git.repository import InfrahubRepository

SOURCE = "feature"
DESTINATION = "main"
REPOSITORY_NAME = "merge-repo"


@dataclass(frozen=True)
class MergeClone:
    remote: LocalRemote
    repository: InfrahubRepository
    client: GraphRecordingClient
    commits: InMemoryGraphCommitReader
    """The commit the graph records for each branch."""

    local_heads: dict[str, str]
    """The head of each branch when this clone took it, which the graph also records."""

    def heads(self) -> dict[str, str]:
        return {
            SOURCE: self.repository.get_commit_value(branch_name=SOURCE, remote=False),
            DESTINATION: str(self.repository.get_git_repo_worktree(identifier=DESTINATION).head.commit),
        }

    def rewind(self, branch_name: str) -> str:
        """Move the remote branch back onto its parent and return the new remote head."""
        parent = str(self.remote.repo.commit(f"{branch_name}~1"))
        self.remote.move_branch(branch_name=branch_name, commit=parent)
        return parent

    def rewrite(self, branch_name: str) -> str:
        """Replace the last commit of the remote branch and return the new remote head."""
        return self.remote.commit(branch_name=branch_name, files={"rewritten.txt": "rewritten\n"}, amend=True)

    async def prepare(self, graph_commits: GraphCommitReader | None = None) -> None:
        await self.repository.prepare_branches_for_merge(
            source_branch=SOURCE, dest_branch=DESTINATION, graph_commits=graph_commits or self.commits
        )


@pytest.fixture
async def merge_clone(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> MergeClone:
    """A clone holding both branches at the commits the graph records, before anything moves on the remote."""
    repos_dir = tmp_path / "repositories"
    repos_dir.mkdir()
    monkeypatch.setattr(registry, "_default_branch", DESTINATION)
    monkeypatch.setattr(config.SETTINGS.git, "repositories_directory", str(repos_dir))

    remote = LocalRemote.create(directory=tmp_path / "remote", trunk=DESTINATION, branches=[])
    local_heads = {
        DESTINATION: remote.commit(branch_name=DESTINATION, files={"trunk.txt": "trunk\n"}),
        SOURCE: remote.commit(branch_name=SOURCE, files={"feature.txt": "feature\n"}),
    }
    client = GraphRecordingClient(branch_names=())
    repository = await clone_repository(
        id=UUIDT.new(),
        name=REPOSITORY_NAME,
        location=str(remote.directory),
        client=client,
        update_commit_value=False,
    )
    await repository.create_branch_in_git(branch_name=SOURCE, branch_id=f"{SOURCE}-id", push_origin=False)
    return MergeClone(
        remote=remote,
        repository=repository,
        client=client,
        commits=InMemoryGraphCommitReader(commits=dict(local_heads)),
        local_heads=local_heads,
    )


@dataclass(frozen=True)
class DivergedBranchCase:
    name: str
    branch_name: str
    rewind: bool
    """Move the remote branch back onto its parent, rather than replace its last commit."""

    def diverge(self, clone: MergeClone) -> str:
        return clone.rewind(branch_name=self.branch_name) if self.rewind else clone.rewrite(self.branch_name)


DIVERGED_BRANCH_CASES = [
    DivergedBranchCase(name="source-rewound", branch_name=SOURCE, rewind=True),
    DivergedBranchCase(name="destination-rewritten", branch_name=DESTINATION, rewind=False),
]


def refusal_message(branch_name: str, local_head: str, graph_commit: str, remote_head: str) -> str:
    return (
        f"Unable to merge {SOURCE} into {DESTINATION} for repository {REPOSITORY_NAME}. "
        f"The remote history of {branch_name} does not contain the local commit {local_head}. "
        f"Infrahub records {graph_commit} for {branch_name}, not the remote head {remote_head}. "
        "Retry the merge after the next synchronization of the repository."
    )


async def test_branches_that_lead_to_their_remote_heads_are_merged_as_they_are(merge_clone: MergeClone) -> None:
    advanced = merge_clone.remote.commit(branch_name=DESTINATION, files={"trunk.txt": "advanced\n"})
    assert advanced != merge_clone.local_heads[DESTINATION]

    await merge_clone.prepare()

    assert merge_clone.heads() == merge_clone.local_heads
    assert merge_clone.commits.reads == []


@pytest.mark.parametrize("case", DIVERGED_BRANCH_CASES, ids=lambda case: case.name)
async def test_a_branch_whose_rewrite_the_graph_lacks_refuses_the_merge(
    merge_clone: MergeClone, case: DivergedBranchCase
) -> None:
    remote_head = case.diverge(clone=merge_clone)
    imported = merge_clone.local_heads[case.branch_name]
    message = refusal_message(
        branch_name=case.branch_name, local_head=imported, graph_commit=imported, remote_head=remote_head
    )

    with pytest.raises(RepositoryDivergentHistoryError, match=rf"^{re.escape(message)}$"):
        await merge_clone.prepare()

    assert merge_clone.heads() == merge_clone.local_heads
    assert merge_clone.client.recorded_commits == []


@pytest.mark.parametrize("case", DIVERGED_BRANCH_CASES, ids=lambda case: case.name)
async def test_a_branch_behind_a_rewrite_the_graph_records_is_reset_before_the_merge(
    merge_clone: MergeClone, case: DivergedBranchCase
) -> None:
    remote_head = case.diverge(clone=merge_clone)
    merge_clone.commits.commits[case.branch_name] = remote_head

    await merge_clone.prepare()

    assert merge_clone.heads() == {**merge_clone.local_heads, case.branch_name: remote_head}
    assert merge_clone.client.recorded_commits == []


async def test_a_source_without_a_worktree_has_its_ref_moved_onto_the_remote_head(merge_clone: MergeClone) -> None:
    """The merge reads the source from its ref, so the ref moves even when no worktree holds the branch."""
    worktree = merge_clone.repository.get_worktree(identifier=SOURCE)
    merge_clone.repository.get_git_repo_main().git.worktree("remove", "--force", str(worktree.directory))
    remote_head = merge_clone.rewind(branch_name=SOURCE)
    merge_clone.commits.commits[SOURCE] = remote_head

    await merge_clone.prepare()

    assert merge_clone.repository.get_commit_value(branch_name=SOURCE, remote=False) == remote_head


async def test_a_refused_branch_keeps_the_other_branch_where_it_is(merge_clone: MergeClone) -> None:
    """The refusal comes before any reset, so a refused merge leaves the clone exactly as it found it."""
    merge_clone.commits.commits[SOURCE] = merge_clone.rewind(branch_name=SOURCE)
    destination_head = merge_clone.rewrite(DESTINATION)
    imported = merge_clone.local_heads[DESTINATION]
    message = refusal_message(
        branch_name=DESTINATION, local_head=imported, graph_commit=imported, remote_head=destination_head
    )

    with pytest.raises(RepositoryDivergentHistoryError, match=rf"^{re.escape(message)}$"):
        await merge_clone.prepare()

    assert merge_clone.heads() == merge_clone.local_heads


async def test_a_diverged_branch_whose_graph_commit_cannot_be_read_refuses_the_merge(merge_clone: MergeClone) -> None:
    merge_clone.rewind(branch_name=SOURCE)

    with pytest.raises(RepositoryError, match=rf"^The API is unreachable from {SOURCE}$"):
        await merge_clone.prepare(graph_commits=FailingGraphCommitReader())

    assert merge_clone.heads() == merge_clone.local_heads
