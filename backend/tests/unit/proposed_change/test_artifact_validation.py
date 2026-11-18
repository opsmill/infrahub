from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import TYPE_CHECKING
from uuid import UUID

import pytest

from infrahub.core.constants import InfrahubKind, ValidatorConclusion
from infrahub.core.schema import SchemaRoot, core_models
from infrahub.core.schema.schema_branch import SchemaBranch
from infrahub.message_bus.types import ProposedChangeArtifactDefinition, ProposedChangeRepository
from infrahub.proposed_change.artifact_validation import (
    ArtifactValidationRecord,
    ArtifactValidationRecords,
    ArtifactValidationRun,
    ChangesToValidate,
    RecentChanges,
    TargetCheckOutcomes,
    changes_reach_definition,
    changes_validated_until,
    diff_tracks_members,
)
from infrahub.proposed_change.branch_changes import BranchChanges, BranchDiffWindow
from tests.adapters.cache import MemoryCache
from tests.helpers.diff_summary import node_diff

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from infrahub_sdk.diff import NodeDiff

BRANCHED_AT = datetime(2026, 1, 1, 8, 0, tzinfo=UTC)
REBASED_AT = datetime(2026, 1, 1, 9, 0, tzinfo=UTC)
BEFORE = datetime(2026, 1, 1, 10, 0, tzinfo=UTC)
VALIDATED_UNTIL = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
AFTER = datetime(2026, 1, 1, 14, 0, tzinfo=UTC)
NOW = datetime(2026, 1, 1, 16, 0, tzinfo=UTC)

PROPOSED_CHANGE_ID = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
DEFINITION_ID = "11111111-1111-1111-1111-111111111111"
OTHER_DEFINITION_ID = "12121212-1212-1212-1212-121212121212"
QUERY_ID = "22222222-2222-2222-2222-222222222222"
GROUP_ID = "33333333-3333-3333-3333-333333333333"
DEVICE_1 = "44444444-4444-4444-4444-444444444444"
DEVICE_2 = "55555555-5555-5555-5555-555555555555"
REPOSITORY_ID = "77777777-7777-7777-7777-777777777777"
FIRST_PIPELINE = UUID("00000000-0000-0000-0000-000000000001")
SECOND_PIPELINE = UUID("00000000-0000-0000-0000-000000000002")

RECORD_KEY = f"proposed_change:{PROPOSED_CHANGE_ID}:artifact_definition:{DEFINITION_ID}:validation"
THIRTY_DAYS_IN_SECONDS = 2_592_000


def _repository(
    *, source_commit: str = "source-1", destination_commit: str = "destination-1"
) -> ProposedChangeRepository:
    return ProposedChangeRepository(
        repository_id=REPOSITORY_ID,
        repository_name="repository",
        read_only=False,
        source_branch="feature",
        destination_branch="main",
        internal_status="active",
        source_commit=source_commit,
        destination_commit=destination_commit,
    )


def _record(
    *,
    pipeline_id: UUID = FIRST_PIPELINE,
    completed: bool = True,
    diff_from_time: datetime = BRANCHED_AT,
    diff_to_time: datetime = VALIDATED_UNTIL,
    failed_target_ids: frozenset[str] = frozenset(),
) -> ArtifactValidationRecord:
    return ArtifactValidationRecord(
        pipeline_id=pipeline_id,
        completed=completed,
        diff_from_time=diff_from_time,
        diff_to_time=diff_to_time,
        source_commit="source-1",
        destination_commit="destination-1",
        failed_target_ids=failed_target_ids,
    )


def _window(*, from_time: datetime = BRANCHED_AT, to_time: datetime = NOW) -> BranchDiffWindow:
    return BranchDiffWindow(from_time=from_time, to_time=to_time)


def _definition() -> ProposedChangeArtifactDefinition:
    return ProposedChangeArtifactDefinition(
        definition_id=DEFINITION_ID,
        definition_name="artifact-def",
        artifact_name="device-config",
        query_name="GetNetworkDevice",
        query_id=QUERY_ID,
        query_payload="query { TestDevice { edges { node { id } } } }",
        repository_id=REPOSITORY_ID,
        transform_kind=InfrahubKind.TRANSFORMJINJA2,
        template_path="device.j2",
        content_type="application/json",
        timeout=60,
    )


@dataclass(frozen=True, kw_only=True)
class ValidatedUntilCase:
    name: str
    record: ArtifactValidationRecord | None
    window: BranchDiffWindow | None
    repository: ProposedChangeRepository | None
    expected: datetime | None


VALIDATED_UNTIL_CASES: list[ValidatedUntilCase] = [
    ValidatedUntilCase(
        name="completed_record_of_the_same_branch_state_is_relied_on",
        record=_record(),
        window=_window(),
        repository=_repository(),
        expected=VALIDATED_UNTIL,
    ),
    ValidatedUntilCase(
        name="diff_read_at_the_recorded_time_is_relied_on",
        record=_record(),
        window=_window(to_time=VALIDATED_UNTIL),
        repository=_repository(),
        expected=VALIDATED_UNTIL,
    ),
    ValidatedUntilCase(
        name="no_record",
        record=None,
        window=_window(),
        repository=_repository(),
        expected=None,
    ),
    ValidatedUntilCase(
        name="record_of_a_validation_that_did_not_complete",
        record=_record(completed=False),
        window=_window(),
        repository=_repository(),
        expected=None,
    ),
    ValidatedUntilCase(
        name="no_diff_window",
        record=_record(),
        window=None,
        repository=_repository(),
        expected=None,
    ),
    ValidatedUntilCase(
        name="no_repository",
        record=_record(),
        window=_window(),
        repository=None,
        expected=None,
    ),
    ValidatedUntilCase(
        name="branch_rebased_since",
        record=_record(),
        window=_window(from_time=REBASED_AT),
        repository=_repository(),
        expected=None,
    ),
    ValidatedUntilCase(
        name="diff_older_than_the_recorded_one",
        record=_record(),
        window=_window(to_time=BEFORE),
        repository=_repository(),
        expected=None,
    ),
    ValidatedUntilCase(
        name="source_commit_moved",
        record=_record(),
        window=_window(),
        repository=_repository(source_commit="source-2"),
        expected=None,
    ),
    ValidatedUntilCase(
        name="destination_commit_moved",
        record=_record(),
        window=_window(),
        repository=_repository(destination_commit="destination-2"),
        expected=None,
    ),
]


@pytest.mark.parametrize("test_case", [pytest.param(tc, id=tc.name) for tc in VALIDATED_UNTIL_CASES])
def test_changes_validated_until(test_case: ValidatedUntilCase) -> None:
    validated_until = changes_validated_until(
        record=test_case.record, window=test_case.window, repository=test_case.repository
    )

    assert validated_until == test_case.expected


async def test_started_record_is_stored_as_not_completed_for_thirty_days() -> None:
    cache = MemoryCache()
    records = ArtifactValidationRecords(cache=cache, proposed_change_id=PROPOSED_CHANGE_ID)

    await records.start(definition_id=DEFINITION_ID, record=_record(completed=True))

    assert await records.get(definition_ids=[DEFINITION_ID]) == {DEFINITION_ID: _record(completed=False)}
    assert cache.expiries == {RECORD_KEY: THIRTY_DAYS_IN_SECONDS}


async def test_completed_record_is_stored_as_completed() -> None:
    records = ArtifactValidationRecords(cache=MemoryCache(), proposed_change_id=PROPOSED_CHANGE_ID)
    await records.start(definition_id=DEFINITION_ID, record=_record())

    await records.complete(definition_id=DEFINITION_ID, record=_record(), failed_target_ids=[])

    assert await records.get(definition_ids=[DEFINITION_ID]) == {DEFINITION_ID: _record(completed=True)}


async def test_completed_record_holds_the_targets_whose_check_failed() -> None:
    records = ArtifactValidationRecords(cache=MemoryCache(), proposed_change_id=PROPOSED_CHANGE_ID)
    await records.start(definition_id=DEFINITION_ID, record=_record())

    await records.complete(definition_id=DEFINITION_ID, record=_record(), failed_target_ids=[DEVICE_1])

    assert await records.get(definition_ids=[DEFINITION_ID]) == {
        DEFINITION_ID: _record(completed=True, failed_target_ids=frozenset({DEVICE_1}))
    }


async def test_record_whose_completion_mark_cannot_be_read_is_not_completed() -> None:
    cache = MemoryCache()
    records = ArtifactValidationRecords(cache=cache, proposed_change_id=PROPOSED_CHANGE_ID)
    await records.start(definition_id=DEFINITION_ID, record=_record())
    await cache.set(key=f"{RECORD_KEY}:{FIRST_PIPELINE}:completed", value="completed")

    assert await records.get(definition_ids=[DEFINITION_ID]) == {DEFINITION_ID: _record(completed=False)}


async def test_record_of_a_later_validation_is_not_completed_by_an_earlier_one() -> None:
    records = ArtifactValidationRecords(cache=MemoryCache(), proposed_change_id=PROPOSED_CHANGE_ID)
    first = _record(pipeline_id=FIRST_PIPELINE)
    second = _record(pipeline_id=SECOND_PIPELINE, diff_to_time=AFTER)
    await records.start(definition_id=DEFINITION_ID, record=first)
    await records.start(definition_id=DEFINITION_ID, record=second)

    await records.complete(definition_id=DEFINITION_ID, record=first, failed_target_ids=[])

    assert await records.get(definition_ids=[DEFINITION_ID]) == {
        DEFINITION_ID: _record(pipeline_id=SECOND_PIPELINE, diff_to_time=AFTER, completed=False)
    }


class _CacheWithHookOnRead(MemoryCache):
    """Runs a write once, right after the next read, the way another flow writes between a read and a write."""

    def __init__(self) -> None:
        super().__init__()
        self.on_next_read: Callable[[], Awaitable[None]] | None = None

    async def get_values(self, keys: list[str]) -> list[str | None]:
        values = await super().get_values(keys=keys)
        hook, self.on_next_read = self.on_next_read, None
        if hook is not None:
            await hook()
        return values


async def test_validation_that_starts_while_another_completes_stays_not_completed() -> None:
    cache = _CacheWithHookOnRead()
    records = ArtifactValidationRecords(cache=cache, proposed_change_id=PROPOSED_CHANGE_ID)
    first = _record(pipeline_id=FIRST_PIPELINE)
    second = _record(pipeline_id=SECOND_PIPELINE, diff_to_time=AFTER)
    await records.start(definition_id=DEFINITION_ID, record=first)

    async def start_second() -> None:
        await records.start(definition_id=DEFINITION_ID, record=second)

    cache.on_next_read = start_second
    await records.complete(definition_id=DEFINITION_ID, record=first, failed_target_ids=[])
    if cache.on_next_read is not None:
        cache.on_next_read = None
        await start_second()

    assert await records.get(definition_ids=[DEFINITION_ID]) == {
        DEFINITION_ID: _record(pipeline_id=SECOND_PIPELINE, diff_to_time=AFTER, completed=False)
    }


async def test_completing_a_record_that_is_no_longer_stored_leaves_no_record() -> None:
    records = ArtifactValidationRecords(cache=MemoryCache(), proposed_change_id=PROPOSED_CHANGE_ID)

    await records.complete(definition_id=DEFINITION_ID, record=_record(), failed_target_ids=[])

    assert await records.get(definition_ids=[DEFINITION_ID]) == {}


async def test_record_of_a_validation_that_started_after_a_completion_is_not_completed() -> None:
    records = ArtifactValidationRecords(cache=MemoryCache(), proposed_change_id=PROPOSED_CHANGE_ID)
    first = _record(pipeline_id=FIRST_PIPELINE)
    await records.start(definition_id=DEFINITION_ID, record=first)
    await records.complete(definition_id=DEFINITION_ID, record=first, failed_target_ids=[])

    await records.start(definition_id=DEFINITION_ID, record=_record(pipeline_id=SECOND_PIPELINE, diff_to_time=AFTER))

    assert await records.get(definition_ids=[DEFINITION_ID]) == {
        DEFINITION_ID: _record(pipeline_id=SECOND_PIPELINE, diff_to_time=AFTER, completed=False)
    }


async def test_records_are_read_per_definition() -> None:
    records = ArtifactValidationRecords(cache=MemoryCache(), proposed_change_id=PROPOSED_CHANGE_ID)
    await records.start(definition_id=DEFINITION_ID, record=_record())

    stored = await records.get(definition_ids=[OTHER_DEFINITION_ID, DEFINITION_ID])

    assert stored == {DEFINITION_ID: _record(completed=False)}


async def test_discarded_record_is_removed() -> None:
    cache = MemoryCache()
    records = ArtifactValidationRecords(cache=cache, proposed_change_id=PROPOSED_CHANGE_ID)
    await records.start(definition_id=DEFINITION_ID, record=_record())

    await records.discard(definition_id=DEFINITION_ID)

    assert cache.storage == {}


def _validation_run(
    *,
    records: ArtifactValidationRecords,
    window: BranchDiffWindow | None,
    pipeline_id: UUID = SECOND_PIPELINE,
    repository: ProposedChangeRepository | None = None,
) -> ArtifactValidationRun:
    return ArtifactValidationRun(
        records=records,
        definition_id=DEFINITION_ID,
        pipeline_id=pipeline_id,
        window=window,
        repository=repository or _repository(),
    )


DIFF_SUMMARY: list[NodeDiff] = [
    node_diff(node_id=DEVICE_1, kind="TestDevice", branch="feature", field_names=["name"]),
    node_diff(node_id=DEVICE_2, kind="TestDevice", branch="feature", field_names=["name"]),
]
ONLY_DEVICE_2: list[NodeDiff] = [node_diff(node_id=DEVICE_2, kind="TestDevice", branch="feature", field_names=["name"])]
CHANGES_AFTER_VALIDATION = BranchChanges(diff_summary=ONLY_DEVICE_2)


async def _completed_records() -> ArtifactValidationRecords:
    records = ArtifactValidationRecords(cache=MemoryCache(), proposed_change_id=PROPOSED_CHANGE_ID)
    await records.start(definition_id=DEFINITION_ID, record=_record())
    await records.complete(definition_id=DEFINITION_ID, record=_record(), failed_target_ids=[])
    return records


async def test_run_after_a_completed_validation_selects_from_the_later_changes_only() -> None:
    records = await _completed_records()
    run = _validation_run(records=records, window=_window())

    await run.start(previous_conclusion=ValidatorConclusion.SUCCESS.value)
    changes = run.changes_to_validate(
        diff_summary=DIFF_SUMMARY,
        unvalidated_changes=CHANGES_AFTER_VALIDATION,
        target_group_id=GROUP_ID,
        members_with_artifact=[],
    )

    assert run.unvalidated_window == _window(from_time=VALIDATED_UNTIL, to_time=NOW)
    assert changes == ChangesToValidate(diff_summary=ONLY_DEVICE_2, validated_until=VALIDATED_UNTIL)


async def test_run_holds_the_record_as_not_completed_until_it_completes() -> None:
    records = await _completed_records()
    run = _validation_run(records=records, window=_window())

    await run.start(previous_conclusion=ValidatorConclusion.SUCCESS.value)

    in_progress = _record(pipeline_id=SECOND_PIPELINE, diff_to_time=NOW, completed=False)
    assert await records.get(definition_ids=[DEFINITION_ID]) == {DEFINITION_ID: in_progress}

    await run.complete(failed_target_ids=[])

    completed = _record(pipeline_id=SECOND_PIPELINE, diff_to_time=NOW, completed=True)
    assert await records.get(definition_ids=[DEFINITION_ID]) == {DEFINITION_ID: completed}


async def test_run_after_a_validator_that_failed_outside_the_validation_selects_from_the_whole_diff() -> None:
    records = await _completed_records()
    run = _validation_run(records=records, window=_window())

    await run.start(previous_conclusion=ValidatorConclusion.FAILURE.value)
    changes = run.changes_to_validate(
        diff_summary=DIFF_SUMMARY, unvalidated_changes=None, target_group_id=GROUP_ID, members_with_artifact=[]
    )

    assert run.unvalidated_window is None
    assert changes == ChangesToValidate(diff_summary=DIFF_SUMMARY, validated_until=None)


async def _records_with_a_failed_target() -> ArtifactValidationRecords:
    records = ArtifactValidationRecords(cache=MemoryCache(), proposed_change_id=PROPOSED_CHANGE_ID)
    await records.start(definition_id=DEFINITION_ID, record=_record())
    await records.complete(definition_id=DEFINITION_ID, record=_record(), failed_target_ids=[DEVICE_1])
    return records


async def test_run_after_a_validation_with_a_failed_check_retries_its_target_with_the_later_changes() -> None:
    run = _validation_run(records=await _records_with_a_failed_target(), window=_window())

    await run.start(previous_conclusion=ValidatorConclusion.FAILURE.value)
    changes = run.changes_to_validate(
        diff_summary=DIFF_SUMMARY,
        unvalidated_changes=CHANGES_AFTER_VALIDATION,
        target_group_id=GROUP_ID,
        members_with_artifact=[],
    )

    assert run.targets_to_retry == frozenset({DEVICE_1})
    assert changes == ChangesToValidate(diff_summary=ONLY_DEVICE_2, validated_until=VALIDATED_UNTIL)


@dataclass(frozen=True, kw_only=True)
class FailedTargetCase:
    name: str
    previous_conclusion: str | None
    window: BranchDiffWindow


FAILED_TARGET_CASES: list[FailedTargetCase] = [
    FailedTargetCase(
        name="validator_shows_success",
        previous_conclusion=ValidatorConclusion.SUCCESS.value,
        window=_window(),
    ),
    FailedTargetCase(name="validator_not_completed", previous_conclusion=None, window=_window()),
    FailedTargetCase(
        name="branch_rebased_since",
        previous_conclusion=ValidatorConclusion.FAILURE.value,
        window=_window(from_time=REBASED_AT),
    ),
]


@pytest.mark.parametrize("test_case", [pytest.param(tc, id=tc.name) for tc in FAILED_TARGET_CASES])
async def test_run_that_cannot_rely_on_a_validation_with_a_failed_check_selects_from_the_whole_diff(
    test_case: FailedTargetCase,
) -> None:
    run = _validation_run(records=await _records_with_a_failed_target(), window=test_case.window)

    await run.start(previous_conclusion=test_case.previous_conclusion)
    changes = run.changes_to_validate(
        diff_summary=DIFF_SUMMARY, unvalidated_changes=None, target_group_id=GROUP_ID, members_with_artifact=[]
    )

    assert run.targets_to_retry == frozenset()
    assert changes == ChangesToValidate(diff_summary=DIFF_SUMMARY, validated_until=None)


async def test_run_records_the_targets_whose_check_failed_when_it_completes() -> None:
    records = await _completed_records()
    run = _validation_run(records=records, window=_window())
    await run.start(previous_conclusion=ValidatorConclusion.SUCCESS.value)

    await run.complete(failed_target_ids=[DEVICE_2])

    assert await records.get(definition_ids=[DEFINITION_ID]) == {
        DEFINITION_ID: _record(
            pipeline_id=SECOND_PIPELINE, diff_to_time=NOW, completed=True, failed_target_ids=frozenset({DEVICE_2})
        )
    }


async def _conclusion(conclusion: ValidatorConclusion) -> ValidatorConclusion:
    return conclusion


async def _raise_timeout() -> ValidatorConclusion:
    raise TimeoutError("The artifact check timed out")


async def test_check_outcomes_hold_the_targets_whose_check_failed_or_raised() -> None:
    outcomes = TargetCheckOutcomes()

    succeeded = await outcomes.track(target_id=DEVICE_1, check=_conclusion(ValidatorConclusion.SUCCESS))
    failed = await outcomes.track(target_id=DEVICE_2, check=_conclusion(ValidatorConclusion.FAILURE))
    with pytest.raises(TimeoutError, match=r"^The artifact check timed out$"):
        await outcomes.track(target_id=GROUP_ID, check=_raise_timeout())

    assert (succeeded, failed) == (ValidatorConclusion.SUCCESS, ValidatorConclusion.FAILURE)
    assert outcomes.failed_target_ids == frozenset({DEVICE_2, GROUP_ID})


async def test_run_after_a_validation_that_is_still_in_progress_selects_from_the_whole_diff() -> None:
    records = ArtifactValidationRecords(cache=MemoryCache(), proposed_change_id=PROPOSED_CHANGE_ID)
    await records.start(definition_id=DEFINITION_ID, record=_record())
    run = _validation_run(records=records, window=_window())

    await run.start(previous_conclusion=ValidatorConclusion.SUCCESS.value)
    changes = run.changes_to_validate(
        diff_summary=DIFF_SUMMARY, unvalidated_changes=None, target_group_id=GROUP_ID, members_with_artifact=[]
    )

    assert run.unvalidated_window is None
    assert changes == ChangesToValidate(diff_summary=DIFF_SUMMARY, validated_until=None)


async def test_run_without_a_diff_window_selects_from_the_whole_diff_and_removes_the_record() -> None:
    cache = MemoryCache()
    records = ArtifactValidationRecords(cache=cache, proposed_change_id=PROPOSED_CHANGE_ID)
    await records.start(definition_id=DEFINITION_ID, record=_record())
    await records.complete(definition_id=DEFINITION_ID, record=_record(), failed_target_ids=[])
    run = _validation_run(records=records, window=None)

    await run.start(previous_conclusion=ValidatorConclusion.SUCCESS.value)
    changes = run.changes_to_validate(
        diff_summary=DIFF_SUMMARY, unvalidated_changes=None, target_group_id=GROUP_ID, members_with_artifact=[]
    )
    await run.complete(failed_target_ids=[])

    assert run.unvalidated_window is None
    assert changes == ChangesToValidate(diff_summary=DIFF_SUMMARY, validated_until=None)
    assert await records.get(definition_ids=[DEFINITION_ID]) == {}


@dataclass(frozen=True, kw_only=True)
class GroupMemberCase:
    name: str
    members_with_artifact: list[str]
    expected: ChangesToValidate


GROUP_MEMBER_CASES: list[GroupMemberCase] = [
    GroupMemberCase(
        name="member_with_an_artifact_joined_after_the_validation",
        members_with_artifact=[DEVICE_1],
        expected=ChangesToValidate(diff_summary=DIFF_SUMMARY, validated_until=None),
    ),
    GroupMemberCase(
        name="member_without_an_artifact_joined_after_the_validation",
        members_with_artifact=[DEVICE_2],
        expected=ChangesToValidate(diff_summary=ONLY_DEVICE_2, validated_until=VALIDATED_UNTIL),
    ),
]


@pytest.mark.parametrize("test_case", [pytest.param(tc, id=tc.name) for tc in GROUP_MEMBER_CASES])
async def test_run_with_a_change_of_the_target_group_members(test_case: GroupMemberCase) -> None:
    records = await _completed_records()
    run = _validation_run(records=records, window=_window())

    await run.start(previous_conclusion=ValidatorConclusion.SUCCESS.value)
    changes = run.changes_to_validate(
        diff_summary=DIFF_SUMMARY,
        unvalidated_changes=BranchChanges(
            diff_summary=ONLY_DEVICE_2, changed_peers={GROUP_ID: {"members": [DEVICE_1]}}
        ),
        target_group_id=GROUP_ID,
        members_with_artifact=test_case.members_with_artifact,
    )

    assert changes == test_case.expected


@dataclass(frozen=True, kw_only=True)
class ReachDefinitionCase:
    name: str
    recent_diff_summary: list[NodeDiff] = field(default_factory=list)
    recent_kinds: list[str] = field(default_factory=list)
    changed_peers: dict[str, dict[str, list[str]]] = field(default_factory=dict)
    expected: bool


REACH_DEFINITION_CASES: list[ReachDefinitionCase] = [
    ReachDefinitionCase(name="no_change", expected=False),
    ReachDefinitionCase(
        name="change_of_a_kind_the_query_does_not_read",
        recent_diff_summary=[node_diff(node_id=DEVICE_1, kind="TestInterface", field_names=["name"])],
        recent_kinds=["TestInterface"],
        expected=False,
    ),
    ReachDefinitionCase(
        name="change_of_a_kind_the_query_reads",
        recent_diff_summary=[node_diff(node_id=DEVICE_1, kind="TestDevice", field_names=["name"])],
        recent_kinds=["TestDevice"],
        expected=True,
    ),
    ReachDefinitionCase(
        name="query_changed",
        recent_diff_summary=[node_diff(node_id=QUERY_ID, kind="CoreGraphQLQuery", field_names=["query"])],
        recent_kinds=["CoreGraphQLQuery"],
        expected=True,
    ),
    ReachDefinitionCase(
        name="definition_changed",
        recent_diff_summary=[node_diff(node_id=DEFINITION_ID, kind="CoreArtifactDefinition", field_names=["targets"])],
        recent_kinds=["CoreArtifactDefinition"],
        expected=True,
    ),
    ReachDefinitionCase(
        name="target_group_member_changed", changed_peers={GROUP_ID: {"members": [DEVICE_1]}}, expected=True
    ),
    ReachDefinitionCase(
        name="member_of_another_group_changed",
        changed_peers={DEVICE_2: {"members": [DEVICE_1]}},
        expected=False,
    ),
]


@pytest.mark.parametrize("test_case", [pytest.param(tc, id=tc.name) for tc in REACH_DEFINITION_CASES])
def test_changes_reach_definition(test_case: ReachDefinitionCase) -> None:
    reached = changes_reach_definition(
        definition=_definition(),
        target_group_id=GROUP_ID,
        read_kinds=["TestDevice"],
        recent_changes=RecentChanges(
            changes=BranchChanges(diff_summary=test_case.recent_diff_summary, changed_peers=test_case.changed_peers),
            modified_kinds=test_case.recent_kinds,
        ),
    )

    assert reached is test_case.expected


async def test_run_for_a_target_group_the_diff_does_not_track_selects_from_the_whole_diff() -> None:
    records = await _completed_records()
    run = _validation_run(records=records, window=_window())

    await run.start(previous_conclusion=ValidatorConclusion.SUCCESS.value)
    changes = run.changes_to_validate(
        diff_summary=DIFF_SUMMARY,
        unvalidated_changes=CHANGES_AFTER_VALIDATION,
        target_group_id=None,
        members_with_artifact=[],
    )

    assert changes == ChangesToValidate(diff_summary=DIFF_SUMMARY, validated_until=None)


@pytest.fixture(scope="module")
def core_schema_branch() -> SchemaBranch:
    schema_branch = SchemaBranch(cache={}, name="test")
    schema_branch.load_schema(schema=SchemaRoot(**core_models))
    schema_branch.process()
    return schema_branch


def test_diff_tracks_the_members_of_a_branch_aware_group(core_schema_branch: SchemaBranch) -> None:
    assert diff_tracks_members(group_kind=InfrahubKind.STANDARDGROUP, schema_branch=core_schema_branch) is True


def test_diff_does_not_track_the_members_of_a_branch_local_group(core_schema_branch: SchemaBranch) -> None:
    assert diff_tracks_members(group_kind=InfrahubKind.GENERATORGROUP, schema_branch=core_schema_branch) is False
