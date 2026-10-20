from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import pytest
from infrahub_sdk.uuidt import UUIDT

from infrahub.core.constants import RepositoryInternalStatus
from infrahub.git.repository import InfrahubRepository
from infrahub.git.writeback.constants import LOCAL_GIT_TIMEOUT_SECONDS
from infrahub.git.writeback.git_adapter import RepositoryDeliveryGitAdapter
from tests.adapters.message_bus import BusRecorder
from tests.helpers.git import build_repository_client

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.core.schema.schema_branch import SchemaBranch

FULL_COMMIT = "c" * 40


@dataclass
class RecordedCommitCase:
    name: str
    stored: str | None
    expected: str | None


@pytest.mark.parametrize(
    "case",
    [
        RecordedCommitCase(name="full_commit_id", stored=FULL_COMMIT, expected=FULL_COMMIT),
        RecordedCommitCase(name="short_commit_id", stored="c0ffee1", expected=None),
        RecordedCommitCase(name="text_that_is_no_commit", stored="not a commit", expected=None),
        RecordedCommitCase(name="no_value", stored=None, expected=None),
    ],
    ids=lambda case: case.name,
)
async def test_a_recorded_value_that_is_not_a_full_commit_id_counts_as_never_recorded(
    default_branch: Branch, register_core_models_schema: SchemaBranch, case: RecordedCommitCase
) -> None:
    repository_id = str(UUIDT())
    client = build_repository_client(
        repository_id=repository_id,
        name="delivery-repo",
        location="https://git.example.com/delivery-repo.git",
        default_branch="main",
        commit=case.stored,
    )
    adapter = RepositoryDeliveryGitAdapter(
        repository=InfrahubRepository(
            id=repository_id,
            name="delivery-repo",
            client=client,
            default_branch="main",
            internal_status=RepositoryInternalStatus.ACTIVE,
            location="https://git.example.com/delivery-repo.git",
            infrahub_branch_name=default_branch.name,
        ),
        destination_branch=default_branch.name,
        destination_branch_id=str(default_branch.get_uuid()),
        message_bus=BusRecorder(),
        initiator_id="worker",
        request_id="request",
        use_explicit_merge_commit=True,
        local_timeout_seconds=LOCAL_GIT_TIMEOUT_SECONDS,
    )

    assert await adapter.recorded_commit() == case.expected
