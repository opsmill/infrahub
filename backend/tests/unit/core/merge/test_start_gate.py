from dataclasses import dataclass
from uuid import uuid4

import pytest

from infrahub.core.branch import Branch
from infrahub.core.constants import RepositoryInternalStatus, RepositorySyncStatus
from infrahub.core.merge.repository_import_guard import RepositoryImportGuard
from infrahub.core.merge.start_gate import MergeStartGate
from infrahub.core.merge.write_blocker import MERGE_PROTECTED_CACHE_KEY, MergeWriteBlocker
from infrahub.exceptions import MergeRepositoryImportError
from infrahub.git.sync_status import RepositoryBranchSyncStatus, RepositoryBranchSyncStatusReader
from tests.adapters.cache import MemoryCache

BRANCH_NAME = "feature"
MERGING = f"{BRANCH_NAME}::MERGING"


class SequencedStatusReader(RepositoryBranchSyncStatusReader):
    """Returns one status per read, and records the merge write block in place at each read."""

    def __init__(self, cache: MemoryCache, statuses: list[RepositorySyncStatus]) -> None:
        self.cache = cache
        self.statuses = statuses
        self.blocks_seen: list[str | None] = []

    async def list_statuses_on_branch(self, branch: Branch) -> list[RepositoryBranchSyncStatus]:
        self.blocks_seen.append(self.cache.storage.get(MERGE_PROTECTED_CACHE_KEY))
        return [
            RepositoryBranchSyncStatus(
                repository_name="repo",
                internal_status=RepositoryInternalStatus.ACTIVE,
                sync_status=self.statuses[len(self.blocks_seen) - 1],
            )
        ]


def _build_gate(
    cache: MemoryCache, statuses: list[RepositorySyncStatus]
) -> tuple[MergeStartGate, SequencedStatusReader]:
    reader = SequencedStatusReader(cache=cache, statuses=statuses)
    gate = MergeStartGate(
        merge_write_blocker=MergeWriteBlocker(cache=cache),
        repository_import_guard=RepositoryImportGuard(status_reader=reader),
    )
    return gate, reader


@dataclass
class RefusalCase:
    name: str
    statuses: list[RepositorySyncStatus]
    blocks_seen: list[str | None]


REFUSAL_CASES = [
    RefusalCase(
        name="refused_before_the_block",
        statuses=[RepositorySyncStatus.ERROR_IMPORT],
        blocks_seen=[None],
    ),
    RefusalCase(
        name="refused_under_the_block",
        statuses=[RepositorySyncStatus.IN_SYNC, RepositorySyncStatus.ERROR_IMPORT],
        blocks_seen=[None, MERGING],
    ),
]


@pytest.mark.parametrize("case", REFUSAL_CASES, ids=lambda case: case.name)
async def test_refused_merge_leaves_no_write_block(case: RefusalCase) -> None:
    cache = MemoryCache()
    gate, reader = _build_gate(cache=cache, statuses=case.statuses)

    with pytest.raises(
        MergeRepositoryImportError,
        match=(
            r"^Cannot merge\. The last import of repository 'repo' failed: push a fix, reimport the current commit, "
            r"or set the repository to inactive\.$"
        ),
    ):
        await gate.block_writes(branch=Branch(name=BRANCH_NAME, uuid=uuid4()))

    assert reader.blocks_seen == case.blocks_seen
    assert cache.storage == {}


async def test_usable_imports_leave_the_write_block_set() -> None:
    cache = MemoryCache()
    gate, reader = _build_gate(cache=cache, statuses=[RepositorySyncStatus.IN_SYNC, RepositorySyncStatus.IN_SYNC])

    await gate.block_writes(branch=Branch(name=BRANCH_NAME, uuid=uuid4()))

    assert reader.blocks_seen == [None, MERGING]
    assert cache.storage == {MERGE_PROTECTED_CACHE_KEY: MERGING}
