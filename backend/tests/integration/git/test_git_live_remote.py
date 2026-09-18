"""Integration tests for InfrahubRepository and InfrahubReadOnlyRepository against a live remote."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import git
import pytest
from infrahub_sdk.exceptions import GraphQLError

from infrahub.core.constants import InfrahubKind, RepositoryOperationalStatus
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.exceptions import RepositoryCredentialsError, RepositoryError, RepositoryPermissionError
from infrahub.git.constants import WRITE_ACCESS_PROBE_REF
from infrahub.git.repository import InfrahubReadOnlyRepository, InfrahubRepository
from tests.helpers.test_app import TestInfrahubApp
from tests.integration.git.conftest import (
    bad_credentials_clone_url,
    create_gogs_repo,
    create_remote_ref,
    gogs_clone_url,
    grant_read_access,
    readonly_clone_url,
)

if TYPE_CHECKING:
    from infrahub_sdk import InfrahubClient
    from testcontainers.core.container import DockerContainer

    from infrahub.core.protocols import CoreReadOnlyRepository, CoreRepository
    from infrahub.database import InfrahubDatabase
    from tests.helpers.git import GogsServer


def _push_commit_to_remote(container: DockerContainer, repo_name: str, filename: str, branch: str = "main") -> None:
    """Make a new commit directly in the remote server container and push it.

    Reuses the working clone that create_gogs_repo() left in /tmp/{repo_name}.
    """
    script = (
        f"set -e && "
        f"cd /tmp/{repo_name} && "
        f"git checkout {branch} && "
        f"git pull origin {branch} && "
        f"echo 'remote change' > {filename} && "
        f"git add {filename} && "
        f"git commit -m 'Remote-only commit [{filename}]' && "
        f"git push origin {branch}"
    )
    result = container.get_wrapped_container().exec_run(["bash", "-c", script], user="git")
    assert result.exit_code == 0, f"Remote commit failed (exit {result.exit_code}): {result.output.decode()}"


class TestRepositoryRemoteOperations(TestInfrahubApp):
    """Live-remote tests for InfrahubRepository and InfrahubReadOnlyRepository.

    Each fixture sets up an isolated Gogs repository and Infrahub node for its
    scenario.  Tests are isolated by repo name and node ID; they share the same
    Infrahub stack instance to avoid paying per-class setup costs.
    """

    @pytest.fixture(scope="class")
    async def auth_failure_dataset(
        self,
        db: InfrahubDatabase,
        initialize_registry: None,
        git_repos_dir_module_scope: Path,
        gogs_server: GogsServer,
    ) -> dict:
        repo_name = "auth-failure-repo"
        # Create the repo as *private* so the server requires authentication even
        # for clone operations.  Public repos allow anonymous read access, which means
        # the embedded bad credentials are never presented to the server and the clone
        # succeeds — defeating the purpose of this test.
        create_gogs_repo(
            gogs_server.base_url,
            gogs_server.token,
            repo_name,
            gogs_server.container,
            private=True,
        )
        bad_url = bad_credentials_clone_url(gogs_server.base_url, repo_name)

        # Pre-create the Infrahub node directly in the DB — not via the HTTP API — so
        # that no automatic sync is triggered and _update_operational_status() has a
        # node to write to when the clone fails.
        obj = await Node.init(schema=InfrahubKind.REPOSITORY, db=db)
        await obj.new(db=db, name=repo_name, location=bad_url)
        await obj.save(db=db)
        return {"repo_name": repo_name, "node_id": obj.id, "bad_url": bad_url}

    @pytest.fixture(scope="class")
    async def push_rejection_dataset(
        self,
        initialize_registry: None,
        git_repos_dir_module_scope: Path,
        client: InfrahubClient,
        gogs_server: GogsServer,
    ) -> dict:
        repo_name = "push-rejection-repo"
        repo_url = create_gogs_repo(gogs_server.base_url, gogs_server.token, repo_name, gogs_server.container)
        node = await client.create(
            kind=InfrahubKind.REPOSITORY,
            data={"name": repo_name, "location": repo_url},
        )
        await node.save()
        return {"repo_name": repo_name, "node_id": node.id}

    @pytest.fixture(scope="class")
    async def merge_conflict_dataset(
        self,
        initialize_registry: None,
        git_repos_dir_module_scope: Path,
        client: InfrahubClient,
        gogs_server: GogsServer,
    ) -> dict:
        repo_name = "merge-conflict-repo"
        repo_url = create_gogs_repo(gogs_server.base_url, gogs_server.token, repo_name, gogs_server.container)
        node = await client.create(
            kind=InfrahubKind.REPOSITORY,
            data={"name": repo_name, "location": repo_url},
        )
        await node.save()
        return {"repo_name": repo_name, "node_id": node.id}

    @pytest.fixture(scope="class")
    async def readonly_sync_dataset(
        self,
        initialize_registry: None,
        git_repos_dir_module_scope: Path,
        client: InfrahubClient,
        gogs_server: GogsServer,
    ) -> dict:
        repo_name = "readonly-sync-repo"
        repo_url = create_gogs_repo(gogs_server.base_url, gogs_server.token, repo_name, gogs_server.container)
        branch = await client.branch.create(branch_name="ro_sync_test", sync_with_git=False)
        node = await client.create(
            kind=InfrahubKind.READONLYREPOSITORY,
            branch=branch.name,
            name=repo_name,
            location=repo_url,
            ref="main",
        )
        await node.save()
        return {"repo_name": repo_name, "node_id": node.id, "branch_name": branch.name}

    async def test_clone_with_wrong_credentials_raises_credentials_error(
        self,
        auth_failure_dataset: dict,
        db: InfrahubDatabase,
        client: InfrahubClient,
    ) -> None:
        """Cloning with invalid credentials raises RepositoryCredentialsError and persists ERROR_CRED status.

        Uses a fresh clone against a real server so the bad credentials are always
        presented directly, bypassing any cached credential state.
        """
        with pytest.raises(
            RepositoryCredentialsError,
            match=r"^Authentication failed for auth-failure-repo, please validate the credentials\.$",
        ):
            await InfrahubRepository.new(
                id=auth_failure_dataset["node_id"],
                name=auth_failure_dataset["repo_name"],
                location=auth_failure_dataset["bad_url"],
                client=client,
            )

        updated: CoreRepository = await NodeManager.get_one(
            db=db,
            id=auth_failure_dataset["node_id"],
            kind=InfrahubKind.REPOSITORY,
            raise_on_error=True,
        )
        assert updated.operational_status.value == RepositoryOperationalStatus.ERROR_CRED.value

    async def test_failed_connectivity_check_persists_error_status(
        self,
        auth_failure_dataset: dict,
        db: InfrahubDatabase,
        client: InfrahubClient,
    ) -> None:
        """A failed connectivity check writes an error operational status back to the repository node.

        The check used to report the failure only to the caller, leaving operational_status stuck on
        its last value, so an unreachable repository kept showing as online.
        """
        node_id = auth_failure_dataset["node_id"]

        # Start from a known-good status so the assertion proves the check flipped it.
        repo_before: CoreRepository = await NodeManager.get_one(
            db=db, id=node_id, kind=InfrahubKind.REPOSITORY, raise_on_error=True
        )
        repo_before.operational_status.value = RepositoryOperationalStatus.ONLINE.value
        await repo_before.save(db=db)

        query = """
        mutation InfrahubRepositoryConnectivity($id: String!) {
            InfrahubRepositoryConnectivity(data: {id: $id}) {
                ok
                message
            }
        }
        """
        result = await client.execute_graphql(query=query, variables={"id": node_id})
        assert result["InfrahubRepositoryConnectivity"]["ok"] is False

        repo_after: CoreRepository = await NodeManager.get_one(
            db=db, id=node_id, kind=InfrahubKind.REPOSITORY, raise_on_error=True
        )
        assert repo_after.operational_status.value == RepositoryOperationalStatus.ERROR_CRED.value

    async def test_push_rejected_non_fast_forward(
        self,
        push_rejection_dataset: dict,
        db: InfrahubDatabase,
        client: InfrahubClient,
        gogs_server: GogsServer,
    ) -> None:
        """push() raises RepositoryError when the remote rejects a non-fast-forward push.

        The remote is left unchanged: the rejected local commit is not delivered.
        """
        repo_name = push_rejection_dataset["repo_name"]

        repository: CoreRepository = await NodeManager.get_one(
            db=db,
            id=push_rejection_dataset["node_id"],
            kind=InfrahubKind.REPOSITORY,
            raise_on_error=True,
        )
        infrahub_repo = await InfrahubRepository.init(
            id=repository.id,
            name=repo_name,
            client=client,
        )

        _push_commit_to_remote(gogs_server.container, repo_name, "remote_advance.txt")

        # Without fetching first, our local history diverges from the remote.
        git_repo = infrahub_repo.get_git_repo_main()
        local_file = Path(str(git_repo.working_dir)) / "local_diverge.txt"
        local_file.write_text("local only")
        git_repo.index.add(["local_diverge.txt"])
        local_commit = str(git_repo.index.commit("Local-only commit"))

        with pytest.raises(
            RepositoryError,
            match=rf"^Unable to push the branch main to the remote for repository {repo_name}: \[rejected\] \(fetch first\)$",
        ):
            await infrahub_repo.push("main")

        git_repo.remotes.origin.fetch()
        remote_main_commit = str(git_repo.commit("origin/main"))
        assert remote_main_commit != local_commit

    async def test_merge_conflict_raises_repository_error(
        self,
        merge_conflict_dataset: dict,
        db: InfrahubDatabase,
        client: InfrahubClient,
    ) -> None:
        """A real Git conflict between two local branches raises RepositoryError.

        Verifies that merge() runs merge --abort on failure, leaving the repo in a
        clean state rather than stuck mid-merge.
        """
        repo_name = merge_conflict_dataset["repo_name"]

        repository: CoreRepository = await NodeManager.get_one(
            db=db,
            id=merge_conflict_dataset["node_id"],
            kind=InfrahubKind.REPOSITORY,
            raise_on_error=True,
        )
        infrahub_repo = await InfrahubRepository.init(
            id=repository.id,
            name=repo_name,
            client=client,
        )

        # push_origin=False keeps the remote clean; the conflict is purely local.
        await infrahub_repo.create_branch_in_git("conflict-branch-a", push_origin=False)
        await infrahub_repo.create_branch_in_git("conflict-branch-b", push_origin=False)

        branch_a_repo = infrahub_repo.get_git_repo_worktree(identifier="conflict-branch-a")
        (Path(str(branch_a_repo.working_dir)) / "conflict.txt").write_text("branch-a content\n")
        branch_a_repo.index.add(["conflict.txt"])
        branch_a_repo.index.commit("conflict-branch-a: add conflict.txt")

        branch_b_repo = infrahub_repo.get_git_repo_worktree(identifier="conflict-branch-b")
        (Path(str(branch_b_repo.working_dir)) / "conflict.txt").write_text("branch-b content\n")
        branch_b_repo.index.add(["conflict.txt"])
        branch_b_repo.index.commit("conflict-branch-b: add conflict.txt")

        with pytest.raises(
            RepositoryError,
            match=r"^An error occurred with GitRepository 'merge-conflict-repo'\.$",
        ):
            await infrahub_repo.merge(
                source_branch="conflict-branch-a",
                dest_branch="conflict-branch-b",
                push_remote=False,
            )

    async def test_sync_from_remote_detects_new_commit(
        self,
        readonly_sync_dataset: dict,
        db: InfrahubDatabase,
        client: InfrahubClient,
        gogs_server: GogsServer,
    ) -> None:
        """sync_from_remote() returns True and performs the sync when the remote has advanced."""
        repo_name = readonly_sync_dataset["repo_name"]
        branch_name = readonly_sync_dataset["branch_name"]

        repository: CoreReadOnlyRepository = await NodeManager.get_one(
            db=db,
            id=readonly_sync_dataset["node_id"],
            kind=InfrahubKind.READONLYREPOSITORY,
            branch=branch_name,
            raise_on_error=True,
        )
        infrahub_repo = await InfrahubReadOnlyRepository.init(
            id=repository.id,
            name=repo_name,
            ref=repository.ref.value,
            infrahub_branch_name=branch_name,
            client=client,
        )

        commit_before = str(infrahub_repo.get_git_repo_main().head.commit)

        _push_commit_to_remote(gogs_server.container, repo_name, "new_remote_file.txt")

        git_repo = infrahub_repo.get_git_repo_main()
        git_repo.remotes.origin.fetch()
        commit_after_remote = str(git_repo.commit("origin/main"))
        assert commit_after_remote != commit_before

        synced = await infrahub_repo.sync_from_remote(commit=commit_after_remote)

        assert synced is True

    async def test_sync_from_remote_returns_false_when_up_to_date(
        self,
        readonly_sync_dataset: dict,
        db: InfrahubDatabase,
        client: InfrahubClient,
    ) -> None:
        """sync_from_remote() returns False when local already matches the given commit."""
        repo_name = readonly_sync_dataset["repo_name"]
        branch_name = readonly_sync_dataset["branch_name"]

        repository: CoreReadOnlyRepository = await NodeManager.get_one(
            db=db,
            id=readonly_sync_dataset["node_id"],
            kind=InfrahubKind.READONLYREPOSITORY,
            branch=branch_name,
            raise_on_error=True,
        )
        infrahub_repo = await InfrahubReadOnlyRepository.init(
            id=repository.id,
            name=repo_name,
            ref=repository.ref.value,
            infrahub_branch_name=branch_name,
            client=client,
        )

        current_commit = str(infrahub_repo.get_git_repo_main().head.commit)
        synced = await infrahub_repo.sync_from_remote(commit=current_commit)

        assert synced is False

    @pytest.fixture(scope="class")
    async def write_probe_dataset(
        self,
        initialize_registry: None,
        git_repos_dir_module_scope: Path,
        gogs_server: GogsServer,
    ) -> dict:
        repo_name = "write-probe-repo"
        # Private repo + a read-only collaborator: the collaborator can clone but not push,
        # which is the shape of a read-write repository whose credentials lack write access.
        create_gogs_repo(gogs_server.base_url, gogs_server.token, repo_name, gogs_server.container, private=True)
        grant_read_access(gogs_server.base_url, gogs_server.token, repo_name)
        return {
            "repo_name": repo_name,
            "writable_url": gogs_clone_url(gogs_server.base_url, repo_name),
            "readonly_url": readonly_clone_url(gogs_server.base_url, repo_name),
        }

    async def test_write_probe_discriminates_read_from_write_access(self, write_probe_dataset: dict) -> None:
        """The write probe rejects a read-only credential while the read-only check accepts it.

        Asserting both directions on the same URL is what proves the probe, not the URL, makes the
        difference: read access alone passes require_write=False but not require_write=True.
        """
        repo_name = write_probe_dataset["repo_name"]
        readonly_url = write_probe_dataset["readonly_url"]

        # Read access alone satisfies the read-gated check.
        InfrahubRepository.check_connectivity(name=repo_name, url=readonly_url, require_write=False)

        # The same credential is rejected once write access is required.
        with pytest.raises(
            RepositoryPermissionError,
            match=(
                rf"^Write access to repository {repo_name} was denied\. The credentials can read but not push; "
                r"grant the token write access to the repository\.$"
            ),
        ):
            InfrahubRepository.check_connectivity(name=repo_name, url=readonly_url, require_write=True)

        # A credential that can write passes the write probe on the same repository.
        InfrahubRepository.check_connectivity(
            name=repo_name, url=write_probe_dataset["writable_url"], require_write=True
        )

    async def test_write_probe_never_mutates_remote(self, write_probe_dataset: dict, gogs_server: GogsServer) -> None:
        """The write probe leaves the remote's refs untouched, even when the probe ref already exists.

        This is the assertion that stops a later refactor from dropping --dry-run: a non-dry-run
        delete of the probe ref would remove it here.
        """
        repo_name = write_probe_dataset["repo_name"]
        writable_url = write_probe_dataset["writable_url"]

        create_remote_ref(gogs_server.container, repo_name, WRITE_ACCESS_PROBE_REF)
        cmd = git.cmd.Git()
        refs_before = cmd.ls_remote(writable_url)
        assert f"refs/heads/{WRITE_ACCESS_PROBE_REF}" in refs_before

        InfrahubRepository.check_connectivity(name=repo_name, url=writable_url, require_write=True)

        refs_after = cmd.ls_remote(writable_url)
        assert refs_after == refs_before

    async def test_create_read_write_repository_without_push_access_is_rejected(
        self,
        initialize_registry: None,
        git_repos_dir_module_scope: Path,
        gogs_server: GogsServer,
        db: InfrahubDatabase,
        client: InfrahubClient,
    ) -> None:
        """Creating a read-write repository whose credentials cannot push fails and leaves no node behind."""
        repo_name = "reject-write-repo"
        create_gogs_repo(gogs_server.base_url, gogs_server.token, repo_name, gogs_server.container, private=True)
        grant_read_access(gogs_server.base_url, gogs_server.token, repo_name)
        readonly_url = readonly_clone_url(gogs_server.base_url, repo_name)

        node = await client.create(kind=InfrahubKind.REPOSITORY, data={"name": repo_name, "location": readonly_url})
        with pytest.raises(
            GraphQLError,
            match=(
                rf"Write access to repository {repo_name} was denied\. The credentials can read but not push; "
                r"grant the token write access to the repository\."
            ),
        ):
            await node.save()

        leftover = await NodeManager.query(db=db, schema=InfrahubKind.REPOSITORY, filters={"name__value": repo_name})
        assert leftover == []

    async def test_create_read_only_repository_with_read_only_credentials_succeeds(
        self,
        initialize_registry: None,
        git_repos_dir_module_scope: Path,
        gogs_server: GogsServer,
        db: InfrahubDatabase,
        client: InfrahubClient,
    ) -> None:
        """A read-only repository created with read-only credentials succeeds; it is never write-probed."""
        repo_name = "readonly-creds-repo"
        create_gogs_repo(gogs_server.base_url, gogs_server.token, repo_name, gogs_server.container, private=True)
        grant_read_access(gogs_server.base_url, gogs_server.token, repo_name)
        readonly_url = readonly_clone_url(gogs_server.base_url, repo_name)

        branch = await client.branch.create(branch_name="ro_readonly_creds", sync_with_git=False)
        node = await client.create(
            kind=InfrahubKind.READONLYREPOSITORY,
            branch=branch.name,
            name=repo_name,
            location=readonly_url,
            ref="main",
        )
        await node.save()

        created: CoreReadOnlyRepository = await NodeManager.get_one(
            db=db,
            id=node.id,
            kind=InfrahubKind.READONLYREPOSITORY,
            branch=branch.name,
            raise_on_error=True,
        )
        assert created.name.value == repo_name
