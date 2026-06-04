from infrahub.core.constants import InfrahubKind
from infrahub.message_bus.types import ProposedChangeRepository
from infrahub.proposed_change.branch_diff import RepositoryFileDiff, populate_repository_file_diffs
from tests.adapters.repository_file_diff import RecordingRepositoryFileDiffer


def _repository(
    *,
    repository_id: str,
    read_only: bool,
    source_commit: str,
    destination_commit: str,
) -> ProposedChangeRepository:
    return ProposedChangeRepository(
        repository_id=repository_id,
        repository_name=f"repo-{repository_id}",
        read_only=read_only,
        source_branch="feature",
        destination_branch="main",
        internal_status="active",
        source_commit=source_commit,
        destination_commit=destination_commit,
    )


async def test_managed_repository_diff_computed_from_commits_only() -> None:
    """A managed repository with differing branch tips is diffed using those commits and its kind.

    The diff depends solely on the source and destination commits, so it is computed independent of
    the source branch's sync_with_git flag.
    """
    repo = _repository(repository_id="managed-1", read_only=False, source_commit="aaaa", destination_commit="bbbb")
    differ = RecordingRepositoryFileDiffer(
        results={"managed-1": RepositoryFileDiff(files_changed=["templates/foo.j2"])}
    )

    await populate_repository_file_diffs(repositories=[repo], differ=differ)

    assert len(differ.requests) == 1
    request = differ.requests[0]
    assert request.repository_kind == InfrahubKind.REPOSITORY
    assert request.source_commit == "aaaa"
    assert request.destination_commit == "bbbb"
    assert repo.files_changed == ["templates/foo.j2"]


async def test_managed_repository_unmoved_tips_yields_no_diff() -> None:
    """When a managed repository's tracked tips did not move, the commits match and no diff runs."""
    repo = _repository(repository_id="managed-1", read_only=False, source_commit="aaaa", destination_commit="aaaa")
    differ = RecordingRepositoryFileDiffer()

    await populate_repository_file_diffs(repositories=[repo], differ=differ)

    assert differ.requests == []
    assert repo.files_changed == []
    assert repo.files_added == []
    assert repo.files_removed == []


async def test_managed_repository_missing_destination_commit_skipped() -> None:
    """A repository present only on the source branch has no commit pair to diff against."""
    repo = _repository(repository_id="managed-1", read_only=False, source_commit="aaaa", destination_commit="")
    differ = RecordingRepositoryFileDiffer()

    await populate_repository_file_diffs(repositories=[repo], differ=differ)

    assert differ.requests == []


async def test_readonly_repository_diff_uses_pinned_commits() -> None:
    """A read-only repository is diffed between its per-branch pinned commits.

    Read-only repositories previously never received a file diff; they now participate using the
    pinned commit recorded on each Infrahub branch.
    """
    repo = _repository(repository_id="readonly-1", read_only=True, source_commit="cccc", destination_commit="dddd")
    differ = RecordingRepositoryFileDiffer(
        results={"readonly-1": RepositoryFileDiff(files_added=["queries/example.gql"])}
    )

    await populate_repository_file_diffs(repositories=[repo], differ=differ)

    assert len(differ.requests) == 1
    request = differ.requests[0]
    assert request.repository_kind == InfrahubKind.READONLYREPOSITORY
    assert request.source_commit == "cccc"
    assert request.destination_commit == "dddd"
    assert repo.files_added == ["queries/example.gql"]


async def test_readonly_repository_equal_pinned_commits_yields_no_diff() -> None:
    """A read-only repository pinned to the same commit on both branches yields no file changes."""
    repo = _repository(repository_id="readonly-1", read_only=True, source_commit="cccc", destination_commit="cccc")
    differ = RecordingRepositoryFileDiffer()

    await populate_repository_file_diffs(repositories=[repo], differ=differ)

    assert differ.requests == []
    assert repo.files_added == []


async def test_managed_and_readonly_repositories_diffed_together() -> None:
    """Both repository kinds are diffed in a single pass, each keyed by its own repository id."""
    managed = _repository(repository_id="managed-1", read_only=False, source_commit="aaaa", destination_commit="bbbb")
    readonly = _repository(repository_id="readonly-1", read_only=True, source_commit="cccc", destination_commit="dddd")
    differ = RecordingRepositoryFileDiffer(
        results={
            "managed-1": RepositoryFileDiff(files_changed=["a.py"]),
            "readonly-1": RepositoryFileDiff(files_removed=["b.gql"]),
        }
    )

    await populate_repository_file_diffs(repositories=[managed, readonly], differ=differ)

    assert {request.repository_id for request in differ.requests} == {"managed-1", "readonly-1"}
    assert managed.files_changed == ["a.py"]
    assert readonly.files_removed == ["b.gql"]
