from dataclasses import dataclass

from infrahub.proposed_change.branch_diff import RepositoryFileDiff


@dataclass
class RecordedDiffRequest:
    repository_id: str
    repository_name: str
    repository_kind: str
    source_commit: str
    destination_commit: str


class RecordingRepositoryFileDiffer:
    """In-memory RepositoryFileDiffer that records every request and returns seeded results.

    Lets a test assert which repositories were diffed and with which commits and kind, without
    touching git. Results are keyed by repository id; an unseeded repository yields an empty diff.
    """

    def __init__(self, results: dict[str, RepositoryFileDiff] | None = None) -> None:
        self.results: dict[str, RepositoryFileDiff] = results or {}
        self.requests: list[RecordedDiffRequest] = []

    async def calculate_diff(
        self,
        *,
        repository_id: str,
        repository_name: str,
        repository_kind: str,
        source_commit: str,
        destination_commit: str,
    ) -> RepositoryFileDiff:
        self.requests.append(
            RecordedDiffRequest(
                repository_id=repository_id,
                repository_name=repository_name,
                repository_kind=repository_kind,
                source_commit=source_commit,
                destination_commit=destination_commit,
            )
        )
        return self.results.get(repository_id, RepositoryFileDiff())
