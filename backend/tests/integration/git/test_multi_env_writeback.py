"""Multi-environment single-repo validation: write-back and branch-mapping behaviour.

These tests exercise a read-write repository whose git default branch is not the Infrahub
primary branch (the multi-environment "one branch per environment" pattern). They reproduce a
write-back loss that occurs when the clone performing the merge has no local copy of the default
branch, and they guard the working branch-mapping contract.

The suite mirrors ``test_git_live_remote.py``: a live Gogs remote plus the in-process app.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from git import Repo

from infrahub import config
from infrahub.core.constants import InfrahubKind
from infrahub.core.manager import NodeManager
from infrahub.exceptions import RepositoryError
from infrahub.git.repository import InfrahubRepository, get_initialized_repo
from infrahub.git.tasks import sync_remote_repositories
from tests.helpers.test_app import TestInfrahubApp
from tests.integration.git.conftest import create_gogs_repo

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator, Generator

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


def _push_conflicting_branch(container: DockerContainer, repo_name: str, branch: str, against: str) -> None:
    """Create ``branch`` from main whose content genuinely conflicts with ``against``.

    Both branches add the same file with different content, so a merge between them cannot be
    resolved automatically.
    """
    script = (
        f"set -e && cd /tmp/{repo_name} && "
        f"git checkout {against} && git pull origin {against} && "
        f"echo 'content from {against}' > clash.txt && git add clash.txt && "
        f"git commit -m 'clash on {against}' && git push origin {against} && "
        f"git checkout main && git checkout -b {branch} && "
        f"echo 'content from {branch}' > clash.txt && git add clash.txt && "
        f"git commit -m 'clash on {branch}' && git push origin {branch}"
    )
    result = container.get_wrapped_container().exec_run(["bash", "-c", script], user="git")
    assert result.exit_code == 0, f"Creating conflicting branch {branch} failed: {result.output.decode()}"


def _seed_local_bare_remote(base_dir: Path) -> Path:
    """Create a local bare remote holding main + develop (equal tips) and a minimal repo config."""
    bare_path = base_dir / "remote.git"
    Repo.init(bare_path, bare=True, initial_branch="main")

    seed_path = base_dir / "seed"
    seed = Repo.init(seed_path, initial_branch="main")
    with seed.config_writer() as cfg:
        cfg.set_value("user", "name", "Infrahub Test")
        cfg.set_value("user", "email", "infrahub@test.local")
    (seed_path / ".infrahub.yml").write_text("---\n")
    seed.index.add([".infrahub.yml"])
    seed.index.commit("Initial commit")
    seed.create_head(DEV_BRANCH)
    seed.create_remote("origin", str(bare_path))
    seed.remotes.origin.push(refspec=["main", DEV_BRANCH])
    return bare_path


def _install_reject_all_pushes_hook(bare_path: Path) -> None:
    """Install a pre-receive hook that rejects every push — a stand-in for branch protection."""
    hook = bare_path / "hooks" / "pre-receive"
    hook.write_text("#!/bin/sh\necho 'pushes are rejected by policy' >&2\nexit 1\n")
    hook.chmod(0o755)


async def _register_and_import(client: InfrahubClient, gogs_server: GogsServer, repo_name: str) -> dict:
    """Create a Gogs repo with main + develop, register it with default_branch=develop, and import it.

    After import the on-disk clone holds a local ``develop`` (the working, "importer" state).
    """
    repo_url = create_gogs_repo(gogs_server.base_url, gogs_server.token, repo_name, gogs_server.container)
    _create_remote_branch_from_main(gogs_server.container, repo_name, DEV_BRANCH)
    node = await client.create(
        kind=InfrahubKind.REPOSITORY,
        data={"name": repo_name, "location": repo_url, "default_branch": DEV_BRANCH},
    )
    await node.save()
    await sync_remote_repositories()
    return {"repo_name": repo_name, "node_id": node.id}


async def _writeback_merge(repo: InfrahubRepository, feature_name: str, filename: str) -> str:
    """Commit a change on a new feature branch, merge it into the primary branch (write-back).

    Returns the primary worktree's tip after the merge — the commit the write-back should have
    delivered to the remote. Read from the worktree, not the merge return value, so the assertion
    cannot be satisfied vacuously by a non-SHA return.
    """
    await repo.create_branch_in_git(feature_name, push_origin=False)
    worktree = repo.get_git_repo_worktree(identifier=feature_name)
    (Path(str(worktree.working_dir)) / filename).write_text("write-back content\n")
    worktree.index.add([filename])
    worktree.index.commit(f"{feature_name}: write-back change")
    await repo.merge(source_branch=feature_name, dest_branch="main", push_remote=True)
    return str(repo.get_git_repo_worktree(identifier="main").head.commit)


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
        assert DEV_BRANCH not in repo.get_branches_from_local(include_worktree=False)

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
        repo = await InfrahubRepository.init(
            id=repository.id, name=repo_name, client=client, default_branch_name=DEV_BRANCH
        )

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
        assert not repo_b.git.status("--porcelain")

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

        repo = await InfrahubRepository.init(id=node_id, name=repo_name, client=client, default_branch_name=DEV_BRANCH)
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

        Class-scoped: the filter stays active for every later test in this class. That is benign
        while later repos only carry main/develop remotely — a later test adding a remote feature/*
        branch would get silently filtered syncs. Keep new remote branches within the filter, or
        make this fixture function-scoped first.
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

    # -- Write-back robustness angles (beyond the happy path) ------------------------------------

    @pytest.mark.xfail(
        strict=True,
        reason="a write-back lost to a non-fast-forward push is not re-delivered by a later sync",
    )
    async def test_nonff_writeback_lost_permanently_after_resync(
        self,
        db: InfrahubDatabase,
        client: InfrahubClient,
        gogs_server: GogsServer,
    ) -> None:
        """After a non-ff write-back drop, a subsequent sync does not re-deliver the write-back.

        Probes whether the drop is transient (self-heals on the next sync) or permanent.
        """
        ds = await _register_and_import(client, gogs_server, "multi-env-perm-repo")
        repository: CoreRepository = await NodeManager.get_one(
            db=db, id=ds["node_id"], kind=InfrahubKind.REPOSITORY, raise_on_error=True
        )
        repo = await InfrahubRepository.init(
            id=repository.id, name=ds["repo_name"], client=client, default_branch_name=DEV_BRANCH
        )

        _push_commit_to_remote(gogs_server.container, ds["repo_name"], "out_of_band.txt", branch=DEV_BRANCH)
        writeback_commit = await _writeback_merge(repo, "feature-perm", "wb.txt")

        await sync_remote_repositories()

        remote_develop = _remote_branch_commit(gogs_server.container, ds["repo_name"], DEV_BRANCH)
        # Intended contract: the write-back eventually reaches the remote default branch.
        assert remote_develop == writeback_commit

    @pytest.mark.xfail(
        strict=True,
        reason="write-back drop records the commit before confirming the push, leaving the repo diverged and unable to converge on a later sync",
    )
    async def test_writeback_drop_then_sync_converges_to_remote(
        self,
        db: InfrahubDatabase,
        client: InfrahubClient,
        gogs_server: GogsServer,
    ) -> None:
        """After a write-back drop, a later sync should converge to the remote default tip.

        It does not: ``merge()`` records the commit (``update_commit_value``) *before* the push is
        confirmed, so a dropped push leaves the graph pointing at an un-pushed commit. The next sync
        sees local ahead of remote, the pull fails ("conflicts that must be resolved"), the branch is
        skipped, and the repo stays stuck at the local write-back commit — it never converges. (Pure
        divergence without a recorded-ahead commit does recover — see the divergence guard above.)
        """
        ds = await _register_and_import(client, gogs_server, "multi-env-converge-repo")
        repository: CoreRepository = await NodeManager.get_one(
            db=db, id=ds["node_id"], kind=InfrahubKind.REPOSITORY, raise_on_error=True
        )
        repo = await InfrahubRepository.init(
            id=repository.id, name=ds["repo_name"], client=client, default_branch_name=DEV_BRANCH
        )

        _push_commit_to_remote(gogs_server.container, ds["repo_name"], "out_of_band.txt", branch=DEV_BRANCH)
        await _writeback_merge(repo, "feature-converge", "wb.txt")
        remote_develop = _remote_branch_commit(gogs_server.container, ds["repo_name"], DEV_BRANCH)

        await sync_remote_repositories()

        repo_after: CoreRepository = await NodeManager.get_one(
            db=db, id=ds["node_id"], kind=InfrahubKind.REPOSITORY, raise_on_error=True
        )
        assert repo_after.commit.value == remote_develop

    @pytest.mark.xfail(
        strict=True,
        reason="repeated non-fast-forward write-backs are each silently dropped",
    )
    async def test_repeated_nonff_writebacks_each_dropped(
        self,
        db: InfrahubDatabase,
        client: InfrahubClient,
        gogs_server: GogsServer,
    ) -> None:
        """A second write-back, after another out-of-band advance, is also silently dropped."""
        ds = await _register_and_import(client, gogs_server, "multi-env-repeat-repo")
        repository: CoreRepository = await NodeManager.get_one(
            db=db, id=ds["node_id"], kind=InfrahubKind.REPOSITORY, raise_on_error=True
        )
        repo = await InfrahubRepository.init(
            id=repository.id, name=ds["repo_name"], client=client, default_branch_name=DEV_BRANCH
        )

        _push_commit_to_remote(gogs_server.container, ds["repo_name"], "oob1.txt", branch=DEV_BRANCH)
        await _writeback_merge(repo, "feature-r1", "wb1.txt")

        _push_commit_to_remote(gogs_server.container, ds["repo_name"], "oob2.txt", branch=DEV_BRANCH)
        writeback_commit = await _writeback_merge(repo, "feature-r2", "wb2.txt")

        remote_develop = _remote_branch_commit(gogs_server.container, ds["repo_name"], DEV_BRANCH)
        # Intended contract: the second write-back reaches the remote default branch.
        assert remote_develop == writeback_commit

    @pytest.fixture
    def explicit_merge_commit(self) -> Generator[None, None, None]:
        """Force write-back merges to create explicit merge commits (--no-ff)."""
        original = config.SETTINGS.git.use_explicit_merge_commit
        config.SETTINGS.git.use_explicit_merge_commit = True
        yield
        config.SETTINGS.git.use_explicit_merge_commit = original

    @pytest.mark.xfail(
        strict=True,
        reason="non-fast-forward write-back is dropped regardless of the explicit-merge-commit setting",
    )
    async def test_writeback_drop_independent_of_explicit_merge_commit(
        self,
        explicit_merge_commit: None,
        db: InfrahubDatabase,
        client: InfrahubClient,
        gogs_server: GogsServer,
    ) -> None:
        """The write-back drop is a push-layer failure — it happens with explicit merge commits too."""
        ds = await _register_and_import(client, gogs_server, "multi-env-mergecommit-repo")
        repository: CoreRepository = await NodeManager.get_one(
            db=db, id=ds["node_id"], kind=InfrahubKind.REPOSITORY, raise_on_error=True
        )
        repo = await InfrahubRepository.init(
            id=repository.id, name=ds["repo_name"], client=client, default_branch_name=DEV_BRANCH
        )

        _push_commit_to_remote(gogs_server.container, ds["repo_name"], "out_of_band.txt", branch=DEV_BRANCH)
        develop_before = _remote_branch_commit(gogs_server.container, ds["repo_name"], DEV_BRANCH)

        await _writeback_merge(repo, "feature-mc", "wb.txt")

        develop_after = _remote_branch_commit(gogs_server.container, ds["repo_name"], DEV_BRANCH)
        # Intended contract: the write-back reached the remote default branch.
        assert develop_after != develop_before

    @pytest.fixture
    def git_pull_rebase_config(self, tmp_path: Path) -> Generator[None, None, None]:
        """Point GIT_CONFIG_GLOBAL at a config that sets pull.rebase=true (an operator lever)."""
        cfg = tmp_path / "gitconfig"
        cfg.write_text(
            "[user]\n\tname = Infrahub\n\temail = infrahub@opsmill.com\n"
            "[safe]\n\tdirectory = *\n"
            "[pull]\n\trebase = true\n"
        )
        original = os.environ.get("GIT_CONFIG_GLOBAL")
        os.environ["GIT_CONFIG_GLOBAL"] = str(cfg)
        yield
        if original is None:
            os.environ.pop("GIT_CONFIG_GLOBAL", None)
        else:
            os.environ["GIT_CONFIG_GLOBAL"] = original

    @pytest.mark.xfail(
        strict=True,
        reason="pull.rebase=true does not rescue the write-back-drop stuck state; the graph still diverges from the remote",
    )
    async def test_pull_rebase_config_does_not_rescue_writeback_drop(
        self,
        git_pull_rebase_config: None,
        db: InfrahubDatabase,
        client: InfrahubClient,
        gogs_server: GogsServer,
    ) -> None:
        """Probe whether the GIT_CONFIG_GLOBAL pull.rebase lever mitigates the write-back-drop stuck state.

        Infrahub ships no pull reconciliation config, so divergent pulls fail outright. This checks
        whether an operator supplying pull.rebase=true (via INFRAHUB_GIT_GLOBAL_CONFIG_FILE) lets the
        post-drop divergence reconcile to the remote tip.
        """
        ds = await _register_and_import(client, gogs_server, "multi-env-rebase-repo")
        repository: CoreRepository = await NodeManager.get_one(
            db=db, id=ds["node_id"], kind=InfrahubKind.REPOSITORY, raise_on_error=True
        )
        repo = await InfrahubRepository.init(
            id=repository.id, name=ds["repo_name"], client=client, default_branch_name=DEV_BRANCH
        )

        _push_commit_to_remote(gogs_server.container, ds["repo_name"], "out_of_band.txt", branch=DEV_BRANCH)
        await _writeback_merge(repo, "feature-rebase", "wb.txt")
        remote_develop = _remote_branch_commit(gogs_server.container, ds["repo_name"], DEV_BRANCH)

        await sync_remote_repositories()

        repo_after: CoreRepository = await NodeManager.get_one(
            db=db, id=ds["node_id"], kind=InfrahubKind.REPOSITORY, raise_on_error=True
        )
        # Intended contract (with the lever): the branch reconciles and converges to the remote tip.
        assert repo_after.commit.value == remote_develop

    # -- Default-branch awareness of downstream flows ---------------------------------------------

    @pytest.mark.xfail(
        strict=True,
        reason=(
            "a repository initialized from its id and name alone does not learn its configured "
            "default branch, so branch resolution in downstream flows (artifacts, transforms, "
            "proposed-change checks, generators) falls back to the primary branch name"
        ),
    )
    async def test_initialized_repo_resolves_configured_default_branch(
        self,
        db: InfrahubDatabase,
        client: InfrahubClient,
        gogs_server: GogsServer,
    ) -> None:
        """A repository object built by the shared factory must know its configured default branch.

        Downstream flows build their repository object from just the id, name, and kind. For a repo
        whose git default branch is not the primary branch, that object must still resolve the
        configured default branch — otherwise every branch-name lookup in those flows targets the
        wrong branch (or a branch that does not exist locally).
        """
        ds = await _register_and_import(client, gogs_server, "multi-env-init-repo")

        repo = await get_initialized_repo.fn(
            client=client,
            repository_id=ds["node_id"],
            name=ds["repo_name"],
            repository_kind=InfrahubKind.REPOSITORY,
        )

        assert repo.default_branch == DEV_BRANCH
        # Intended: the default branch's local tip resolves (it backs the primary-branch worktree).
        assert repo.get_commit_value(branch_name=repo.default_branch, remote=False)

    @pytest.mark.xfail(
        strict=True,
        reason=(
            "a write-back push rejected by the remote (server-side hook or branch protection) is "
            "silently swallowed; the merge reports success while the remote default branch never "
            "receives the write-back"
        ),
    )
    async def test_writeback_rejected_by_remote_not_silently_dropped(
        self,
        db: InfrahubDatabase,
        client: InfrahubClient,
        tmp_path: Path,
    ) -> None:
        """A write-back rejected by the remote must land or fail loudly — not vanish.

        Real deployments protect long-lived branches (server-side hooks, required reviews). When the
        remote rejects the write-back push, the merge must not report success while the change never
        leaves the instance.
        """
        bare_path = _seed_local_bare_remote(tmp_path)
        repo_name = "multi-env-protected-repo"

        node = await client.create(
            kind=InfrahubKind.REPOSITORY,
            data={"name": repo_name, "location": str(bare_path), "default_branch": DEV_BRANCH},
        )
        await node.save()
        await sync_remote_repositories()

        repo = await InfrahubRepository.init(id=node.id, name=repo_name, client=client, default_branch_name=DEV_BRANCH)
        assert DEV_BRANCH in repo.get_branches_from_local(include_worktree=False)

        # The remote turns protected AFTER the import — the realistic sequence.
        _install_reject_all_pushes_hook(bare_path)
        develop_before = str(Repo(bare_path).commit(DEV_BRANCH))

        await _writeback_merge(repo, "feature-protected", "wb.txt")

        develop_after = str(Repo(bare_path).commit(DEV_BRANCH))
        # Intended contract: the write-back reached the remote default branch (or the merge failed).
        assert develop_after != develop_before

    async def test_writeback_succeeds_on_importer_clone(
        self,
        db: InfrahubDatabase,
        client: InfrahubClient,
        gogs_server: GogsServer,
    ) -> None:
        """The write-back lands when the clone holds the default branch and the remote has not moved.

        The working path that the single-worker deployment recommendation depends on: the importing
        clone (local default branch present, remote tip unchanged) merges a feature branch and the
        remote default branch advances to exactly the merged commit. Also guards, outside any
        expected-failure envelope, the imported-clone reconstruction the defect tests rely on.
        """
        ds = await _register_and_import(client, gogs_server, "multi-env-happy-repo")
        repository: CoreRepository = await NodeManager.get_one(
            db=db, id=ds["node_id"], kind=InfrahubKind.REPOSITORY, raise_on_error=True
        )
        repo = await InfrahubRepository.init(
            id=repository.id, name=ds["repo_name"], client=client, default_branch_name=DEV_BRANCH
        )
        assert DEV_BRANCH in repo.get_branches_from_local(include_worktree=False)

        merged_tip = await _writeback_merge(repo, "feature-happy", "wb.txt")

        assert _remote_branch_commit(gogs_server.container, ds["repo_name"], DEV_BRANCH) == merged_tip

    @pytest.fixture
    def no_sync_filter(self) -> Generator[None, None, None]:
        """Force an unset import-sync filter for this test, shadowing the class-scoped filter."""
        original = config.SETTINGS.git.import_sync_branch_names
        config.SETTINGS.git.import_sync_branch_names = []
        yield
        config.SETTINGS.git.import_sync_branch_names = original

    async def test_unset_filter_imports_every_branch(
        self,
        no_sync_filter: None,
        db: InfrahubDatabase,
        client: InfrahubClient,
        gogs_server: GogsServer,
    ) -> None:
        """With no import-sync filter configured, every remote branch is imported standalone.

        Documented-trap guard: an unset filter means "import every branch", not "only the default" —
        a consumer without a filter pulls all feature branches as standalone Infrahub branches.
        """
        repo_name = "multi-env-unset-filter-repo"
        repo_url = create_gogs_repo(gogs_server.base_url, gogs_server.token, repo_name, gogs_server.container)
        _create_remote_branch_from_main(gogs_server.container, repo_name, DEV_BRANCH)
        _create_remote_branch_from_main(gogs_server.container, repo_name, "feature/unfiltered")

        node = await client.create(
            kind=InfrahubKind.REPOSITORY,
            data={"name": repo_name, "location": repo_url, "default_branch": DEV_BRANCH},
        )
        await node.save()
        await sync_remote_repositories()

        branches = await client.branch.all()
        assert "feature/unfiltered" in branches
        # The configured default still maps onto the primary branch rather than importing standalone.
        assert DEV_BRANCH not in branches

    @pytest.mark.xfail(
        strict=True,
        reason=(
            "a standalone branch imported while default_branch was unset lingers permanently after "
            "default_branch is updated; no reconciliation removes the now-redundant branch"
        ),
    )
    async def test_default_branch_update_reconciles_phantom(
        self,
        no_sync_filter: None,
        db: InfrahubDatabase,
        client: InfrahubClient,
        gogs_server: GogsServer,
    ) -> None:
        """Setting default_branch after registration must not strand a duplicate standalone branch.

        Registering with default_branch unset imports the future default branch standalone; updating
        default_branch afterwards should reconcile — the standalone duplicate should map onto the
        primary branch and disappear. It lingers instead, which is why the pattern requires setting
        default_branch at creation time.
        """
        repo_name = "multi-env-late-default-repo"
        repo_url = create_gogs_repo(gogs_server.base_url, gogs_server.token, repo_name, gogs_server.container)
        _create_remote_branch_from_main(gogs_server.container, repo_name, "staging")

        node = await client.create(kind=InfrahubKind.REPOSITORY, data={"name": repo_name, "location": repo_url})
        await node.save()
        await sync_remote_repositories()
        assert "staging" in await client.branch.all()

        repo_node = await client.get(kind=InfrahubKind.REPOSITORY, id=node.id)
        repo_node.default_branch.value = "staging"
        await repo_node.save()
        await sync_remote_repositories()
        await sync_remote_repositories()

        # Intended contract: the standalone duplicate of the (new) default branch is reconciled away.
        assert "staging" not in await client.branch.all()

    async def test_conflicting_remote_branch_imports_without_blocking_others(
        self,
        no_sync_filter: None,
        db: InfrahubDatabase,
        client: InfrahubClient,
        gogs_server: GogsServer,
    ) -> None:
        """A remote branch whose content conflicts with the default branch still imports, warn-only.

        The sync runs a merge-tree conflict pre-check for every new remote branch against the default
        branch, but the result must only warn: branches never merge into each other during sync, so a
        conflicting branch is importable and the conflict materialises only when a merge is attempted.
        The conflicting branch must not prevent other branches from importing, and the repository's
        default-branch import must keep advancing.
        """
        ds = await _register_and_import(client, gogs_server, "multi-env-conflict-branch-repo")
        _push_conflicting_branch(gogs_server.container, ds["repo_name"], branch="feature/clashing", against=DEV_BRANCH)
        _create_remote_branch_from_main(gogs_server.container, ds["repo_name"], "feature/calm")

        await sync_remote_repositories()

        branches = await client.branch.all()
        # Warn-only contract: the conflicting branch is imported alongside the healthy one.
        assert "feature/clashing" in branches
        assert "feature/calm" in branches

        # The default-branch import is unaffected: a later commit still advances the recorded commit.
        _push_commit_to_remote(gogs_server.container, ds["repo_name"], "after_conflict.txt", branch=DEV_BRANCH)
        await sync_remote_repositories()
        repo_after: CoreRepository = await NodeManager.get_one(
            db=db, id=ds["node_id"], kind=InfrahubKind.REPOSITORY, raise_on_error=True
        )
        assert repo_after.commit.value == _remote_branch_commit(gogs_server.container, ds["repo_name"], DEV_BRANCH)
