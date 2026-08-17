"""Removal of the Python work a schema-driven refresh already covers."""

from __future__ import annotations

from infrahub.core.merge.post_merge import PostMergeDispatcher
from infrahub.core.merge.python_target_resolution import DroppingPythonTargetResolver
from infrahub.core.merge.recompute_coalescing import (
    COMPUTED_ATTRIBUTE,
    DISPLAY_LABEL,
    PYTHON_ATTRIBUTE,
    AffectedTarget,
    CoalescedRecompute,
    CoalescedRecomputeBuilder,
    CoalescedRecomputeSubmitter,
    MergeChange,
    MergeRecomputeCoordinator,
    ReaderLookup,
    RecomputeFamily,
    _drop_schema_covered,
)
from infrahub.core.schema.schema_branch import SchemaBranch
from infrahub.events.models import EventBranchContext, EventContext
from infrahub.workflows.catalogue import COMPUTED_ATTRIBUTE_PROCESS_JINJA2
from tests.adapters.workflow import WorkflowRecorder
from tests.helpers.merge_recompute.dataset import (
    PROFILE_NODE_KIND,
    PROFILE_PEER_KIND,
    PROFILE_PYTHON_ATTRIBUTE,
    build_profile_schema,
)

COVERED = frozenset({(PROFILE_NODE_KIND, PROFILE_PYTHON_ATTRIBUTE)})


def _schema_branch() -> SchemaBranch:
    schema_branch = SchemaBranch(cache={}, name="test")
    schema_branch.load_schema(schema=build_profile_schema(python_attribute=True))
    schema_branch.process()
    return schema_branch


def _target(family: RecomputeFamily, attribute_name: str) -> AffectedTarget:
    return AffectedTarget(
        family=family,
        target_kind=PROFILE_NODE_KIND,
        attribute_name=attribute_name,
        reads_across_relationship=True,
        reader_lookups=frozenset(
            {ReaderLookup(source_kind=PROFILE_PEER_KIND, filter_key="peer__ids", source_node_ids=frozenset({"p1"}))}
        ),
    )


def test_a_covered_python_target_is_dropped() -> None:
    coalesced = CoalescedRecompute(
        branch="main", targets=frozenset({_target(PYTHON_ATTRIBUTE, PROFILE_PYTHON_ATTRIBUTE)})
    )

    result = _drop_schema_covered(coalesced=coalesced, covered=COVERED)

    assert result.targets == frozenset()


def test_the_other_families_are_never_dropped() -> None:
    """The schema pass does not refresh them the same way, so dropping one would leave it stale."""
    jinja = _target(COMPUTED_ATTRIBUTE, PROFILE_PYTHON_ATTRIBUTE)
    coalesced = CoalescedRecompute(branch="main", targets=frozenset({jinja}))

    result = _drop_schema_covered(coalesced=coalesced, covered=COVERED)

    assert result.targets == frozenset({jinja})


def test_an_uncovered_python_target_survives() -> None:
    coalesced = CoalescedRecompute(branch="main", targets=frozenset({_target(PYTHON_ATTRIBUTE, "other")}))

    result = _drop_schema_covered(coalesced=coalesced, covered=COVERED)

    assert len(result.targets) == 1


async def test_the_coordinator_still_submits_the_families_it_did_not_drop() -> None:
    """Subtracting the Python pair must not disturb the pass around it."""
    recorder = WorkflowRecorder()
    coordinator = MergeRecomputeCoordinator(
        builder=CoalescedRecomputeBuilder(schema_branch=_schema_branch()),
        submitter=CoalescedRecomputeSubmitter(workflow=recorder),
        resolver=DroppingPythonTargetResolver(),
    )
    changes = [
        MergeChange(node_id="peer-0", kind=PROFILE_PEER_KIND, action="updated", changed_fields=frozenset({"name"}))
    ]

    submissions = await coordinator.run(
        changes=changes,
        branch="main",
        context=EventContext(branch=EventBranchContext(name="main"), account_id=""),
        schema_covered_pairs=COVERED,
    )

    assert [submission.family for submission in submissions] == [COMPUTED_ATTRIBUTE, DISPLAY_LABEL]
    assert len(recorder.get_submit_calls_for(COMPUTED_ATTRIBUTE_PROCESS_JINJA2)) == 1


def test_nothing_is_subtracted_without_a_delivered_notification() -> None:
    """A send that failed means no schema refresh will run, so its work must not be removed."""
    covered = PostMergeDispatcher._schema_covered_pairs(schema_branch=_schema_branch(), schema_event=None)

    assert covered == frozenset()
