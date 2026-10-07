"""How a merge brings its two branches onto their remote heads, or refuses when the graph lacks a rewrite."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import TYPE_CHECKING

import pytest
from infrahub_sdk.uuidt import UUIDT

from infrahub import config
from infrahub.core.registry import registry
from infrahub.exceptions import RepositoryDivergentHistoryError
from tests.helpers.git import GraphRecordingClient, LocalRemote, clone_repository

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

    from infrahub.git.repository import InfrahubRepository

SOURCE = "feature"
DESTINATION = "main"
REPOSITORY_NAME = "merge-repo"


@dataclass(frozen=True)
class MergeClone:
    remote: LocalRemote
    remote_trunk: str
    """The name the remote gives the branch Infrahub calls main."""

    repository: InfrahubRepository
    client: GraphRecordingClient
    commits: dict[str, str | None]
    """The commit the graph records for each branch."""

    local_heads: dict[str, str]
    """The head of each branch when this clone took it, which the graph also records."""

    def heads(self) -> dict[str, str]:
        return {
            SOURCE: self.repository.get_commit_value(branch_name=SOURCE, remote=False),
            DESTINATION: str(self.repository.get_git_repo_worktree(identifier=DESTINATION).head.commit),
        }

    def remote_branch(self, branch_name: str) -> str:
        return self.remote_trunk if branch_name == DESTINATION else branch_name

    def local_head(self, branch_name: str) -> str:
        """Leave the remote branch as it is and return the head this clone holds."""
        return self.local_heads[branch_name]

    def rewind(self, branch_name: str) -> str:
        """Move the remote branch back onto its parent and return the new remote head."""
        parent = str(self.remote.repo.commit(f"{self.remote_branch(branch_name)}~1"))
        self.remote.move_branch(branch_name=self.remote_branch(branch_name), commit=parent)
        return parent

    def advance(self, branch_name: str) -> str:
        """Add a commit on top of the remote branch and return the new remote head."""
        return self.remote.commit(branch_name=self.remote_branch(branch_name), files={"advanced.txt": "advanced\n"})

    def rewrite(self, branch_name: str) -> str:
        """Replace the last commit of the remote branch and return the new remote head."""
        return self.remote.commit(
            branch_name=self.remote_branch(branch_name), files={"rewritten.txt": "rewritten\n"}, amend=True
        )

    def advance_without_import(self, branch_name: str) -> str:
        """Add a commit on top of the remote branch and return the head this clone holds, which the graph keeps."""
        self.advance(branch_name)
        return self.local_heads[branch_name]

    def import_then_advance(self, branch_name: str) -> str:
        """Push a commit this clone never fetched, add one on top of it, and return the first one."""
        imported = self.remote.commit(branch_name=self.remote_branch(branch_name), files={"imported.txt": "imported\n"})
        self.advance(branch_name)
        return imported

    def import_then_rewrite(self, branch_name: str) -> str:
        """Push a commit this clone never fetched, replace it on the remote, and return the dropped one."""
        imported = self.remote.commit(branch_name=self.remote_branch(branch_name), files={"imported.txt": "imported\n"})
        self.rewrite(branch_name)
        return imported

    def delete(self, branch_name: str) -> str:
        """Delete the remote branch and return the head this clone holds."""
        self.remote.delete_branch(branch_name=self.remote_branch(branch_name))
        return self.local_heads[branch_name]

    async def prepare(self, dest_branch: str = DESTINATION) -> None:
        await self.repository.prepare_branches_for_merge(
            source_branch=SOURCE,
            dest_branch=dest_branch,
            source_commit=self.commits[SOURCE],
            destination_commit=self.commits.get(dest_branch),
        )

    async def prepare_and_merge(self) -> None:
        """Run the guard and then the merge with its push, as the merge flow does."""
        await self.prepare()
        await self.repository.merge(source_branch=SOURCE, dest_branch=DESTINATION)

    def refusal_message(self, branch_name: str, graph_commit: str, remote_head: str) -> str:
        return (
            f"Unable to merge {SOURCE} into {DESTINATION} in the Git repository {REPOSITORY_NAME}. "
            f"The remote history of {self.remote_branch(branch_name)} does not contain the local commit "
            f"{self.local_heads[branch_name]}. Infrahub records {graph_commit} for {branch_name}, not the remote head "
            f"{remote_head}. The branch is merged in Infrahub and not in Git. To finish the merge, merge {SOURCE} into "
            f"{self.remote_trunk} in the Git repository. The next synchronization imports the result."
        )

    def trunk_behind_message(self, graph_commit: str, remote_head: str) -> str:
        return (
            f"Unable to merge {SOURCE} into {DESTINATION} in the Git repository {REPOSITORY_NAME}. "
            f"The remote head {remote_head} of {self.remote_trunk} is ahead of the local commit "
            f"{self.local_heads[DESTINATION]}, and Infrahub records {graph_commit} for {DESTINATION}, not that head. "
            f"The branch is merged in Infrahub and not in Git. To finish the merge, merge {SOURCE} into "
            f"{self.remote_trunk} in the Git repository. The next synchronization imports the result."
        )

    def accept_pushes(self) -> None:
        """Let the remote take a push to the branch its working copy has checked out, as a bare remote does."""
        with self.remote.repo.config_writer() as remote_config:
            remote_config.set_value("receive", "denyCurrentBranch", "ignore")


async def build_merge_clone(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, remote_trunk: str) -> MergeClone:
    """Clone both branches at the commits the graph records, before anything moves on the remote."""
    repos_dir = tmp_path / "repositories"
    repos_dir.mkdir()
    monkeypatch.setattr(registry, "_default_branch", DESTINATION)
    monkeypatch.setattr(config.SETTINGS.git, "repositories_directory", str(repos_dir))

    remote = LocalRemote.create(directory=tmp_path / "remote", trunk=remote_trunk, branches=[])
    local_heads = {
        DESTINATION: remote.commit(branch_name=remote_trunk, files={"trunk.txt": "trunk\n"}),
        SOURCE: remote.commit(branch_name=SOURCE, files={"feature.txt": "feature\n"}),
    }
    client = GraphRecordingClient(branch_names=())
    repository = await clone_repository(
        id=UUIDT.new(),
        name=REPOSITORY_NAME,
        location=str(remote.directory),
        client=client,
        default_branch=remote_trunk,
        update_commit_value=False,
    )
    await repository.create_branch_in_git(branch_name=SOURCE, branch_id=f"{SOURCE}-id", push_origin=False)
    return MergeClone(
        remote=remote,
        remote_trunk=remote_trunk,
        repository=repository,
        client=client,
        commits=dict(local_heads),
        local_heads=local_heads,
    )


@pytest.fixture
async def merge_clone(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> MergeClone:
    return await build_merge_clone(tmp_path=tmp_path, monkeypatch=monkeypatch, remote_trunk=DESTINATION)


@dataclass(frozen=True)
class RemoteChangeCase:
    name: str
    branch_name: str
    graph_commit: Callable[[MergeClone, str], str]
    """Change the remote branch and return the commit the graph records for it."""

    remote_trunk: str = DESTINATION


@pytest.mark.parametrize(
    "case",
    [
        RemoteChangeCase(name="source-behind", branch_name=SOURCE, graph_commit=MergeClone.advance),
        RemoteChangeCase(name="destination-behind", branch_name=DESTINATION, graph_commit=MergeClone.advance),
        RemoteChangeCase(name="source-rewound", branch_name=SOURCE, graph_commit=MergeClone.rewind),
        RemoteChangeCase(name="destination-rewritten", branch_name=DESTINATION, graph_commit=MergeClone.rewrite),
        RemoteChangeCase(
            name="destination-rewritten-on-master",
            branch_name=DESTINATION,
            graph_commit=MergeClone.rewrite,
            remote_trunk="master",
        ),
        RemoteChangeCase(
            name="source-behind-its-graph-commit", branch_name=SOURCE, graph_commit=MergeClone.import_then_advance
        ),
    ],
    ids=lambda case: case.name,
)
async def test_a_branch_is_moved_onto_the_commit_the_graph_records_before_the_merge(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, case: RemoteChangeCase
) -> None:
    """A clone that missed a broadcast would merge an old source, or push onto an old trunk and be rejected."""
    clone = await build_merge_clone(tmp_path=tmp_path, monkeypatch=monkeypatch, remote_trunk=case.remote_trunk)
    graph_commit = case.graph_commit(clone, case.branch_name)
    clone.commits[case.branch_name] = graph_commit

    await clone.prepare()

    assert clone.heads() == {**clone.local_heads, case.branch_name: graph_commit}
    assert clone.client.recorded_commits == []


@pytest.mark.parametrize(
    "case",
    [
        RemoteChangeCase(name="both-on-their-remote-heads", branch_name=SOURCE, graph_commit=MergeClone.local_head),
        RemoteChangeCase(
            name="source-behind-a-head-not-imported",
            branch_name=SOURCE,
            graph_commit=MergeClone.advance_without_import,
        ),
        RemoteChangeCase(
            name="source-behind-a-graph-commit-the-remote-dropped",
            branch_name=SOURCE,
            graph_commit=MergeClone.import_then_rewrite,
        ),
        RemoteChangeCase(name="source-deleted-on-the-remote", branch_name=SOURCE, graph_commit=MergeClone.delete),
    ],
    ids=lambda case: case.name,
)
async def test_a_branch_the_graph_does_not_record_ahead_of_it_is_merged_as_it_is(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, case: RemoteChangeCase
) -> None:
    """The merge then builds on the commit the graph records, not on content the graph never imported."""
    clone = await build_merge_clone(tmp_path=tmp_path, monkeypatch=monkeypatch, remote_trunk=case.remote_trunk)
    clone.commits[case.branch_name] = case.graph_commit(clone, case.branch_name)

    await clone.prepare()

    assert clone.heads() == clone.local_heads


@dataclass(frozen=True)
class RefusalCase:
    name: str
    branch_name: str
    diverge: Callable[[MergeClone, str], str]
    """Move the remote branch off the history of the clone and return the new remote head."""

    remote_trunk: str = DESTINATION
    graph_records_a_commit: bool = True


@pytest.mark.parametrize(
    "case",
    [
        RefusalCase(name="source-rewound", branch_name=SOURCE, diverge=MergeClone.rewind),
        RefusalCase(name="destination-rewritten", branch_name=DESTINATION, diverge=MergeClone.rewrite),
        RefusalCase(
            name="destination-rewritten-on-master",
            branch_name=DESTINATION,
            diverge=MergeClone.rewrite,
            remote_trunk="master",
        ),
        RefusalCase(
            name="source-rewound-with-no-commit-in-the-graph",
            branch_name=SOURCE,
            diverge=MergeClone.rewind,
            graph_records_a_commit=False,
        ),
    ],
    ids=lambda case: case.name,
)
async def test_a_branch_whose_rewrite_the_graph_lacks_refuses_the_merge(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, case: RefusalCase
) -> None:
    clone = await build_merge_clone(tmp_path=tmp_path, monkeypatch=monkeypatch, remote_trunk=case.remote_trunk)
    remote_head = case.diverge(clone, case.branch_name)
    imported = clone.local_heads[case.branch_name]
    clone.commits[case.branch_name] = imported if case.graph_records_a_commit else None
    message = clone.refusal_message(
        branch_name=case.branch_name,
        graph_commit=imported if case.graph_records_a_commit else "no commit",
        remote_head=remote_head,
    )

    with pytest.raises(RepositoryDivergentHistoryError, match=rf"^{re.escape(message)}$"):
        await clone.prepare()

    assert clone.heads() == clone.local_heads
    assert clone.client.recorded_commits == []


@pytest.mark.parametrize(
    "case",
    [
        RemoteChangeCase(
            name="behind-a-head-not-imported", branch_name=DESTINATION, graph_commit=MergeClone.advance_without_import
        ),
        RemoteChangeCase(
            name="behind-its-graph-commit", branch_name=DESTINATION, graph_commit=MergeClone.import_then_advance
        ),
        RemoteChangeCase(
            name="behind-a-graph-commit-the-remote-dropped",
            branch_name=DESTINATION,
            graph_commit=MergeClone.import_then_rewrite,
        ),
    ],
    ids=lambda case: case.name,
)
async def test_a_trunk_behind_a_head_the_graph_does_not_record_refuses_the_merge_before_the_push(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, case: RemoteChangeCase
) -> None:
    """The remote rejects a push onto an older trunk, and by then the graph merge is done."""
    clone = await build_merge_clone(tmp_path=tmp_path, monkeypatch=monkeypatch, remote_trunk=DESTINATION)
    clone.accept_pushes()
    graph_commit = case.graph_commit(clone, DESTINATION)
    clone.commits[DESTINATION] = graph_commit
    remote_head = str(clone.remote.repo.commit(DESTINATION))
    message = clone.trunk_behind_message(graph_commit=graph_commit, remote_head=remote_head)

    with pytest.raises(RepositoryDivergentHistoryError, match=rf"^{re.escape(message)}$"):
        await clone.prepare_and_merge()

    assert str(clone.remote.repo.commit(DESTINATION)) == remote_head
    assert clone.heads() == clone.local_heads


async def test_a_refused_branch_keeps_the_other_branch_where_it_is(merge_clone: MergeClone) -> None:
    """The refusal comes before any reset, so a refused merge leaves the clone exactly as it found it."""
    merge_clone.commits[SOURCE] = merge_clone.rewind(branch_name=SOURCE)
    destination_head = merge_clone.rewrite(DESTINATION)
    message = merge_clone.refusal_message(
        branch_name=DESTINATION, graph_commit=merge_clone.local_heads[DESTINATION], remote_head=destination_head
    )

    with pytest.raises(RepositoryDivergentHistoryError, match=rf"^{re.escape(message)}$"):
        await merge_clone.prepare()

    assert merge_clone.heads() == merge_clone.local_heads


async def test_a_source_without_a_worktree_has_its_ref_moved_onto_the_remote_head(merge_clone: MergeClone) -> None:
    """The merge reads the source from its ref, so the ref moves even when no worktree holds the branch."""
    worktree = merge_clone.repository.get_worktree(identifier=SOURCE)
    merge_clone.repository.get_git_repo_main().git.worktree("remove", "--force", str(worktree.directory))
    remote_head = merge_clone.rewind(branch_name=SOURCE)
    merge_clone.commits[SOURCE] = remote_head

    await merge_clone.prepare()

    assert merge_clone.repository.get_commit_value(branch_name=SOURCE, remote=False) == remote_head


async def test_a_destination_without_a_worktree_is_left_to_the_merge(merge_clone: MergeClone) -> None:
    """The merge builds in the destination worktree and fails without one, so the guard does not move the branch."""
    merge_clone.remote.create_branch(branch_name="release")
    merge_clone.repository.get_git_repo_main().git.branch("release", merge_clone.local_heads[SOURCE])
    merge_clone.commits["release"] = merge_clone.local_heads[DESTINATION]

    await merge_clone.prepare(dest_branch="release")

    assert (
        merge_clone.repository.get_commit_value(branch_name="release", remote=False) == merge_clone.local_heads[SOURCE]
    )
