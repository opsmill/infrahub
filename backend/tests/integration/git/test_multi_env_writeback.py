"""Multi-environment single-repo validation: write-back and branch-mapping behaviour.

These tests exercise a read-write repository whose git default branch is not the Infrahub
primary branch (the multi-environment "one branch per environment" pattern). They reproduce a
write-back loss that occurs when the clone performing the merge has no local copy of the default
branch, and they guard the working branch-mapping contract.

The suite mirrors ``test_git_live_remote.py``: a live Gogs remote plus the in-process app.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from infrahub import config
from infrahub.core.constants import InfrahubKind
from infrahub.core.manager import NodeManager
from infrahub.exceptions import RepositoryError
from infrahub.git.repository import InfrahubRepository
from infrahub.git.tasks import sync_remote_repositories
from tests.helpers.test_app import TestInfrahubApp
from tests.integration.git.conftest import create_gogs_repo

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

    from infrahub_sdk import InfrahubClient
    from testcontainers.core.container import DockerContainer

    from infrahub.core.protocols import CoreRepository
    from infrahub.database import InfrahubDatabase
    from tests.helpers.git import GogsServer

DEV_BRANCH = "develop"


def _create_remote_branch_from_main(container: DockerContainer, repo_name: str, branch: str) -> None:
    """Create ``branch`` on the remote, pointed at the current ``main`` tip, and push it."""
    script = (
        f"set -e && "
        f"cd /tmp/{repo_name} && "
        f"git checkout main && "
        f"git pull origin main && "
        f"git checkout -b {branch} && "
        f"git push origin {branch}"
    )
    result = container.get_wrapped_container().exec_run(["bash", "-c", script], user="git")
    assert result.exit_code == 0, f"Creating remote branch {branch} failed: {result.output.decode()}"


def _push_commit_to_remote(container: DockerContainer, repo_name: str, filename: str, branch: str) -> None:
    """Make a new commit on ``branch`` in the remote server's working clone and push it."""
    script = (
        f"set -e && "
        f"cd /tmp/{repo_name} && "
        f"git checkout {branch} && "
        f"git pull origin {branch} && "
        f"echo 'remote change' > {filename} && "
        f"git add {filename} && "
        f"git commit -m 'Remote commit [{filename}]' && "
        f"git push origin {branch}"
    )
    result = container.get_wrapped_container().exec_run(["bash", "-c", script], user="git")
    assert result.exit_code == 0, f"Remote commit on {branch} failed: {result.output.decode()}"


def _remote_branch_commit(container: DockerContainer, repo_name: str, branch: str) -> str:
    """Return the commit SHA that ``branch`` points at on the remote server."""
    script = f"cd /data/git/repositories/gogsadmin/{repo_name}.git && git rev-parse {branch}"
    result = container.get_wrapped_container().exec_run(["bash", "-c", script], user="git")
    assert result.exit_code == 0, f"Reading remote {branch} failed: {result.output.decode()}"
    return result.output.decode().strip()


def _force_rewrite_remote_branch(container: DockerContainer, repo_name: str, branch: str) -> None:
    """Rewrite ``branch``'s history on the remote and force-push it (a non-fast-forward update)."""
    script = (
        f"set -e && cd /tmp/{repo_name} && git checkout {branch} && "
        f"git reset --hard main && echo rewritten > rewrite.txt && git add rewrite.txt && "
        f"git commit -m 'rewrite history' && git push -f origin {branch}"
    )
    result = container.get_wrapped_container().exec_run(["bash", "-c", script], user="git")
    assert result.exit_code == 0, f"Force-rewrite of {branch} failed: {result.output.decode()}"


class TestMultiEnvWriteBack(TestInfrahubApp):
    """Read-write repository whose git default branch is not the Infrahub primary branch."""

    @pytest.fixture(scope="class")
    async def nonmain_default_dataset(
        self,
        db: InfrahubDatabase,
        client: InfrahubClient,
        gogs_server: GogsServer,
    ) -> dict:
        """A repo whose remote has main + develop; registered with default_branch=develop."""
        repo_name = "multi-env-writeback-repo"
        repo_url = create_gogs_repo(gogs_server.base_url, gogs_server.token, repo_name, gogs_server.container)
        _create_remote_branch_from_main(gogs_server.container, repo_name, DEV_BRANCH)

        node = await client.create(
            kind=InfrahubKind.REPOSITORY,
            data={"name": repo_name, "location": repo_url, "default_branch": DEV_BRANCH},
        )
        await node.save()
        return {"repo_name": repo_name, "node_id": node.id}

    @pytest.mark.xfail(
        strict=True,
        reason="write-back push is silently dropped when the executing clone has no local default branch",
    )
    async def test_writeback_dropped_when_default_branch_absent_locally(
        self,
        nonmain_default_dataset: dict,
        db: InfrahubDatabase,
        client: InfrahubClient,
        gogs_server: GogsServer,
    ) -> None:
        """Reconstruct a non-importer clone and assert the write-back to the default branch is lost.

        A worker that did not perform the initial import holds only a local primary branch plus
        remote-tracking refs — no local copy of the git default branch. Merging an Infrahub branch
        into the primary branch writes back by pushing to the (mapped) default branch. With no local
        default-branch ref, that push fails on a missing refspec, which is swallowed: the merge
        reports success while the remote default branch never advances.
        """
        repo_name = nonmain_default_dataset["repo_name"]
        repository: CoreRepository = await NodeManager.get_one(
            db=db,
            id=nonmain_default_dataset["node_id"],
            kind=InfrahubKind.REPOSITORY,
            raise_on_error=True,
        )

        # Fresh clone with default_branch=develop, mimicking a worker's local clone.
        repo = await InfrahubRepository.init(
            id=repository.id,
            name=repo_name,
            client=client,
            default_branch_name=DEV_BRANCH,
        )

        # Non-importer state: a local primary branch worktree with a commit to write back, and NO
        # local develop branch (only origin/develop from the fetch).
        assert "develop" not in repo.get_branches_from_local(include_worktree=False)

        await repo.create_branch_in_git("feature-x", push_origin=False)
        feature_repo = repo.get_git_repo_worktree(identifier="feature-x")
        (Path(str(feature_repo.working_dir)) / "change.txt").write_text("write-back content\n")
        feature_repo.index.add(["change.txt"])
        feature_repo.index.commit("feature-x: change to write back")

        develop_before = _remote_branch_commit(gogs_server.container, repo_name, DEV_BRANCH)

        # Merge into the primary branch; the write-back pushes the mapped default branch (develop).
        await repo.merge(source_branch="feature-x", dest_branch="main", push_remote=True)

        develop_after = _remote_branch_commit(gogs_server.container, repo_name, DEV_BRANCH)

        # The intended contract: the write-back reached the remote default branch.
        assert develop_after != develop_before

    @pytest.fixture(scope="class")
    async def synced_nonmain_default_dataset(
        self,
        db: InfrahubDatabase,
        client: InfrahubClient,
        gogs_server: GogsServer,
    ) -> dict:
        """A separate repo whose remote has main + develop; registered with default_branch=develop.

        Kept distinct from ``nonmain_default_dataset`` so the sync-driven branch assertions are not
        perturbed by the write-back reconstruction test.
        """
        repo_name = "multi-env-sync-repo"
        repo_url = create_gogs_repo(gogs_server.base_url, gogs_server.token, repo_name, gogs_server.container)
        _create_remote_branch_from_main(gogs_server.container, repo_name, DEV_BRANCH)

        node = await client.create(
            kind=InfrahubKind.REPOSITORY,
            data={"name": repo_name, "location": repo_url, "default_branch": DEV_BRANCH},
        )
        await node.save()
        return {"repo_name": repo_name, "node_id": node.id}

    async def test_nonmain_default_maps_to_primary_no_phantom(
        self,
        synced_nonmain_default_dataset: dict,
        db: InfrahubDatabase,
        client: InfrahubClient,
    ) -> None:
        """A non-primary git default branch maps onto the primary branch with no standalone copy.

        The duplicate ("phantom") branch is created by the periodic sync flow, not the initial
        import, so the flow is run explicitly before asserting the branch set.
        """
        await sync_remote_repositories()

        branches = await client.branch.all()
        assert DEV_BRANCH not in branches

    async def test_nonmain_default_import_not_frozen(
        self,
        synced_nonmain_default_dataset: dict,
        db: InfrahubDatabase,
        client: InfrahubClient,
        gogs_server: GogsServer,
    ) -> None:
        """A new commit on the configured default branch is imported (the repo is not pinned)."""
        repo_name = synced_nonmain_default_dataset["repo_name"]
        node_id = synced_nonmain_default_dataset["node_id"]

        repo_before: CoreRepository = await NodeManager.get_one(
            db=db, id=node_id, kind=InfrahubKind.REPOSITORY, raise_on_error=True
        )
        commit_before = repo_before.commit.value

        _push_commit_to_remote(gogs_server.container, repo_name, "advance.txt", branch=DEV_BRANCH)
        await sync_remote_repositories()

        repo_after: CoreRepository = await NodeManager.get_one(
            db=db, id=node_id, kind=InfrahubKind.REPOSITORY, raise_on_error=True
        )
        assert repo_after.commit.value != commit_before

    async def test_merge_conflict_surfaced_and_worktree_clean(
        self,
        nonmain_default_dataset: dict,
        db: InfrahubDatabase,
        client: InfrahubClient,
    ) -> None:
        """A genuine content conflict during merge surfaces as an error and leaves a clean worktree.

        Confirms working behaviour: the merge aborts on conflict rather than stranding the worktree
        mid-merge (which would poison every later operation on it).
        """
        repo_name = nonmain_default_dataset["repo_name"]
        repository: CoreRepository = await NodeManager.get_one(
            db=db,
            id=nonmain_default_dataset["node_id"],
            kind=InfrahubKind.REPOSITORY,
            raise_on_error=True,
        )
        repo = await InfrahubRepository.init(id=repository.id, name=repo_name, client=client)

        await repo.create_branch_in_git("conflict-a", push_origin=False)
        await repo.create_branch_in_git("conflict-b", push_origin=False)

        repo_a = repo.get_git_repo_worktree(identifier="conflict-a")
        (Path(str(repo_a.working_dir)) / "conflict.txt").write_text("content from a\n")
        repo_a.index.add(["conflict.txt"])
        repo_a.index.commit("conflict-a change")

        repo_b = repo.get_git_repo_worktree(identifier="conflict-b")
        (Path(str(repo_b.working_dir)) / "conflict.txt").write_text("content from b\n")
        repo_b.index.add(["conflict.txt"])
        repo_b.index.commit("conflict-b change")

        with pytest.raises(RepositoryError):
            await repo.merge(source_branch="conflict-a", dest_branch="conflict-b", push_remote=False)

        # The merge must have been aborted: no unmerged paths remain in the destination worktree.
        assert repo_b.git.status("--porcelain") == ""

    @pytest.fixture(scope="class")
    async def imported_nonff_dataset(
        self,
        db: InfrahubDatabase,
        client: InfrahubClient,
        gogs_server: GogsServer,
    ) -> dict:
        """Repo (default_branch=develop) fully imported so the on-disk clone holds a local develop."""
        repo_name = "multi-env-nonff-repo"
        repo_url = create_gogs_repo(gogs_server.base_url, gogs_server.token, repo_name, gogs_server.container)
        _create_remote_branch_from_main(gogs_server.container, repo_name, DEV_BRANCH)
        node = await client.create(
            kind=InfrahubKind.REPOSITORY,
            data={"name": repo_name, "location": repo_url, "default_branch": DEV_BRANCH},
        )
        await node.save()
        await sync_remote_repositories()
        return {"repo_name": repo_name, "node_id": node.id}

    @pytest.mark.xfail(
        strict=True,
        reason="non-fast-forward write-back push is silently swallowed when the remote default branch advanced out of band",
    )
    async def test_nonff_writeback_not_silently_dropped(
        self,
        imported_nonff_dataset: dict,
        db: InfrahubDatabase,
        client: InfrahubClient,
        gogs_server: GogsServer,
    ) -> None:
        """A write-back blocked by a non-fast-forward remote must land or fail, not vanish.

        Distinct from the missing-local-branch drop: here a local default branch exists (imported),
        but the remote advanced out of band, so the write-back push is rejected non-fast-forward and
        the rejection is swallowed — the remote default branch never receives the write-back.
        """
        repo_name = imported_nonff_dataset["repo_name"]
        repository: CoreRepository = await NodeManager.get_one(
            db=db, id=imported_nonff_dataset["node_id"], kind=InfrahubKind.REPOSITORY, raise_on_error=True
        )
        repo = await InfrahubRepository.init(
            id=repository.id, name=repo_name, client=client, default_branch_name=DEV_BRANCH
        )
        assert DEV_BRANCH in repo.get_branches_from_local(include_worktree=False)

        # Remote default branch advances out of band; the local clone does not know yet.
        _push_commit_to_remote(gogs_server.container, repo_name, "out_of_band.txt", branch=DEV_BRANCH)
        develop_before = _remote_branch_commit(gogs_server.container, repo_name, DEV_BRANCH)

        # A write-back change merged into the primary branch pushes the (mapped) default branch.
        await repo.create_branch_in_git("feature-nonff", push_origin=False)
        feature_repo = repo.get_git_repo_worktree(identifier="feature-nonff")
        (Path(str(feature_repo.working_dir)) / "wb.txt").write_text("write-back content\n")
        feature_repo.index.add(["wb.txt"])
        feature_repo.index.commit("feature-nonff: write-back change")

        await repo.merge(source_branch="feature-nonff", dest_branch="main", push_remote=True)

        develop_after = _remote_branch_commit(gogs_server.container, repo_name, DEV_BRANCH)
        # Intended contract: the write-back reached the remote default branch.
        assert develop_after != develop_before

    @pytest.fixture(scope="class")
    async def imported_divergence_dataset(
        self,
        db: InfrahubDatabase,
        client: InfrahubClient,
        gogs_server: GogsServer,
    ) -> dict:
        """Repo (default_branch=develop) fully imported so the on-disk clone holds a local develop."""
        repo_name = "multi-env-divergence-repo"
        repo_url = create_gogs_repo(gogs_server.base_url, gogs_server.token, repo_name, gogs_server.container)
        _create_remote_branch_from_main(gogs_server.container, repo_name, DEV_BRANCH)
        node = await client.create(
            kind=InfrahubKind.REPOSITORY,
            data={"name": repo_name, "location": repo_url, "default_branch": DEV_BRANCH},
        )
        await node.save()
        await sync_remote_repositories()
        return {"repo_name": repo_name, "node_id": node.id}

    async def test_divergent_default_branch_recovers_on_resync(
        self,
        imported_divergence_dataset: dict,
        db: InfrahubDatabase,
        client: InfrahubClient,
        gogs_server: GogsServer,
    ) -> None:
        """Divergence between the local and remote default branch recovers on a later sync.

        The local clone gains a commit the remote lacks, and the remote gains a different commit, so a
        sync's pull of the default branch diverges and surfaces an error. A subsequent sync must
        recover — re-importing to the remote tip — without manual worktree repair. Regression guard:
        divergence must not permanently strand the branch.
        """
        repo_name = imported_divergence_dataset["repo_name"]
        node_id = imported_divergence_dataset["node_id"]

        repo = await InfrahubRepository.init(
            id=node_id, name=repo_name, client=client, default_branch_name=DEV_BRANCH
        )
        # Local default branch advances (a commit that never reaches the remote).
        main_worktree = repo.get_git_repo_worktree(identifier="main")
        (Path(str(main_worktree.working_dir)) / "local_only.txt").write_text("local only\n")
        main_worktree.index.add(["local_only.txt"])
        main_worktree.index.commit("local-only develop commit")

        # Remote default branch advances differently -> the two histories diverge.
        _push_commit_to_remote(gogs_server.container, repo_name, "remote_only.txt", branch=DEV_BRANCH)
        remote_target = _remote_branch_commit(gogs_server.container, repo_name, DEV_BRANCH)

        # First sync hits the divergence; a second sync is the recovery attempt.
        await sync_remote_repositories()
        await sync_remote_repositories()

        repo_after: CoreRepository = await NodeManager.get_one(
            db=db, id=node_id, kind=InfrahubKind.REPOSITORY, raise_on_error=True
        )
        # Intended contract: the branch recovered and imported the remote tip.
        assert repo_after.commit.value == remote_target

    @pytest.fixture(scope="class")
    async def filter_dataset(
        self,
        db: InfrahubDatabase,
        client: InfrahubClient,
        gogs_server: GogsServer,
    ) -> AsyncGenerator[dict, None]:
        """Repo registered while the import-sync filter already excludes feature/*.

        The filter is set BEFORE registration so the initial import honours it — a branch imported
        before the filter was applied would linger (there is no deletion path to remove it).
        """
        original = config.SETTINGS.git.import_sync_branch_names
        config.SETTINGS.git.import_sync_branch_names = ["^main$", f"^{DEV_BRANCH}$"]
        try:
            repo_name = "multi-env-filter-repo"
            repo_url = create_gogs_repo(gogs_server.base_url, gogs_server.token, repo_name, gogs_server.container)
            _create_remote_branch_from_main(gogs_server.container, repo_name, DEV_BRANCH)
            _create_remote_branch_from_main(gogs_server.container, repo_name, "feature/excluded")
            node = await client.create(
                kind=InfrahubKind.REPOSITORY,
                data={"name": repo_name, "location": repo_url, "default_branch": DEV_BRANCH},
            )
            await node.save()
            yield {"repo_name": repo_name, "node_id": node.id}
        finally:
            config.SETTINGS.git.import_sync_branch_names = original

    async def test_filter_excludes_branch(
        self,
        filter_dataset: dict,
        db: InfrahubDatabase,
        client: InfrahubClient,
    ) -> None:
        """A branch outside the import-sync filter is not imported as a standalone Infrahub branch."""
        await sync_remote_repositories()

        branches = await client.branch.all()
        assert "feature/excluded" not in branches
        # The in-filter non-primary default still maps onto the primary branch (no phantom).
        assert DEV_BRANCH not in branches

    async def test_fetch_tolerates_problematic_excluded_ref(
        self,
        filter_dataset: dict,
        db: InfrahubDatabase,
        client: InfrahubClient,
        gogs_server: GogsServer,
    ) -> None:
        """A force-pushed (rewritten) branch outside the filter must not break in-filter syncing.

        Infrahub fetches the whole remote before applying the filter, so this probes whether a
        problematic excluded ref aborts the sync of the in-filter branches. Empirically the fetch
        force-updates the excluded ref without error, so the suspected fetch-before-filter blast
        radius is not reachable via a force-push; this is a green guard for that.
        """
        repo_name = filter_dataset["repo_name"]
        node_id = filter_dataset["node_id"]

        await sync_remote_repositories()

        # A non-fast-forward rewrite of the excluded branch, then advance an in-filter branch.
        _force_rewrite_remote_branch(gogs_server.container, repo_name, "feature/excluded")
        _push_commit_to_remote(gogs_server.container, repo_name, "in_filter_advance.txt", branch=DEV_BRANCH)
        develop_target = _remote_branch_commit(gogs_server.container, repo_name, DEV_BRANCH)

        await sync_remote_repositories()

        repo_after: CoreRepository = await NodeManager.get_one(
            db=db, id=node_id, kind=InfrahubKind.REPOSITORY, raise_on_error=True
        )
        # The in-filter default branch still imported despite the problematic excluded ref.
        assert repo_after.commit.value == develop_target
