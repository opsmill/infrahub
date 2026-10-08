"""Integration tests for InfrahubRepository and InfrahubReadOnlyRepository against a live remote."""

from __future__ import annotations

import logging
import re
import shutil
from contextlib import contextmanager
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from functools import partial
from pathlib import Path
from typing import TYPE_CHECKING

import git
import pytest
import yaml
from infrahub_sdk.exceptions import GraphQLError
from infrahub_sdk.task.models import TaskFilter, TaskState
from prefect.client.schemas.objects import StateType

from infrahub import config, lock
from infrahub.core.constants import (
    InfrahubKind,
    RepositoryDeliveryFailureCause,
    RepositoryDeliveryStatus,
    RepositoryInternalStatus,
    RepositoryOperationalStatus,
    RepositorySyncStatus,
)
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.core.registry import registry
from infrahub.exceptions import RepositoryCredentialsError, RepositoryError, RepositoryPermissionError
from infrahub.git.constants import WRITE_ACCESS_PROBE_REF
from infrahub.git.convergence import WorktreeConverger
from infrahub.git.models import GitRepositoryDeliveryRetry
from infrahub.git.remote_refs import ensure_write_access, list_remote_refs
from infrahub.git.repository import InfrahubReadOnlyRepository, InfrahubRepository
from infrahub.git.tasks import retry_repository_delivery, sync_remote_repositories
from infrahub.git.writeback.store import WritebackIntentStore
from infrahub.message_bus.messages import RefreshGitFetch
from infrahub.message_bus.messages.refresh_git_fetch import BranchCommitPair
from infrahub.workflows.catalogue import GIT_REPOSITORY_DELIVERY_RETRY
from tests.constants import TestKind
from tests.helpers.schema import CAR_SCHEMA, load_schema
from tests.helpers.test_app import TestInfrahubApp
from tests.integration.git.conftest import (
    GOGS_ADMIN,
    TrackedBranchRepository,
    bad_credentials_clone_url,
    commit_to_remote_branch,
    create_gogs_repo,
    create_remote_ref,
    gogs_clone_url,
    gogs_repo_branch_commit,
    gogs_repo_tag,
    grant_read_access,
    readonly_clone_url,
    tracked_branch_files,
)

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable, Generator

    from infrahub_sdk import InfrahubClient
    from testcontainers.core.container import DockerContainer

    from infrahub.core.protocols import CoreArtifact, CoreGraphQLQuery, CoreReadOnlyRepository, CoreRepository
    from infrahub.database import InfrahubDatabase
    from infrahub.git.writeback.models import WritebackIntent
    from tests.adapters.message_bus import BusSimulator
    from tests.helpers.git import GogsServer

SYNC_LOGGER = "infrahub.tasks"
RETRY_DELIVERY = """
mutation RetryDelivery($id: String!) {
    InfrahubRepositoryDeliveryRetry(data: {id: $id}) {
        ok
    }
}
"""


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


def _install_remote_branch_rejection_hook(container: DockerContainer, repo_name: str, branch: str = "main") -> None:
    """Install a pre-receive hook in the remote bare repository that rejects updates to one branch.

    Reproduces server-side branch protection or a missing push permission: the push is accepted
    at the transport level and the rejection arrives as a per-ref status.
    """
    script = f"""set -e
cd /data/git/repositories/{GOGS_ADMIN}/{repo_name}.git/hooks
if [ -f pre-receive ] && [ ! -f pre-receive.orig ]; then mv pre-receive pre-receive.orig; fi
cat > pre-receive <<'HOOK'
#!/bin/sh
while read old new ref; do
    if [ "$ref" = "refs/heads/{branch}" ]; then
        echo "branch {branch} is protected" >&2
        exit 1
    fi
done
exit 0
HOOK
chmod +x pre-receive
"""
    result = container.get_wrapped_container().exec_run(["bash", "-c", script], user="git")
    assert result.exit_code == 0, f"Hook install failed (exit {result.exit_code}): {result.output.decode()}"


def _remove_remote_branch_rejection_hook(container: DockerContainer, repo_name: str) -> None:
    """Remove the rejecting pre-receive hook, restoring the hook that was in place before."""
    script = f"""set -e
cd /data/git/repositories/{GOGS_ADMIN}/{repo_name}.git/hooks
rm -f pre-receive
if [ -f pre-receive.orig ]; then mv pre-receive.orig pre-receive; fi
"""
    result = container.get_wrapped_container().exec_run(["bash", "-c", script], user="git")
    assert result.exit_code == 0, f"Hook removal failed (exit {result.exit_code}): {result.output.decode()}"


def _remote_branch_contains(container: DockerContainer, repo_name: str, branch: str, commit: str) -> bool:
    """Return whether the history of a branch of the remote holds the commit."""
    result = container.get_wrapped_container().exec_run(
        [
            "git",
            f"--git-dir=/data/git/repositories/{GOGS_ADMIN}/{repo_name}.git",
            "merge-base",
            "--is-ancestor",
            commit,
            branch,
        ],
        user="git",
    )
    # Any other exit code means that Git could not answer, which is not a "no".
    assert result.exit_code in {0, 1}, f"Ancestry check failed (exit {result.exit_code}): {result.output.decode()}"
    return result.exit_code == 0


async def _delivery_state(db: InfrahubDatabase, repository_id: str) -> WritebackIntent:
    """Return the delivery state of the repository, which lives on the default branch."""
    store = WritebackIntentStore(
        db=db,
        lock_registry=lock.registry,
        default_branch=await registry.get_branch(db=db),
        clock=partial(datetime.now, UTC),
    )
    return await store.read(repository_id=repository_id)


async def _recorded_commit(db: InfrahubDatabase, repository_id: str) -> str | None:
    """Return the commit that the default branch records for the repository."""
    repository: CoreRepository = await NodeManager.get_one(
        db=db, id=repository_id, kind=InfrahubKind.REPOSITORY, raise_on_error=True
    )
    return repository.commit.value


async def _sync_new_branch(
    *,
    db: InfrahubDatabase,
    client: InfrahubClient,
    container: DockerContainer,
    repo_name: str,
    repository_id: str,
    branch_name: str,
) -> str:
    """Create a branch that syncs with Git and adds a file that main lacks, and return the commit the branch records."""
    await client.branch.create(branch_name=branch_name, sync_with_git=True)
    source_commit = commit_to_remote_branch(
        container, repo_name, branch=branch_name, files={f"{branch_name}.txt": f"{branch_name}\n"}
    )

    # A synchronisation visits every repository of the stack, so only this repository pulls the branch.
    repo = await InfrahubRepository.init(
        id=repository_id, name=repo_name, client=client, infrahub_branch_name=registry.default_branch
    )
    await repo.fetch()
    await repo.pull(branch_name=branch_name)
    on_branch: CoreRepository = await NodeManager.get_one(
        db=db, id=repository_id, kind=InfrahubKind.REPOSITORY, branch=branch_name, raise_on_error=True
    )
    assert on_branch.commit.value == source_commit, "the branch does not record the commit of its file"
    return source_commit


async def _retry_states(client: InfrahubClient, repository_id: str) -> list[TaskState]:
    """Return the state of each retry run of the repository's pending pushes."""
    tasks = await client.task.filter(
        filter=TaskFilter(workflow=[GIT_REPOSITORY_DELIVERY_RETRY.name], related_node__ids=[repository_id])
    )
    return [task.state for task in tasks]


CARD_GROUP = "delivery-remote-advanced-people"
CARD_DEFINITION = "delivery-remote-advanced-card"


def _card_files(version: int) -> dict[str, str]:
    """Return a repository configuration whose artifact definition renders a card of each person, at a version."""
    repository_config = {
        "queries": [{"name": "delivery_remote_advanced_person", "file_path": "person.gql"}],
        "jinja2_transforms": [
            {
                "name": "delivery_remote_advanced_card",
                "query": "delivery_remote_advanced_person",
                "template_path": "card.j2",
            }
        ],
        "artifact_definitions": [
            {
                "name": CARD_DEFINITION,
                "artifact_name": f"card-v{version}",
                "parameters": {"name": "name__value"},
                "content_type": "text/plain",
                "targets": CARD_GROUP,
                "transformation": "delivery_remote_advanced_card",
            }
        ],
    }
    return {
        ".infrahub.yml": yaml.safe_dump(repository_config),
        "person.gql": (
            "query delivery_remote_advanced_person($name: String!) "
            "{ TestingPerson(name__value: $name) { edges { node { name { value } } } } }\n"
        ),
        "card.j2": f"Card v{version} of {{{{ data.TestingPerson.edges[0].node.name.value }}}}",
    }


async def _card_artifacts(db: InfrahubDatabase, client: InfrahubClient) -> list[tuple[str | None, str]]:
    """Return the name and the stored content of each artifact of the card definition on the default branch."""
    artifacts: list[CoreArtifact] = await NodeManager.query(
        db=db, schema=InfrahubKind.ARTIFACT, filters={"definition__name__value": CARD_DEFINITION}
    )
    return [
        (artifact.name.value, await client.object_store.get(identifier=str(artifact.storage_id.value)))
        for artifact in artifacts
    ]


@dataclass(frozen=True)
class SyncedBranchRepository:
    """A repository on a remote of its own, with a branch that syncs with Git and holds a file that main lacks."""

    name: str
    node_id: str
    branch_name: str
    trunk_commit: str
    """The head of the default branch of the remote, which Infrahub records."""
    source_commit: str
    """The head of the branch, which Infrahub records on the branch."""


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
    async def protected_branch_dataset(
        self,
        initialize_registry: None,
        git_repos_dir_module_scope: Path,
        client: InfrahubClient,
        gogs_server: GogsServer,
    ) -> dict:
        repo_name = "protected-branch-repo"
        repo_url = create_gogs_repo(gogs_server.base_url, gogs_server.token, repo_name, gogs_server.container)
        node = await client.create(
            kind=InfrahubKind.REPOSITORY,
            data={"name": repo_name, "location": repo_url},
        )
        await node.save()
        return {"repo_name": repo_name, "node_id": node.id}

    @pytest.fixture
    def reject_pushes_to_main(
        self, gogs_server: GogsServer
    ) -> Generator[Callable[[str], Callable[[], None]], None, None]:
        """Yield a callable that makes a remote reject pushes to main, and returns a callable that lifts the rejection."""
        rejected: list[str] = []

        def reject(repo_name: str) -> Callable[[], None]:
            _install_remote_branch_rejection_hook(container=gogs_server.container, repo_name=repo_name)
            rejected.append(repo_name)
            return partial(_remove_remote_branch_rejection_hook, container=gogs_server.container, repo_name=repo_name)

        yield reject
        for repo_name in rejected:
            _remove_remote_branch_rejection_hook(container=gogs_server.container, repo_name=repo_name)

    @pytest.fixture
    def rejected_push_to_main(
        self, protected_branch_dataset: dict, reject_pushes_to_main: Callable[[str], Callable[[], None]]
    ) -> Callable[[], None]:
        """Make the remote reject pushes to main, returning a callable that lifts the rejection."""
        return reject_pushes_to_main(protected_branch_dataset["repo_name"])

    @pytest.fixture
    def synced_branch_repository(
        self,
        initialize_registry: None,
        git_repos_dir_module_scope: Path,
        db: InfrahubDatabase,
        client: InfrahubClient,
        gogs_server: GogsServer,
    ) -> Callable[..., Awaitable[SyncedBranchRepository]]:
        """Return a factory for a repository whose branch adds a file that the default branch does not have.

        Each test gets a remote and a repository of its own, so a queued merge of one test never reaches another.
        The files of `trunk_files` are on the default branch before the repository and its branch exist.
        """

        async def create(branch_name: str, trunk_files: dict[str, str] | None = None) -> SyncedBranchRepository:
            repo_name = f"{branch_name}-repo"
            location = create_gogs_repo(gogs_server.base_url, gogs_server.token, repo_name, gogs_server.container)
            if trunk_files:
                commit_to_remote_branch(gogs_server.container, repo_name, branch="main", files=trunk_files)
            node = await client.create(kind=InfrahubKind.REPOSITORY, data={"name": repo_name, "location": location})
            await node.save()
            source_commit = await _sync_new_branch(
                db=db,
                client=client,
                container=gogs_server.container,
                repo_name=repo_name,
                repository_id=node.id,
                branch_name=branch_name,
            )
            return SyncedBranchRepository(
                name=repo_name,
                node_id=node.id,
                branch_name=branch_name,
                trunk_commit=gogs_repo_branch_commit(gogs_server.container, repo_name, "main"),
                source_commit=source_commit,
            )

        return create

    @pytest.fixture
    def block_commit_worktree(self) -> Generator[Callable[[Path], Callable[[], None]], None, None]:
        """Yield a callable that occupies a commit worktree directory, returning a callable that releases it."""
        blocked: list[Path] = []

        def block(directory: Path) -> Callable[[], None]:
            directory.mkdir()
            (directory / "blocker.txt").write_text("blocking worktree creation\n")
            blocked.append(directory)

            def release() -> None:
                shutil.rmtree(directory, ignore_errors=True)

            return release

        yield block
        for directory in blocked:
            shutil.rmtree(directory, ignore_errors=True)

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

    @pytest.fixture(scope="class")
    async def master_only_dataset(
        self,
        initialize_registry: None,
        git_repos_dir_module_scope: Path,
        gogs_server: GogsServer,
    ) -> dict:
        repo_name = "master-only-repo"
        repo_url = create_gogs_repo(
            gogs_server.base_url,
            gogs_server.token,
            repo_name,
            gogs_server.container,
            create_main=False,
        )
        return {
            "repo_name": repo_name,
            "repo_url": repo_url,
            "master_commit": gogs_repo_branch_commit(gogs_server.container, repo_name, "master"),
        }

    @pytest.fixture(scope="class")
    async def tag_pinned_dataset(
        self,
        initialize_registry: None,
        git_repos_dir_module_scope: Path,
        gogs_server: GogsServer,
    ) -> dict:
        repo_name = "tag-pinned-repo"
        tag_name = "v1.0.0"
        repo_url = create_gogs_repo(
            gogs_server.base_url,
            gogs_server.token,
            repo_name,
            gogs_server.container,
            create_main=False,
        )
        gogs_repo_tag(gogs_server.container, repo_name, tag_name)

        return {"repo_name": repo_name, "repo_url": repo_url, "tag_name": tag_name}

    async def test_connecting_with_a_default_branch_absent_from_the_remote_is_rejected(
        self,
        master_only_dataset: dict,
        db: InfrahubDatabase,
        client: InfrahubClient,
    ) -> None:
        """A default branch the remote does not have is rejected, leaves nothing behind, and a corrected retry connects."""
        repo_name = master_only_dataset["repo_name"]
        repo_url = master_only_dataset["repo_url"]

        rejected = await client.create(
            kind=InfrahubKind.REPOSITORY,
            data={"name": repo_name, "location": repo_url},
        )
        with pytest.raises(GraphQLError) as exc:
            await rejected.save()

        assert [error["message"] for error in exc.value.errors] == [
            f"Branch 'main' does not exist on the remote repository {repo_name}; "
            "the remote's default branch is 'master'."
        ]
        assert await NodeManager.query(db=db, schema=InfrahubKind.REPOSITORY, filters={"name__value": repo_name}) == []

        retried = await client.create(
            kind=InfrahubKind.REPOSITORY,
            data={"name": repo_name, "location": repo_url, "default_branch": "master"},
        )
        await retried.save()

        repository: CoreRepository = await NodeManager.get_one(
            db=db, id=retried.id, kind=InfrahubKind.REPOSITORY, raise_on_error=True
        )
        assert repository.default_branch.value == "master"
        assert repository.commit.value == master_only_dataset["master_commit"]
        assert repository.internal_status.value == RepositoryInternalStatus.ACTIVE.value
        assert repository.operational_status.value == RepositoryOperationalStatus.ONLINE.value

    async def test_connecting_a_read_only_repository_pinned_to_a_tag_is_not_branch_checked(
        self,
        tag_pinned_dataset: dict,
        db: InfrahubDatabase,
        client: InfrahubClient,
    ) -> None:
        """A read-only repository tracks a ref no branch listing can confirm, so it is connected unchecked."""
        node = await client.create(
            kind=InfrahubKind.READONLYREPOSITORY,
            data={
                "name": tag_pinned_dataset["repo_name"],
                "location": tag_pinned_dataset["repo_url"],
                "ref": tag_pinned_dataset["tag_name"],
            },
        )
        await node.save()

        repository: CoreReadOnlyRepository = await NodeManager.get_one(
            db=db, id=node.id, kind=InfrahubKind.READONLYREPOSITORY, raise_on_error=True
        )
        assert repository.ref.value == tag_pinned_dataset["tag_name"]
        assert repository.operational_status.value == RepositoryOperationalStatus.ONLINE.value

    async def test_unreachable_remote_reports_a_connectivity_error(
        self,
        db: InfrahubDatabase,
        client: InfrahubClient,
    ) -> None:
        """An unreachable remote is reported as a connectivity failure, never as a missing-branch failure."""
        repo_name = "unreachable-repo"

        node = await client.create(
            kind=InfrahubKind.REPOSITORY,
            data={
                "name": repo_name,
                "location": "http://localhost:1/nonexistent.git",
                "default_branch": "master",
            },
        )
        with pytest.raises(GraphQLError) as exc:
            await node.save()

        assert [error["message"] for error in exc.value.errors] == [
            f"Unable to clone the repository {repo_name}, please check the address and the credential"
        ]
        assert await NodeManager.query(db=db, schema=InfrahubKind.REPOSITORY, filters={"name__value": repo_name}) == []

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
                infrahub_branch_name="main",
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
            infrahub_branch_name="main",
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
            match=(
                rf"^Unable to push the branch main to the remote for repository {repo_name}: "
                r"the remote branch has commits that are missing locally \(non-fast-forward\): "
                r"\[rejected\] \(fetch first\)$"
            ),
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
            infrahub_branch_name="main",
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

    async def test_merge_push_rejected_leaves_state_unchanged(
        self,
        protected_branch_dataset: dict,
        db: InfrahubDatabase,
        client: InfrahubClient,
        rejected_push_to_main: Callable[[], None],
    ) -> None:
        """A merge whose push is rejected raises and leaves everything at the pre-merge state.

        The destination worktree, the commit recorded in the graph and the remote branch must
        all still point at the pre-merge commit.
        """
        repo_name = protected_branch_dataset["repo_name"]

        repository: CoreRepository = await NodeManager.get_one(
            db=db,
            id=protected_branch_dataset["node_id"],
            kind=InfrahubKind.REPOSITORY,
            raise_on_error=True,
        )
        infrahub_repo = await InfrahubRepository.init(
            id=repository.id,
            name=repo_name,
            client=client,
            infrahub_branch_name="main",
        )

        await infrahub_repo.create_branch_in_git(branch_name="blocked-change", push_origin=False)
        branch_repo = infrahub_repo.get_git_repo_worktree(identifier="blocked-change")
        (Path(str(branch_repo.working_dir)) / "blocked_change.txt").write_text("blocked change\n")
        branch_repo.index.add(["blocked_change.txt"])
        branch_repo.index.commit("blocked-change: add blocked_change.txt")

        main_repo = infrahub_repo.get_git_repo_worktree(identifier="main")
        commit_before = str(main_repo.head.commit)
        graph_commit_before = repository.commit.value

        with pytest.raises(
            RepositoryError,
            match=(
                rf"^Unable to push the branch main to the remote for repository {repo_name}: "
                r"the remote refused the update \(for example missing push permission or branch protection\): "
                r"\[remote rejected\] \(pre-receive hook declined\)$"
            ),
        ):
            await infrahub_repo.merge(source_branch="blocked-change", dest_branch="main")

        assert str(main_repo.head.commit) == commit_before

        main_repo.remotes.origin.fetch()
        assert str(main_repo.commit("origin/main")) == commit_before

        updated: CoreRepository = await NodeManager.get_one(
            db=db,
            id=protected_branch_dataset["node_id"],
            kind=InfrahubKind.REPOSITORY,
            raise_on_error=True,
        )
        assert updated.commit.value == graph_commit_before

    async def test_merge_retry_succeeds_after_push_rejection_lifted(
        self,
        protected_branch_dataset: dict,
        db: InfrahubDatabase,
        client: InfrahubClient,
        rejected_push_to_main: Callable[[], None],
    ) -> None:
        """After a rejected push, lifting the rejection and merging again delivers the merge everywhere.

        This only works when the failed attempt left the destination worktree on its pre-merge
        commit: left on the unpushed merge commit, the retry would find nothing to merge and
        never reach the push.
        """
        repo_name = protected_branch_dataset["repo_name"]

        repository: CoreRepository = await NodeManager.get_one(
            db=db,
            id=protected_branch_dataset["node_id"],
            kind=InfrahubKind.REPOSITORY,
            raise_on_error=True,
        )
        infrahub_repo = await InfrahubRepository.init(
            id=repository.id,
            name=repo_name,
            client=client,
            infrahub_branch_name="main",
        )

        await infrahub_repo.create_branch_in_git(branch_name="retried-change", push_origin=False)
        branch_repo = infrahub_repo.get_git_repo_worktree(identifier="retried-change")
        (Path(str(branch_repo.working_dir)) / "retried_change.txt").write_text("retried change\n")
        branch_repo.index.add(["retried_change.txt"])
        branch_repo.index.commit("retried-change: add retried_change.txt")

        main_repo = infrahub_repo.get_git_repo_worktree(identifier="main")
        commit_before = str(main_repo.head.commit)

        with pytest.raises(
            RepositoryError,
            match=(
                rf"^Unable to push the branch main to the remote for repository {repo_name}: "
                r"the remote refused the update \(for example missing push permission or branch protection\): "
                r"\[remote rejected\] \(pre-receive hook declined\)$"
            ),
        ):
            await infrahub_repo.merge(source_branch="retried-change", dest_branch="main")

        rejected_push_to_main()

        merged_commit = await infrahub_repo.merge(source_branch="retried-change", dest_branch="main")

        assert merged_commit == str(main_repo.head.commit)
        assert merged_commit != commit_before

        main_repo.remotes.origin.fetch()
        assert str(main_repo.commit("origin/main")) == merged_commit

        updated: CoreRepository = await NodeManager.get_one(
            db=db,
            id=protected_branch_dataset["node_id"],
            kind=InfrahubKind.REPOSITORY,
            raise_on_error=True,
        )
        assert updated.commit.value == merged_commit

    async def test_merge_writeback_failure_after_push_resets_worktree_for_sync_repair(
        self,
        protected_branch_dataset: dict,
        db: InfrahubDatabase,
        client: InfrahubClient,
        fast_forward_merges: None,
        block_commit_worktree: Callable[[Path], Callable[[], None]],
    ) -> None:
        """A failure recording the merge after a successful push resets the worktree behind the remote.

        The pushed merge commit exists only on the remote afterwards, which is the state the
        periodic synchronization repairs: it detects the destination branch as updated, moves the
        worktree onto the merge commit and records it in the graph.
        """
        repo_name = protected_branch_dataset["repo_name"]

        infrahub_repo = await InfrahubRepository.init(
            id=protected_branch_dataset["node_id"],
            name=repo_name,
            client=client,
            infrahub_branch_name="main",
        )

        await infrahub_repo.create_branch_in_git(branch_name="recorded-change", push_origin=False)
        branch_repo = infrahub_repo.get_git_repo_worktree(identifier="recorded-change")
        (Path(str(branch_repo.working_dir)) / "recorded_change.txt").write_text("recorded change\n")
        branch_repo.index.add(["recorded_change.txt"])
        merge_commit = str(branch_repo.index.commit("recorded-change: add recorded_change.txt"))

        main_repo = infrahub_repo.get_git_repo_worktree(identifier="main")
        commit_before = str(main_repo.head.commit)

        # The merge fast-forwards the destination to the source tip, so the commit worktree
        # directory is known ahead of time and can be blocked to fail the writeback after the push.
        blocked_directory = infrahub_repo.directory_commits / merge_commit
        release_blocked_directory = block_commit_worktree(blocked_directory)

        with pytest.raises(RepositoryError, match=rf"'{re.escape(str(blocked_directory))}' already exists"):
            await infrahub_repo.merge(source_branch="recorded-change", dest_branch="main")

        # The synchronization below records the pushed merge commit, which needs this worktree.
        release_blocked_directory()

        assert str(main_repo.head.commit) == commit_before

        main_repo.remotes.origin.fetch()
        assert str(main_repo.commit("origin/main")) == merge_commit

        await infrahub_repo.fetch()
        _, updated_branches = await infrahub_repo.compare_local_remote()
        assert updated_branches == ["main"]

        pulled_commit = await infrahub_repo.pull(branch_name="main")
        assert pulled_commit == merge_commit
        assert str(main_repo.head.commit) == merge_commit

        updated: CoreRepository = await NodeManager.get_one(
            db=db,
            id=protected_branch_dataset["node_id"],
            kind=InfrahubKind.REPOSITORY,
            raise_on_error=True,
        )
        assert updated.commit.value == merge_commit

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
        difference: read access alone passes the ref listing but not the write probe.
        """
        repo_name = write_probe_dataset["repo_name"]
        readonly_url = write_probe_dataset["readonly_url"]

        # Read access alone satisfies the read-gated check.
        list_remote_refs(name=repo_name, url=readonly_url)

        # The same credential is rejected once write access is required.
        with pytest.raises(
            RepositoryPermissionError,
            match=(
                rf"^Write access to repository {repo_name} was denied\. The credentials can read but not push; "
                r"grant the token write access to the repository\.$"
            ),
        ):
            ensure_write_access(name=repo_name, url=readonly_url)

        # A credential that can write passes the write probe on the same repository.
        ensure_write_access(name=repo_name, url=write_probe_dataset["writable_url"])

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

        ensure_write_access(name=repo_name, url=writable_url)

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

    async def _retry_delivery(self, client: InfrahubClient, repository: SyncedBranchRepository) -> None:
        """Ask for a retry of the pending pushes of the repository, as a user does, on the default branch.

        The local workflow runs the retry inside the request, so a retry run that fails comes back as the error of the
        mutation.
        """
        await client.execute_graphql(
            query=RETRY_DELIVERY, variables={"id": repository.node_id}, branch_name=registry.default_branch
        )

    async def test_delivery_visible(
        self,
        db: InfrahubDatabase,
        client: InfrahubClient,
        gogs_server: GogsServer,
        synced_branch_repository: Callable[[str], Awaitable[SyncedBranchRepository]],
        reject_pushes_to_main: Callable[[str], Callable[[], None]],
    ) -> None:
        """A merge that the remote refuses stays queued, and the repository shows why in the words of the remote."""
        repository = await synced_branch_repository("delivery-visible")
        reject_pushes_to_main(repository.name)

        await client.branch.merge(branch_name=repository.branch_name)

        state = await _delivery_state(db=db, repository_id=repository.node_id)
        assert (state.status, state.cause, state.error) == (
            RepositoryDeliveryStatus.ACTION_REQUIRED,
            RepositoryDeliveryFailureCause.PERMISSION,
            "remote: branch main is protected\n"
            "Unable to push the branch main to the remote for repository delivery-visible-repo: "
            "the remote refused the update (for example missing push permission or branch protection): "
            "[remote rejected] (pre-receive hook declined)",
        )
        assert [
            (entry.source_branch, entry.source_git_branch, entry.source_commit) for entry in state.queue.entries
        ] == [(repository.branch_name, repository.branch_name, repository.source_commit)]
        assert await _recorded_commit(db=db, repository_id=repository.node_id) == repository.trunk_commit
        assert gogs_repo_branch_commit(gogs_server.container, repository.name, "main") == repository.trunk_commit

    async def test_first_attempt_delivers(
        self,
        db: InfrahubDatabase,
        client: InfrahubClient,
        gogs_server: GogsServer,
        bus_simulator: BusSimulator,
        fast_forward_merges: None,
        synced_branch_repository: Callable[[str], Awaitable[SyncedBranchRepository]],
    ) -> None:
        """A merge that the remote accepts leaves nothing pending, and the workers fetch the commit it pushed.

        The merge fast-forwards the default branch, so the pushed commit is the head of the branch.
        """
        repository = await synced_branch_repository("delivery-first-attempt")
        main = await client.branch.get(branch_name=registry.default_branch)
        sent_before = len(bus_simulator.messages)

        await client.branch.merge(branch_name=repository.branch_name)

        state = await _delivery_state(db=db, repository_id=repository.node_id)
        assert (state.status, state.cause, state.error, state.queue.entries, state.last_delivered_commit) == (
            RepositoryDeliveryStatus.NONE,
            None,
            None,
            (),
            repository.source_commit,
        )
        assert await _recorded_commit(db=db, repository_id=repository.node_id) == repository.source_commit
        assert gogs_repo_branch_commit(gogs_server.container, repository.name, "main") == repository.source_commit
        assert [
            (message.infrahub_branch_name, message.infrahub_branch_id, message.commit)
            for message in bus_simulator.messages[sent_before:]
            if isinstance(message, RefreshGitFetch) and message.repository_id == repository.node_id
        ] == [(main.name, main.id, repository.source_commit)]

    async def test_source_discarded(
        self,
        db: InfrahubDatabase,
        client: InfrahubClient,
        gogs_server: GogsServer,
        synced_branch_repository: Callable[[str], Awaitable[SyncedBranchRepository]],
        reject_pushes_to_main: Callable[[str], Callable[[], None]],
    ) -> None:
        """A retry pushes nothing when the remote branch of a queued merge no longer holds its commit.

        This worker still holds the discarded commit, so only the check of the source branch keeps it off the remote.
        """
        repository = await synced_branch_repository("delivery-source-discarded")
        lift_rejection = reject_pushes_to_main(repository.name)
        await client.branch.merge(branch_name=repository.branch_name)
        assert (await _delivery_state(db=db, repository_id=repository.node_id)).cause == (
            RepositoryDeliveryFailureCause.PERMISSION
        )
        rewritten = commit_to_remote_branch(
            gogs_server.container,
            repository.name,
            branch=repository.branch_name,
            files={"rewritten.txt": "rewritten\n"},
            amend=True,
        )
        lift_rejection()

        with pytest.raises(GraphQLError) as exc:
            await self._retry_delivery(client=client, repository=repository)

        assert [error["message"] for error in exc.value.errors] == [
            f"The delivery to repository {repository.name} ended with the outcome unreplayable."
        ]
        assert await _retry_states(client=client, repository_id=repository.node_id) == [TaskState.FAILED]
        state = await _delivery_state(db=db, repository_id=repository.node_id)
        entry_ids = [entry.entry_id for entry in state.queue.entries]
        assert [(entry.source_branch, entry.source_commit) for entry in state.queue.entries] == [
            (repository.branch_name, repository.source_commit)
        ]
        assert (state.status, state.cause, state.error) == (
            RepositoryDeliveryStatus.ACTION_REQUIRED,
            RepositoryDeliveryFailureCause.SOURCE_DISCARDED,
            f"The remote branch {repository.branch_name} of repository {repository.name} is at {rewritten}, "
            f"which does not contain the commit {repository.source_commit} of the merge {entry_ids[0]} of branch "
            f"{repository.branch_name}, so nothing was pushed.",
        )
        assert gogs_repo_branch_commit(gogs_server.container, repository.name, "main") == repository.trunk_commit
        assert not _remote_branch_contains(
            gogs_server.container, repository.name, branch="main", commit=repository.source_commit
        )

    async def test_destination_rewritten(
        self,
        db: InfrahubDatabase,
        client: InfrahubClient,
        gogs_server: GogsServer,
        synced_branch_repository: Callable[[str], Awaitable[SyncedBranchRepository]],
        reject_pushes_to_main: Callable[[str], Callable[[], None]],
    ) -> None:
        """A retry pushes nothing when the default branch of the remote no longer holds the commit that Infrahub records.

        A branch forked from the old history holds that history, so a replay would push the discarded commits back.
        """
        repository = await synced_branch_repository("delivery-destination-rewritten")
        lift_rejection = reject_pushes_to_main(repository.name)
        await client.branch.merge(branch_name=repository.branch_name)
        assert (await _delivery_state(db=db, repository_id=repository.node_id)).cause == (
            RepositoryDeliveryFailureCause.PERMISSION
        )
        lift_rejection()
        rewritten = commit_to_remote_branch(
            gogs_server.container, repository.name, branch="main", files={"rewritten.txt": "rewritten\n"}, amend=True
        )

        with pytest.raises(GraphQLError) as exc:
            await self._retry_delivery(client=client, repository=repository)

        assert [error["message"] for error in exc.value.errors] == [
            f"The delivery to repository {repository.name} ended with the outcome unreplayable."
        ]
        assert await _retry_states(client=client, repository_id=repository.node_id) == [TaskState.FAILED]
        state = await _delivery_state(db=db, repository_id=repository.node_id)
        assert [(entry.source_branch, entry.source_commit) for entry in state.queue.entries] == [
            (repository.branch_name, repository.source_commit)
        ]
        assert (state.status, state.cause, state.error) == (
            RepositoryDeliveryStatus.ACTION_REQUIRED,
            RepositoryDeliveryFailureCause.DESTINATION_REWRITTEN,
            f"The remote branch main of repository {repository.name} is at {rewritten}, which does not contain "
            f"the commit {repository.trunk_commit} that Infrahub records, so nothing was pushed.",
        )
        assert gogs_repo_branch_commit(gogs_server.container, repository.name, "main") == rewritten
        assert await _recorded_commit(db=db, repository_id=repository.node_id) == repository.trunk_commit

    async def test_one_retry_delivers_both(
        self,
        db: InfrahubDatabase,
        client: InfrahubClient,
        gogs_server: GogsServer,
        fast_forward_merges: None,
        synced_branch_repository: Callable[[str], Awaitable[SyncedBranchRepository]],
        reject_pushes_to_main: Callable[[str], Callable[[], None]],
    ) -> None:
        """A retry fails while the remote refuses, and one retry after that delivers every pending merge in order."""
        first = await synced_branch_repository("delivery-one-retry")
        second_branch = "delivery-one-retry-second"
        second = replace(
            first,
            branch_name=second_branch,
            source_commit=await _sync_new_branch(
                db=db,
                client=client,
                container=gogs_server.container,
                repo_name=first.name,
                repository_id=first.node_id,
                branch_name=second_branch,
            ),
        )
        lift_rejection = reject_pushes_to_main(first.name)
        await client.branch.merge(branch_name=first.branch_name)
        await client.branch.merge(branch_name=second.branch_name)
        queued = await _delivery_state(db=db, repository_id=first.node_id)
        assert [(entry.source_branch, entry.source_commit) for entry in queued.queue.entries] == [
            (first.branch_name, first.source_commit),
            (second.branch_name, second.source_commit),
        ]

        with pytest.raises(GraphQLError) as exc:
            await self._retry_delivery(client=client, repository=first)

        assert [error["message"] for error in exc.value.errors] == [
            f"The delivery to repository {first.name} ended with the outcome failed."
        ]
        assert await _retry_states(client=client, repository_id=first.node_id) == [TaskState.FAILED]
        refused = await _delivery_state(db=db, repository_id=first.node_id)
        assert (refused.status, refused.cause, refused.queue.entries) == (
            RepositoryDeliveryStatus.ACTION_REQUIRED,
            RepositoryDeliveryFailureCause.PERMISSION,
            queued.queue.entries,
        )
        assert gogs_repo_branch_commit(gogs_server.container, first.name, "main") == first.trunk_commit
        lift_rejection()

        await self._retry_delivery(client=client, repository=first)

        assert sorted(await _retry_states(client=client, repository_id=first.node_id)) == [
            TaskState.COMPLETED,
            TaskState.FAILED,
        ]
        head = gogs_repo_branch_commit(gogs_server.container, first.name, "main")
        state = await _delivery_state(db=db, repository_id=first.node_id)
        assert (
            state.status,
            state.cause,
            state.error,
            state.queue.entries,
            state.queue.import_owed_commit,
            state.last_delivered_commit,
        ) == (RepositoryDeliveryStatus.NONE, None, None, (), None, head)
        assert await _recorded_commit(db=db, repository_id=first.node_id) == head
        # The first merge fast-forwards main, so the head merges the second source commit into the first one.
        parents = [gogs_repo_branch_commit(gogs_server.container, first.name, f"main^{number}") for number in (1, 2)]
        assert parents == [first.source_commit, second.source_commit]

    async def test_remote_advanced_is_imported(
        self,
        db: InfrahubDatabase,
        client: InfrahubClient,
        gogs_server: GogsServer,
        caplog: pytest.LogCaptureFixture,
        synced_branch_repository: Callable[..., Awaitable[SyncedBranchRepository]],
        reject_pushes_to_main: Callable[[str], Callable[[], None]],
    ) -> None:
        """A retry replays a merge onto a remote that moved meanwhile, records the result, then imports it."""
        await load_schema(db=db, schema=CAR_SCHEMA, update_db=True)
        person = await Node.init(schema=TestKind.PERSON, db=db)
        await person.new(db=db, name="Ada")
        await person.save(db=db)
        group = await Node.init(schema=InfrahubKind.STANDARDGROUP, db=db)
        await group.new(db=db, name=CARD_GROUP, members=[person])
        await group.save(db=db)
        # The artifact definition is on the default branch before the branch forks, so only the remote changes it.
        repository = await synced_branch_repository("delivery-remote-advanced", trunk_files=_card_files(version=1))
        lift_rejection = reject_pushes_to_main(repository.name)
        await client.branch.merge(branch_name=repository.branch_name)
        assert (await _delivery_state(db=db, repository_id=repository.node_id)).cause == (
            RepositoryDeliveryFailureCause.PERMISSION
        )
        assert await _card_artifacts(db=db, client=client) == [("card-v1", "Card v1 of Ada")]
        # Someone else pushes to the default branch of the remote while the merge waits.
        lift_rejection()
        advanced = commit_to_remote_branch(
            gogs_server.container, repository.name, branch="main", files=_card_files(version=2)
        )

        with caplog.at_level(logging.INFO, logger=SYNC_LOGGER):
            await self._retry_delivery(client=client, repository=repository)

        assert await _retry_states(client=client, repository_id=repository.node_id) == [TaskState.COMPLETED]
        head = gogs_repo_branch_commit(gogs_server.container, repository.name, "main")
        state = await _delivery_state(db=db, repository_id=repository.node_id)
        assert (
            state.status,
            state.cause,
            state.error,
            state.queue.entries,
            state.queue.import_owed_commit,
            state.last_delivered_commit,
        ) == (RepositoryDeliveryStatus.NONE, None, None, (), None, head)
        assert await _recorded_commit(db=db, repository_id=repository.node_id) == head
        parents = [
            gogs_repo_branch_commit(gogs_server.container, repository.name, f"main^{number}") for number in (1, 2)
        ]
        assert parents == [advanced, repository.source_commit]
        assert [
            record.getMessage()
            for record in caplog.records
            if record.name == SYNC_LOGGER
            and record.getMessage().startswith(("An import of ", "Recorded ", "Imported "))
            and record.getMessage().endswith(f" for repository {repository.name}.")
        ] == [
            f"An import of {head} is owed for repository {repository.name}.",
            f"Recorded {head} for repository {repository.name}.",
            f"Imported {head} for repository {repository.name}.",
        ]
        # The import renders at the recorded commit, so a render before the record would give the first card.
        assert await _card_artifacts(db=db, client=client) == [("card-v2", "Card v2 of Ada")]

    async def test_observed_after_record_failure(
        self,
        db: InfrahubDatabase,
        client: InfrahubClient,
        gogs_server: GogsServer,
        caplog: pytest.LogCaptureFixture,
        fast_forward_merges: None,
        synced_branch_repository: Callable[[str], Awaitable[SyncedBranchRepository]],
        block_commit_worktree: Callable[[Path], Callable[[], None]],
    ) -> None:
        """A retry after a push whose record failed records the commit that the remote holds and pushes nothing again."""
        repository = await synced_branch_repository("delivery-observed")
        repo = await InfrahubRepository.init(
            id=repository.node_id, name=repository.name, client=client, infrahub_branch_name=registry.default_branch
        )
        # The pull of the branch made the worktree of the commit that the merge fast-forwards to, and a record reuses it.
        blocked_directory = repo.directory_commits / repository.source_commit
        repo.get_git_repo_main().git.worktree("remove", "--force", str(blocked_directory))
        release_blocked_directory = block_commit_worktree(blocked_directory)

        await client.branch.merge(branch_name=repository.branch_name)

        failed = await _delivery_state(db=db, repository_id=repository.node_id)
        assert [(entry.source_branch, entry.source_commit) for entry in failed.queue.entries] == [
            (repository.branch_name, repository.source_commit)
        ]
        assert (failed.status, failed.cause, failed.error) == (
            RepositoryDeliveryStatus.ACTION_REQUIRED,
            RepositoryDeliveryFailureCause.RECORD_FAILED,
            "The record step of the delivery failed with RepositoryError.",
        )
        assert await _recorded_commit(db=db, repository_id=repository.node_id) == repository.trunk_commit
        assert gogs_repo_branch_commit(gogs_server.container, repository.name, "main") == repository.source_commit
        release_blocked_directory()

        with caplog.at_level(logging.INFO, logger=SYNC_LOGGER):
            await self._retry_delivery(client=client, repository=repository)

        assert await _retry_states(client=client, repository_id=repository.node_id) == [TaskState.COMPLETED]
        assert [
            record.getMessage()
            for record in caplog.records
            if record.name == SYNC_LOGGER
            and record.getMessage().startswith(f"The remote of repository {repository.name} ")
        ] == [
            f"The remote of repository {repository.name} already holds the merges ['{failed.queue.entries[0].entry_id}']."
        ]
        state = await _delivery_state(db=db, repository_id=repository.node_id)
        # The first attempt stopped before it settled and the retry pushed nothing, so no delivered commit is set.
        assert (
            state.status,
            state.cause,
            state.error,
            state.queue.entries,
            state.queue.import_owed_commit,
            state.last_delivered_commit,
        ) == (RepositoryDeliveryStatus.NONE, None, None, (), None, None)
        assert await _recorded_commit(db=db, repository_id=repository.node_id) == repository.source_commit
        assert gogs_repo_branch_commit(gogs_server.container, repository.name, "main") == repository.source_commit

    async def test_concurrent_attempts(
        self,
        db: InfrahubDatabase,
        client: InfrahubClient,
        gogs_server: GogsServer,
        fast_forward_merges: None,
        synced_branch_repository: Callable[[str], Awaitable[SyncedBranchRepository]],
    ) -> None:
        """A retry run after the queue was delivered finds nothing pending and changes only its progress times."""
        repository = await synced_branch_repository("delivery-concurrent-attempts")
        await client.branch.merge(branch_name=repository.branch_name)
        delivered = await _delivery_state(db=db, repository_id=repository.node_id)
        assert (delivered.status, delivered.queue.entries, delivered.last_delivered_commit) == (
            RepositoryDeliveryStatus.NONE,
            (),
            repository.source_commit,
        )

        # A retry sent while the merge was queued waits for the repository lock, so it runs after the merge's attempt.
        final_state = await retry_repository_delivery(
            model=GitRepositoryDeliveryRetry(repository_id=repository.node_id, repository_name=repository.name),
            return_state=True,
        )

        assert (final_state.type, final_state.message) == (
            StateType.COMPLETED,
            f"The delivery to repository {repository.name} ended with the outcome nothing-pending.",
        )
        # The attempt stamps its start before it reads the queue, so only its progress times move.
        after = await _delivery_state(db=db, repository_id=repository.node_id)
        assert (replace(after, progress=delivered.progress), after.progress.retry_due_at) == (delivered, None)
        assert await _recorded_commit(db=db, repository_id=repository.node_id) == repository.source_commit
        assert gogs_repo_branch_commit(gogs_server.container, repository.name, "main") == repository.source_commit


async def _tracked_graph_state(db: InfrahubDatabase, tracked: TrackedBranchRepository) -> tuple[str | None, str | None]:
    """Return the commit and the synchronisation status the graph records for the tracked branch."""
    repository: CoreRepository = await NodeManager.get_one(
        db=db, id=tracked.node_id, kind=InfrahubKind.REPOSITORY, branch=tracked.branch_name, raise_on_error=True
    )
    return repository.commit.value, repository.sync_status.value


async def _tracked_query_names(db: InfrahubDatabase, tracked: TrackedBranchRepository) -> set[str]:
    queries: list[CoreGraphQLQuery] = await NodeManager.query(
        db=db,
        schema=InfrahubKind.GRAPHQLQUERY,
        branch=tracked.branch_name,
        filters={"repository__ids": [tracked.node_id]},
    )
    return {query.name.value for query in queries}


def _tracked_reconciliation_messages(caplog: pytest.LogCaptureFixture, tracked: TrackedBranchRepository) -> list[str]:
    prefix = f"Reconciled branch {tracked.branch_name} of repository {tracked.name} "
    return [
        record.getMessage()
        for record in caplog.records
        if record.name == SYNC_LOGGER and record.getMessage().startswith(prefix)
    ]


@contextmanager
def repositories_directory(directory: Path) -> Generator[None, None, None]:
    """Run the block as a worker whose clones live in ``directory``."""
    original = config.SETTINGS.git.repositories_directory
    config.SETTINGS.git.repositories_directory = str(directory)
    try:
        yield
    finally:
        config.SETTINGS.git.repositories_directory = original


class FreshRepositoryLoader:
    """Builds the repository from the current repositories directory, as a worker with a disk of its own does."""

    def __init__(self, client: InfrahubClient) -> None:
        self._client = client

    async def load(self, message: RefreshGitFetch) -> InfrahubRepository:
        return await InfrahubRepository.init(
            id=message.repository_id,
            name=message.repository_name,
            client=self._client,
            infrahub_branch_name=message.infrahub_branch_name,
        )


class TestRewrittenBranchSynchronisation(TestInfrahubApp):
    """Periodic synchronisation cycles against a remote whose branches move or are rewritten.

    The cycle visits every repository of the stack, so these tests run in a stack of their own.
    """

    @pytest.fixture(autouse=True)
    def capture_sync_logs(self, caplog: pytest.LogCaptureFixture) -> None:
        caplog.set_level(logging.INFO, logger=SYNC_LOGGER)

    async def test_a_force_pushed_branch_is_reconciled_and_imported_again(
        self,
        db: InfrahubDatabase,
        gogs_server: GogsServer,
        caplog: pytest.LogCaptureFixture,
        tracked_branch_repository: Callable[[str, str], Awaitable[TrackedBranchRepository]],
    ) -> None:
        tracked = await tracked_branch_repository("force-pushed-repo", "force-pushed-branch")
        rewritten = commit_to_remote_branch(
            gogs_server.container,
            tracked.name,
            branch=tracked.branch_name,
            files=tracked_branch_files(repo_name=tracked.name, version=2),
            amend=True,
        )

        await sync_remote_repositories()

        assert await _tracked_graph_state(db=db, tracked=tracked) == (rewritten, RepositorySyncStatus.IN_SYNC.value)
        assert await _tracked_query_names(db=db, tracked=tracked) == {"force_pushed_repo_v2"}
        main: CoreRepository = await NodeManager.get_one(
            db=db, id=tracked.node_id, kind=InfrahubKind.REPOSITORY, raise_on_error=True
        )
        assert main.operational_status.value == RepositoryOperationalStatus.ONLINE.value
        assert _tracked_reconciliation_messages(caplog=caplog, tracked=tracked) == [
            f"Reconciled branch {tracked.branch_name} of repository {tracked.name} with the remote history: "
            f"{tracked.imported_commit} was discarded and replaced by {rewritten}"
        ]

    async def test_a_force_pushed_branch_is_recorded_once_however_many_cycles_run(
        self,
        db: InfrahubDatabase,
        gogs_server: GogsServer,
        tracked_branch_repository: Callable[[str, str], Awaitable[TrackedBranchRepository]],
    ) -> None:
        """The record has attributes of its own, so the synchronisation status does not change."""
        tracked = await tracked_branch_repository("recorded-rewrite-repo", "recorded-rewrite-branch")
        _, sync_status_before = await _tracked_graph_state(db=db, tracked=tracked)
        rewritten = commit_to_remote_branch(
            gogs_server.container,
            tracked.name,
            branch=tracked.branch_name,
            files=tracked_branch_files(repo_name=tracked.name, version=2),
            amend=True,
        )
        started_at = datetime.now(tz=UTC)

        for _ in range(3):
            await sync_remote_repositories()

        finished_at = datetime.now(tz=UTC)
        on_branch: CoreRepository = await NodeManager.get_one(
            db=db, id=tracked.node_id, kind=InfrahubKind.REPOSITORY, branch=tracked.branch_name, raise_on_error=True
        )
        assert (
            on_branch.last_rewrite_previous_commit.value,
            on_branch.last_rewrite_commit.value,
            on_branch.rewrite_count.value,
        ) == (tracked.imported_commit, rewritten, 1)
        assert on_branch.last_rewrite_at.value is not None
        assert started_at <= datetime.fromisoformat(on_branch.last_rewrite_at.value) <= finished_at
        assert (sync_status_before, on_branch.sync_status.value) == (
            RepositorySyncStatus.IN_SYNC.value,
            RepositorySyncStatus.IN_SYNC.value,
        )
        on_trunk: CoreRepository = await NodeManager.get_one(
            db=db, id=tracked.node_id, kind=InfrahubKind.REPOSITORY, raise_on_error=True
        )
        assert (
            on_trunk.last_rewrite_previous_commit.value,
            on_trunk.last_rewrite_commit.value,
            on_trunk.last_rewrite_at.value,
            on_trunk.rewrite_count.value,
        ) == (None, None, None, None)

    async def test_a_fast_forwarded_branch_is_imported_without_a_reconciliation(
        self,
        db: InfrahubDatabase,
        gogs_server: GogsServer,
        caplog: pytest.LogCaptureFixture,
        tracked_branch_repository: Callable[[str, str], Awaitable[TrackedBranchRepository]],
    ) -> None:
        tracked = await tracked_branch_repository("fast-forward-repo", "fast-forward-branch")
        advanced = commit_to_remote_branch(
            gogs_server.container,
            tracked.name,
            branch=tracked.branch_name,
            files=tracked_branch_files(repo_name=tracked.name, version=2),
        )

        await sync_remote_repositories()

        assert await _tracked_graph_state(db=db, tracked=tracked) == (advanced, RepositorySyncStatus.IN_SYNC.value)
        assert await _tracked_query_names(db=db, tracked=tracked) == {"fast_forward_repo_v2"}
        assert _tracked_reconciliation_messages(caplog=caplog, tracked=tracked) == []

    async def test_a_cycle_records_the_commit_a_worktree_already_holds(
        self,
        db: InfrahubDatabase,
        client: InfrahubClient,
        tracked_branch_repository: Callable[[str, str], Awaitable[TrackedBranchRepository]],
    ) -> None:
        """Nothing moved in git, so only the commits the cycle reads from the graph can show the gap."""
        tracked = await tracked_branch_repository("graph-behind-repo", "graph-behind-branch")
        repo = await InfrahubRepository.init(
            id=tracked.node_id, name=tracked.name, client=client, infrahub_branch_name=registry.default_branch
        )
        await repo.update_commit_value(branch_name=tracked.branch_name, commit=tracked.trunk_commit)

        await sync_remote_repositories()

        assert await _tracked_graph_state(db=db, tracked=tracked) == (
            tracked.imported_commit,
            RepositorySyncStatus.IN_SYNC.value,
        )

    async def test_a_branch_created_in_infrahub_records_the_commit_it_was_created_at(
        self,
        db: InfrahubDatabase,
        client: InfrahubClient,
        gogs_server: GogsServer,
        tracked_branch_repository: Callable[[str, str], Awaitable[TrackedBranchRepository]],
    ) -> None:
        """This worker's trunk is ahead of the commit the graph records for it when the branch is created.

        The new branch therefore starts at a commit its origin branch never recorded, which is the one
        it must read.
        """
        tracked = await tracked_branch_repository("created-branch-repo", "created-branch-tracked")
        repo = await InfrahubRepository.init(
            id=tracked.node_id, name=tracked.name, client=client, infrahub_branch_name=registry.default_branch
        )
        commit_to_remote_branch(
            gogs_server.container, tracked.name, branch="main", files={"trunk_ahead.txt": "trunk ahead\n"}
        )
        await repo.fetch()
        await repo.pull(branch_name="main", update_commit_value=False)

        branch = await client.branch.create(branch_name="created-in-infrahub", sync_with_git=True)

        created_at = gogs_repo_branch_commit(gogs_server.container, tracked.name, branch.name)
        assert created_at != tracked.trunk_commit
        repository: CoreRepository = await NodeManager.get_one(
            db=db, id=tracked.node_id, kind=InfrahubKind.REPOSITORY, branch=branch.name, raise_on_error=True
        )
        assert repository.commit.value == created_at

    async def test_a_failed_branch_does_not_keep_another_worker_off_a_healthy_branch(
        self,
        client: InfrahubClient,
        gogs_server: GogsServer,
        bus_simulator: BusSimulator,
        tmp_path: Path,
        tracked_branch_repository: Callable[[str, str], Awaitable[TrackedBranchRepository]],
    ) -> None:
        """A second worker with a clone of its own converges the healthy branch from the cycle's message alone."""
        tracked = await tracked_branch_repository("partly-failing-cycle-repo", "healthy-cycle-branch")
        main = await client.branch.get(branch_name=registry.default_branch)
        healthy = await client.branch.get(branch_name=tracked.branch_name)
        second_worker = tmp_path / "second-worker-repositories"
        second_worker.mkdir()
        with repositories_directory(second_worker):
            clone = await InfrahubRepository.init(
                id=tracked.node_id, name=tracked.name, client=client, infrahub_branch_name=registry.default_branch
            )
            await clone.create_branch_in_git(branch_name=tracked.branch_name, branch_id=healthy.id, push_origin=False)
            assert clone.get_commit_value(branch_name=tracked.branch_name, remote=False) == tracked.imported_commit

        await client.branch.create(branch_name="broken-cycle-branch", sync_with_git=False)
        commit_to_remote_branch(
            gogs_server.container,
            tracked.name,
            branch="broken-cycle-branch",
            files={".infrahub.yml": "schemas: [unclosed\n"},
        )
        advanced = commit_to_remote_branch(
            gogs_server.container,
            tracked.name,
            branch=tracked.branch_name,
            files=tracked_branch_files(repo_name=tracked.name, version=2),
        )
        sent_before = len(bus_simulator.messages)

        await sync_remote_repositories()

        cycle_messages = [
            message
            for message in bus_simulator.messages[sent_before:]
            if isinstance(message, RefreshGitFetch) and message.repository_id == tracked.node_id
        ]
        assert [message.branches for message in cycle_messages] == [
            (
                BranchCommitPair(infrahub_branch_name="main", infrahub_branch_id=main.id, commit=tracked.trunk_commit),
                BranchCommitPair(
                    infrahub_branch_name=tracked.branch_name, infrahub_branch_id=healthy.id, commit=advanced
                ),
            )
        ]

        with repositories_directory(second_worker):
            converger = WorktreeConverger(
                lock_registry=lock.registry,
                loader=FreshRepositoryLoader(client=client),
                worker_identity="second-worker",
            )
            await converger.converge(cycle_messages[0])
            converged = await InfrahubRepository.init(
                id=tracked.node_id, name=tracked.name, client=client, infrahub_branch_name=registry.default_branch
            )
            assert converged.get_commit_value(branch_name=tracked.branch_name, remote=False) == advanced
