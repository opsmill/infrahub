from dataclasses import dataclass

from infrahub.exceptions import RepositoryError
from infrahub.git.divergence.models import RewriteRecord
from infrahub.git.divergence.recorder import HistoryRewriteRecorder


@dataclass(frozen=True)
class WrittenRecord:
    repository_id: str
    infrahub_branch_name: str
    record: RewriteRecord


class InMemoryRepositoryRecordStore:
    """RepositoryRecordStore that keeps every record it is given, in the order they were written.

    A branch reads the count of its last record, or the count seeded for it.
    """

    def __init__(self, counts: dict[tuple[str, str], int] | None = None) -> None:
        self.counts: dict[tuple[str, str], int] = dict(counts or {})
        self.written: list[WrittenRecord] = []

    async def get_rewrite_count(self, repository_id: str, infrahub_branch_name: str) -> int | None:
        return self.counts.get((repository_id, infrahub_branch_name))

    async def write_record(self, repository_id: str, infrahub_branch_name: str, record: RewriteRecord) -> None:
        self.written.append(
            WrittenRecord(repository_id=repository_id, infrahub_branch_name=infrahub_branch_name, record=record)
        )
        self.counts[repository_id, infrahub_branch_name] = record.rewrite_count


class FailingRepositoryRecordStore:
    """RepositoryRecordStore whose every call fails the way the Infrahub API fails."""

    async def get_rewrite_count(self, repository_id: str, infrahub_branch_name: str) -> int | None:
        raise RepositoryError(identifier=repository_id, message=f"The API is unreachable from {infrahub_branch_name}")

    async def write_record(self, repository_id: str, infrahub_branch_name: str, record: RewriteRecord) -> None:
        raise RepositoryError(identifier=repository_id, message=f"The API is unreachable from {infrahub_branch_name}")


def build_in_memory_recorder() -> HistoryRewriteRecorder:
    return HistoryRewriteRecorder(store=InMemoryRepositoryRecordStore())
