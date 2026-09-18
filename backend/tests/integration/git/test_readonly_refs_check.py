"""Read-only refs check against a live remote.

The check exists to notice that a tracked ref moved without disturbing anything Infrahub has
already imported, so each case that detects movement also asserts the tracked commit and the
imported content.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

import pytest
from git import Blob

from infrahub.core.constants import InfrahubKind
from infrahub.core.manager import NodeManager
from infrahub.git.models import GitReadOnlyRepositoryCheckRefs, TrackedRef
from infrahub.git.refs_check.checker import ReadOnlyRepositoryRefsChecker, RefNameValidator, RefsCheckScheduler
from infrahub.git.refs_check.gateway import GitRepositoryRefsGateway, git_check_ref_format
from infrahub.git.repository import InfrahubReadOnlyRepository
from tests.adapters.cache import ClaimAwareCache
from tests.adapters.lock import LockTimeline, RecordingLockRegistry
from tests.adapters.message_bus import BusRecorder
from tests.helpers.test_app import TestInfrahubApp
from tests.integration.git.conftest import create_gogs_repo

if TYPE_CHECKING:
    from pathlib import Path

    from infrahub_sdk import InfrahubClient
    from testcontainers.core.container import DockerContainer

    from infrahub.core.protocols import CoreReadOnlyRepository
    from infrahub.database import InfrahubDatabase
    from tests.helpers.git import GogsServer


def _run_in_remote(container: DockerContainer, repo_name: str, script: str) -> None:
    full_script = f"set -e && cd /tmp/{repo_name} && {script}"
    result = container.get_wrapped_container().exec_run(["bash", "-c", full_script], user="git")
    assert result.exit_code == 0, f"Remote command failed (exit {result.exit_code}): {result.output.decode()}"


def advance_branch(container: DockerContainer, repo_name: str, filename: str, branch: str = "main") -> None:
    _run_in_remote(
        container,
        repo_name,
        f"git checkout {branch} && git pull origin {branch} && echo 'advanced' > {filename} && "
        f"git add {filename} && git commit -m 'Advance {branch}' && git push origin {branch}",
    )


def rewrite_branch_head(container: DockerContainer, repo_name: str, branch: str = "main") -> None:
    _run_in_remote(
        container,
        repo_name,
        f"git checkout {branch} && git commit --amend -m 'Rewritten history' && git push --force origin {branch}",
    )


def create_tag(container: DockerContainer, repo_name: str, tag: str, branch: str = "main") -> None:
    """Create an annotated tag, which is the shape a release tag usually takes.

    An annotated tag publishes both a tag object and the commit it peels to, and the two carry
    different hashes; a lightweight tag publishes one line and hides that distinction.
    """
    _run_in_remote(
        container, repo_name, f"git checkout {branch} && git tag -a {tag} -m 'Release {tag}' && git push origin {tag}"
    )


def move_tag(container: DockerContainer, repo_name: str, tag: str, branch: str = "main") -> None:
    _run_in_remote(
        container,
        repo_name,
        f"git checkout {branch} && git tag -f -a {tag} -m 'Release {tag}' && git push --force origin refs/tags/{tag}",
    )


def delete_tag(container: DockerContainer, repo_name: str, tag: str) -> None:
    _run_in_remote(container, repo_name, f"git tag -d {tag} && git push origin :refs/tags/{tag}")


class TestReadOnlyRefsCheck(TestInfrahubApp):
    @pytest.fixture(scope="class")
    def timeline(self) -> LockTimeline:
        return LockTimeline()

    @pytest.fixture(scope="class")
    def bus(self) -> BusRecorder:
        return BusRecorder()

    @pytest.fixture(scope="class")
    def cache(self) -> ClaimAwareCache:
        return ClaimAwareCache()

    @pytest.fixture(scope="class")
    async def branch_tracking_dataset(
        self,
        initialize_registry: None,
        git_repos_dir_module_scope: Path,
        client: InfrahubClient,
        gogs_server: GogsServer,
    ) -> dict:
        repo_name = "refs-check-branch-repo"
        repo_url = create_gogs_repo(gogs_server.base_url, gogs_server.token, repo_name, gogs_server.container)
        node = await client.create(
            kind=InfrahubKind.READONLYREPOSITORY,
            name=repo_name,
            location=repo_url,
            ref="main",
        )
        await node.save()
        return {"repo_name": repo_name, "node_id": node.id, "location": repo_url, "ref": "main"}

    @pytest.fixture(scope="class")
    async def tag_tracking_dataset(
        self,
        initialize_registry: None,
        git_repos_dir_module_scope: Path,
        client: InfrahubClient,
        gogs_server: GogsServer,
    ) -> dict:
        repo_name = "refs-check-tag-repo"
        repo_url = create_gogs_repo(gogs_server.base_url, gogs_server.token, repo_name, gogs_server.container)
        create_tag(gogs_server.container, repo_name, "release")
        node = await client.create(
            kind=InfrahubKind.READONLYREPOSITORY,
            name=repo_name,
            location=repo_url,
            ref="release",
        )
        await node.save()
        return {"repo_name": repo_name, "node_id": node.id, "location": repo_url, "ref": "release"}

    def build_checker(
        self, cache: ClaimAwareCache, bus: BusRecorder, timeline: LockTimeline, client: InfrahubClient
    ) -> ReadOnlyRepositoryRefsChecker:
        return ReadOnlyRepositoryRefsChecker(
            cache=cache,
            message_bus=bus,
            lock_registry=RecordingLockRegistry(timeline=timeline),
            gateway=GitRepositoryRefsGateway(client=client),
            ref_validator=RefNameValidator(check_ref_format=git_check_ref_format),
            scheduler=RefsCheckScheduler(cache=cache, interval_seconds=900, retry_seconds=300),
            claim_ttl_seconds=180,
            detect_timeout_seconds=120,
        )

    async def build_model(self, db: InfrahubDatabase, dataset: dict) -> GitReadOnlyRepositoryCheckRefs:
        repository: CoreReadOnlyRepository = await NodeManager.get_one(
            db=db, id=dataset["node_id"], kind=InfrahubKind.READONLYREPOSITORY, raise_on_error=True
        )
        return GitReadOnlyRepositoryCheckRefs(
            repository_id=dataset["node_id"],
            repository_name=dataset["repo_name"],
            location=dataset["location"],
            refs=(
                TrackedRef(
                    infrahub_branch_name="main",
                    infrahub_branch_id="main-branch-id",
                    ref=dataset["ref"],
                    commit=repository.commit.value,
                ),
            ),
        )

    async def tracked_commit(self, db: InfrahubDatabase, dataset: dict) -> str | None:
        repository: CoreReadOnlyRepository = await NodeManager.get_one(
            db=db, id=dataset["node_id"], kind=InfrahubKind.READONLYREPOSITORY, raise_on_error=True
        )
        return repository.commit.value

    def assert_commit_readable(self, dataset: dict, commit: str) -> None:
        """The imported commit's objects must still be present in this worker's clone.

        Its own worktree is what keeps them reachable once a ref stops pointing at them.
        """
        repo = InfrahubReadOnlyRepository(  # type: ignore[call-arg]
            id=UUID(dataset["node_id"]), name=dataset["repo_name"], location=dataset["location"]
        )
        repo.validate_local_directories()
        assert commit in {worktree.identifier for worktree in repo.get_worktrees()}
        tree = repo.get_git_repo_main().commit(commit).tree
        assert ".infrahub.yml" in [blob.path for blob in tree.traverse() if isinstance(blob, Blob)]

    async def test_step01_an_unchanged_remote_reports_no_movement_and_takes_no_lock(
        self,
        db: InfrahubDatabase,
        branch_tracking_dataset: dict,
        client: InfrahubClient,
        cache: ClaimAwareCache,
        bus: BusRecorder,
        timeline: LockTimeline,
    ) -> None:
        model = await self.build_model(db, branch_tracking_dataset)
        checker = self.build_checker(cache, bus, timeline, client)
        lock_name = f"repository.{branch_tracking_dataset['repo_name']}"

        result = await checker.check(model, run_id="step01")

        assert result.movements == ()
        assert result.failure_reason is None
        # Nothing moved, so the repository lock was never taken and no concurrent import of the
        # same repository could have been made to wait on this remote.
        assert timeline.acquire_sequence(prefix=lock_name) == []
        assert bus.messages == []

    async def test_step02_an_advanced_branch_moves_without_touching_the_tracked_commit(
        self,
        db: InfrahubDatabase,
        branch_tracking_dataset: dict,
        client: InfrahubClient,
        gogs_server: GogsServer,
        cache: ClaimAwareCache,
        bus: BusRecorder,
        timeline: LockTimeline,
    ) -> None:
        imported_commit = await self.tracked_commit(db, branch_tracking_dataset)
        assert imported_commit

        advance_branch(gogs_server.container, branch_tracking_dataset["repo_name"], "advanced.txt")

        model = await self.build_model(db, branch_tracking_dataset)
        checker = self.build_checker(cache, bus, timeline, client)
        lock_name = f"repository.{branch_tracking_dataset['repo_name']}"

        result = await checker.check(model, run_id="step02")

        assert [movement.ref for movement in result.movements] == ["main"]
        assert result.movements[0].previous_head == imported_commit
        assert result.movements[0].new_head != imported_commit
        assert await self.tracked_commit(db, branch_tracking_dataset) == imported_commit
        self.assert_commit_readable(branch_tracking_dataset, imported_commit)
        # The convergence steps are serialised against other work on the local copy; the listing is not.
        assert timeline.acquire_sequence(prefix=lock_name) == [lock_name]
        assert [message.commit for message in bus.messages] == [imported_commit]

    async def test_step03_a_rewritten_branch_moves_without_losing_the_imported_commit(
        self,
        db: InfrahubDatabase,
        branch_tracking_dataset: dict,
        client: InfrahubClient,
        gogs_server: GogsServer,
        cache: ClaimAwareCache,
        bus: BusRecorder,
        timeline: LockTimeline,
    ) -> None:
        imported_commit = await self.tracked_commit(db, branch_tracking_dataset)
        assert imported_commit

        rewrite_branch_head(gogs_server.container, branch_tracking_dataset["repo_name"])

        model = await self.build_model(db, branch_tracking_dataset)
        checker = self.build_checker(cache, bus, timeline, client)

        result = await checker.check(model, run_id="step03")

        assert [movement.ref for movement in result.movements] == ["main"]
        assert await self.tracked_commit(db, branch_tracking_dataset) == imported_commit
        self.assert_commit_readable(branch_tracking_dataset, imported_commit)

    async def test_step04_an_unchanged_annotated_tag_reports_no_movement(
        self,
        db: InfrahubDatabase,
        tag_tracking_dataset: dict,
        client: InfrahubClient,
        cache: ClaimAwareCache,
        bus: BusRecorder,
        timeline: LockTimeline,
    ) -> None:
        """An annotated tag publishes a tag object and a peeled commit with different hashes.

        Comparing the wrong one of the two against the local read would report movement on every
        check of a tag that has not moved, and no fetch could ever make the two agree.
        """
        model = await self.build_model(db, tag_tracking_dataset)
        checker = self.build_checker(cache, bus, timeline, client)
        messages_before = len(bus.messages)

        result = await checker.check(model, run_id="step04")

        assert result.movements == ()
        assert result.failure_reason is None
        assert len(bus.messages) == messages_before

    async def test_step05_a_moved_tag_moves_without_touching_the_tracked_commit(
        self,
        db: InfrahubDatabase,
        tag_tracking_dataset: dict,
        client: InfrahubClient,
        gogs_server: GogsServer,
        cache: ClaimAwareCache,
        bus: BusRecorder,
        timeline: LockTimeline,
    ) -> None:
        imported_commit = await self.tracked_commit(db, tag_tracking_dataset)
        assert imported_commit
        messages_before = len(bus.messages)

        advance_branch(gogs_server.container, tag_tracking_dataset["repo_name"], "tagged_change.txt")
        move_tag(gogs_server.container, tag_tracking_dataset["repo_name"], "release")

        model = await self.build_model(db, tag_tracking_dataset)
        checker = self.build_checker(cache, bus, timeline, client)

        result = await checker.check(model, run_id="step05")

        assert [movement.ref for movement in result.movements] == ["release"]
        assert await self.tracked_commit(db, tag_tracking_dataset) == imported_commit
        self.assert_commit_readable(tag_tracking_dataset, imported_commit)
        # The pool is told to pick up the objects the tag now reaches, still pinned to the
        # commit Infrahub imported.
        assert [message.commit for message in bus.messages[messages_before:]] == [imported_commit]

    async def test_step06_a_deleted_tag_reports_no_movement_and_no_failure(
        self,
        db: InfrahubDatabase,
        tag_tracking_dataset: dict,
        client: InfrahubClient,
        gogs_server: GogsServer,
        cache: ClaimAwareCache,
        bus: BusRecorder,
        timeline: LockTimeline,
    ) -> None:
        imported_commit = await self.tracked_commit(db, tag_tracking_dataset)
        assert imported_commit

        delete_tag(gogs_server.container, tag_tracking_dataset["repo_name"], "release")

        model = await self.build_model(db, tag_tracking_dataset)
        checker = self.build_checker(cache, bus, timeline, client)

        result = await checker.check(model, run_id="step06")

        assert result.movements == ()
        assert result.failure_reason is None
        assert await self.tracked_commit(db, tag_tracking_dataset) == imported_commit
        self.assert_commit_readable(tag_tracking_dataset, imported_commit)
