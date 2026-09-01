"""The Python transform family joins the coalesced pass through its own derivation.

The schema-derived families come from the builder, which reads only a processed schema branch. The
Python family needs the database and the query groups, so it arrives through an injected derivation;
these tests pin the wiring between the two, not the narrowing itself.
"""

from __future__ import annotations

from infrahub.computed_attribute.scoping import ChangedElementSet
from infrahub.core.merge.recompute_coalescing import (
    COMPUTED_ATTRIBUTE,
    PYTHON_COMPUTED_ATTRIBUTE,
    AffectedTarget,
    CoalescedRecomputeBuilder,
    CoalescedRecomputeSubmitter,
    MergeChange,
    MergeRecomputeCoordinator,
    ReaderLookup,
    RecomputeChainSubmitter,
)
from infrahub.core.recompute.bulk_write import WrittenNode
from infrahub.core.schema import AttributeSchema
from infrahub.core.schema.computed_attribute import ComputedAttribute, ComputedAttributeKind
from infrahub.core.schema.schema_branch import SchemaBranch
from infrahub.events.models import EventBranchContext, EventContext
from tests.adapters.python_target_sources import (
    FailingPythonTargetResolver,
    RecordingPythonTargetResolver,
    ResolveCall,
)
from tests.adapters.workflow import WorkflowRecorder
from tests.helpers.merge_recompute.dataset import build_chain_schema, chain_kind

BRANCH = "main"
PYTHON_KIND = "TestingProbe"
SCHEMA_SCOPE = ChangedElementSet(changed_fields={PYTHON_KIND: frozenset({"digest"})})


def _schema_branch() -> SchemaBranch:
    schema_branch = SchemaBranch(cache={}, name="test")
    schema_branch.load_schema(schema=build_chain_schema(levels=3))
    schema_branch.process()
    return schema_branch


def _schema_branch_with_a_python_attribute() -> SchemaBranch:
    """The chain schema, plus one Python transform computed attribute on its first level."""
    schema = build_chain_schema(levels=3)
    node = next(item for item in schema.nodes if item.kind == chain_kind(1))
    node.attributes.append(
        AttributeSchema(
            name="digest",
            kind="Text",
            optional=True,
            read_only=True,
            computed_attribute=ComputedAttribute(
                kind=ComputedAttributeKind.TRANSFORM_PYTHON, transform="transform_digest"
            ),
        )
    )
    schema_branch = SchemaBranch(cache={}, name="test")
    schema_branch.load_schema(schema=schema)
    schema_branch.process()
    return schema_branch


def _event_context() -> EventContext:
    return EventContext(branch=EventBranchContext(name=BRANCH), account_id="")


def _python_target() -> AffectedTarget:
    return AffectedTarget(
        family=PYTHON_COMPUTED_ATTRIBUTE,
        target_kind=PYTHON_KIND,
        attribute_name="digest",
        reads_across_relationship=False,
        reader_lookups=frozenset(
            {ReaderLookup(source_kind=PYTHON_KIND, filter_key="ids", source_node_ids=frozenset({"probe-1"}))}
        ),
    )


def _root_change() -> MergeChange:
    return MergeChange(node_id="l1-0", kind=chain_kind(1), action="updated", changed_fields=frozenset({"name"}))


def _families(submissions: list) -> set[str]:
    return {submission.family for submission in submissions}


async def test_the_coordinator_submits_the_python_family_alongside_the_schema_ones() -> None:
    resolver = RecordingPythonTargetResolver(targets=[_python_target()])
    coordinator = MergeRecomputeCoordinator(
        builder=CoalescedRecomputeBuilder(schema_branch=_schema_branch()),
        submitter=CoalescedRecomputeSubmitter(workflow=WorkflowRecorder()),
        python_resolver=resolver,
    )

    # A generator, since both derivations read the change set and the second would find it empty.
    submissions = await coordinator.run(
        changes=(change for change in [_root_change()]),
        branch=BRANCH,
        context=_event_context(),
        schema_changed_elements=SCHEMA_SCOPE,
    )

    assert _families(submissions) == {COMPUTED_ATTRIBUTE, PYTHON_COMPUTED_ATTRIBUTE}
    # The derivation decides for itself what the schema pass already covers, so it needs that scope.
    assert resolver.calls == [ResolveCall(branch=BRANCH, node_ids=("l1-0",), schema_scope=SCHEMA_SCOPE)]


async def test_a_chained_level_derives_the_python_targets_of_its_writes() -> None:
    """A Python attribute reading a value the pass just wrote is reached by the next chain level."""
    resolver = RecordingPythonTargetResolver(targets=[_python_target()])
    recorder = WorkflowRecorder()

    submissions = await RecomputeChainSubmitter(
        builder=CoalescedRecomputeBuilder(schema_branch=_schema_branch()),
        submitter=CoalescedRecomputeSubmitter(workflow=recorder),
        python_resolver=resolver,
    ).submit(
        written=[WrittenNode(node_id="l1-0", kind=chain_kind(1), fields=("name",))],
        branch=BRANCH,
        context=_event_context(),
        depth=0,
    )

    assert _families(submissions) == {COMPUTED_ATTRIBUTE, PYTHON_COMPUTED_ATTRIBUTE}
    # A chained level replays data writes, never a schema change.
    assert resolver.calls == [ResolveCall(branch=BRANCH, node_ids=("l1-0",), schema_scope=None)]
    python_calls = [
        call for call in recorder.submit_calls if call["parameters"].get("computed_attribute_kind") == PYTHON_KIND
    ]
    assert len(python_calls) == 1
    assert python_calls[0]["parameters"]["recompute_depth"] == 1
    assert python_calls[0]["parameters"]["coalesced"] is True


async def test_a_failing_resolution_widens_python_and_keeps_the_other_families() -> None:
    """A failed resolution costs precision, never the recompute itself.

    Only this family reads the database, so letting the failure out would drop the three that
    cannot fail with it. Returning nothing would be just as wrong: the per-node automations ignore
    a replayed change, so every declared attribute is refreshed over its whole kind instead.
    """
    resolver = FailingPythonTargetResolver()
    coordinator = MergeRecomputeCoordinator(
        builder=CoalescedRecomputeBuilder(schema_branch=_schema_branch_with_a_python_attribute()),
        submitter=CoalescedRecomputeSubmitter(workflow=WorkflowRecorder()),
        python_resolver=resolver,
    )

    submissions = await coordinator.run(changes=[_root_change()], branch=BRANCH, context=_event_context())

    assert resolver.calls == [BRANCH]
    assert _families(submissions) == {COMPUTED_ATTRIBUTE, PYTHON_COMPUTED_ATTRIBUTE}
    python = [submission for submission in submissions if submission.family == PYTHON_COMPUTED_ATTRIBUTE]
    assert [(submission.target_kind, submission.attribute_name, submission.whole_kind) for submission in python] == [
        (chain_kind(1), "digest", True)
    ]


async def test_a_failing_resolution_on_a_chained_level_widens_the_same_way() -> None:
    resolver = FailingPythonTargetResolver()

    submissions = await RecomputeChainSubmitter(
        builder=CoalescedRecomputeBuilder(schema_branch=_schema_branch_with_a_python_attribute()),
        submitter=CoalescedRecomputeSubmitter(workflow=WorkflowRecorder()),
        python_resolver=resolver,
    ).submit(
        written=[WrittenNode(node_id="l1-0", kind=chain_kind(1), fields=("name",))],
        branch=BRANCH,
        context=_event_context(),
        depth=0,
    )

    assert resolver.calls == [BRANCH]
    assert _families(submissions) == {COMPUTED_ATTRIBUTE, PYTHON_COMPUTED_ATTRIBUTE}
