"""Submission of the coalesced recompute.

``plan_coalesced_submissions`` turns the deduplicated target set into one submission per derived
target and source kind, each carrying the union of changed node ids. ``submit_coalesced_recompute``
reuses the existing per-family process flows, recorded here through the workflow adapter so the
dispatch is asserted without a task worker.
"""

from __future__ import annotations

from infrahub.core.merge.recompute_coalescing import (
    COMPUTED_ATTRIBUTE,
    DISPLAY_LABEL,
    HFID,
    AffectedTarget,
    CoalescedRecompute,
    ReaderLookup,
    plan_coalesced_submissions,
    submit_coalesced_recompute,
)
from infrahub.events.models import EventBranchContext, EventContext
from infrahub.workflows.catalogue import (
    COMPUTED_ATTRIBUTE_PROCESS_JINJA2,
    DISPLAY_LABELS_PROCESS_JINJA2,
    HFID_PROCESS,
)
from tests.adapters.workflow import WorkflowRecorder

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
    submissions = plan_coalesced_submissions(_coalesced())

    assert [
        (s.family, s.target_kind, s.attribute_name, s.source_kind, s.filter_key, s.node_ids) for s in submissions
    ] == [
        (COMPUTED_ATTRIBUTE, TARGET_KIND, "summary", SOURCE_KIND, "peer__ids", ("p1", "p2", "p3")),
        (DISPLAY_LABEL, TARGET_KIND, None, SOURCE_KIND, "peer__ids", ("p1", "p2", "p3")),
        (HFID, TARGET_KIND, None, TARGET_KIND, "ids", ("n1",)),
    ]


async def test_submit_reuses_process_flows_over_the_union() -> None:
    recorder = WorkflowRecorder()

    submissions = await submit_coalesced_recompute(coalesced=_coalesced(), workflow=recorder, context=_event_context())

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
