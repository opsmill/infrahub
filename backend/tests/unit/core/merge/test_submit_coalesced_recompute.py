"""Submission of the coalesced recompute."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from infrahub.core.merge.recompute_coalescing import (
    COMPUTED_ATTRIBUTE,
    DISPLAY_LABEL,
    HFID,
    AffectedTarget,
    CoalescedRecompute,
    CoalescedRecomputeSubmitter,
    ReaderLookup,
)
from infrahub.events.limits import get_submission_chunk_size
from infrahub.events.models import EventBranchContext, EventContext
from infrahub.workflows.catalogue import (
    COMPUTED_ATTRIBUTE_PROCESS_JINJA2,
    DISPLAY_LABELS_PROCESS_JINJA2,
    HFID_PROCESS,
)
from tests.adapters.workflow import WorkflowRecorder

if TYPE_CHECKING:
    from infrahub.workflows.models import WorkflowInfo

SOURCE_KIND = "TestingPeer"
TARGET_KIND = "TestingNode"


def _coalesced() -> CoalescedRecompute:
    peer_lookup = ReaderLookup(
        source_kind=SOURCE_KIND, filter_key="peer__ids", source_node_ids=frozenset({"p3", "p1", "p2"})
    )
    computed = AffectedTarget(
        family=COMPUTED_ATTRIBUTE,
        target_kind=TARGET_KIND,
        attribute_name="summary",
        reads_across_relationship=True,
        reader_lookups=frozenset({peer_lookup}),
    )
    display = AffectedTarget(
        family=DISPLAY_LABEL,
        target_kind=TARGET_KIND,
        attribute_name=None,
        reads_across_relationship=True,
        reader_lookups=frozenset({peer_lookup}),
    )
    hfid = AffectedTarget(
        family=HFID,
        target_kind=TARGET_KIND,
        attribute_name=None,
        reads_across_relationship=False,
        reader_lookups=frozenset(
            {ReaderLookup(source_kind=TARGET_KIND, filter_key="ids", source_node_ids=frozenset({"n1"}))}
        ),
    )
    return CoalescedRecompute(branch="main", targets=frozenset({computed, display, hfid}))


def _event_context() -> EventContext:
    return EventContext(branch=EventBranchContext(name="main"), account_id="")


def test_plan_makes_one_submission_per_target_with_union_ids() -> None:
    submissions = CoalescedRecomputeSubmitter.plan(_coalesced())

    assert [
        (s.family, s.target_kind, s.attribute_name, s.source_kind, s.filter_key, s.node_ids) for s in submissions
    ] == [
        (COMPUTED_ATTRIBUTE, TARGET_KIND, "summary", SOURCE_KIND, "peer__ids", ("p1", "p2", "p3")),
        (DISPLAY_LABEL, TARGET_KIND, None, SOURCE_KIND, "peer__ids", ("p1", "p2", "p3")),
        (HFID, TARGET_KIND, None, TARGET_KIND, "ids", ("n1",)),
    ]


async def test_submit_reuses_process_flows_over_the_union() -> None:
    recorder = WorkflowRecorder()

    submissions = await CoalescedRecomputeSubmitter(workflow=recorder).submit(
        coalesced=_coalesced(), context=_event_context()
    )

    assert len(submissions) == 3
    assert len(recorder.submit_calls) == 3

    computed = recorder.get_submit_calls_for(COMPUTED_ATTRIBUTE_PROCESS_JINJA2)
    assert len(computed) == 1
    assert computed[0]["parameters"]["node_kind"] == SOURCE_KIND
    assert computed[0]["parameters"]["computed_attribute_kind"] == TARGET_KIND
    assert computed[0]["parameters"]["computed_attribute_name"] == "summary"
    assert computed[0]["parameters"]["object_ids"] == ["p1", "p2", "p3"]

    display = recorder.get_submit_calls_for(DISPLAY_LABELS_PROCESS_JINJA2)
    assert len(display) == 1
    assert display[0]["parameters"]["node_kind"] == SOURCE_KIND
    assert display[0]["parameters"]["target_kind"] == TARGET_KIND
    assert display[0]["parameters"]["object_ids"] == ["p1", "p2", "p3"]

    hfid = recorder.get_submit_calls_for(HFID_PROCESS)
    assert len(hfid) == 1
    assert hfid[0]["parameters"]["node_kind"] == TARGET_KIND
    assert hfid[0]["parameters"]["target_kind"] == TARGET_KIND
    assert hfid[0]["parameters"]["object_ids"] == ["n1"]


def test_plan_chunks_a_union_larger_than_the_submission_limit() -> None:
    chunk_size = get_submission_chunk_size()
    ids = frozenset(f"p{index:05d}" for index in range(chunk_size * 2 + 1))
    target = AffectedTarget(
        family=COMPUTED_ATTRIBUTE,
        target_kind=TARGET_KIND,
        attribute_name="summary",
        reads_across_relationship=True,
        reader_lookups=frozenset({ReaderLookup(source_kind=SOURCE_KIND, filter_key="peer__ids", source_node_ids=ids)}),
    )

    submissions = CoalescedRecomputeSubmitter.plan(CoalescedRecompute(branch="main", targets=frozenset({target})))

    # The oversized union splits into bounded submissions, each below the flow-run parameter limit.
    assert [len(submission.node_ids) for submission in submissions] == [chunk_size, chunk_size, 1]
    assert all(len(submission.node_ids) <= chunk_size for submission in submissions)
    # Every id is submitted exactly once, in a deterministic order.
    rebuilt = tuple(node_id for submission in submissions for node_id in submission.node_ids)
    assert rebuilt == tuple(sorted(ids))


class _FailFirstWorkflow(WorkflowRecorder):
    """A recorder that raises on its first submission, to prove one failure does not drop the rest."""

    def __init__(self) -> None:
        super().__init__()
        self._attempts = 0

    async def submit_workflow(self, *args: Any, **kwargs: Any) -> WorkflowInfo:
        self._attempts += 1
        if self._attempts == 1:
            raise RuntimeError("submission rejected")
        return await super().submit_workflow(*args, **kwargs)


async def test_submit_skips_a_failing_submission_and_keeps_the_rest() -> None:
    recorder = _FailFirstWorkflow()

    submitted = await CoalescedRecomputeSubmitter(workflow=recorder).submit(
        coalesced=_coalesced(), context=_event_context()
    )

    # The first submission failed; the other two were still dispatched and returned.
    assert len(recorder.submit_calls) == 2
    assert len(submitted) == 2
