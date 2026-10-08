from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

import httpx
import pytest
from infrahub_sdk import Config, InfrahubClient
from structlog.testing import capture_logs

from infrahub.auth.session import AccountSession
from infrahub.auth.types import AuthType
from infrahub.context import BranchContext, InfrahubContext
from infrahub.core.constants import FullRegenerationReason
from infrahub.core.diff.summary_cache import DiffSummaryCache
from infrahub.core.diff.summary_serializer import DiffSummarySerializer
from infrahub.core.merge.python_target_sources import DeclaredAttribute
from infrahub.core.merge.recompute_coalescing import (
    PYTHON_COMPUTED_ATTRIBUTE,
    SELF_FILTER,
    AffectedTarget,
    CoalescedRecomputeSubmitter,
    PythonTargetRequest,
    ReaderLookup,
)
from infrahub.core.merge.regeneration_barrier import NarrowedHoldCache, RegenerationBarrier
from infrahub.core.merge.regeneration_dispatcher import PostMergeRegenerationDispatcher
from infrahub.core.merge.regeneration_release import HeldRegenerationReleaser
from infrahub.core.merge.selective_regen.definition_selector.artifact_selector import ArtifactSelector
from infrahub.core.merge.selective_regen.definition_selector.generator_selector import GeneratorSelector
from infrahub.core.merge.selective_regen.gate import DefinitionGate
from infrahub.core.merge.selective_regen.models import CascadeRole, PlannedRegeneration
from infrahub.core.merge.selective_regen.orchestrator import MergeSelectiveRegeneration
from infrahub.core.merge.selective_regen.participant import CascadeSource, CascadeTerminal
from infrahub.exceptions import ServiceUnavailableError
from infrahub.generators.constants import GeneratorDefinitionRunSource
from infrahub.generators.models import ProposedChangeGeneratorDefinition, RequestGeneratorDefinitionRun
from infrahub.git.models import RequestArtifactDefinitionGenerate
from infrahub.git.writeback.constants import NARROWED_HOLD_MAX_BYTES, NARROWED_HOLD_TTL_SECONDS
from infrahub.git.writeback.models import HeldItem, HeldPythonAttribute, HeldRegeneration, HeldWiden, PendingMerge
from infrahub.workflows.catalogue import (
    COMPUTED_ATTRIBUTE_PROCESS_TRANSFORM,
    REQUEST_ARTIFACT_DEFINITION_GENERATE,
    REQUEST_GENERATOR_DEFINITION_RUN,
    TRIGGER_ARTIFACT_DEFINITION_GENERATE,
    TRIGGER_GENERATOR_DEFINITION_RUN,
    TRIGGER_UPDATE_PYTHON_COMPUTED_ATTRIBUTES,
)
from tests.adapters.cache import MemoryCache
from tests.adapters.workflow import WorkflowRecorder
from tests.helpers.selective_regen import NoImpactResolver, PassthroughExpander, StubCascadeSourceOutput
from tests.unit.git.writeback.fakes import FixedClock, InMemoryDeliveryState

if TYPE_CHECKING:
    from collections.abc import Collection, Mapping, Sequence

    from infrahub_sdk.diff import NodeDiff

    from infrahub.events.models import EventContext
    from infrahub.workflows.constants import WorkflowPriority
    from infrahub.workflows.models import WorkflowDefinition, WorkflowInfo

DEFAULT_BRANCH = "main"
NOW = datetime(2026, 10, 8, 12, 0, tzinfo=UTC)
REPOSITORY_X = "repository-x"
REPOSITORY_Y = "repository-y"
COMMIT = "0123456789abcdef0123456789abcdef01234567"
LOG = logging.getLogger("test")
CLIENT = InfrahubClient(config=Config(address="http://mock"))
CONTEXT = InfrahubContext(
    branch=BranchContext(name=DEFAULT_BRANCH),
    account=AccountSession(account_id="test-account", auth_type=AuthType.API),
)
CAR_DESCRIPTION = DeclaredAttribute(kind="TestCar", attribute_name="description")
PERSON_SUMMARY = DeclaredAttribute(kind="TestPerson", attribute_name="summary")
LOCATION_NAME = DeclaredAttribute(kind="TestLocation", attribute_name="name")
FULL_RELEASE_EVENT = "Regenerating every definition of the repository to release its held regeneration"
TERMINALS_RELEASE_EVENT = "Regenerating every artifact definition of the repository to release its held regeneration"


def _generator_run(
    *, definition_id: str, file_path: str = "gen.py", target_members: tuple[str, ...] = ()
) -> RequestGeneratorDefinitionRun:
    return RequestGeneratorDefinitionRun(
        branch=DEFAULT_BRANCH,
        generator_definition=ProposedChangeGeneratorDefinition(
            definition_id=definition_id,
            definition_name=definition_id,
            query_name="q",
            convert_query_response=False,
            class_name="Gen",
            file_path=file_path,
            group_id="group-1",
            parameters={},
            execute_in_proposed_change=False,
            execute_after_merge=True,
            query_id="q1",
            query_models=["TestDevice"],
            query_payload="query { TestDevice { edges { node { id } } } }",
            repository_id=REPOSITORY_X,
        ),
        target_members=list(target_members),
    )


def _artifact_generate(
    *,
    definition_id: str,
    repository_id: str = REPOSITORY_X,
    name: str | None = None,
    members: tuple[str, ...] = (),
    limit: tuple[str, ...] = (),
) -> RequestArtifactDefinitionGenerate:
    return RequestArtifactDefinitionGenerate(
        branch=DEFAULT_BRANCH,
        artifact_definition_id=definition_id,
        artifact_definition_name=name or definition_id,
        members=list(members),
        limit=list(limit),
        repository_id=repository_id,
    )


class FakeHeldDefinitions:
    """The definitions that exist now on the default branch, and the Python computed attributes of each repository."""

    def __init__(
        self,
        *,
        artifacts: Sequence[RequestArtifactDefinitionGenerate] = (),
        generators: Sequence[RequestGeneratorDefinitionRun] = (),
        python_attributes: Mapping[str, list[DeclaredAttribute]] | None = None,
    ) -> None:
        self.artifacts = artifacts
        self.generators = generators
        self.owned_python_attributes = python_attributes or {}

    async def artifact_requests(
        self, *, branch: str, ids: Collection[str]
    ) -> dict[str, RequestArtifactDefinitionGenerate]:
        if branch != DEFAULT_BRANCH:
            return {}
        return {
            request.artifact_definition_id: request
            for request in self.artifacts
            if request.artifact_definition_id in ids
        }

    async def generator_requests(
        self, *, branch: str, ids: Collection[str]
    ) -> dict[str, RequestGeneratorDefinitionRun | None]:
        if branch != DEFAULT_BRANCH:
            return {}
        return {
            request.generator_definition.definition_id: request
            for request in self.generators
            if request.generator_definition.definition_id in ids
        }

    async def python_attributes(self, *, branch: str, repository_id: str) -> list[DeclaredAttribute]:
        if branch != DEFAULT_BRANCH:
            return []
        return self.owned_python_attributes.get(repository_id, [])


class ReselectingPlanner(MergeSelectiveRegeneration):
    """The merge planner with its real participants, and a fixed reselection of artifacts from the generator output."""

    def __init__(self, *, reselected: Sequence[RequestArtifactDefinitionGenerate]) -> None:
        gate = DefinitionGate(log=LOG)
        super().__init__(
            participants=[
                CascadeSource(
                    GeneratorSelector(client=CLIENT, gate=gate, impacted_resolver=NoImpactResolver(), log=LOG),
                    output=StubCascadeSourceOutput(),
                ),
                CascadeTerminal(
                    ArtifactSelector(client=CLIENT, gate=gate, impacted_resolver=NoImpactResolver(), log=LOG)
                ),
            ],
            kinds_expander=PassthroughExpander(),
        )
        self.reselected = reselected

    async def reselect_from_cascade_output(
        self, diff_summary: list[NodeDiff], target_branch: str
    ) -> list[PlannedRegeneration]:
        return [
            PlannedRegeneration(
                workflow=REQUEST_ARTIFACT_DEFINITION_GENERATE,
                cascade_role=CascadeRole.TERMINAL,
                requests=self.reselected,
            )
        ]


class FailingWorkflowRecorder(WorkflowRecorder):
    """Record each call, and raise on every submission or run of one workflow."""

    def __init__(self, *, failing: WorkflowDefinition, run_error: type[Exception] = RuntimeError) -> None:
        super().__init__()
        self.failing = failing
        self.run_error = run_error

    async def execute_workflow(  # noqa: PLR0913, PLR0917
        self,
        workflow: WorkflowDefinition,
        expected_return: type | None = None,
        context: InfrahubContext | EventContext | None = None,
        parameters: dict[str, Any] | None = None,
        tags: list[str] | None = None,
        priority: WorkflowPriority | None = None,
    ) -> Any:
        result = await super().execute_workflow(
            workflow,
            expected_return=expected_return,
            context=context,
            parameters=parameters,
            tags=tags,
            priority=priority,
        )
        if workflow == self.failing:
            raise self.run_error(f"Could not run {workflow.name}")
        return result

    async def submit_workflow(
        self,
        workflow: WorkflowDefinition,
        context: InfrahubContext | EventContext | None = None,
        parameters: dict[str, Any] | None = None,
        tags: list[str] | None = None,
        priority: WorkflowPriority | None = None,
    ) -> WorkflowInfo:
        info = await super().submit_workflow(
            workflow, context=context, parameters=parameters, tags=tags, priority=priority
        )
        if workflow == self.failing:
            raise RuntimeError(f"Could not submit {workflow.name}")
        return info


class RecordedRenewals:
    """Record how many workflow calls the recorder holds at each renewal of the lease."""

    def __init__(self, *, recorder: WorkflowRecorder) -> None:
        self.recorder = recorder
        self.after_calls: list[int] = []

    async def __call__(self) -> None:
        self.after_calls.append(len(self.recorder.calls))


async def _no_wait(delay: float) -> None:
    """Return at once; no case here makes the delivery state fail."""


async def _delivery_state(*pending: str) -> InMemoryDeliveryState:
    """Queue one merge for each repository of `pending`, so that each one has a pending delivery."""
    state = InMemoryDeliveryState(
        clock=FixedClock(now=NOW), repository_names={REPOSITORY_X: REPOSITORY_X, REPOSITORY_Y: REPOSITORY_Y}
    )
    for repository_id in pending:
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
    state.calls.clear()
    return state


def _narrowed() -> NarrowedHoldCache:
    return NarrowedHoldCache(
        cache=MemoryCache(), ttl_seconds=NARROWED_HOLD_TTL_SECONDS, max_bytes=NARROWED_HOLD_MAX_BYTES
    )


def _releaser(
    *,
    recorder: WorkflowRecorder,
    definitions: FakeHeldDefinitions,
    state: InMemoryDeliveryState,
    narrowed: NarrowedHoldCache,
    reselected: Sequence[RequestArtifactDefinitionGenerate] = (),
) -> HeldRegenerationReleaser:
    dispatcher = PostMergeRegenerationDispatcher(
        workflow=recorder,
        planner=ReselectingPlanner(reselected=reselected),
        summary_cache=DiffSummaryCache(
            cache=MemoryCache(), serializer=DiffSummarySerializer(), key_namespace="branch_merge"
        ),
        barrier=RegenerationBarrier(state=state, narrowed=narrowed, default_branch_name=DEFAULT_BRANCH, sleep=_no_wait),
        log=LOG,
    )
    return HeldRegenerationReleaser(
        dispatcher=dispatcher,
        python_submitter=CoalescedRecomputeSubmitter(workflow=recorder),
        definitions=definitions,
        narrowed=narrowed,
        default_branch_name=DEFAULT_BRANCH,
        context=CONTEXT,
    )


def _calls(recorder: WorkflowRecorder) -> list[tuple[str, WorkflowDefinition, dict[str, Any]]]:
    return [(call["kind"], call["workflow"], call["parameters"]) for call in recorder.calls]


def _python_recompute(attribute: DeclaredAttribute) -> tuple[str, WorkflowDefinition, dict[str, Any]]:
    return (
        "submit",
        TRIGGER_UPDATE_PYTHON_COMPUTED_ATTRIBUTES,
        {
            "branch_name": DEFAULT_BRANCH,
            "computed_attribute_name": attribute.attribute_name,
            "computed_attribute_kind": attribute.kind,
            "context": CONTEXT.to_event_context(),
            "coalesced": True,
            "widened": True,
            "recompute_depth": 0,
        },
    )


ARTIFACT_TRIGGER_OF_X = (
    "submit",
    TRIGGER_ARTIFACT_DEFINITION_GENERATE,
    {"branch": DEFAULT_BRANCH, "include_repository_ids": [REPOSITORY_X]},
)
GENERATOR_TRIGGER_OF_X = (
    "submit",
    TRIGGER_GENERATOR_DEFINITION_RUN,
    {"branch": DEFAULT_BRANCH, "source": GeneratorDefinitionRunSource.MERGE, "include_repository_ids": [REPOSITORY_X]},
)


@dataclass
class NarrowingTestCase:
    name: str
    kept_artifact: RequestArtifactDefinitionGenerate | None
    kept_generator_run: RequestGeneratorDefinitionRun | None
    expected_artifact: RequestArtifactDefinitionGenerate
    expected_generator_run: RequestGeneratorDefinitionRun


NARROWING_TEST_CASES: list[NarrowingTestCase] = [
    NarrowingTestCase(
        name="a_kept_request_gives_its_narrowing_to_the_definition_as_it_is_now",
        kept_artifact=_artifact_generate(
            definition_id="ad-x", name="ad-x-before-the-import", members=("member-1", "member-2"), limit=("limit-1",)
        ),
        kept_generator_run=_generator_run(
            definition_id="gd-x", file_path="before_the_import.py", target_members=("target-1",)
        ),
        expected_artifact=_artifact_generate(
            definition_id="ad-x", members=("member-1", "member-2"), limit=("limit-1",)
        ),
        expected_generator_run=_generator_run(definition_id="gd-x", target_members=("target-1",)),
    ),
    NarrowingTestCase(
        name="a_missing_request_releases_every_member",
        kept_artifact=None,
        kept_generator_run=None,
        expected_artifact=_artifact_generate(definition_id="ad-x"),
        expected_generator_run=_generator_run(definition_id="gd-x"),
    ),
]


@pytest.mark.parametrize("test_case", [pytest.param(tc, id=tc.name) for tc in NARROWING_TEST_CASES])
async def test_a_held_definition_is_released_with_the_narrowing_kept_at_its_hold(
    test_case: NarrowingTestCase,
) -> None:
    recorder = WorkflowRecorder()
    renew = RecordedRenewals(recorder=recorder)
    narrowed = _narrowed()
    if test_case.kept_artifact is not None:
        await narrowed.put(repository_id=REPOSITORY_X, hold_seq=3, identifier="ad-x", request=test_case.kept_artifact)
    if test_case.kept_generator_run is not None:
        await narrowed.put(
            repository_id=REPOSITORY_X, hold_seq=4, identifier="gd-x", request=test_case.kept_generator_run
        )
    releaser = _releaser(
        recorder=recorder,
        definitions=FakeHeldDefinitions(
            artifacts=[_artifact_generate(definition_id="ad-x")], generators=[_generator_run(definition_id="gd-x")]
        ),
        state=await _delivery_state(),
        narrowed=narrowed,
    )

    with capture_logs() as records:
        await releaser.release(
            repository_id=REPOSITORY_X,
            held=HeldRegeneration(
                artifact_definitions=(HeldItem(id="ad-x", hold_seq=3),),
                generator_definitions=(HeldItem(id="gd-x", hold_seq=4),),
            ),
            renew=renew,
        )

    assert _calls(recorder) == [
        ("execute", REQUEST_GENERATOR_DEFINITION_RUN, {"model": test_case.expected_generator_run}),
        ("submit", REQUEST_ARTIFACT_DEFINITION_GENERATE, {"model": test_case.expected_artifact}),
    ]
    assert renew.after_calls == [0, 0, 1, 2]
    assert records == []


@dataclass
class PythonNarrowingTestCase:
    name: str
    kept: PythonTargetRequest | None
    expected_calls: list[tuple[str, WorkflowDefinition, dict[str, Any]]]


PYTHON_NARROWING_TEST_CASES: list[PythonNarrowingTestCase] = [
    PythonNarrowingTestCase(
        name="a_kept_target_submits_the_nodes_of_its_hold",
        kept=PythonTargetRequest(
            target=AffectedTarget(
                family=PYTHON_COMPUTED_ATTRIBUTE,
                target_kind="TestCar",
                attribute_name="description",
                reads_across_relationship=False,
                reader_lookups=frozenset(
                    {ReaderLookup(source_kind="TestCar", filter_key=SELF_FILTER, source_node_ids=frozenset({"car-1"}))}
                ),
            )
        ),
        expected_calls=[
            (
                "submit",
                COMPUTED_ATTRIBUTE_PROCESS_TRANSFORM,
                {
                    "branch_name": DEFAULT_BRANCH,
                    "node_kind": "TestCar",
                    "object_ids": ["car-1"],
                    "context": CONTEXT.to_event_context(),
                    "computed_attribute_name": "description",
                    "computed_attribute_kind": "TestCar",
                    "coalesced": True,
                    "recompute_depth": 0,
                },
            )
        ],
    ),
    PythonNarrowingTestCase(
        name="a_missing_target_submits_the_whole_kind",
        kept=None,
        expected_calls=[_python_recompute(CAR_DESCRIPTION)],
    ),
]


@pytest.mark.parametrize("test_case", [pytest.param(tc, id=tc.name) for tc in PYTHON_NARROWING_TEST_CASES])
async def test_a_held_python_attribute_is_released_with_the_target_kept_at_its_hold(
    test_case: PythonNarrowingTestCase,
) -> None:
    recorder = WorkflowRecorder()
    renew = RecordedRenewals(recorder=recorder)
    narrowed = _narrowed()
    if test_case.kept is not None:
        await narrowed.put(
            repository_id=REPOSITORY_X, hold_seq=5, identifier="TestCar.description", request=test_case.kept
        )
    releaser = _releaser(
        recorder=recorder, definitions=FakeHeldDefinitions(), state=await _delivery_state(), narrowed=narrowed
    )

    await releaser.release(
        repository_id=REPOSITORY_X,
        held=HeldRegeneration(
            python_attributes=(HeldPythonAttribute(kind="TestCar", attribute="description", hold_seq=5),)
        ),
        renew=renew,
    )

    assert _calls(recorder) == test_case.expected_calls
    assert renew.after_calls == [0, 1]


@dataclass
class HeldTwiceTestCase:
    name: str
    holds: list[tuple[list[RequestGeneratorDefinitionRun], list[RequestArtifactDefinitionGenerate]]]
    """The generator runs and the artifact generations of each hold."""
    expected_calls: list[tuple[str, WorkflowDefinition, dict[str, Any]]]
    expected_renewals: list[int]


HELD_TWICE_TEST_CASES: list[HeldTwiceTestCase] = [
    HeldTwiceTestCase(
        name="an_artifact_definition",
        holds=[
            ([], [_artifact_generate(definition_id="ad-x", members=("member-2",))]),
            ([], [_artifact_generate(definition_id="ad-x", members=("member-1",))]),
        ],
        expected_calls=[
            (
                "submit",
                REQUEST_ARTIFACT_DEFINITION_GENERATE,
                {"model": _artifact_generate(definition_id="ad-x", members=("member-1", "member-2"))},
            )
        ],
        expected_renewals=[0, 0, 1],
    ),
    HeldTwiceTestCase(
        name="a_generator_definition",
        holds=[
            ([_generator_run(definition_id="gd-x", target_members=("member-2",))], []),
            ([_generator_run(definition_id="gd-x", target_members=("member-1",))], []),
        ],
        expected_calls=[
            (
                "execute",
                REQUEST_GENERATOR_DEFINITION_RUN,
                {"model": _generator_run(definition_id="gd-x", target_members=("member-1", "member-2"))},
            )
        ],
        expected_renewals=[0, 0, 1, 1],
    ),
]


@pytest.mark.parametrize("test_case", [pytest.param(tc, id=tc.name) for tc in HELD_TWICE_TEST_CASES])
async def test_a_definition_held_twice_is_released_with_the_members_of_both_holds(
    test_case: HeldTwiceTestCase,
) -> None:
    state = await _delivery_state(REPOSITORY_X)
    recorder = WorkflowRecorder()
    renew = RecordedRenewals(recorder=recorder)
    releaser = _releaser(
        recorder=recorder,
        definitions=FakeHeldDefinitions(
            artifacts=[_artifact_generate(definition_id="ad-x")], generators=[_generator_run(definition_id="gd-x")]
        ),
        state=state,
        narrowed=_narrowed(),
    )
    for generator_runs, artifact_generates in test_case.holds:
        await releaser.dispatcher.dispatch_requests(
            context=CONTEXT,
            target_branch=DEFAULT_BRANCH,
            generator_runs=generator_runs,
            artifact_generates=artifact_generates,
            releasing=None,
            renew=None,
        )
    assert recorder.calls == []

    await releaser.release(repository_id=REPOSITORY_X, held=state.intents[REPOSITORY_X].held, renew=renew)

    assert _calls(recorder) == test_case.expected_calls
    assert renew.after_calls == test_case.expected_renewals


@dataclass
class FullReleaseTestCase:
    name: str
    held: HeldRegeneration
    expected_record: dict[str, Any]
    expected_renewals: list[int]
    expected_python_recomputes: list[DeclaredAttribute] = field(
        default_factory=lambda: [CAR_DESCRIPTION, PERSON_SUMMARY]
    )


FULL_RELEASE_TEST_CASES: list[FullReleaseTestCase] = [
    FullReleaseTestCase(
        name="a_definition_that_no_longer_exists_releases_every_definition_of_the_repository",
        held=HeldRegeneration(
            artifact_definitions=(HeldItem(id="ad-x", hold_seq=1),),
            generator_definitions=(HeldItem(id="gd-deleted", hold_seq=2),),
        ),
        expected_record={
            "event": FULL_RELEASE_EVENT,
            "log_level": "info",
            "repository_id": REPOSITORY_X,
            "reason": FullRegenerationReason.HELD_SET_UNRESOLVED,
            "unresolved_ids": ["gd-deleted"],
        },
        expected_renewals=[0, 2, 2, 4],
    ),
    FullReleaseTestCase(
        name="a_marker_of_scope_all_logs_its_own_reason_and_resolves_nothing",
        held=HeldRegeneration(
            artifact_definitions=(HeldItem(id="ad-x", hold_seq=1),),
            generator_definitions=(HeldItem(id="gd-deleted", hold_seq=2),),
            python_attributes=(HeldPythonAttribute(kind="TestCar", attribute="description", hold_seq=3),),
            widen=HeldWiden(scope="all", reason=FullRegenerationReason.UNHELD_FOLLOW_UP, hold_seq=4),
        ),
        expected_record={
            "event": FULL_RELEASE_EVENT,
            "log_level": "info",
            "repository_id": REPOSITORY_X,
            "reason": FullRegenerationReason.UNHELD_FOLLOW_UP,
        },
        expected_renewals=[2, 2, 4],
    ),
    FullReleaseTestCase(
        name="a_held_python_attribute_that_the_repository_does_not_own_is_recomputed_once_too",
        held=HeldRegeneration(
            python_attributes=(
                HeldPythonAttribute(kind="TestCar", attribute="description", hold_seq=1),
                HeldPythonAttribute(kind="TestLocation", attribute="name", hold_seq=2),
            ),
            widen=HeldWiden(scope="all", reason=FullRegenerationReason.UNHELD_FOLLOW_UP, hold_seq=3),
        ),
        expected_record={
            "event": FULL_RELEASE_EVENT,
            "log_level": "info",
            "repository_id": REPOSITORY_X,
            "reason": FullRegenerationReason.UNHELD_FOLLOW_UP,
        },
        expected_renewals=[2, 2, 5],
        expected_python_recomputes=[CAR_DESCRIPTION, LOCATION_NAME, PERSON_SUMMARY],
    ),
]


@pytest.mark.parametrize("test_case", [pytest.param(tc, id=tc.name) for tc in FULL_RELEASE_TEST_CASES])
async def test_a_full_release_regenerates_every_definition_and_python_attribute_of_the_repository(
    test_case: FullReleaseTestCase,
) -> None:
    recorder = WorkflowRecorder()
    renew = RecordedRenewals(recorder=recorder)
    releaser = _releaser(
        recorder=recorder,
        definitions=FakeHeldDefinitions(
            artifacts=[_artifact_generate(definition_id="ad-x")],
            python_attributes={REPOSITORY_X: [CAR_DESCRIPTION, PERSON_SUMMARY], REPOSITORY_Y: [PERSON_SUMMARY]},
        ),
        state=await _delivery_state(),
        narrowed=_narrowed(),
    )

    with capture_logs() as records:
        await releaser.release(repository_id=REPOSITORY_X, held=test_case.held, renew=renew)

    assert _calls(recorder) == [
        ARTIFACT_TRIGGER_OF_X,
        GENERATOR_TRIGGER_OF_X,
        *(_python_recompute(attribute) for attribute in test_case.expected_python_recomputes),
    ]
    assert renew.after_calls == test_case.expected_renewals
    assert records == [test_case.expected_record]


async def test_a_marker_of_scope_terminals_alone_regenerates_the_artifact_definitions_of_the_repository() -> None:
    recorder = WorkflowRecorder()
    renew = RecordedRenewals(recorder=recorder)
    releaser = _releaser(
        recorder=recorder,
        definitions=FakeHeldDefinitions(python_attributes={REPOSITORY_X: [CAR_DESCRIPTION]}),
        state=await _delivery_state(),
        narrowed=_narrowed(),
    )

    with capture_logs() as records:
        await releaser.release(
            repository_id=REPOSITORY_X,
            held=HeldRegeneration(
                widen=HeldWiden(scope="terminals", reason=FullRegenerationReason.TERMINAL_SELECTION_FAILED, hold_seq=1)
            ),
            renew=renew,
        )

    assert _calls(recorder) == [ARTIFACT_TRIGGER_OF_X]
    assert renew.after_calls == [0, 1]
    assert records == [
        {
            "event": TERMINALS_RELEASE_EVENT,
            "log_level": "info",
            "repository_id": REPOSITORY_X,
            "reason": FullRegenerationReason.TERMINAL_SELECTION_FAILED,
        }
    ]


async def test_a_marker_of_scope_terminals_still_releases_the_held_generators_and_python_attributes() -> None:
    recorder = WorkflowRecorder()
    renew = RecordedRenewals(recorder=recorder)
    releaser = _releaser(
        recorder=recorder,
        definitions=FakeHeldDefinitions(
            artifacts=[_artifact_generate(definition_id="ad-x")], generators=[_generator_run(definition_id="gd-x")]
        ),
        state=await _delivery_state(),
        narrowed=_narrowed(),
    )

    await releaser.release(
        repository_id=REPOSITORY_X,
        held=HeldRegeneration(
            artifact_definitions=(HeldItem(id="ad-x", hold_seq=1),),
            generator_definitions=(HeldItem(id="gd-x", hold_seq=2),),
            python_attributes=(HeldPythonAttribute(kind="TestCar", attribute="description", hold_seq=3),),
            widen=HeldWiden(scope="terminals", reason=FullRegenerationReason.TERMINAL_SELECTION_FAILED, hold_seq=4),
        ),
        renew=renew,
    )

    # The artifact trigger covers the held artifact definition, so only the generator and the attribute follow it.
    assert _calls(recorder) == [
        ARTIFACT_TRIGGER_OF_X,
        ("execute", REQUEST_GENERATOR_DEFINITION_RUN, {"model": _generator_run(definition_id="gd-x")}),
        _python_recompute(CAR_DESCRIPTION),
    ]
    assert renew.after_calls == [0, 1, 1, 2, 2, 3]


async def test_the_released_repository_dispatches_its_work_while_another_pending_repository_holds() -> None:
    state = await _delivery_state(REPOSITORY_X, REPOSITORY_Y)
    recorder = WorkflowRecorder()
    renew = RecordedRenewals(recorder=recorder)
    releaser = _releaser(
        recorder=recorder,
        definitions=FakeHeldDefinitions(
            artifacts=[_artifact_generate(definition_id="ad-x")], generators=[_generator_run(definition_id="gd-x")]
        ),
        state=state,
        narrowed=_narrowed(),
        reselected=[
            _artifact_generate(definition_id="ad-x-reselected"),
            _artifact_generate(definition_id="ad-y-reselected", repository_id=REPOSITORY_Y),
        ],
    )

    await releaser.release(
        repository_id=REPOSITORY_X,
        held=HeldRegeneration(
            artifact_definitions=(HeldItem(id="ad-x", hold_seq=1),),
            generator_definitions=(HeldItem(id="gd-x", hold_seq=2),),
        ),
        renew=renew,
    )

    assert _calls(recorder) == [
        ("execute", REQUEST_GENERATOR_DEFINITION_RUN, {"model": _generator_run(definition_id="gd-x")}),
        ("submit", REQUEST_ARTIFACT_DEFINITION_GENERATE, {"model": _artifact_generate(definition_id="ad-x")}),
        (
            "submit",
            REQUEST_ARTIFACT_DEFINITION_GENERATE,
            {"model": _artifact_generate(definition_id="ad-x-reselected")},
        ),
    ]
    assert renew.after_calls == [0, 0, 1, 3]
    assert state.calls == ["pending_repository_ids", "pending_repository_ids", "hold"]
    assert {repository_id: intent.held for repository_id, intent in state.intents.items()} == {
        REPOSITORY_X: HeldRegeneration(),
        REPOSITORY_Y: HeldRegeneration(
            next_hold_seq=2, artifact_definitions=(HeldItem(id="ad-y-reselected", hold_seq=1),)
        ),
    }


@dataclass
class DispatchFailureTestCase:
    name: str
    failing: WorkflowDefinition
    held: HeldRegeneration
    error: type[Exception]
    match: str
    expected_calls: list[tuple[str, WorkflowDefinition, dict[str, Any]]] = field(default_factory=list)
    expected_renewals: list[int] = field(default_factory=list)
    """Each renewal comes before the failed call, so none counts a call."""
    run_error: type[Exception] = RuntimeError


DISPATCH_FAILURE_TEST_CASES: list[DispatchFailureTestCase] = [
    DispatchFailureTestCase(
        name="a_held_generator_run_that_the_orchestrator_cannot_start",
        failing=REQUEST_GENERATOR_DEFINITION_RUN,
        held=HeldRegeneration(generator_definitions=(HeldItem(id="gd-x", hold_seq=1),)),
        run_error=httpx.ConnectError,
        error=httpx.ConnectError,
        match=r"^Could not run request-generator-definition-run$",
        expected_calls=[("execute", REQUEST_GENERATOR_DEFINITION_RUN, {"model": _generator_run(definition_id="gd-x")})],
        expected_renewals=[0, 0],
    ),
    DispatchFailureTestCase(
        name="a_failed_submission_of_a_held_artifact_definition",
        failing=REQUEST_ARTIFACT_DEFINITION_GENERATE,
        held=HeldRegeneration(artifact_definitions=(HeldItem(id="ad-x", hold_seq=1),)),
        error=RuntimeError,
        match=r"^Could not submit request_artifact_definitions_generate$",
        expected_calls=[
            ("submit", REQUEST_ARTIFACT_DEFINITION_GENERATE, {"model": _artifact_generate(definition_id="ad-x")})
        ],
        expected_renewals=[0, 0],
    ),
    DispatchFailureTestCase(
        name="a_failed_submission_of_the_blanket_regeneration",
        failing=TRIGGER_ARTIFACT_DEFINITION_GENERATE,
        held=HeldRegeneration(widen=HeldWiden(scope="all", reason=FullRegenerationReason.UNHELD_FOLLOW_UP, hold_seq=1)),
        error=RuntimeError,
        match=r"^Could not submit artifact-definition-generate$",
        expected_calls=[ARTIFACT_TRIGGER_OF_X],
    ),
    DispatchFailureTestCase(
        name="a_failed_submission_of_a_python_recompute",
        failing=TRIGGER_UPDATE_PYTHON_COMPUTED_ATTRIBUTES,
        held=HeldRegeneration(
            python_attributes=(HeldPythonAttribute(kind="TestCar", attribute="description", hold_seq=1),)
        ),
        error=ServiceUnavailableError,
        match=r"^The recompute of the Python computed attributes TestCar\.description could not be submitted\.$",
        expected_calls=[_python_recompute(CAR_DESCRIPTION)],
        expected_renewals=[0],
    ),
]


@pytest.mark.parametrize("test_case", [pytest.param(tc, id=tc.name) for tc in DISPATCH_FAILURE_TEST_CASES])
async def test_a_failed_dispatch_raises_with_no_renewal_after_it(test_case: DispatchFailureTestCase) -> None:
    recorder = FailingWorkflowRecorder(failing=test_case.failing, run_error=test_case.run_error)
    renew = RecordedRenewals(recorder=recorder)
    releaser = _releaser(
        recorder=recorder,
        definitions=FakeHeldDefinitions(
            artifacts=[_artifact_generate(definition_id="ad-x")], generators=[_generator_run(definition_id="gd-x")]
        ),
        state=await _delivery_state(),
        narrowed=_narrowed(),
    )

    with pytest.raises(test_case.error, match=test_case.match):
        await releaser.release(repository_id=REPOSITORY_X, held=test_case.held, renew=renew)

    assert _calls(recorder) == test_case.expected_calls
    assert renew.after_calls == test_case.expected_renewals


async def test_a_failed_generator_run_regenerates_the_terminals_of_its_repository_and_does_not_raise() -> None:
    state = await _delivery_state(REPOSITORY_X, REPOSITORY_Y)
    recorder = FailingWorkflowRecorder(failing=REQUEST_GENERATOR_DEFINITION_RUN)
    renew = RecordedRenewals(recorder=recorder)
    releaser = _releaser(
        recorder=recorder,
        definitions=FakeHeldDefinitions(generators=[_generator_run(definition_id="gd-x")]),
        state=state,
        narrowed=_narrowed(),
    )

    await releaser.release(
        repository_id=REPOSITORY_X,
        held=HeldRegeneration(generator_definitions=(HeldItem(id="gd-x", hold_seq=1),)),
        renew=renew,
    )

    assert _calls(recorder) == [
        ("execute", REQUEST_GENERATOR_DEFINITION_RUN, {"model": _generator_run(definition_id="gd-x")}),
        (
            "submit",
            TRIGGER_ARTIFACT_DEFINITION_GENERATE,
            {"branch": DEFAULT_BRANCH, "include_repository_ids": [REPOSITORY_X]},
        ),
    ]
    assert renew.after_calls == [0, 0, 1, 2]
    assert state.calls == ["pending_repository_ids"]
    assert {repository_id: intent.held for repository_id, intent in state.intents.items()} == {
        REPOSITORY_X: HeldRegeneration(),
        REPOSITORY_Y: HeldRegeneration(),
    }
