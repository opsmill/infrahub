from __future__ import annotations

import logging
import os
import re
import socket
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from git.exc import GitCommandError
from infrahub_sdk import Config, InfrahubClient
from infrahub_sdk.uuidt import UUIDT

from infrahub import config
from infrahub.core.constants import RepositoryDeliveryFailureCause
from infrahub.core.registry import registry
from infrahub.exceptions import RepositoryConnectionError, RepositoryError
from infrahub.git.writeback.classifier import classify_delivery_failure
from infrahub.git.writeback.constants import LOCAL_GIT_TIMEOUT_SECONDS
from infrahub.git.writeback.git_adapter import RepositoryDeliveryGitAdapter
from infrahub.git.writeback.models import DeliveryFailure, DeliveryStage
from infrahub.git.writeback.ports import ReplayResult
from tests.adapters.message_bus import BusRecorder
from tests.helpers.git import LocalRemote, clone_repository, open_repository
from tests.helpers.test_client import dummy_async_request

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable, Iterator

    from git import Repo

    from infrahub.git.repository import InfrahubRepository

REPOSITORY_NAME = "delivery-repo"
DESTINATION = "main"
ABSENT = "0" * 40
TIME_LIMIT_MESSAGE = (
    f"The Git command for repository {REPOSITORY_NAME} did not complete within its time limit, "
    "please check that the remote is reachable."
)


@dataclass(frozen=True)
class DeliveryClone:
    """A clone of a remote whose branches each hold one commit made from the trunk."""

    repository: InfrahubRepository
    trunk: str
    feature: str
    """Adds a file that no other branch has, so it merges cleanly."""
    left: str
    right: str
    """Changes the same file as `left` in another way, so the two conflict."""

    @property
    def worktree(self) -> Repo:
        return self.repository.get_git_repo_worktree(identifier=DESTINATION)

    def worktree_head(self) -> str:
        return str(self.worktree.head.commit)


@pytest.fixture(autouse=True)
def machine_git_config_ignored(monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep the Git configuration of the machine out of the merges, because it can sign them or refuse a fast-forward."""
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", os.devnull)
    monkeypatch.setenv("GIT_CONFIG_SYSTEM", os.devnull)


@pytest.fixture
async def clone(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> DeliveryClone:
    repositories_directory = tmp_path / "repositories"
    repositories_directory.mkdir()
    monkeypatch.setattr(registry, "_default_branch", DESTINATION)
    monkeypatch.setattr(config.SETTINGS.git, "repositories_directory", str(repositories_directory))

    remote = LocalRemote.create(directory=tmp_path / "remote", trunk=DESTINATION, branches=[])
    feature = remote.commit(branch_name="feature", files={"feature.txt": "feature\n"})
    left = remote.commit(branch_name="left", files={"data.txt": "left\n"})
    right = remote.commit(branch_name="right", files={"data.txt": "right\n"})
    repository = await clone_repository(
        id=UUIDT.new(),
        name=REPOSITORY_NAME,
        location=str(remote.directory),
        client=InfrahubClient(config=Config(requester=dummy_async_request)),
        update_commit_value=False,
    )
    return DeliveryClone(
        repository=repository,
        trunk=str(remote.repo.commit(DESTINATION)),
        feature=feature,
        left=left,
        right=right,
    )


@pytest.fixture
def silent_remote() -> Iterator[str]:
    """Return the address of an HTTP remote whose connections the kernel accepts and that never answers."""
    with socket.create_server(("127.0.0.1", 0)) as server:
        yield f"http://127.0.0.1:{server.getsockname()[1]}/{REPOSITORY_NAME}.git"


def build_adapter(
    repository: InfrahubRepository,
    use_explicit_merge_commit: bool = True,
    local_timeout_seconds: float = LOCAL_GIT_TIMEOUT_SECONDS,
) -> RepositoryDeliveryGitAdapter:
    return RepositoryDeliveryGitAdapter(
        repository=repository,
        destination_branch=DESTINATION,
        destination_branch_id="main-id",
        message_bus=BusRecorder(),
        initiator_id="worker",
        request_id="request",
        use_explicit_merge_commit=use_explicit_merge_commit,
        local_timeout_seconds=local_timeout_seconds,
    )


def corrupt_object_store(repo: Repo) -> None:
    """Pack every object, then overwrite the objects in the pack and keep its header and its checksum."""
    repo.git.repack("-a", "-d")
    pack = next(Path(repo.git_dir, "objects", "pack").glob("*.pack"))
    content = pack.read_bytes()
    pack.chmod(0o644)
    pack.write_bytes(content[:12] + bytes(len(content) - 32) + content[-20:])


def comparison_failed(clone: DeliveryClone) -> str:
    return (
        rf"^Unable to compare the commit {clone.trunk} against {clone.feature} in the clone of repository "
        rf"{REPOSITORY_NAME} on this worker\.$"
    )


def test_a_commit_is_its_own_ancestor(clone: DeliveryClone) -> None:
    assert build_adapter(repository=clone.repository).is_ancestor(ancestor=clone.trunk, descendant=clone.trunk) is True


def test_an_earlier_commit_is_an_ancestor_of_a_later_one(clone: DeliveryClone) -> None:
    adapter = build_adapter(repository=clone.repository)

    assert adapter.is_ancestor(ancestor=clone.trunk, descendant=clone.feature) is True
    assert adapter.is_ancestor(ancestor=clone.feature, descendant=clone.trunk) is False


def test_a_commit_on_another_branch_is_not_an_ancestor(clone: DeliveryClone) -> None:
    assert build_adapter(repository=clone.repository).is_ancestor(ancestor=clone.left, descendant=clone.right) is False


def test_a_commit_missing_from_the_clone_answers_no(clone: DeliveryClone) -> None:
    adapter = build_adapter(repository=clone.repository)

    assert adapter.is_ancestor(ancestor=ABSENT, descendant=clone.trunk) is False
    assert adapter.is_ancestor(ancestor=clone.trunk, descendant=ABSENT) is False


def test_a_corrupt_object_store_raises_instead_of_answering(clone: DeliveryClone) -> None:
    corrupt_object_store(repo=clone.repository.get_git_repo_main())

    with pytest.raises(RepositoryError, match=comparison_failed(clone=clone)):
        build_adapter(repository=clone.repository).is_ancestor(ancestor=clone.trunk, descendant=clone.feature)


@pytest.mark.skipif(os.geteuid() == 0, reason="chmod does not stop root from reading a file")
def test_an_unreadable_object_store_raises_with_no_path_of_the_worker(clone: DeliveryClone) -> None:
    main = clone.repository.get_git_repo_main()
    main.git.repack("-a", "-d")
    pack = next(Path(main.git_dir, "objects", "pack").glob("*.pack"))
    pack.chmod(0o000)

    try:
        with pytest.raises(RepositoryError, match=comparison_failed(clone=clone)) as error:
            build_adapter(repository=clone.repository).is_ancestor(ancestor=clone.trunk, descendant=clone.feature)
    finally:
        pack.chmod(0o644)

    assert str(pack) in str(error.value.__cause__)


def test_a_replay_merges_each_commit_with_a_merge_commit_of_its_own(clone: DeliveryClone) -> None:
    result = build_adapter(repository=clone.repository).replay(base=clone.trunk, commits=[clone.feature])

    merge = clone.worktree.commit(result.head)
    assert result.conflicting_commit is None
    assert clone.worktree_head() == result.head
    assert [str(parent) for parent in merge.parents] == [clone.trunk, clone.feature]
    assert merge.summary == "Merged by Infrahub"


def test_a_replay_without_merge_commits_moves_the_worktree_to_the_merged_commit(clone: DeliveryClone) -> None:
    adapter = build_adapter(repository=clone.repository, use_explicit_merge_commit=False)

    result = adapter.replay(base=clone.trunk, commits=[clone.feature])

    assert result == ReplayResult(head=clone.feature)
    assert clone.worktree_head() == clone.feature


def test_a_replay_resets_the_worktree_to_the_base_first(clone: DeliveryClone) -> None:
    clone.worktree.git.reset("--hard", clone.left)

    result = build_adapter(repository=clone.repository).replay(base=clone.trunk, commits=[])

    assert result == ReplayResult(head=clone.trunk)
    assert clone.worktree_head() == clone.trunk


def test_a_conflicting_replay_names_the_commit_and_leaves_the_worktree_at_the_base(clone: DeliveryClone) -> None:
    result = build_adapter(repository=clone.repository).replay(base=clone.trunk, commits=[clone.left, clone.right])

    assert result == ReplayResult(head=clone.trunk, conflicting_commit=clone.right)
    assert clone.worktree_head() == clone.trunk
    assert not Path(clone.worktree.git_dir, "MERGE_HEAD").exists()
    assert not clone.worktree.is_dirty(untracked_files=True)


def test_a_merge_stopped_at_its_time_bound_frees_the_index_and_names_only_the_command(clone: DeliveryClone) -> None:
    """A merge driver that never ends holds the index lock until Git stops the merge."""
    main = clone.repository.get_git_repo_main()
    with main.config_writer() as git_config:
        git_config.set_value('merge "stuck"', "driver", "exec sleep 60 </dev/null >/dev/null 2>&1")
    Path(main.git_dir, "info").mkdir(exist_ok=True)
    Path(main.git_dir, "info", "attributes").write_text("* merge=stuck\n", encoding="utf-8")
    adapter = build_adapter(repository=clone.repository, local_timeout_seconds=2)

    with pytest.raises(RepositoryError, match=r"^The command git merge did not complete within 2 seconds\.$"):
        adapter.replay(base=clone.left, commits=[clone.right])

    assert not Path(clone.worktree.git_dir, "index.lock").exists()
    adapter.reset(commit=clone.trunk)
    assert clone.worktree_head() == clone.trunk


@dataclass(frozen=True)
class StalledTransferCase:
    name: str
    transfer: Callable[[InfrahubRepository], Awaitable[object]]
    error: type[Exception]
    message: str
    """The whole message of the error that ends the transfer."""
    stage: DeliveryStage | None
    """The stage that classifies the error; None for a branch deletion, whose failure a delivery only logs."""


STALLED_TRANSFER_CASES: list[StalledTransferCase] = [
    StalledTransferCase(
        name="stalled_fetch",
        transfer=lambda repository: repository.fetch(timeout_seconds=2),
        error=RepositoryConnectionError,
        message=TIME_LIMIT_MESSAGE,
        stage=DeliveryStage.FETCH,
    ),
    StalledTransferCase(
        name="stalled_push",
        transfer=lambda repository: repository.push(branch_name=DESTINATION, timeout_seconds=2),
        error=RepositoryConnectionError,
        message=TIME_LIMIT_MESSAGE,
        stage=DeliveryStage.PUSH,
    ),
    # GitPython writes this message only where `ps` exists; without it, the error is the libcurl one.
    StalledTransferCase(
        name="stalled_remote_branch_deletion",
        transfer=lambda repository: repository.delete_remote_branch(branch_name="feature", timeout_seconds=2),
        error=GitCommandError,
        message=(
            "Cmd('git') failed due to: exit code(-9)\n"
            "  cmdline: git push origin --delete feature\n"
            """  stderr: 'Timeout: the command "git push origin --delete feature" did not complete in 2 secs.'"""
        ),
        stage=None,
    ),
]


# A hung transfer blocks the main thread in a call that the signal method cannot interrupt.
@pytest.mark.timeout(60, method="thread")
@pytest.mark.parametrize("case", [pytest.param(case, id=case.name) for case in STALLED_TRANSFER_CASES])
async def test_a_transfer_to_a_remote_that_never_answers_stops_at_its_bound(
    case: StalledTransferCase, clone: DeliveryClone, silent_remote: str
) -> None:
    clone.repository.get_git_repo_main().git.remote("set-url", "origin", silent_remote)

    with pytest.raises(case.error, match=rf"^{re.escape(case.message)}$") as error:
        await case.transfer(clone.repository)

    if case.stage is not None:
        assert classify_delivery_failure(error=error.value, stage=case.stage) == DeliveryFailure(
            cause=RepositoryDeliveryFailureCause.REMOTE_UNREACHABLE, retryable=True, message=TIME_LIMIT_MESSAGE
        )


def test_reset_moves_the_worktree_to_the_commit(clone: DeliveryClone) -> None:
    clone.worktree.git.reset("--hard", clone.feature)

    build_adapter(repository=clone.repository).reset(commit=clone.trunk)

    assert clone.worktree_head() == clone.trunk


def test_a_reset_that_fails_is_logged_and_leaves_the_worktree(
    clone: DeliveryClone, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.ERROR, logger="infrahub.tasks")

    build_adapter(repository=clone.repository).reset(commit=ABSENT)

    assert clone.worktree_head() == clone.trunk
    assert [record.getMessage() for record in caplog.records if record.levelno == logging.ERROR] == [
        f"Failed to reset the worktree of branch {DESTINATION} of repository {REPOSITORY_NAME} to {ABSENT} while "
        "recovering from a failed merge; manual reconciliation may be required before the merge can be retried."
    ]


def test_the_remote_head_is_the_fetched_branch_and_none_for_a_branch_the_remote_lacks(clone: DeliveryClone) -> None:
    adapter = build_adapter(repository=clone.repository)

    assert adapter.remote_head(git_branch="feature") == clone.feature
    assert adapter.remote_head(git_branch="missing") is None


async def test_a_fetch_on_a_clone_without_origin_raises_and_names_no_path(clone: DeliveryClone) -> None:
    clone.repository.get_git_repo_main().git.remote("remove", "origin")
    without_origin = await open_repository(
        id=clone.repository.id,
        name=REPOSITORY_NAME,
        location=str(clone.repository.location),
        client=InfrahubClient(config=Config(requester=dummy_async_request)),
    )

    with pytest.raises(
        RepositoryError, match=rf"^The clone of repository {REPOSITORY_NAME} on this worker has no origin\.$"
    ):
        await build_adapter(repository=without_origin).fetch()
