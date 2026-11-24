import pytest

from infrahub.artifacts.models import ArtifactCheckResult
from infrahub.core.constants import ValidatorConclusion, ValidatorState
from infrahub.proposed_change.artifact_retry import (
    ArtifactRetryRecord,
    ArtifactRetryRecords,
    merge_artifact_outcomes,
)
from tests.adapters.cache import MemoryCache

COMPLETED_AT = "2026-11-24T10:00:00.000000Z"


def test_partial_retry_keeps_untouched_outcomes_and_replaces_repaired_failure() -> None:
    previous = {
        "repaired": ArtifactCheckResult(conclusion=ValidatorConclusion.FAILURE, check_id="check-1"),
        "still-failed": ArtifactCheckResult(conclusion=ValidatorConclusion.FAILURE, check_id="check-2"),
        "succeeded": ArtifactCheckResult(conclusion=ValidatorConclusion.SUCCESS, check_id="check-3"),
        "removed": ArtifactCheckResult(conclusion=ValidatorConclusion.SUCCESS, check_id="check-4"),
    }

    outcomes = merge_artifact_outcomes(
        previous=previous,
        updates={
            "repaired": ArtifactCheckResult(conclusion=ValidatorConclusion.SUCCESS, check_id="check-1"),
            "new": ArtifactCheckResult(conclusion=ValidatorConclusion.FAILURE),
        },
        eligible_target_ids={"repaired", "still-failed", "succeeded", "new"},
    )
    record = ArtifactRetryRecord(validator_id="validator", outcomes=outcomes)

    assert outcomes == {
        "repaired": ArtifactCheckResult(conclusion=ValidatorConclusion.SUCCESS, check_id="check-1"),
        "still-failed": ArtifactCheckResult(conclusion=ValidatorConclusion.FAILURE, check_id="check-2"),
        "succeeded": ArtifactCheckResult(conclusion=ValidatorConclusion.SUCCESS, check_id="check-3"),
        "new": ArtifactCheckResult(conclusion=ValidatorConclusion.FAILURE),
    }
    assert record.failed_target_ids == {"still-failed", "new"}
    assert record.conclusion == ValidatorConclusion.FAILURE
    assert previous["repaired"].conclusion == ValidatorConclusion.FAILURE


@pytest.mark.parametrize(
    ("validator_id", "completed_at", "conclusion", "state", "matches"),
    [
        ("validator", COMPLETED_AT, "failure", "completed", True),
        ("another-validator", COMPLETED_AT, "failure", "completed", False),
        ("validator", "2026-11-24T11:00:00.000000Z", "failure", "completed", False),
        ("validator", None, "failure", "completed", False),
        ("validator", COMPLETED_AT, "success", "completed", False),
        ("validator", COMPLETED_AT, "failure", "in_progress", False),
        ("validator", COMPLETED_AT, "failure", "queued", False),
    ],
)
def test_retry_record_requires_the_same_completed_validator(
    validator_id: str, completed_at: str | None, conclusion: str, state: str, matches: bool
) -> None:
    record = ArtifactRetryRecord(
        validator_id="validator",
        completed=True,
        completed_at=COMPLETED_AT,
        outcomes={"target": ArtifactCheckResult(conclusion=ValidatorConclusion.FAILURE, check_id="check")},
    )

    assert (
        record.matches_validator(
            validator_id=validator_id, completed_at=completed_at, conclusion=conclusion, state=state
        )
        is matches
    )


def test_unknown_outcome_cannot_authorize_a_retry() -> None:
    record = ArtifactRetryRecord(
        validator_id="validator",
        completed=True,
        completed_at=COMPLETED_AT,
        outcomes={
            "failed": ArtifactCheckResult(conclusion=ValidatorConclusion.FAILURE),
            "unfinished": ArtifactCheckResult(conclusion=ValidatorConclusion.UNKNOWN),
        },
    )

    assert not record.matches_validator(
        validator_id="validator",
        completed_at=COMPLETED_AT,
        conclusion=ValidatorConclusion.FAILURE.value,
        state=ValidatorState.COMPLETED.value,
    )
    assert record.failed_target_ids == {"failed"}


async def test_start_invalidates_previous_completion_until_new_outcomes_are_saved() -> None:
    cache = MemoryCache()
    records = ArtifactRetryRecords(cache=cache)
    previous = ArtifactRetryRecord(
        validator_id="validator",
        completed=True,
        completed_at=COMPLETED_AT,
        outcomes={"target": ArtifactCheckResult(conclusion=ValidatorConclusion.FAILURE, check_id="stable-check")},
    )

    await records.start(proposed_change_id="pc", definition_id="definition", record=previous)
    started = await records.get(proposed_change_id="pc", definition_id="definition")

    assert started is not None
    assert started.outcomes == previous.outcomes
    assert not started.matches_validator(
        validator_id="validator",
        completed_at=COMPLETED_AT,
        conclusion=ValidatorConclusion.FAILURE.value,
        state=ValidatorState.COMPLETED.value,
    )
    assert started.completed_at is None
    assert previous.completed is True

    await records.complete(
        proposed_change_id="pc",
        definition_id="definition",
        record=started,
        completed_at="2026-11-24T11:00:00.000000Z",
        outcomes={"target": ArtifactCheckResult(conclusion=ValidatorConclusion.SUCCESS, check_id="stable-check")},
    )
    completed = await records.get(proposed_change_id="pc", definition_id="definition")

    assert completed is not None
    assert completed.failed_target_ids == frozenset()
    assert completed.outcomes["target"].check_id == "stable-check"
    assert completed.matches_validator(
        validator_id="validator",
        completed_at="2026-11-24T11:00:00.000000Z",
        conclusion=ValidatorConclusion.SUCCESS.value,
        state=ValidatorState.COMPLETED.value,
    )
    assert list(cache.expiries.values()) == [2592000]


async def test_records_are_isolated_by_proposed_change_and_definition() -> None:
    records = ArtifactRetryRecords(cache=MemoryCache())
    record = ArtifactRetryRecord(
        validator_id="validator", outcomes={"target": ArtifactCheckResult(conclusion=ValidatorConclusion.FAILURE)}
    )
    await records.complete(
        proposed_change_id="pc-1",
        definition_id="definition-1",
        record=record,
        completed_at=COMPLETED_AT,
        outcomes=record.outcomes,
    )

    assert await records.get(proposed_change_id="pc-2", definition_id="definition-1") is None
    assert await records.get(proposed_change_id="pc-1", definition_id="definition-2") is None
    stored = await records.get(proposed_change_id="pc-1", definition_id="definition-1")
    assert stored is not None
    assert stored.failed_target_ids == {"target"}


@pytest.mark.parametrize("payload", ["", "not-json", '{"validator_id": null}', '{"outcomes": {}}'])
async def test_missing_or_unreadable_record_does_not_supply_retry_targets(payload: str) -> None:
    cache = MemoryCache()
    await cache.set(key="proposed_change:pc:artifact_definition:definition:retry", value=payload)

    assert await ArtifactRetryRecords(cache=cache).get(proposed_change_id="pc", definition_id="definition") is None
