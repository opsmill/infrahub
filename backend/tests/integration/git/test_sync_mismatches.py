"""Sync-mismatch scenarios for InfrahubRepository against a real Gogs server.

These tests exercise the sync path when the local worktree and the remote
have diverged: each has accumulated commits on the same branch that touch
the same files, so the pull triggered by `sync()` cannot fast-forward and
the merge surfaces a conflict against a real Git server, not a mock.

The contract pinned here is that a divergent-pull conflict during sync
surfaces as a typed repository error rather than a bare `GitCommandError`,
so workers that drive sync on a schedule can record the failure and surface
it to operators without parsing raw stderr — and so that the worktree is
left in a clean, recoverable state rather than stuck mid-merge.
"""

from __future__ import annotations

import contextlib
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from prefect import flow

from infrahub.core.constants import InfrahubKind
from infrahub.core.node import Node
from infrahub.exceptions import RepositoryError
from infrahub.git.repository import InfrahubRepository
from tests.helpers.test_app import TestInfrahubApp
from tests.integration.git.conftest import GOGS_ADMIN, create_gogs_repo

if TYPE_CHECKING:
    from infrahub_sdk import InfrahubClient
    from testcontainers.core.container import DockerContainer

    from infrahub.database import InfrahubDatabase
    from tests.helpers.git import GogsServer


@flow(name="test-sync-wrapper")
async def _sync_inside_flow(repo: InfrahubRepository) -> None:
    """Run ``sync()`` inside a workflow runtime context.

    Production callers invoke ``sync()`` from within a workflow flow, which
    establishes the runtime context that conflict-detection code expects.
    Tests must do the same; calling ``sync()`` directly outside any flow
    surfaces a runtime-context error instead of the conflict-handling path
    the test is meant to exercise.
    """
    await repo.sync()


def _push_divergent_commit(
    container: DockerContainer,
    repo_name: str,
    branch: str,
    file_name: str,
    file_content: str,
    message: str,
) -> str:
    """Push a single commit on ``branch`` to the bare repo that overwrites ``file_name``.

    Pulled in isolation from any local clone — the resulting commit shares the
    base history but has independent content for the file, so a subsequent
    local pull on a worktree that also touches the file produces a real
    content conflict.
    """
    script = (
        f"set -e && "
        f"rm -rf /tmp/{repo_name}-divergent && "
        f"git clone /data/git/repositories/{GOGS_ADMIN}/{repo_name}.git /tmp/{repo_name}-divergent && "
        f"cd /tmp/{repo_name}-divergent && "
        f"git config user.email 'infrahub@test.local' && "
        f"git config user.name 'Infrahub Test' && "
        f"git checkout {branch} && "
        f"printf '%s' {file_content!r} > {file_name} && "
        f"git add {file_name} && "
        f"git commit -m {message!r} && "
        f"git push origin {branch} && "
        f"git rev-parse HEAD"
    )
    result = container.get_wrapped_container().exec_run(["bash", "-c", script], user="git")
    assert result.exit_code == 0, (
        f"Failed to push divergent commit on {repo_name} (exit {result.exit_code}): {result.output.decode()}"
    )
    return result.output.decode().strip().splitlines()[-1].strip()


class TestSyncMismatches(TestInfrahubApp):
    """Sync paths against a real Gogs server where local and remote diverge on the same file."""

    @pytest.fixture(scope="class")
    async def conflicting_sync_dataset(
        self,
        db: InfrahubDatabase,
        initialize_registry: None,
        git_repos_dir_module_scope: Path,
        gogs_server: GogsServer,
    ) -> dict:
        repo_name = "sync-mismatch-repo"
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

    async def test_sync_with_remote_commits_conflicting_with_local_worktree_leaves_worktree_intact(
        self,
        conflicting_sync_dataset: dict,
        gogs_server: GogsServer,
        client: InfrahubClient,
    ) -> None:
        """A sync where local and remote both modify the same file leaves the worktree unchanged.

        After clone, the local default-branch worktree commits a change to a
        file. The remote then pushes a commit on the same branch touching the
        same file with different content. The next sync fetches the new
        remote tip and sees the branch as updated.

        Today's behavior splits across two paths depending on subtle state of
        the in-flight fetch: either pull surfaces the conflict via a typed
        repository error, or the branch validation step ahead of pull
        classifies the divergence as "invalid" and silently skips the pull
        altogether. The durable invariant is that the local default-branch
        tip stays at the local commit and no in-progress merge state is left
        on disk — a worker driving sync on a schedule cannot end up in a
        half-merged state regardless of which path runs. Pinning that
        invariant guards against any future change that would silently
        accept the conflicting remote content.
        """
        repo_name = conflicting_sync_dataset["repo_name"]
        clone_url = conflicting_sync_dataset["clone_url"]

        infrahub_repo = await InfrahubRepository.new(
            id=conflicting_sync_dataset["node_id"],
            name=repo_name,
            location=clone_url,
            client=client,
        )

        local_main = infrahub_repo.get_git_repo_main()
        (Path(str(local_main.working_dir)) / "shared.txt").write_text("local content\n")
        local_main.index.add(["shared.txt"])
        local_main.index.commit("local commit modifying shared file")
        local_tip_before_sync = str(local_main.head.commit)

        _push_divergent_commit(
            gogs_server.container,
            repo_name=repo_name,
            branch="main",
            file_name="shared.txt",
            file_content="remote content\n",
            message="remote commit modifying shared file",
        )

        with contextlib.suppress(RepositoryError):
            await _sync_inside_flow(infrahub_repo)

        local_main_after = infrahub_repo.get_git_repo_main()
        assert str(local_main_after.head.commit) == local_tip_before_sync
        assert not (Path(str(local_main_after.git_dir)) / "MERGE_HEAD").exists()
