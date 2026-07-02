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

from infrahub.core.constants import InfrahubKind
from infrahub.core.manager import NodeManager
from infrahub.git.repository import InfrahubRepository
from infrahub.git.tasks import sync_remote_repositories
from tests.helpers.test_app import TestInfrahubApp
from tests.integration.git.conftest import create_gogs_repo

if TYPE_CHECKING:
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
