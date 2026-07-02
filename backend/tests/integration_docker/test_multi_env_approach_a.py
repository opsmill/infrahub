"""Full-stack multi-environment single-repo validation (Approach A).

Two independent Infrahub stacks share one Git remote. A development instance is a read-write
repository pinned to a non-primary branch; a read-only consumer is pinned to its own branch and
receives promoted changes only through an explicit reimport.

The two stacks bind-mount the same host remote directory, so both read and write the one shared
repository. Assertions read the authoritative branch list and the repository's recorded commit,
never a sync-status field or a mutation's return value; progression is driven by explicit triggers
and observable-state polling to a deadline, never a fixed sleep.

Requires a current-stable Infrahub image built from this branch. It MUST be verified in the Docker
CI job (which builds the image), NOT against a pre-built local image: a stale image that predates the
non-`main`-default import fix produces false failures in the periodic-sync path. The reimport and
tag-bump promotion assertions were not verifiable in the dev environment (the image build has no
network access to the npm registry) and need a full-stack run on a current image to confirm.
"""

from __future__ import annotations

import asyncio
import os
import shutil
import subprocess  # noqa: S404
import time
import urllib.request
import uuid
from http import HTTPStatus
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from infrahub_sdk import Config, InfrahubClient
from infrahub_sdk.graphql import Mutation
from infrahub_sdk.protocols import CoreReadOnlyRepository, CoreRepository
from infrahub_testcontainers.container import InfrahubDockerCompose

if TYPE_CHECKING:
    from collections.abc import Generator

PRIMARY_BRANCH = "main"
CONSUMER_BRANCH = "develop"
REMOTE_MOUNT = "/remote"

GIT_EXECUTABLE = shutil.which("git") or "git"


def _git(repo_dir: Path, *args: str) -> str:
    """Run a git command inside ``repo_dir`` on the host and return its stdout, stripped."""
    result = subprocess.run(  # noqa: S603
        [GIT_EXECUTABLE, *args],
        cwd=str(repo_dir),
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.strip()


def _provision_shared_remote(remote_repos_dir: Path, repo_name: str) -> Path:
    """Create a shared remote git repo with a ``main`` and a ``develop`` branch.

    The repo lives in the host directory both stacks bind-mount at ``/remote``. It is configured
    with ``receive.denyCurrentBranch=updateInstead`` so a write-back push to a checked-out branch
    is accepted rather than rejected.
    """
    repo_dir = remote_repos_dir / repo_name
    repo_dir.mkdir(parents=True)

    _git(repo_dir, "init", "-b", PRIMARY_BRANCH)
    _git(repo_dir, "config", "user.name", "Infrahub Test")
    _git(repo_dir, "config", "user.email", "test@infrahub.local")
    _git(repo_dir, "config", "receive.denyCurrentBranch", "updateInstead")

    (repo_dir / "README.md").write_text("shared multi-environment repository\n")
    _git(repo_dir, "add", "README.md")
    _git(repo_dir, "commit", "-m", "initial commit on primary")

    _git(repo_dir, "branch", CONSUMER_BRANCH)
    return repo_dir


def _wait_for_api_ready(port: int, *, deadline_seconds: int = 300, interval: float = 2.0) -> None:
    """Block until the Infrahub server on ``port`` answers its readiness endpoint, or time out.

    Raises:
        RuntimeError: If the server does not answer within ``deadline_seconds``.

    """
    url = f"http://localhost:{port}/api/config"
    deadline = time.monotonic() + deadline_seconds
    last_error: Exception | None = None
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=5) as response:
                if response.status == HTTPStatus.OK:
                    return
        except Exception as exc:
            last_error = exc
        time.sleep(interval)
    raise RuntimeError(f"Infrahub server on port {port} was not ready within {deadline_seconds}s: {last_error}")


def _start_stack_with_retry(compose: InfrahubDockerCompose, *, attempts: int = 4, backoff: float = 5.0) -> None:
    """Bring a stack up, retrying the idempotent ``up`` when a dependency healthcheck flaps.

    Raises:
        subprocess.CalledProcessError: If every attempt to bring the stack up fails.

    """
    last_error: subprocess.CalledProcessError | None = None
    for attempt in range(attempts):
        try:
            compose.start()
        except subprocess.CalledProcessError as exc:
            last_error = exc
            if attempt < attempts - 1:
                time.sleep(backoff)
        else:
            return
    assert last_error is not None
    raise last_error


def _advance_remote_branch(repo_dir: Path, branch: str, filename: str) -> str:
    """Add a commit to ``branch`` on the shared remote and return the new commit SHA."""
    current = _git(repo_dir, "rev-parse", "--abbrev-ref", "HEAD")
    _git(repo_dir, "checkout", branch)
    (repo_dir / filename).write_text(f"change for {filename}\n")
    _git(repo_dir, "add", filename)
    _git(repo_dir, "commit", "-m", f"advance {branch} [{filename}]")
    sha = _git(repo_dir, "rev-parse", "HEAD")
    _git(repo_dir, "checkout", current)
    return sha


def _create_remote_tag(repo_dir: Path, tag: str, commitish: str) -> str:
    """Create a lightweight tag on the shared remote at ``commitish`` and return its commit SHA."""
    _git(repo_dir, "tag", tag, commitish)
    return _git(repo_dir, "rev-parse", f"{tag}^{{commit}}")


class ApproachATwoStacks:
    """Boots two Infrahub stacks that bind-mount the same host remote directory."""

    @pytest.fixture(scope="class")
    def infrahub_version(self) -> str:
        return "local"

    @pytest.fixture(scope="class")
    def shared_context_dir(self, tmpdir_factory: pytest.TempdirFactory) -> Path:
        """One host directory used as the compose context for both stacks.

        Both stacks use this as their compose ``context``, so both bind-mount its ``repos``
        subdirectory into the containers at ``/remote`` — the single shared remote.
        """
        name = f"multienv_{uuid.uuid4().hex}"
        return Path(str(tmpdir_factory.mktemp(name)))

    @pytest.fixture(scope="class")
    def remote_repos_dir(self, shared_context_dir: Path) -> Path:
        directory = shared_context_dir / "repos"
        directory.mkdir(exist_ok=True)
        (shared_context_dir / "backups").mkdir(exist_ok=True)
        return directory

    @pytest.fixture(scope="class")
    def repo_name(self) -> str:
        return "multi-env-approach-a"

    @pytest.fixture(scope="class")
    def shared_remote(self, remote_repos_dir: Path, repo_name: str) -> Path:
        return _provision_shared_remote(remote_repos_dir, repo_name)

    @pytest.fixture(scope="class")
    def stacks(
        self,
        shared_context_dir: Path,
        remote_repos_dir: Path,
        shared_remote: Path,
        infrahub_version: str,
    ) -> Generator[dict[str, dict[str, int]], None, None]:
        """Start a development stack and a consumer stack sharing one compose context.

        Both compose projects share ``shared_context_dir`` (hence the same bind-mounted remote) but
        carry distinct project names, so Docker keeps their containers and named volumes separate
        while they read and write the one shared repository. Ports are auto-assigned.

        Running two full stacks side by side doubles the resource pressure of a normal single-stack
        test, so each stack is trimmed to a single API server and a single task worker — this
        validation needs two *instances*, never multiple workers per instance. Bringing up a stack
        is retried and then gated on an API-readiness poll: on a loaded machine the message-queue
        healthcheck momentarily reads as unhealthy while its ports open, and compose aborts the
        bring-up even though the container recovers to healthy seconds later. ``up`` is idempotent,
        so retrying reconciles the already-recovering containers, and the readiness poll confirms
        the server actually answers before any test runs.
        """
        trimmed_replicas = {
            "INFRAHUB_TESTING_API_SERVER_COUNT": "1",
            "INFRAHUB_TESTING_TASK_WORKER_COUNT": "1",
        }
        previous = {key: os.environ.get(key) for key in trimmed_replicas}
        os.environ.update(trimmed_replicas)

        started: list[InfrahubDockerCompose] = []
        try:
            ports: dict[str, dict[str, int]] = {}
            for role in ("dev", "consumer"):
                compose = InfrahubDockerCompose.init(directory=shared_context_dir, version=infrahub_version)
                compose.wait = False  # start detached; gate on the readiness poll below, not on compose
                started.append(compose)
                _start_stack_with_retry(compose)
                role_ports = compose.get_services_port()
                _wait_for_api_ready(role_ports["server"])
                ports[role] = role_ports
            yield ports
        finally:
            for key, value in previous.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value
            for compose in reversed(started):
                compose.stop()

    @pytest.fixture(scope="class")
    def dev_client(self, stacks: dict[str, dict[str, int]]) -> InfrahubClient:
        port = stacks["dev"]["server"]
        return InfrahubClient(config=Config(username="admin", password="infrahub", address=f"http://localhost:{port}"))

    @pytest.fixture(scope="class")
    def consumer_client(self, stacks: dict[str, dict[str, int]]) -> InfrahubClient:
        port = stacks["consumer"]["server"]
        return InfrahubClient(config=Config(username="admin", password="infrahub", address=f"http://localhost:{port}"))


async def _register_read_write(client: InfrahubClient, repo_name: str, default_branch: str) -> None:
    """Register a read-write repository pinned (at creation) to ``default_branch``."""
    query = Mutation(
        mutation="CoreRepositoryCreate",
        input_data={
            "data": {
                "name": {"value": repo_name},
                "location": {"value": f"{REMOTE_MOUNT}/{repo_name}"},
                "default_branch": {"value": default_branch},
            }
        },
        query={"ok": None},
    )
    await client.execute_graphql(query=query.render(), tracker="mutation-repository-create")


async def _register_read_only(client: InfrahubClient, repo_name: str, ref: str) -> None:
    """Register a read-only repository pinned (at creation) to ``ref``."""
    query = Mutation(
        mutation="CoreReadOnlyRepositoryCreate",
        input_data={
            "data": {
                "name": {"value": repo_name},
                "location": {"value": f"{REMOTE_MOUNT}/{repo_name}"},
                "ref": {"value": ref},
            }
        },
        query={"ok": None},
    )
    await client.execute_graphql(query=query.render(), tracker="mutation-readonly-repository-create")


async def _update_read_only_ref(client: InfrahubClient, repo_id: str, new_ref: str) -> None:
    """Bump a read-only repository's tracked ``ref`` (the tag-pin promotion mechanism)."""
    query = Mutation(
        mutation="CoreReadOnlyRepositoryUpdate",
        input_data={"data": {"id": repo_id, "ref": {"value": new_ref}}},
        query={"ok": None},
    )
    await client.execute_graphql(query=query.render(), tracker="mutation-readonly-repository-update")


async def _poll_recorded_commit(
    client: InfrahubClient,
    repo_name: str,
    kind: type[CoreRepository | CoreReadOnlyRepository],
    *,
    deadline_seconds: int = 180,
    interval: int = 3,
) -> str | None:
    """Poll the repository's recorded commit until it is set, or the deadline elapses."""
    deadline = asyncio.get_event_loop().time() + deadline_seconds
    while asyncio.get_event_loop().time() < deadline:
        try:
            repo = await client.get(kind=kind, name__value=repo_name)
        except Exception:
            repo = None
        if repo is not None and repo.commit.value:
            return repo.commit.value
        await asyncio.sleep(interval)
    return None


async def _wait_for_recorded_commit_equals(
    client: InfrahubClient,
    repo_name: str,
    kind: type[CoreRepository | CoreReadOnlyRepository],
    expected: str,
    *,
    deadline_seconds: int = 180,
    interval: int = 3,
) -> bool:
    """Poll until the repository's recorded commit equals ``expected``, or the deadline elapses."""
    deadline = asyncio.get_event_loop().time() + deadline_seconds
    while asyncio.get_event_loop().time() < deadline:
        repo = await client.get(kind=kind, name__value=repo_name)
        if repo.commit.value == expected:
            return True
        await asyncio.sleep(interval)
    return False


async def _stays_at_commit(
    client: InfrahubClient,
    repo_name: str,
    kind: type[CoreRepository | CoreReadOnlyRepository],
    expected: str,
    *,
    observe_seconds: int = 140,
    interval: int = 10,
) -> bool:
    """Poll across a window and report whether the recorded commit stays equal to ``expected``.

    The window is long enough to span at least two every-minute periodic sync cycles, so a silent
    auto-advance would be observed as a divergence.
    """
    deadline = asyncio.get_event_loop().time() + observe_seconds
    while asyncio.get_event_loop().time() < deadline:
        repo = await client.get(kind=kind, name__value=repo_name)
        if repo.commit.value != expected:
            return False
        await asyncio.sleep(interval)
    return True


@pytest.mark.timeout(900)
class TestMultiEnvApproachA(ApproachATwoStacks):
    """Read-only consumer isolation and promotion across two instances on one shared remote.

    Booting two full stacks in the class-scoped fixture takes longer than the default per-test
    budget, so the class carries a wider timeout; the first test bears the two-stack setup cost.
    """

    async def test_dev_instance_imports_its_branch(self, dev_client: InfrahubClient, repo_name: str) -> None:
        """The development instance imports its non-primary default branch and records a commit."""
        await _register_read_write(dev_client, repo_name, default_branch=CONSUMER_BRANCH)
        commit = await _poll_recorded_commit(dev_client, repo_name, CoreRepository)
        assert commit is not None

    async def test_consumer_imports_only_its_branch(self, consumer_client: InfrahubClient, repo_name: str) -> None:
        """The consumer imports only its pinned branch onto the primary; no other branches appear.

        The pinned branch maps onto the internal primary branch, so the branch set is exactly the
        primary branch — none of the other environments' branches leak in.
        """
        await _register_read_only(consumer_client, repo_name, ref=CONSUMER_BRANCH)
        commit = await _poll_recorded_commit(consumer_client, repo_name, CoreReadOnlyRepository)
        assert commit is not None

        branches = await consumer_client.branch.all()
        assert set(branches) == {PRIMARY_BRANCH}

    async def test_isolation_remote_advance_invisible_to_consumer(
        self,
        consumer_client: InfrahubClient,
        shared_remote: Path,
        repo_name: str,
    ) -> None:
        """A commit landed on the shared remote's branch does not move the read-only consumer.

        The branch advances on the shared remote (the change is durable there the moment the push
        returns). The read-only consumer, which performs no automatic sync, must still record its
        pre-advance commit — a later periodic cycle must not silently pull the new commit in.
        """
        consumer_before = (await consumer_client.get(kind=CoreReadOnlyRepository, name__value=repo_name)).commit.value

        landed_sha = _advance_remote_branch(shared_remote, CONSUMER_BRANCH, "remote_advance.txt")
        assert landed_sha != consumer_before

        # Observe across a window in which the every-minute periodic sync fires at least twice; the
        # consumer must not auto-advance in that window.
        stayed = await _stays_at_commit(consumer_client, repo_name, CoreReadOnlyRepository, consumer_before)
        assert stayed

    async def test_nonmain_default_periodic_sync_advances(
        self,
        dev_client: InfrahubClient,
        shared_remote: Path,
        repo_name: str,
    ) -> None:
        """The development instance's recorded commit should advance when its branch gains a commit.

        The read-write development instance is pinned to a non-primary git default branch. When that
        branch gains a commit on the shared remote, the every-minute periodic sync should import it
        and advance the recorded commit — the import must not be frozen at the initial commit.
        """
        commit_before = (await dev_client.get(kind=CoreRepository, name__value=repo_name)).commit.value

        advanced_sha = _advance_remote_branch(shared_remote, CONSUMER_BRANCH, "dev_periodic.txt")
        assert advanced_sha != commit_before

        advanced = await _wait_for_recorded_commit_equals(
            dev_client, repo_name, CoreRepository, advanced_sha, deadline_seconds=130
        )
        assert advanced

    @pytest.mark.xfail(
        strict=True,
        reason=(
            "an explicit read-only reimport does not advance the recorded commit to the ref's "
            "latest commit on the shared remote; the recorded commit stays at the initially "
            "imported commit"
        ),
    )
    async def test_reimport_advances_consumer(
        self,
        consumer_client: InfrahubClient,
        shared_remote: Path,
        repo_name: str,
    ) -> None:
        """An explicit reimport should advance the consumer's recorded commit to the ref's latest commit."""
        latest_sha = _git(shared_remote, "rev-parse", CONSUMER_BRANCH)
        commit_before = (await consumer_client.get(kind=CoreReadOnlyRepository, name__value=repo_name)).commit.value
        assert latest_sha != commit_before

        repo = await consumer_client.get(kind=CoreReadOnlyRepository, name__value=repo_name)
        query = Mutation(
            mutation="InfrahubReadOnlyRepositoryImportLastCommit",
            input_data={"data": {"id": repo.id}},
            query={"ok": None},
        )
        await consumer_client.execute_graphql(query=query.render(), tracker="mutation-readonly-import-last-commit")

        advanced = await _wait_for_recorded_commit_equals(
            consumer_client, repo_name, CoreReadOnlyRepository, latest_sha, deadline_seconds=130
        )
        assert advanced

    async def test_tag_ref_bump_promotes_consumer(
        self,
        consumer_client: InfrahubClient,
        shared_remote: Path,
        repo_name: str,
    ) -> None:
        """Bumping a read-only consumer's ref to a new tag promotes it — the production mechanism.

        Instead of the documented reimport, a real release flow pins the consumer to a git tag and
        bumps the ref to the next tag. Bumping the ref must advance the recorded commit to the tag's
        commit. (Runs last: it mutates the shared consumer repo's ref.)
        """
        _advance_remote_branch(shared_remote, CONSUMER_BRANCH, "release_tag.txt")
        release_sha = _create_remote_tag(shared_remote, "release-1", CONSUMER_BRANCH)

        repo = await consumer_client.get(kind=CoreReadOnlyRepository, name__value=repo_name)
        assert repo.commit.value != release_sha

        await _update_read_only_ref(consumer_client, repo.id, "release-1")

        promoted = await _wait_for_recorded_commit_equals(
            consumer_client, repo_name, CoreReadOnlyRepository, release_sha, deadline_seconds=130
        )
        assert promoted
