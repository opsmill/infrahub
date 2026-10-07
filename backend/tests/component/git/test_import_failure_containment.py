from __future__ import annotations

import logging
from typing import TYPE_CHECKING
from uuid import uuid4

import pytest
from infrahub_sdk import Config, InfrahubClient

from infrahub import config
from infrahub.core.branch import Branch
from infrahub.core.registry import registry
from infrahub.exceptions import RepositoryConnectionError
from infrahub.git.import_errors import RepositoryImportError
from infrahub.git.repository import PendingObjectImport
from infrahub.git.sync import RepositoryBranchesFailedError, RepositorySyncer, import_branch
from infrahub.lock import InfrahubLockRegistry
from tests.adapters.lock import FailingImporter
from tests.helpers.flow import call_in_flow
from tests.helpers.repository_sync import FLOW_RUN_LOGGER
from tests.helpers.test_client import (
    REJECTED_REQUEST_MESSAGE,
    registered_branches_async_request,
    rejected_async_request,
)

if TYPE_CHECKING:
    from infrahub.git import InfrahubRepository


@pytest.fixture
def capture_flow_run_logs(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.INFO, logger=FLOW_RUN_LOGGER)


def flow_run_errors(caplog: pytest.LogCaptureFixture) -> list[tuple[str, BaseException | None]]:
    """Return each error-level entry of the flow run logger with the exception attached to it."""
    return [
        (record.getMessage(), record.exc_info[1] if record.exc_info else None)
        for record in caplog.records
        if record.name == FLOW_RUN_LOGGER and record.levelno >= logging.ERROR
    ]


def pending_main_import(repo: InfrahubRepository) -> PendingObjectImport:
    return PendingObjectImport(infrahub_branch_name="main", commit=repo.get_commit_value(branch_name="main"))


async def test_failure_raised_outside_the_import_is_returned_and_logged_with_its_traceback(
    prefect_test_fixture: None,
    git_repo_04: InfrahubRepository,
    caplog: pytest.LogCaptureFixture,
    capture_flow_run_logs: None,
) -> None:
    error = RuntimeError("lock backend unavailable")

    failure = await call_in_flow(
        lambda: import_branch(
            lock_registry=InfrahubLockRegistry(local_only=True),
            importer=FailingImporter(error),
            repo=git_repo_04,
            pending_import=pending_main_import(git_repo_04),
        )
    )

    assert isinstance(failure, RepositoryImportError)
    assert failure.message == "RuntimeError: lock backend unavailable"
    assert flow_run_errors(caplog) == [
        ("Failed to import branch 'main': RuntimeError: lock backend unavailable", error)
    ]


async def test_converted_import_failure_is_returned_without_logging_it_again(
    prefect_test_fixture: None,
    git_repo_04: InfrahubRepository,
    caplog: pytest.LogCaptureFixture,
    capture_flow_run_logs: None,
) -> None:
    error = RepositoryImportError(identifier=git_repo_04.name, branch_name="main", message="Schema not valid")

    failure = await call_in_flow(
        lambda: import_branch(
            lock_registry=InfrahubLockRegistry(local_only=True),
            importer=FailingImporter(error),
            repo=git_repo_04,
            pending_import=pending_main_import(git_repo_04),
        )
    )

    assert failure is error
    assert flow_run_errors(caplog) == []


async def test_connection_failure_is_raised(prefect_test_fixture: None, git_repo_04: InfrahubRepository) -> None:
    error = RepositoryConnectionError(identifier=git_repo_04.name, message="The remote repository is unreachable")

    with pytest.raises(RepositoryConnectionError, match=r"^The remote repository is unreachable$"):
        await call_in_flow(
            lambda: import_branch(
                lock_registry=InfrahubLockRegistry(local_only=True),
                importer=FailingImporter(error),
                repo=git_repo_04,
                pending_import=pending_main_import(git_repo_04),
            )
        )


async def test_sync_records_a_failure_raised_outside_the_import_on_its_branch(
    prefect_test_fixture: None, git_repo_04: InfrahubRepository, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(config.SETTINGS.git, "import_sync_branch_names", [])
    branch = Branch(name="branch01", uuid=uuid4())
    monkeypatch.setitem(registry.branch, branch.name, branch)
    git_repo_04.client = InfrahubClient(config=Config(requester=registered_branches_async_request))
    syncer = RepositorySyncer(
        lock_registry=InfrahubLockRegistry(local_only=True), importer=FailingImporter(RuntimeError("lock lost"))
    )

    with pytest.raises(
        RepositoryBranchesFailedError,
        match=r"^Unable to synchronize the following branches of repository .+: "
        r"branch01 \(step=import\): RuntimeError: lock lost$",
    ) as exc_info:
        await call_in_flow(lambda: syncer.sync(git_repo_04))

    assert exc_info.value.report.failed_import_branches == ("branch01",)
    assert exc_info.value.report.imported_branches == ()


async def test_failed_status_write_does_not_replace_the_import_failure(
    prefect_test_fixture: None,
    git_repo_04: InfrahubRepository,
    caplog: pytest.LogCaptureFixture,
    capture_flow_run_logs: None,
) -> None:
    """Every request is rejected, so recording the sync in progress fails and so does recording the failure."""
    git_repo_04.client = InfrahubClient(config=Config(requester=rejected_async_request))
    commit = git_repo_04.get_commit_value(branch_name="main")

    with pytest.raises(RepositoryImportError, match=rf"^{REJECTED_REQUEST_MESSAGE}$"):
        await call_in_flow(lambda: git_repo_04.build_import_plan(infrahub_branch_name="main", commit=commit))

    *entries, finished_entry = [message for message, _ in flow_run_errors(caplog)]
    assert entries == [
        f"Failed to import branch 'main': {REJECTED_REQUEST_MESSAGE}",
        "Failed to set the sync status of branch 'main' to ERROR_IMPORT",
    ]
    # Prefect's own closing entry is matched by its prefix, which is the part of its wording it owns.
    assert finished_entry.startswith("Finished in state Failed(")
