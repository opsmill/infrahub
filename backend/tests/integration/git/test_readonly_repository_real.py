"""Read-only repository scenarios against a real Gogs server.

These tests exercise the read-only repository's interaction with a real remote
across three concerns: branch churn picked up by a fetch with prune, tag-based
ref checkout in three states (present, absent, deleted after sync), and the
update path against a force-pushed remote whose previously-known commit is no
longer reachable through any remote ref.

Read-only repositories pin a single `ref` and rely on the standard fetch with
prune to keep their view of the remote consistent. The contracts pinned here
are: (a) new remote branches become visible after the next update and deleted
remote branches stop being visible — this is what makes `sync_with_git` on
read-only repos observable rather than a black box; (b) checkout against a
tag uses the same path as a branch ref, but a missing tag must fail loudly so
operators do not unknowingly track an empty ref; (c) when a remote rewrites
history with a force-push, the local repository recovers to the new tip
rather than wedging on the now-unreachable commit.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from infrahub.core.constants import InfrahubKind
from infrahub.core.node import Node
from infrahub.exceptions import RepositoryError
from infrahub.git.repository import InfrahubReadOnlyRepository
from tests.helpers.test_app import TestInfrahubApp
from tests.integration.git.conftest import GOGS_ADMIN, create_gogs_repo

if TYPE_CHECKING:
    from pathlib import Path

    from infrahub_sdk import InfrahubClient
    from testcontainers.core.container import DockerContainer

    from infrahub.database import InfrahubDatabase
    from tests.helpers.git import GogsServer


def _push_remote_branch(container: DockerContainer, repo_name: str, branch_name: str) -> None:
    """Push a new branch with one commit to the bare repo, bypassing Infrahub."""
    script = (
        f"set -e && "
        f"rm -rf /tmp/{repo_name}-newbranch && "
        f"git clone /data/git/repositories/{GOGS_ADMIN}/{repo_name}.git /tmp/{repo_name}-newbranch && "
        f"cd /tmp/{repo_name}-newbranch && "
        f"git config user.email 'infrahub@test.local' && "
        f"git config user.name 'Infrahub Test' && "
        f"git checkout main && "
        f"git checkout -b {branch_name} && "
        f"printf 'branch %s content\\n' {branch_name!r} > {branch_name}.txt && "
        f"git add {branch_name}.txt && "
        f"git commit -m 'Add file on {branch_name}' && "
        f"git push origin {branch_name}"
    )
    result = container.get_wrapped_container().exec_run(["bash", "-c", script], user="git")
    assert result.exit_code == 0, (
        f"Failed to push branch {branch_name} on {repo_name} (exit {result.exit_code}): {result.output.decode()}"
    )


def _delete_remote_branch(container: DockerContainer, repo_name: str, branch_name: str) -> None:
    script = f"set -e && cd /tmp/{repo_name}-newbranch && git push origin --delete {branch_name}"
    result = container.get_wrapped_container().exec_run(["bash", "-c", script], user="git")
    assert result.exit_code == 0, (
        f"Failed to delete remote branch {branch_name} on {repo_name} "
        f"(exit {result.exit_code}): {result.output.decode()}"
    )


def _push_remote_tag(container: DockerContainer, repo_name: str, tag_name: str, ref: str = "main") -> str:
    """Tag the current tip of ``ref`` on the bare repo and push it. Returns the tagged SHA."""
    script = (
        f"set -e && "
        f"rm -rf /tmp/{repo_name}-tag-{tag_name} && "
        f"git clone /data/git/repositories/{GOGS_ADMIN}/{repo_name}.git /tmp/{repo_name}-tag-{tag_name} && "
        f"cd /tmp/{repo_name}-tag-{tag_name} && "
        f"git config user.email 'infrahub@test.local' && "
        f"git config user.name 'Infrahub Test' && "
        f"git tag {tag_name} origin/{ref} && "
        f"git push origin {tag_name} && "
        f"git rev-parse refs/tags/{tag_name}^{{commit}}"
    )
    result = container.get_wrapped_container().exec_run(["bash", "-c", script], user="git")
    assert result.exit_code == 0, (
        f"Failed to push tag {tag_name} on {repo_name} (exit {result.exit_code}): {result.output.decode()}"
    )
    return result.output.decode().strip().splitlines()[-1].strip()


def _delete_remote_tag(container: DockerContainer, repo_name: str, tag_name: str) -> None:
    script = f"set -e && cd /tmp/{repo_name}-tag-{tag_name} && git push origin :refs/tags/{tag_name}"
    result = container.get_wrapped_container().exec_run(["bash", "-c", script], user="git")
    assert result.exit_code == 0, (
        f"Failed to delete remote tag {tag_name} on {repo_name} (exit {result.exit_code}): {result.output.decode()}"
    )


def _force_push_orphan_history(container: DockerContainer, repo_name: str, branch: str = "main") -> str:
    """Replace ``branch`` on the bare repo with an unrelated single-commit history.

    The previously-known tip becomes unreachable from any remote ref. Returns
    the new tip SHA so callers can assert recovery to it.
    """
    script = (
        f"set -e && "
        f"rm -rf /tmp/{repo_name}-orphan && "
        f"git clone /data/git/repositories/{GOGS_ADMIN}/{repo_name}.git /tmp/{repo_name}-orphan && "
        f"cd /tmp/{repo_name}-orphan && "
        f"git config user.email 'infrahub@test.local' && "
        f"git config user.name 'Infrahub Test' && "
        f"git checkout --orphan rewritten-history && "
        f"git rm -rf . && "
        f"printf -- '---\\n' > .infrahub.yml && "
        f"printf 'rewritten history\\n' > orphan.txt && "
        f"git add .infrahub.yml orphan.txt && "
        f"git commit -m 'Orphan commit replacing prior history' && "
        f"git push origin rewritten-history:{branch} --force && "
        f"git rev-parse HEAD"
    )
    result = container.get_wrapped_container().exec_run(["bash", "-c", script], user="git")
    assert result.exit_code == 0, (
        f"Failed to force-push orphan history on {repo_name} (exit {result.exit_code}): {result.output.decode()}"
    )
    return result.output.decode().strip().splitlines()[-1].strip()


async def _create_readonly_node(db: InfrahubDatabase, name: str, location: str, ref: str) -> str:
    """Create a CoreReadOnlyRepository node directly in the DB and return its id."""
    obj = await Node.init(schema=InfrahubKind.READONLYREPOSITORY, db=db)
    await obj.new(db=db, name=name, location=location, ref=ref)
    await obj.save(db=db)
    return obj.id


class TestReadOnlyRepositoryReal(TestInfrahubApp):
    """Read-only repository paths against a real Gogs server."""

    @pytest.fixture(scope="class")
    async def branch_churn_dataset(
        self,
        db: InfrahubDatabase,
        initialize_registry: None,
        git_repos_dir_module_scope: Path,
        gogs_server: GogsServer,
    ) -> dict:
        repo_name = "ro-branch-churn-repo"
        clone_url = create_gogs_repo(
            gogs_server.base_url,
            gogs_server.token,
            repo_name,
            gogs_server.container,
        )
        node_id = await _create_readonly_node(db=db, name=repo_name, location=clone_url, ref="main")
        return {"repo_name": repo_name, "clone_url": clone_url, "node_id": node_id}

    @pytest.fixture(scope="class")
    async def tag_present_dataset(
        self,
        db: InfrahubDatabase,
        initialize_registry: None,
        git_repos_dir_module_scope: Path,
        gogs_server: GogsServer,
    ) -> dict:
        repo_name = "ro-tag-present-repo"
        clone_url = create_gogs_repo(
            gogs_server.base_url,
            gogs_server.token,
            repo_name,
            gogs_server.container,
        )
        tag_sha = _push_remote_tag(gogs_server.container, repo_name, "v1.0.0")
        node_id = await _create_readonly_node(db=db, name=repo_name, location=clone_url, ref="v1.0.0")
        return {"repo_name": repo_name, "clone_url": clone_url, "tag_sha": tag_sha, "node_id": node_id}

    @pytest.fixture(scope="class")
    async def tag_missing_dataset(
        self,
        db: InfrahubDatabase,
        initialize_registry: None,
        git_repos_dir_module_scope: Path,
        gogs_server: GogsServer,
    ) -> dict:
        repo_name = "ro-tag-missing-repo"
        clone_url = create_gogs_repo(
            gogs_server.base_url,
            gogs_server.token,
            repo_name,
            gogs_server.container,
        )
        node_id = await _create_readonly_node(db=db, name=repo_name, location=clone_url, ref="nonexistent-tag")
        return {"repo_name": repo_name, "clone_url": clone_url, "node_id": node_id}

    @pytest.fixture(scope="class")
    async def tag_deleted_dataset(
        self,
        db: InfrahubDatabase,
        initialize_registry: None,
        git_repos_dir_module_scope: Path,
        gogs_server: GogsServer,
    ) -> dict:
        repo_name = "ro-tag-deleted-repo"
        clone_url = create_gogs_repo(
            gogs_server.base_url,
            gogs_server.token,
            repo_name,
            gogs_server.container,
        )
        _push_remote_tag(gogs_server.container, repo_name, "v0.9.0")
        node_id = await _create_readonly_node(db=db, name=repo_name, location=clone_url, ref="v0.9.0")
        return {"repo_name": repo_name, "clone_url": clone_url, "node_id": node_id}

    @pytest.fixture(scope="class")
    async def force_push_dataset(
        self,
        db: InfrahubDatabase,
        initialize_registry: None,
        git_repos_dir_module_scope: Path,
        gogs_server: GogsServer,
    ) -> dict:
        repo_name = "ro-force-push-repo"
        clone_url = create_gogs_repo(
            gogs_server.base_url,
            gogs_server.token,
            repo_name,
            gogs_server.container,
        )
        node_id = await _create_readonly_node(db=db, name=repo_name, location=clone_url, ref="main")
        return {"repo_name": repo_name, "clone_url": clone_url, "node_id": node_id}

    async def test_update_latest_commit_surfaces_new_remote_branch(
        self,
        branch_churn_dataset: dict,
        gogs_server: GogsServer,
        client: InfrahubClient,
    ) -> None:
        """A branch added on the remote appears in the local remote-tracking refs after update.

        After the read-only repo is initialized, a new branch is pushed on the
        remote bypassing Infrahub. The next update fetches with prune; the new
        branch must show up in the local `origin/*` ref set. This pins that
        operators can observe newly-created remote branches without restarting
        the worker or recloning the repository.
        """
        repo_name = branch_churn_dataset["repo_name"]
        clone_url = branch_churn_dataset["clone_url"]

        infrahub_repo = await InfrahubReadOnlyRepository.new(
            id=branch_churn_dataset["node_id"],
            name=repo_name,
            location=clone_url,
            client=client,
            ref="main",
            infrahub_branch_name="main",
        )

        git_repo = infrahub_repo.get_git_repo_main()
        remote_refs_before = {ref.name for ref in git_repo.remotes.origin.refs}
        assert "origin/feature-added" not in remote_refs_before

        _push_remote_branch(gogs_server.container, repo_name, "feature-added")

        await infrahub_repo.update_latest_commit()

        remote_refs_after = {ref.name for ref in git_repo.remotes.origin.refs}
        assert "origin/feature-added" in remote_refs_after

    async def test_update_latest_commit_prunes_deleted_remote_branch(
        self,
        branch_churn_dataset: dict,
        gogs_server: GogsServer,
        client: InfrahubClient,
    ) -> None:
        """A branch deleted on the remote disappears from the local remote-tracking refs after update.

        Building on the previous test's branch, the branch is deleted on the
        remote. The next update fetches with prune; the branch must be removed
        from the local `origin/*` ref set. Without prune behavior, deleted
        remote branches would persist in the local view indefinitely and
        confuse the next sync's "what changed remotely" computation.
        """
        repo_name = branch_churn_dataset["repo_name"]
        clone_url = branch_churn_dataset["clone_url"]

        infrahub_repo = await InfrahubReadOnlyRepository.init(
            id=branch_churn_dataset["node_id"],
            name=repo_name,
            location=clone_url,
            client=client,
            ref="main",
            infrahub_branch_name="main",
        )

        git_repo = infrahub_repo.get_git_repo_main()
        git_repo.remotes.origin.fetch(prune=True)
        assert "origin/feature-added" in {ref.name for ref in git_repo.remotes.origin.refs}

        _delete_remote_branch(gogs_server.container, repo_name, "feature-added")

        await infrahub_repo.update_latest_commit()

        remote_refs_after = {ref.name for ref in git_repo.remotes.origin.refs}
        assert "origin/feature-added" not in remote_refs_after

    async def test_readonly_clone_with_existing_tag_succeeds(
        self,
        tag_present_dataset: dict,
        client: InfrahubClient,
    ) -> None:
        """Cloning a read-only repository pinned to an existing tag checks out the tagged commit.

        Tags resolve through the same checkout path as branches. A
        successfully-cloned read-only repo pinned to a tag must land its
        worktree on the tag's commit, not on the default branch. Without this
        guarantee, consumers tracking a release tag would silently fetch
        whatever happens to be on `main`.
        """
        repo_name = tag_present_dataset["repo_name"]
        clone_url = tag_present_dataset["clone_url"]
        tag_sha = tag_present_dataset["tag_sha"]

        infrahub_repo = await InfrahubReadOnlyRepository.new(
            id=tag_present_dataset["node_id"],
            name=repo_name,
            location=clone_url,
            client=client,
            ref="v1.0.0",
            infrahub_branch_name="main",
        )

        git_repo = infrahub_repo.get_git_repo_main()
        assert str(git_repo.head.commit) == tag_sha

    async def test_readonly_clone_with_missing_tag_raises_typed_error(
        self,
        tag_missing_dataset: dict,
        client: InfrahubClient,
    ) -> None:
        """Cloning a read-only repository pinned to a non-existent tag raises a typed repository error.

        When the configured ref does not exist on the remote, the clone step
        succeeds but the subsequent checkout fails. The failure must surface
        as a typed repository error so consumers can distinguish a missing-ref
        condition from a generic Git failure, rather than parsing raw stderr.
        """
        repo_name = tag_missing_dataset["repo_name"]
        clone_url = tag_missing_dataset["clone_url"]

        with pytest.raises(RepositoryError, match=r"isn't a valid branch|not found"):
            await InfrahubReadOnlyRepository.new(
                id=tag_missing_dataset["node_id"],
                name=repo_name,
                location=clone_url,
                client=client,
                ref="nonexistent-tag",
                infrahub_branch_name="main",
            )

    async def test_update_latest_commit_surfaces_deleted_tag(
        self,
        tag_deleted_dataset: dict,
        gogs_server: GogsServer,
        client: InfrahubClient,
    ) -> None:
        """A tag deleted on the remote causes the next update to raise the typed missing-ref error.

        A read-only repo pinned to a tag stays valid as long as the tag exists.
        When the tag is removed on the remote, the next update fetches with
        prune_tags and the tag is no longer resolvable through any ref name —
        the update must fail loudly with `ValueError("Ref ... not found.")`
        instead of silently keeping the now-stale local checkout. This is
        what allows operators to detect when a tracked release has been
        retracted upstream.
        """
        repo_name = tag_deleted_dataset["repo_name"]
        clone_url = tag_deleted_dataset["clone_url"]

        infrahub_repo = await InfrahubReadOnlyRepository.new(
            id=tag_deleted_dataset["node_id"],
            name=repo_name,
            location=clone_url,
            client=client,
            ref="v0.9.0",
            infrahub_branch_name="main",
        )

        _delete_remote_tag(gogs_server.container, repo_name, "v0.9.0")

        with pytest.raises(ValueError, match=r"Ref v0\.9\.0 not found\."):
            await infrahub_repo.update_latest_commit()

    async def test_update_latest_commit_recovers_from_force_pushed_history(
        self,
        force_push_dataset: dict,
        gogs_server: GogsServer,
        client: InfrahubClient,
    ) -> None:
        """An orphan force-push that replaces the entire branch history is recovered to the new tip.

        After a destructive remote rewrite where the previously-known commit is
        unreachable from any remote ref, the next update fetches with prune,
        resolves the new tip through `origin/<ref>`, and writes the resulting
        commit value back. The recovery path must not depend on the prior tip
        being reachable, otherwise any operator-driven history rewrite would
        wedge the read-only repo until manually recloned.
        """
        repo_name = force_push_dataset["repo_name"]
        clone_url = force_push_dataset["clone_url"]

        infrahub_repo = await InfrahubReadOnlyRepository.new(
            id=force_push_dataset["node_id"],
            name=repo_name,
            location=clone_url,
            client=client,
            ref="main",
            infrahub_branch_name="main",
        )

        git_repo = infrahub_repo.get_git_repo_main()
        commit_before_force_push = str(git_repo.head.commit)

        new_tip_sha = _force_push_orphan_history(gogs_server.container, repo_name, branch="main")
        assert new_tip_sha != commit_before_force_push

        await infrahub_repo.update_latest_commit()

        git_repo.remotes.origin.fetch(prune=True)
        assert str(git_repo.commit("origin/main")) == new_tip_sha
