from datetime import UTC, datetime

from infrahub.core.constants import InfrahubKind
from infrahub.core.regeneration.changes_since import DiffChangeTimes
from infrahub.message_bus.types import ProposedChangeRepository
from infrahub.proposed_change.branch_diff import (
    RepositoryFileDiff,
    RepositoryFileDiffPopulator,
    parse_diff_change_times,
)
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

    await RepositoryFileDiffPopulator(differ=differ).populate(repositories=[repo])

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

    await RepositoryFileDiffPopulator(differ=differ).populate(repositories=[repo])

    assert differ.requests == []
    assert repo.files_changed == []
    assert repo.files_added == []
    assert repo.files_removed == []


async def test_managed_repository_missing_destination_commit_skipped() -> None:
    """A repository present only on the source branch has no commit pair to diff against."""
    repo = _repository(repository_id="managed-1", read_only=False, source_commit="aaaa", destination_commit="")
    differ = RecordingRepositoryFileDiffer()

    await RepositoryFileDiffPopulator(differ=differ).populate(repositories=[repo])

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

    await RepositoryFileDiffPopulator(differ=differ).populate(repositories=[repo])

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

    await RepositoryFileDiffPopulator(differ=differ).populate(repositories=[repo])

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

    await RepositoryFileDiffPopulator(differ=differ).populate(repositories=[managed, readonly])

    assert {request.repository_id for request in differ.requests} == {"managed-1", "readonly-1"}
    assert managed.files_changed == ["a.py"]
    assert readonly.files_removed == ["b.gql"]


DEVICE_ID = "11111111-1111-1111-1111-111111111111"
GROUP_ID = "22222222-2222-2222-2222-222222222222"
MEMBER_1 = "33333333-3333-3333-3333-333333333333"
MEMBER_2 = "44444444-4444-4444-4444-444444444444"


def test_parse_diff_change_times_collects_the_times_of_nodes_fields_and_peers() -> None:
    diff_tree = {
        "from_time": "2026-01-01T08:00:00+00:00",
        "to_time": "2026-01-01T16:00:00+00:00",
        "nodes": [
            {
                "uuid": DEVICE_ID,
                "last_changed_at": "2026-01-01T12:00:00+00:00",
                "attributes": [
                    {"name": "name", "last_changed_at": "2026-01-01T10:00:00+00:00", "properties": []},
                    {
                        "name": "color",
                        "last_changed_at": "2026-01-01T07:00:00+00:00",
                        "properties": [
                            {"last_changed_at": "2026-01-01T09:00:00+00:00"},
                            {"last_changed_at": "2026-01-01T12:00:00+00:00"},
                        ],
                    },
                ],
                "relationships": [],
            },
            {
                "uuid": GROUP_ID,
                "last_changed_at": "2026-01-01T14:00:00+00:00",
                "attributes": [],
                "relationships": [
                    {
                        "name": "members",
                        "last_changed_at": None,
                        "elements": [
                            {"peer_id": MEMBER_1, "last_changed_at": "2026-01-01T11:00:00+00:00"},
                            {"peer_id": MEMBER_2, "last_changed_at": "2026-01-01T14:00:00+00:00"},
                        ],
                    }
                ],
            },
        ],
    }

    change_times = parse_diff_change_times(diff_tree=diff_tree)

    assert change_times == DiffChangeTimes(
        from_time=datetime(2026, 1, 1, 8, 0, tzinfo=UTC),
        to_time=datetime(2026, 1, 1, 16, 0, tzinfo=UTC),
        nodes={
            DEVICE_ID: datetime(2026, 1, 1, 12, 0, tzinfo=UTC),
            GROUP_ID: datetime(2026, 1, 1, 14, 0, tzinfo=UTC),
        },
        fields={
            DEVICE_ID: {
                "name": datetime(2026, 1, 1, 10, 0, tzinfo=UTC),
                "color": datetime(2026, 1, 1, 12, 0, tzinfo=UTC),
            },
            GROUP_ID: {"members": datetime(2026, 1, 1, 14, 0, tzinfo=UTC)},
        },
        peers={
            GROUP_ID: {
                "members": {
                    MEMBER_1: datetime(2026, 1, 1, 11, 0, tzinfo=UTC),
                    MEMBER_2: datetime(2026, 1, 1, 14, 0, tzinfo=UTC),
                }
            }
        },
    )


def test_parse_diff_change_times_keeps_the_latest_time_of_a_node_listed_twice() -> None:
    diff_tree = {
        "from_time": "2026-01-01T08:00:00+00:00",
        "to_time": "2026-01-01T16:00:00+00:00",
        "nodes": [
            {
                "uuid": DEVICE_ID,
                "last_changed_at": "2026-01-01T12:00:00+00:00",
                "attributes": [{"name": "name", "last_changed_at": "2026-01-01T12:00:00+00:00"}],
                "relationships": [],
            },
            {
                "uuid": DEVICE_ID,
                "last_changed_at": "2026-01-01T10:00:00+00:00",
                "attributes": [{"name": "name", "last_changed_at": "2026-01-01T10:00:00+00:00"}],
                "relationships": [],
            },
        ],
    }

    change_times = parse_diff_change_times(diff_tree=diff_tree)

    assert change_times.nodes == {DEVICE_ID: datetime(2026, 1, 1, 12, 0, tzinfo=UTC)}
    assert change_times.fields == {DEVICE_ID: {"name": datetime(2026, 1, 1, 12, 0, tzinfo=UTC)}}


def test_parse_diff_change_times_leaves_out_a_field_without_a_time() -> None:
    diff_tree = {
        "from_time": "2026-01-01T08:00:00+00:00",
        "to_time": "2026-01-01T16:00:00+00:00",
        "nodes": [
            {
                "uuid": GROUP_ID,
                "last_changed_at": None,
                "attributes": [],
                "relationships": [{"name": "members", "last_changed_at": None, "elements": []}],
            }
        ],
    }

    change_times = parse_diff_change_times(diff_tree=diff_tree)

    assert change_times.nodes == {}
    assert change_times.fields == {GROUP_ID: {}}
    assert change_times.peers == {}
