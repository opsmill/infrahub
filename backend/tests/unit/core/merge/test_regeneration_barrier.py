from __future__ import annotations

import logging
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime
from typing import TYPE_CHECKING

import pytest
from infrahub_sdk import Config, InfrahubClient
from structlog.testing import capture_logs

from infrahub.core.constants import FullRegenerationReason, RepositoryDeliveryStatus
from infrahub.core.merge.regeneration_barrier import NarrowedHoldCache, OwnedRegeneration, RegenerationBarrier
from infrahub.core.merge.selective_regen.definition_selector.artifact_selector import ArtifactSelector
from infrahub.core.merge.selective_regen.gate import DefinitionGate
from infrahub.exceptions import DatabaseError, DeliveryStateUnavailableError
from infrahub.git.models import RequestArtifactDefinitionGenerate
from infrahub.git.writeback.constants import NARROWED_HOLD_MAX_BYTES, NARROWED_HOLD_TTL_SECONDS
from infrahub.git.writeback.models import HeldItem, HeldRegeneration, HeldWiden, PendingMerge
from tests.adapters.cache import MemoryCache, UnreachableCache
from tests.helpers.selective_regen import NoImpactResolver
from tests.unit.git.writeback.fakes import FixedClock, InMemoryDeliveryState

if TYPE_CHECKING:
    from collections.abc import Callable

    from pydantic import BaseModel

    from infrahub.message_bus.types import KVTTL
    from infrahub.services.adapters.cache import InfrahubCache

NOW = datetime(2026, 10, 7, 12, 0, tzinfo=UTC)
DEFAULT_BRANCH = "main"
REPOSITORY_X = "repository-x"
REPOSITORY_Y = "repository-y"
REPOSITORY_Z = "repository-z"
REPOSITORIES = (REPOSITORY_X, REPOSITORY_Y, REPOSITORY_Z)
COMMIT = "0123456789abcdef0123456789abcdef01234567"
SELECTOR_LOG = logging.getLogger("test")
ARTIFACT_SELECTOR = ArtifactSelector(
    client=InfrahubClient(config=Config(address="http://mock")),
    gate=DefinitionGate(log=SELECTOR_LOG),
    impacted_resolver=NoImpactResolver(),
    log=SELECTOR_LOG,
)


class RecordedSleep:
    """Record each delay and return at once."""

    def __init__(self) -> None:
        self.delays: list[float] = []

    async def __call__(self, delay: float) -> None:
        self.delays.append(delay)


class ExpiryRecordingCache(MemoryCache):
    """A memory cache that also records the time to live of each value it keeps."""

    def __init__(self) -> None:
        super().__init__()
        self.expires: dict[str, KVTTL | int | None] = {}

    async def set(
        self, key: str, value: str, expires: KVTTL | int | None = None, not_exists: bool = False
    ) -> bool | None:
        self.expires[key] = expires
        return await super().set(key=key, value=value, expires=expires, not_exists=not_exists)


def _join_artifact_requests(previous: BaseModel, new: BaseModel) -> BaseModel:
    assert isinstance(previous, RequestArtifactDefinitionGenerate)
    assert isinstance(new, RequestArtifactDefinitionGenerate)
    (joined,) = ARTIFACT_SELECTOR.consolidate([previous, new])
    return joined


def _request(*, definition_id: str, members: tuple[str, ...]) -> RequestArtifactDefinitionGenerate:
    return RequestArtifactDefinitionGenerate(
        artifact_definition_id=definition_id,
        artifact_definition_name=f"{definition_id}-name",
        branch=DEFAULT_BRANCH,
        members=list(members),
    )


def _artifact(
    *,
    definition_id: str,
    repository_id: str | None,
    members: tuple[str, ...] = ("member-1",),
    union: Callable[[BaseModel, BaseModel], BaseModel] | None = _join_artifact_requests,
) -> OwnedRegeneration[RequestArtifactDefinitionGenerate]:
    return OwnedRegeneration(
        repository_id=repository_id,
        held=HeldRegeneration(artifact_definitions=(HeldItem(id=definition_id, hold_seq=0),)),
        request=_request(definition_id=definition_id, members=members),
        union=union,
    )


def _widen_marker(*, hold_seq: int) -> HeldWiden:
    return HeldWiden(scope="all", reason=FullRegenerationReason.FEATURE_DISABLED, hold_seq=hold_seq)


def _widen(*, repository_id: str) -> OwnedRegeneration[HeldWiden]:
    return OwnedRegeneration(
        repository_id=repository_id,
        held=HeldRegeneration(widen=_widen_marker(hold_seq=0)),
        request=_widen_marker(hold_seq=0),
        union=None,
    )


def _held_artifacts(*items: tuple[str, int], next_hold_seq: int = 2) -> HeldRegeneration:
    return HeldRegeneration(
        next_hold_seq=next_hold_seq,
        artifact_definitions=tuple(HeldItem(id=item_id, hold_seq=hold_seq) for item_id, hold_seq in items),
    )


def _key(*, repository_id: str, hold_seq: int, definition_id: str) -> str:
    return f"repository-delivery:held:{repository_id}:{hold_seq}:{definition_id}"


async def _state(*, queued: tuple[str, ...] = (), settled: tuple[str, ...] = ()) -> InMemoryDeliveryState:
    """Queue a merge for each repository of `queued`, and mark each of `settled` pending with an empty queue."""
    state = InMemoryDeliveryState(
        clock=FixedClock(now=NOW), repository_names={repository_id: repository_id for repository_id in REPOSITORIES}
    )
    for repository_id in queued:
        await state.enqueue(
            repository_id=repository_id,
            entry=PendingMerge(
                entry_id=f"{repository_id}-merge",
                source_branch="feature",
                source_git_branch="feature",
                source_commit=COMMIT,
                merged_at=NOW,
            ),
            widen=False,
        )
    for repository_id in settled:
        state.intents[repository_id] = replace(state.intents[repository_id], status=RepositoryDeliveryStatus.PENDING)
    state.calls.clear()
    return state


def _barrier(*, state: InMemoryDeliveryState, cache: InfrahubCache, sleep: RecordedSleep) -> RegenerationBarrier:
    return RegenerationBarrier(
        state=state,
        narrowed=NarrowedHoldCache(
            cache=cache, ttl_seconds=NARROWED_HOLD_TTL_SECONDS, max_bytes=NARROWED_HOLD_MAX_BYTES
        ),
        default_branch_name=DEFAULT_BRANCH,
        sleep=sleep,
    )


def _held_by_repository(state: InMemoryDeliveryState) -> dict[str, HeldRegeneration]:
    return {repository_id: state.intents[repository_id].held for repository_id in REPOSITORIES}


def _cached_requests(cache: MemoryCache) -> dict[str, RequestArtifactDefinitionGenerate]:
    return {key: RequestArtifactDefinitionGenerate.model_validate_json(value) for key, value in cache.storage.items()}


async def test_admit_on_another_branch_returns_every_candidate_without_a_read() -> None:
    state = await _state(queued=(REPOSITORY_X,))
    cache = MemoryCache()
    candidates = [_artifact(definition_id="artifact-x", repository_id=REPOSITORY_X)]

    admitted = await _barrier(state=state, cache=cache, sleep=RecordedSleep()).admit(
        branch="feature", candidates=candidates, releasing=None
    )

    assert admitted == candidates
    assert state.calls == []
    assert _held_by_repository(state) == dict.fromkeys(REPOSITORIES, HeldRegeneration())
    assert cache.storage == {}


@dataclass
class PartitionTestCase:
    name: str
    candidates: list[OwnedRegeneration[BaseModel]]
    expected_admitted: list[OwnedRegeneration[BaseModel]]
    expected_calls: list[str]
    queued: tuple[str, ...] = ()
    settled: tuple[str, ...] = ()
    """Pending repositories whose queue is empty, so their hold returns None."""
    releasing: str | None = None
    expected_held: dict[str, HeldRegeneration] = field(default_factory=dict)
    """The held set of each repository that holds something; every other one holds nothing."""
    expected_cached: dict[str, RequestArtifactDefinitionGenerate] = field(default_factory=dict)


ARTIFACT_X = _artifact(definition_id="artifact-x", repository_id=REPOSITORY_X)
ARTIFACT_X_OTHER = _artifact(definition_id="artifact-x-other", repository_id=REPOSITORY_X)
ARTIFACT_Y = _artifact(definition_id="artifact-y", repository_id=REPOSITORY_Y)
ARTIFACT_UNKNOWN = _artifact(definition_id="artifact-unknown", repository_id=None)
WIDEN_X = _widen(repository_id=REPOSITORY_X)

PARTITION_TEST_CASES: list[PartitionTestCase] = [
    PartitionTestCase(
        name="no_pending_delivery_admits_every_candidate_after_one_read",
        candidates=[ARTIFACT_X, ARTIFACT_UNKNOWN],
        expected_admitted=[ARTIFACT_X, ARTIFACT_UNKNOWN],
        expected_calls=["pending_repository_ids"],
    ),
    PartitionTestCase(
        name="a_pending_owner_holds_its_candidate_and_another_owner_is_admitted",
        queued=(REPOSITORY_X,),
        candidates=[ARTIFACT_X, ARTIFACT_Y],
        expected_admitted=[ARTIFACT_Y],
        expected_calls=["pending_repository_ids", "hold"],
        expected_held={REPOSITORY_X: _held_artifacts(("artifact-x", 1))},
        expected_cached={
            _key(repository_id=REPOSITORY_X, hold_seq=1, definition_id="artifact-x"): ARTIFACT_X.request,
        },
    ),
    PartitionTestCase(
        name="a_hold_that_returns_none_admits",
        settled=(REPOSITORY_X,),
        candidates=[ARTIFACT_X],
        expected_admitted=[ARTIFACT_X],
        expected_calls=["pending_repository_ids", "hold"],
    ),
    PartitionTestCase(
        name="an_unknown_owner_is_held_under_every_pending_repository",
        queued=(REPOSITORY_X, REPOSITORY_Z),
        candidates=[ARTIFACT_UNKNOWN],
        expected_admitted=[],
        expected_calls=["pending_repository_ids", "hold", "hold"],
        expected_held={
            REPOSITORY_X: _held_artifacts(("artifact-unknown", 1)),
            REPOSITORY_Z: _held_artifacts(("artifact-unknown", 1)),
        },
        expected_cached={
            _key(repository_id=REPOSITORY_X, hold_seq=1, definition_id="artifact-unknown"): ARTIFACT_UNKNOWN.request,
            _key(repository_id=REPOSITORY_Z, hold_seq=1, definition_id="artifact-unknown"): ARTIFACT_UNKNOWN.request,
        },
    ),
    PartitionTestCase(
        name="an_unknown_owner_stays_held_when_one_hold_returns_none",
        queued=(REPOSITORY_X,),
        settled=(REPOSITORY_Z,),
        candidates=[ARTIFACT_UNKNOWN],
        expected_admitted=[],
        expected_calls=["pending_repository_ids", "hold", "hold"],
        expected_held={REPOSITORY_X: _held_artifacts(("artifact-unknown", 1))},
        expected_cached={
            _key(repository_id=REPOSITORY_X, hold_seq=1, definition_id="artifact-unknown"): ARTIFACT_UNKNOWN.request,
        },
    ),
    PartitionTestCase(
        name="an_unknown_owner_is_admitted_when_every_hold_returns_none",
        settled=(REPOSITORY_X, REPOSITORY_Z),
        candidates=[ARTIFACT_UNKNOWN],
        expected_admitted=[ARTIFACT_UNKNOWN],
        expected_calls=["pending_repository_ids", "hold", "hold"],
    ),
    PartitionTestCase(
        name="releasing_admits_its_own_candidates_and_holds_an_unknown_owner_under_the_others",
        queued=(REPOSITORY_X, REPOSITORY_Z),
        releasing=REPOSITORY_X,
        candidates=[ARTIFACT_X, ARTIFACT_UNKNOWN],
        expected_admitted=[ARTIFACT_X],
        expected_calls=["pending_repository_ids", "hold"],
        expected_held={REPOSITORY_Z: _held_artifacts(("artifact-unknown", 1))},
        expected_cached={
            _key(repository_id=REPOSITORY_Z, hold_seq=1, definition_id="artifact-unknown"): ARTIFACT_UNKNOWN.request,
        },
    ),
    PartitionTestCase(
        name="releasing_the_only_pending_repository_admits_an_unknown_owner_without_a_hold",
        queued=(REPOSITORY_X,),
        releasing=REPOSITORY_X,
        candidates=[ARTIFACT_UNKNOWN],
        expected_admitted=[ARTIFACT_UNKNOWN],
        expected_calls=["pending_repository_ids"],
    ),
    PartitionTestCase(
        name="the_candidates_of_one_repository_share_one_hold",
        queued=(REPOSITORY_X,),
        candidates=[ARTIFACT_X, ARTIFACT_X_OTHER, WIDEN_X],
        expected_admitted=[],
        expected_calls=["pending_repository_ids", "hold"],
        expected_held={
            REPOSITORY_X: HeldRegeneration(
                next_hold_seq=2,
                artifact_definitions=(
                    HeldItem(id="artifact-x", hold_seq=1),
                    HeldItem(id="artifact-x-other", hold_seq=1),
                ),
                widen=_widen_marker(hold_seq=1),
            )
        },
        expected_cached={
            _key(repository_id=REPOSITORY_X, hold_seq=1, definition_id="artifact-x"): ARTIFACT_X.request,
            _key(repository_id=REPOSITORY_X, hold_seq=1, definition_id="artifact-x-other"): ARTIFACT_X_OTHER.request,
        },
    ),
    PartitionTestCase(
        name="two_candidates_of_one_definition_keep_the_union_of_their_members",
        queued=(REPOSITORY_X,),
        candidates=[
            _artifact(definition_id="artifact-x", repository_id=REPOSITORY_X, members=("member-2",)),
            _artifact(definition_id="artifact-x", repository_id=REPOSITORY_X, members=("member-1",)),
        ],
        expected_admitted=[],
        expected_calls=["pending_repository_ids", "hold"],
        expected_held={REPOSITORY_X: _held_artifacts(("artifact-x", 1))},
        expected_cached={
            _key(repository_id=REPOSITORY_X, hold_seq=1, definition_id="artifact-x"): _request(
                definition_id="artifact-x", members=("member-1", "member-2")
            ),
        },
    ),
]


@pytest.mark.parametrize("test_case", [pytest.param(tc, id=tc.name) for tc in PARTITION_TEST_CASES])
async def test_admit_holds_the_candidates_of_each_pending_repository(test_case: PartitionTestCase) -> None:
    state = await _state(queued=test_case.queued, settled=test_case.settled)
    cache = MemoryCache()
    sleep = RecordedSleep()

    admitted = await _barrier(state=state, cache=cache, sleep=sleep).admit(
        branch=DEFAULT_BRANCH, candidates=test_case.candidates, releasing=test_case.releasing
    )

    assert admitted == test_case.expected_admitted
    assert state.calls == test_case.expected_calls
    assert _held_by_repository(state) == {
        repository_id: test_case.expected_held.get(repository_id, HeldRegeneration()) for repository_id in REPOSITORIES
    }
    assert _cached_requests(cache) == test_case.expected_cached
    assert sleep.delays == []


@dataclass
class RepeatedHoldTestCase:
    name: str
    first_members: tuple[str, ...]
    second_members: tuple[str, ...]
    expected_released_members: list[str] | None
    """The members that a release reads under the second hold; None when it reads no entry."""
    union: Callable[[BaseModel, BaseModel], BaseModel] | None = _join_artifact_requests
    first_entry_expired: bool = False


REPEATED_HOLD_TEST_CASES: list[RepeatedHoldTestCase] = [
    RepeatedHoldTestCase(
        name="two_holds_with_different_members_release_both_members",
        first_members=("member-1",),
        second_members=("member-2",),
        expected_released_members=["member-1", "member-2"],
    ),
    RepeatedHoldTestCase(
        name="a_hold_of_every_member_releases_every_member",
        first_members=("member-1",),
        second_members=(),
        expected_released_members=[],
    ),
    RepeatedHoldTestCase(
        name="a_request_with_no_union_keeps_no_entry_for_the_repeated_hold",
        first_members=("member-1",),
        second_members=("member-2",),
        union=None,
        expected_released_members=None,
    ),
    RepeatedHoldTestCase(
        name="a_missing_previous_entry_keeps_no_entry_for_the_repeated_hold",
        first_members=("member-1",),
        second_members=("member-2",),
        first_entry_expired=True,
        expected_released_members=None,
    ),
]


@pytest.mark.parametrize("test_case", [pytest.param(tc, id=tc.name) for tc in REPEATED_HOLD_TEST_CASES])
async def test_a_repeated_hold_keeps_the_union_of_the_narrowed_requests(test_case: RepeatedHoldTestCase) -> None:
    state = await _state(queued=(REPOSITORY_X,))
    cache = ExpiryRecordingCache()
    narrowed = NarrowedHoldCache(cache=cache, ttl_seconds=NARROWED_HOLD_TTL_SECONDS, max_bytes=NARROWED_HOLD_MAX_BYTES)
    barrier = RegenerationBarrier(
        state=state, narrowed=narrowed, default_branch_name=DEFAULT_BRANCH, sleep=RecordedSleep()
    )
    second_key = _key(repository_id=REPOSITORY_X, hold_seq=2, definition_id="artifact-x")

    async def hold(members: tuple[str, ...]) -> None:
        candidate = _artifact(
            definition_id="artifact-x", repository_id=REPOSITORY_X, members=members, union=test_case.union
        )
        assert await barrier.admit(branch=DEFAULT_BRANCH, candidates=[candidate], releasing=None) == []

    await hold(test_case.first_members)
    if test_case.first_entry_expired:
        await cache.delete(key=_key(repository_id=REPOSITORY_X, hold_seq=1, definition_id="artifact-x"))
    await hold(test_case.second_members)

    released = await narrowed.get(
        repository_id=REPOSITORY_X, hold_seq=2, identifier="artifact-x", model=RequestArtifactDefinitionGenerate
    )
    assert state.calls == ["pending_repository_ids", "hold", "pending_repository_ids", "hold"]
    assert _held_by_repository(state)[REPOSITORY_X] == _held_artifacts(("artifact-x", 2), next_hold_seq=3)
    if test_case.expected_released_members is None:
        assert released is None
        assert second_key not in cache.storage
    else:
        assert released == _request(definition_id="artifact-x", members=tuple(test_case.expected_released_members))
        assert cache.expires[second_key] == NARROWED_HOLD_TTL_SECONDS


async def test_a_request_above_the_size_bound_is_not_kept() -> None:
    state = await _state(queued=(REPOSITORY_X,))
    cache = ExpiryRecordingCache()
    oversized = _artifact(
        definition_id="artifact-x-other",
        repository_id=REPOSITORY_X,
        members=tuple(f"member-{index:06d}" for index in range(40_000)),
    )

    admitted = await _barrier(state=state, cache=cache, sleep=RecordedSleep()).admit(
        branch=DEFAULT_BRANCH, candidates=[ARTIFACT_X, oversized], releasing=None
    )

    assert admitted == []
    assert _held_by_repository(state)[REPOSITORY_X] == _held_artifacts(("artifact-x", 1), ("artifact-x-other", 1))
    assert cache.expires == {
        _key(repository_id=REPOSITORY_X, hold_seq=1, definition_id="artifact-x"): NARROWED_HOLD_TTL_SECONDS
    }


async def test_a_cache_failure_is_logged_and_keeps_the_hold() -> None:
    state = await _state(queued=(REPOSITORY_X,))
    sleep = RecordedSleep()
    barrier = _barrier(state=state, cache=UnreachableCache(), sleep=sleep)

    with capture_logs() as records:
        admitted = await barrier.admit(branch=DEFAULT_BRANCH, candidates=[ARTIFACT_X], releasing=None)

    assert admitted == []
    assert state.calls == ["pending_repository_ids", "hold"]
    assert _held_by_repository(state)[REPOSITORY_X] == _held_artifacts(("artifact-x", 1))
    assert sleep.delays == []
    assert [(record["log_level"], record["repository_id"], record["hold_seq"]) for record in records] == [
        ("warning", REPOSITORY_X, 1)
    ]
    assert (
        await barrier.narrowed.get(
            repository_id=REPOSITORY_X, hold_seq=1, identifier="artifact-x", model=RequestArtifactDefinitionGenerate
        )
        is None
    )


@dataclass
class StateFailureTestCase:
    name: str
    failing_method: str
    error: Exception
    failures: int
    expected_admitted: list[OwnedRegeneration[BaseModel]]
    expected_calls: list[str]
    expected_delays: list[float]
    expected_held: HeldRegeneration


STATE_ERROR = DatabaseError(message="the database is unavailable")
LOCK_TIMEOUT = DeliveryStateUnavailableError(repository_id=REPOSITORY_X, acquire_seconds=10)

STATE_FAILURE_TEST_CASES: list[StateFailureTestCase] = [
    StateFailureTestCase(
        name="a_state_error_that_clears_within_the_retries_holds",
        failing_method="pending_repository_ids",
        error=STATE_ERROR,
        failures=2,
        expected_admitted=[],
        expected_calls=["pending_repository_ids", "pending_repository_ids", "pending_repository_ids", "hold"],
        expected_delays=[2, 8],
        expected_held=_held_artifacts(("artifact-x", 1)),
    ),
    StateFailureTestCase(
        name="a_lock_timeout_that_clears_within_the_retries_holds",
        failing_method="hold",
        error=LOCK_TIMEOUT,
        failures=3,
        expected_admitted=[],
        expected_calls=["pending_repository_ids", "hold"] * 4,
        expected_delays=[2, 8, 20],
        expected_held=_held_artifacts(("artifact-x", 1)),
    ),
    StateFailureTestCase(
        name="a_state_error_that_persists_admits_after_the_last_retry",
        failing_method="pending_repository_ids",
        error=STATE_ERROR,
        failures=4,
        expected_admitted=[ARTIFACT_X],
        expected_calls=["pending_repository_ids"] * 4,
        expected_delays=[2, 8, 20],
        expected_held=HeldRegeneration(),
    ),
    StateFailureTestCase(
        name="a_lock_timeout_that_persists_admits_after_the_last_retry",
        failing_method="hold",
        error=LOCK_TIMEOUT,
        failures=4,
        expected_admitted=[ARTIFACT_X],
        expected_calls=["pending_repository_ids", "hold"] * 4,
        expected_delays=[2, 8, 20],
        expected_held=HeldRegeneration(),
    ),
]


@pytest.mark.parametrize("test_case", [pytest.param(tc, id=tc.name) for tc in STATE_FAILURE_TEST_CASES])
async def test_admit_reads_the_state_again_then_admits_when_it_stays_unreadable(
    test_case: StateFailureTestCase,
) -> None:
    state = await _state(queued=(REPOSITORY_X,))
    state.failures[test_case.failing_method] = [test_case.error] * test_case.failures
    cache = MemoryCache()
    sleep = RecordedSleep()

    with capture_logs() as records:
        admitted = await _barrier(state=state, cache=cache, sleep=sleep).admit(
            branch=DEFAULT_BRANCH, candidates=[ARTIFACT_X, ARTIFACT_Y], releasing=None
        )

    assert admitted == [*test_case.expected_admitted, ARTIFACT_Y]
    assert state.calls == test_case.expected_calls
    assert sleep.delays == test_case.expected_delays
    assert _held_by_repository(state)[REPOSITORY_X] == test_case.expected_held
    errors = [(record["branch"], record["repository_ids"]) for record in records if record["log_level"] == "error"]
    assert errors == ([(DEFAULT_BRANCH, [REPOSITORY_X, REPOSITORY_Y])] if test_case.expected_admitted else [])
    assert [record["log_level"] for record in records if record["log_level"] == "warning"] == ["warning"] * len(
        test_case.expected_delays
    )


def _terminals_marker(*, hold_seq: int) -> HeldWiden:
    return HeldWiden(scope="terminals", reason=FullRegenerationReason.TERMINAL_SELECTION_FAILED, hold_seq=hold_seq)


def _held_markers(*repository_ids: str) -> dict[str, HeldRegeneration]:
    """The held set of every repository, with the marker of the first hold under each of `repository_ids`."""
    return {
        repository_id: HeldRegeneration(next_hold_seq=2, widen=_terminals_marker(hold_seq=1))
        if repository_id in repository_ids
        else HeldRegeneration()
        for repository_id in REPOSITORIES
    }


async def test_hold_widen_on_another_branch_holds_nothing_without_a_read() -> None:
    state = await _state(queued=(REPOSITORY_X,))

    holders = await _barrier(state=state, cache=MemoryCache(), sleep=RecordedSleep()).hold_widen(
        branch="feature", widen=_terminals_marker(hold_seq=0), releasing=None
    )

    assert holders == []
    assert state.calls == []
    assert _held_by_repository(state) == _held_markers()


@dataclass
class HoldWidenTestCase:
    name: str
    expected_holders: list[str]
    expected_calls: list[str]
    queued: tuple[str, ...] = ()
    settled: tuple[str, ...] = ()
    """Pending repositories whose queue is empty, so their hold returns None."""
    releasing: str | None = None


HOLD_WIDEN_TEST_CASES: list[HoldWidenTestCase] = [
    HoldWidenTestCase(
        name="no_pending_delivery_holds_nothing_after_one_read",
        expected_holders=[],
        expected_calls=["pending_repository_ids"],
    ),
    HoldWidenTestCase(
        name="each_pending_repository_holds_the_marker",
        queued=(REPOSITORY_Z, REPOSITORY_X),
        expected_holders=[REPOSITORY_X, REPOSITORY_Z],
        expected_calls=["pending_repository_ids", "hold", "hold"],
    ),
    HoldWidenTestCase(
        name="the_releasing_repository_holds_no_marker",
        queued=(REPOSITORY_X, REPOSITORY_Z),
        releasing=REPOSITORY_X,
        expected_holders=[REPOSITORY_Z],
        expected_calls=["pending_repository_ids", "hold"],
    ),
    HoldWidenTestCase(
        name="a_repository_whose_hold_returns_none_is_not_returned",
        queued=(REPOSITORY_Z,),
        settled=(REPOSITORY_X,),
        expected_holders=[REPOSITORY_Z],
        expected_calls=["pending_repository_ids", "hold", "hold"],
    ),
]


@pytest.mark.parametrize("test_case", [pytest.param(tc, id=tc.name) for tc in HOLD_WIDEN_TEST_CASES])
async def test_hold_widen_holds_the_marker_under_each_pending_repository(test_case: HoldWidenTestCase) -> None:
    state = await _state(queued=test_case.queued, settled=test_case.settled)
    cache = MemoryCache()
    sleep = RecordedSleep()

    holders = await _barrier(state=state, cache=cache, sleep=sleep).hold_widen(
        branch=DEFAULT_BRANCH, widen=_terminals_marker(hold_seq=0), releasing=test_case.releasing
    )

    assert holders == test_case.expected_holders
    assert state.calls == test_case.expected_calls
    assert _held_by_repository(state) == _held_markers(*test_case.expected_holders)
    assert cache.storage == {}
    assert sleep.delays == []


@dataclass
class HoldWidenFailureTestCase:
    name: str
    failing_method: str
    error: Exception
    failures: int
    expected_holders: list[str]
    expected_calls: list[str]
    expected_delays: list[float]


HOLD_WIDEN_FAILURE_TEST_CASES: list[HoldWidenFailureTestCase] = [
    HoldWidenFailureTestCase(
        name="a_state_error_that_clears_within_the_retries_holds_the_marker",
        failing_method="pending_repository_ids",
        error=STATE_ERROR,
        failures=2,
        expected_holders=[REPOSITORY_X],
        expected_calls=["pending_repository_ids", "pending_repository_ids", "pending_repository_ids", "hold"],
        expected_delays=[2, 8],
    ),
    HoldWidenFailureTestCase(
        name="a_lock_timeout_that_clears_within_the_retries_holds_the_marker",
        failing_method="hold",
        error=LOCK_TIMEOUT,
        failures=3,
        expected_holders=[REPOSITORY_X],
        expected_calls=["pending_repository_ids", "hold"] * 4,
        expected_delays=[2, 8, 20],
    ),
    HoldWidenFailureTestCase(
        name="a_state_error_that_persists_returns_no_repository_after_the_last_retry",
        failing_method="pending_repository_ids",
        error=STATE_ERROR,
        failures=4,
        expected_holders=[],
        expected_calls=["pending_repository_ids"] * 4,
        expected_delays=[2, 8, 20],
    ),
    HoldWidenFailureTestCase(
        name="a_lock_timeout_that_persists_returns_no_repository_after_the_last_retry",
        failing_method="hold",
        error=LOCK_TIMEOUT,
        failures=4,
        expected_holders=[],
        expected_calls=["pending_repository_ids", "hold"] * 4,
        expected_delays=[2, 8, 20],
    ),
]


@pytest.mark.parametrize("test_case", [pytest.param(tc, id=tc.name) for tc in HOLD_WIDEN_FAILURE_TEST_CASES])
async def test_hold_widen_reads_the_state_again_then_holds_nothing_when_it_stays_unreadable(
    test_case: HoldWidenFailureTestCase,
) -> None:
    state = await _state(queued=(REPOSITORY_X,))
    state.failures[test_case.failing_method] = [test_case.error] * test_case.failures
    sleep = RecordedSleep()

    with capture_logs() as records:
        holders = await _barrier(state=state, cache=MemoryCache(), sleep=sleep).hold_widen(
            branch=DEFAULT_BRANCH, widen=_terminals_marker(hold_seq=0), releasing=None
        )

    assert holders == test_case.expected_holders
    assert state.calls == test_case.expected_calls
    assert sleep.delays == test_case.expected_delays
    assert _held_by_repository(state) == _held_markers(*test_case.expected_holders)
    errors = [
        (record["branch"], record["scope"], record["reason"]) for record in records if record["log_level"] == "error"
    ]
    assert errors == (
        []
        if test_case.expected_holders
        else [(DEFAULT_BRANCH, "terminals", FullRegenerationReason.TERMINAL_SELECTION_FAILED)]
    )
    assert [record["log_level"] for record in records if record["log_level"] == "warning"] == ["warning"] * len(
        test_case.expected_delays
    )
