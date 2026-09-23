"""Merge scenarios for InfrahubRepository against a real Gogs server.

These tests exercise the merge path under conditions only a real Git fixture
can reliably expose: two locally-checked-out branches whose worktrees carry
conflicting edits to the same file, and a merge invoked with a source branch
whose commit is not resolvable in the local object store.

The two scenarios pin two distinct contracts that callers depend on. A merge
that hits a content conflict must raise a typed repository error AND leave the
destination worktree in a clean, recoverable state — not stuck mid-merge with
conflict markers on disk. A merge whose source branch is unknown locally must
fail loudly before any worktree mutation happens, so that callers do not see
a partially-applied state for a name that was never resolved.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from infrahub.core.constants import InfrahubKind
from infrahub.core.node import Node
from infrahub.exceptions import RepositoryError
from infrahub.git.repository import InfrahubRepository
from tests.helpers.test_app import TestInfrahubApp
from tests.integration.git.conftest import create_gogs_repo

if TYPE_CHECKING:
    from infrahub_sdk import InfrahubClient

    from infrahub.database import InfrahubDatabase
    from tests.helpers.git import GogsServer


class TestMergeScenarios(TestInfrahubApp):
    """Merge-failure paths against a real Gogs server."""

    @pytest.fixture(scope="class")
    async def conflict_dataset(
        self,
        db: InfrahubDatabase,
        initialize_registry: None,
        git_repos_dir_module_scope: Path,
        gogs_server: GogsServer,
    ) -> dict:
        repo_name = "merge-real-conflict-repo"
        clone_url = create_gogs_repo(
            gogs_server.base_url,
            gogs_server.token,
            repo_name,
            gogs_server.container,
        )

        obj = await Node.init(schema=InfrahubKind.REPOSITORY, db=db)
        await obj.new(db=db, name=repo_name, location=clone_url)
        await obj.save(db=db)
        return {"repo_name": repo_name, "node_id": obj.id, "clone_url": clone_url}

    @pytest.fixture(scope="class")
    async def missing_source_dataset(
        self,
        db: InfrahubDatabase,
        initialize_registry: None,
        git_repos_dir_module_scope: Path,
        gogs_server: GogsServer,
    ) -> dict:
        repo_name = "merge-missing-source-repo"
        clone_url = create_gogs_repo(
            gogs_server.base_url,
            gogs_server.token,
            repo_name,
            gogs_server.container,
        )

        obj = await Node.init(schema=InfrahubKind.REPOSITORY, db=db)
        await obj.new(db=db, name=repo_name, location=clone_url)
        await obj.save(db=db)
        return {"repo_name": repo_name, "node_id": obj.id, "clone_url": clone_url}

    async def test_merge_with_real_conflicting_changes_raises_repository_error_and_aborts(
        self,
        conflict_dataset: dict,
        client: InfrahubClient,
    ) -> None:
        """A real content conflict surfaces as a typed error and leaves the worktree clean.

        Two branches each commit different content for the same file. The merge
        surfaces a real Git conflict — not a synthesized one — and must be
        aborted so the destination worktree's tip is unchanged and `git status`
        reports nothing. Without the abort, the worktree would be stuck
        mid-merge with conflict markers on disk and a "MERGE_HEAD" pointer,
        which any subsequent operation would inherit and propagate.

        Today's message contract is generic — `git merge` writes conflict
        diagnostics to stdout, but the conversion to `RepositoryError` reads
        only stderr, so the conflict text is dropped and the placeholder
        message is what callers see. The test pins this so that any change
        that starts preserving the diagnostic text is an explicit, observable
        upgrade rather than a silent improvement.
        """
        repo_name = conflict_dataset["repo_name"]
        clone_url = conflict_dataset["clone_url"]

        infrahub_repo = await InfrahubRepository.new(
            id=conflict_dataset["node_id"],
            name=repo_name,
            location=clone_url,
            client=client,
        )

        await infrahub_repo.create_branch_in_git("merge-source", push_origin=False)
        await infrahub_repo.create_branch_in_git("merge-target", push_origin=False)

        source_repo = infrahub_repo.get_git_repo_worktree(identifier="merge-source")
        (Path(str(source_repo.working_dir)) / "conflict.txt").write_text("source-branch content\n")
        source_repo.index.add(["conflict.txt"])
        source_repo.index.commit("source: conflicting edit to shared file")

        target_repo = infrahub_repo.get_git_repo_worktree(identifier="merge-target")
        (Path(str(target_repo.working_dir)) / "conflict.txt").write_text("target-branch content\n")
        target_repo.index.add(["conflict.txt"])
        target_tip_before_merge = str(target_repo.index.commit("target: conflicting edit to shared file"))

        with pytest.raises(RepositoryError, match=rf"GitRepository '{repo_name}'"):
            await infrahub_repo.merge(
                source_branch="merge-source",
                dest_branch="merge-target",
                push_remote=False,
            )

        target_after_abort = infrahub_repo.get_git_repo_worktree(identifier="merge-target")
        assert str(target_after_abort.head.commit) == target_tip_before_merge
        assert not target_after_abort.git.status("--short")
        assert not (Path(str(target_after_abort.git_dir)) / "MERGE_HEAD").exists()

    async def test_merge_with_source_branch_missing_locally_raises_value_error(
        self,
        missing_source_dataset: dict,
        client: InfrahubClient,
    ) -> None:
        """A merge whose source branch is unknown locally raises a bare ValueError.

        The merge resolves the source branch through the local branch map. When
        the name has no local representation — a remote-only branch that was
        never fetched, or a branch deleted locally — the lookup raises a bare
        ValueError before any worktree mutation. Today's contract is the bare
        ValueError; the test pins it so a future refactor that swaps in a typed
        missing-ref error is an explicit, deliberate change.
        """
        repo_name = missing_source_dataset["repo_name"]
        clone_url = missing_source_dataset["clone_url"]

        infrahub_repo = await InfrahubRepository.new(
            id=missing_source_dataset["node_id"],
            name=repo_name,
            location=clone_url,
            client=client,
        )

        target_repo = infrahub_repo.get_git_repo_worktree(identifier="main")
        target_tip_before = str(target_repo.head.commit)

        with pytest.raises(ValueError, match=r"Branch never-existed-locally not found\."):
            await infrahub_repo.merge(
                source_branch="never-existed-locally",
                dest_branch="main",
                push_remote=False,
            )

        target_after_failed_lookup = infrahub_repo.get_git_repo_worktree(identifier="main")
        assert str(target_after_failed_lookup.head.commit) == target_tip_before
        assert not target_after_failed_lookup.git.status("--short")
