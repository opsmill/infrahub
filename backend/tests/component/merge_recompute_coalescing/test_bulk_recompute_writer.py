"""The bulk recompute writer persists all three derived-value families and chains coalesced."""

from __future__ import annotations

from typing import TYPE_CHECKING

from prefect import flow

from infrahub.core.manager import NodeManager
from infrahub.core.merge.recompute_coalescing import (
    COMPUTED_ATTRIBUTE,
    RECOMPUTE_CHAIN_DEPTH_FLOOR,
    CoalescedRecomputeBuilder,
    CoalescedRecomputeSubmitter,
    DisabledPythonTargetDeriver,
    RecomputeChainSubmitter,
    max_recompute_chain_depth,
)
from infrahub.core.node import Node
from infrahub.core.recompute.bulk_write import (
    DISPLAY_LABEL_FIELD,
    HFID_FIELD,
    AttributeValueWrite,
    BulkRecomputeWriter,
    WrittenNode,
)
from infrahub.core.recompute.dispatch import BulkRecomputeDispatcher
from infrahub.core.registry import registry
from infrahub.events.constants import NodeMutationOrigin
from infrahub.events.models import EventBranchContext, EventContext
from infrahub.events.node_action import NodeUpdatedEvent
from infrahub.workflows.catalogue import COMPUTED_ATTRIBUTE_PROCESS_JINJA2
from tests.adapters.event import MemoryInfrahubEvent
from tests.adapters.workflow import WorkflowRecorder
from tests.helpers.merge_recompute.dataset import (
    PROFILE_NODE_KIND,
    PROFILE_PEER_KIND,
    chain_kind,
    load_chain_schema,
    load_profile_schema,
)
from tests.helpers.schema import CASCADE_NODE, CASCADE_SCHEMA, CYCLE_A, CYCLE_B, CYCLE_SCHEMA, load_schema

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.core.schema.schema_branch import SchemaBranch
    from infrahub.database import InfrahubDatabase
    from infrahub.services.adapters.event import InfrahubEventService
    from infrahub.services.adapters.workflow import InfrahubWorkflow


def _event_context() -> EventContext:
    return EventContext(branch=EventBranchContext(name="main"), account_id="")


def _dispatcher(
    db: InfrahubDatabase,
    event_service: InfrahubEventService,
    workflow: InfrahubWorkflow,
    schema_branch: SchemaBranch,
) -> BulkRecomputeDispatcher:
    return BulkRecomputeDispatcher(
        db=db,
        writer=BulkRecomputeWriter(db=db, event_service=event_service),
        chain=RecomputeChainSubmitter(
            builder=CoalescedRecomputeBuilder(schema_branch=schema_branch),
            submitter=CoalescedRecomputeSubmitter(workflow=workflow),
            python_deriver=DisabledPythonTargetDeriver(),
        ),
    )


async def _make_node(db: InfrahubDatabase, branch: Branch, name: str, peer_name: str) -> Node:
    peer = await Node.init(db=db, schema=PROFILE_PEER_KIND, branch=branch)
    await peer.new(db=db, name=peer_name)
    await peer.save(db=db)
    node = await Node.init(db=db, schema=PROFILE_NODE_KIND, branch=branch)
    await node.new(db=db, name=name, peer=peer)
    await node.save(db=db)
    return node


async def test_bulk_writer_persists_all_three_families_and_emits_one_event_per_node(
    db: InfrahubDatabase,
    default_branch: Branch,
    register_core_models_schema: SchemaBranch,
) -> None:
    await load_profile_schema(db=db)
    node = await _make_node(db=db, branch=default_branch, name="n1", peer_name="p1")

    recorder = MemoryInfrahubEvent()
    writer = BulkRecomputeWriter(db=db, event_service=recorder)

    written = await writer.write(
        branch=default_branch,
        writes=[
            AttributeValueWrite(node_id=node.id, field=DISPLAY_LABEL_FIELD, value="custom label"),
            AttributeValueWrite(node_id=node.id, field=HFID_FIELD, value=["custom-hfid"]),
            AttributeValueWrite(node_id=node.id, field="summary", value="custom summary"),
        ],
        context=_event_context(),
    )

    assert len(written) == 1
    assert written[0].node_id == node.id
    assert written[0].kind == PROFILE_NODE_KIND
    assert set(written[0].fields) == {DISPLAY_LABEL_FIELD, HFID_FIELD, "summary"}

    reloaded = await NodeManager.get_one(db=db, id=node.id, branch=default_branch)
    assert reloaded is not None
    assert await reloaded.get_display_label(db=db) == "custom label"
    assert await reloaded.get_hfid(db=db) == ["custom-hfid"]
    assert reloaded.summary.value == "custom summary"

    # One event per node even though three fields were written, carrying every changed field, live
    # origin by default so cross-node readers recompute from it.
    assert len(recorder.events) == 1
    event = recorder.events[0]
    assert isinstance(event, NodeUpdatedEvent)
    assert event.node_id == node.id
    assert set(event.fields) == {DISPLAY_LABEL_FIELD, HFID_FIELD, "summary"}
    assert event.meta.origin is NodeMutationOrigin.LIVE


async def test_bulk_writer_groups_writes_across_many_nodes(
    db: InfrahubDatabase,
    default_branch: Branch,
    register_core_models_schema: SchemaBranch,
) -> None:
    await load_profile_schema(db=db)
    nodes = [await _make_node(db=db, branch=default_branch, name=f"n{i}", peer_name=f"p{i}") for i in range(5)]

    recorder = MemoryInfrahubEvent()
    writer = BulkRecomputeWriter(db=db, event_service=recorder, transaction_chunk_size=2)

    written = await writer.write(
        branch=default_branch,
        writes=[
            AttributeValueWrite(node_id=n.id, field=DISPLAY_LABEL_FIELD, value=f"label-{i}")
            for i, n in enumerate(nodes)
        ],
        context=_event_context(),
    )

    assert len(written) == 5
    # One event per node even though the writes spanned several transaction chunks.
    assert len(recorder.events) == 5
    for index, node in enumerate(nodes):
        reloaded = await NodeManager.get_one(db=db, id=node.id, branch=default_branch)
        assert reloaded is not None
        assert await reloaded.get_display_label(db=db) == f"label-{index}"


async def test_bulk_writer_stamps_recompute_origin_so_per_node_automations_skip_it(
    db: InfrahubDatabase,
    default_branch: Branch,
    register_core_models_schema: SchemaBranch,
) -> None:
    await load_profile_schema(db=db)
    node = await _make_node(db=db, branch=default_branch, name="n1", peer_name="p1")

    recorder = MemoryInfrahubEvent()
    writer = BulkRecomputeWriter(db=db, event_service=recorder)

    await writer.write(
        branch=default_branch,
        writes=[AttributeValueWrite(node_id=node.id, field=DISPLAY_LABEL_FIELD, value="custom label")],
        context=_event_context(),
        origin=NodeMutationOrigin.RECOMPUTE,
    )

    assert len(recorder.events) == 1
    # The per-node recompute automations match the live origin, so a recompute origin excludes them
    # while other consumers still receive the event.
    assert recorder.events[0].meta.origin is NodeMutationOrigin.RECOMPUTE


async def test_bulk_writer_persists_only_the_changed_nodes_in_a_mixed_batch(
    db: InfrahubDatabase,
    default_branch: Branch,
    register_core_models_schema: SchemaBranch,
) -> None:
    """In a batch mixing changed and unchanged values, only the changed nodes are written and announced.

    No-op suppression is per node, so a node whose recomputed value already matches must be skipped
    without suppressing its neighbours, and every node in the batch must end with the correct value.
    """
    await load_profile_schema(db=db)
    nodes = [await _make_node(db=db, branch=default_branch, name=f"n{i}", peer_name=f"p{i}") for i in range(3)]

    # Give the middle node the value it will be asked to write again, so that one write is a no-op.
    seed = BulkRecomputeWriter(db=db, event_service=MemoryInfrahubEvent())
    await seed.write(
        branch=default_branch,
        writes=[AttributeValueWrite(node_id=nodes[1].id, field=DISPLAY_LABEL_FIELD, value="steady")],
        context=_event_context(),
    )

    recorder = MemoryInfrahubEvent()
    writer = BulkRecomputeWriter(db=db, event_service=recorder)
    written = await writer.write(
        branch=default_branch,
        writes=[
            AttributeValueWrite(node_id=nodes[0].id, field=DISPLAY_LABEL_FIELD, value="changed-0"),
            AttributeValueWrite(node_id=nodes[1].id, field=DISPLAY_LABEL_FIELD, value="steady"),
            AttributeValueWrite(node_id=nodes[2].id, field=DISPLAY_LABEL_FIELD, value="changed-2"),
        ],
        context=_event_context(),
    )

    # Only the two nodes whose value actually changed are returned to chain and get an event.
    assert {node.node_id for node in written} == {nodes[0].id, nodes[2].id}
    assert {event.node_id for event in recorder.events} == {nodes[0].id, nodes[2].id}

    # Every node holds the correct value, including the one that was left unchanged.
    for node, expected in ((nodes[0], "changed-0"), (nodes[1], "steady"), (nodes[2], "changed-2")):
        reloaded = await NodeManager.get_one(db=db, id=node.id, branch=default_branch)
        assert reloaded is not None
        assert await reloaded.get_display_label(db=db) == expected


async def test_bulk_writer_persists_a_changed_field_when_another_on_the_node_is_a_no_op(
    db: InfrahubDatabase,
    default_branch: Branch,
    register_core_models_schema: SchemaBranch,
) -> None:
    """A node changed in one field but not another is still saved, and both fields end correct."""
    await load_profile_schema(db=db)
    node = await _make_node(db=db, branch=default_branch, name="n1", peer_name="p1")

    # Seed the display label so re-writing the same value is a no-op for that one field.
    seed = BulkRecomputeWriter(db=db, event_service=MemoryInfrahubEvent())
    await seed.write(
        branch=default_branch,
        writes=[AttributeValueWrite(node_id=node.id, field=DISPLAY_LABEL_FIELD, value="steady")],
        context=_event_context(),
    )

    recorder = MemoryInfrahubEvent()
    writer = BulkRecomputeWriter(db=db, event_service=recorder)
    written = await writer.write(
        branch=default_branch,
        writes=[
            AttributeValueWrite(node_id=node.id, field=DISPLAY_LABEL_FIELD, value="steady"),
            AttributeValueWrite(node_id=node.id, field="summary", value="changed"),
        ],
        context=_event_context(),
    )

    # summary changed, so the node is written and gets one event even though display_label held.
    assert [item.node_id for item in written] == [node.id]
    assert len(recorder.events) == 1
    assert recorder.events[0].node_id == node.id

    reloaded = await NodeManager.get_one(db=db, id=node.id, branch=default_branch)
    assert reloaded is not None
    assert await reloaded.get_display_label(db=db) == "steady"
    assert reloaded.summary.value == "changed"


async def test_bulk_writer_reports_fields_cascaded_by_the_save(
    db: InfrahubDatabase,
    default_branch: Branch,
    register_core_models_schema: SchemaBranch,
) -> None:
    """A write that cascades same-node derived values reports them too, so they can chain.

    Writing ``code`` re-renders both the display label and the hfid (each reads it) in the same save.
    If the writer reported only the requested field, a cross-node reader of either would never chain
    on the coalesced pass. Covers both branches of the writer's field apply (display/hfid and generic).
    """
    await load_schema(db=db, schema=CASCADE_SCHEMA, update_db=True)
    node = await Node.init(db=db, schema=CASCADE_NODE.kind, branch=default_branch)
    await node.new(db=db, name="n1")
    await node.save(db=db)

    recorder = MemoryInfrahubEvent()
    writer = BulkRecomputeWriter(db=db, event_service=recorder)
    written = await writer.write(
        branch=default_branch,
        writes=[AttributeValueWrite(node_id=node.id, field="code", value="override")],
        context=_event_context(),
    )

    # Both the written record and the event carry every cascaded field, not only the requested one.
    assert len(written) == 1
    assert set(written[0].fields) == {"code", DISPLAY_LABEL_FIELD, HFID_FIELD}
    assert set(recorder.events[0].fields) == {"code", DISPLAY_LABEL_FIELD, HFID_FIELD}

    reloaded = await NodeManager.get_one(db=db, id=node.id, branch=default_branch)
    assert reloaded is not None
    assert reloaded.code.value == "override"
    assert await reloaded.get_display_label(db=db) == "override"
    assert await reloaded.get_hfid(db=db) == ["override"]


async def test_dispatch_returns_without_writing_when_branch_is_gone(
    db: InfrahubDatabase,
    default_branch: Branch,
    register_core_models_schema: SchemaBranch,
) -> None:
    """A branch deleted between the reader query and the write leaves nothing persisted or dispatched.

    The dispatcher resolves the branch after tagging the run; a missing branch is the grace path, and
    it must return before any write, event, or chained workflow.
    """
    await load_profile_schema(db=db)
    node = await _make_node(db=db, branch=default_branch, name="n1", peer_name="p1")

    event_recorder = MemoryInfrahubEvent()
    workflow_recorder = WorkflowRecorder()
    schema_branch = registry.schema.get_schema_branch(name=default_branch.name)

    dispatcher = _dispatcher(
        db=db, event_service=event_recorder, workflow=workflow_recorder, schema_branch=schema_branch
    )

    @flow(name="test-dispatch-branch-gone")
    async def _run() -> None:
        await dispatcher.dispatch(
            writes=[AttributeValueWrite(node_id=node.id, field=DISPLAY_LABEL_FIELD, value="ignored")],
            branch_name="branch-that-was-deleted",
            context=_event_context(),
            coalesced=True,
            recompute_depth=0,
        )

    await _run()

    # The grace path is reached after tagging but before any write, so nothing is persisted.
    assert event_recorder.events == []
    assert workflow_recorder.submit_calls == []

    reloaded = await NodeManager.get_one(db=db, id=node.id, branch=default_branch)
    assert reloaded is not None
    assert await reloaded.get_display_label(db=db) != "ignored"


async def test_dispatch_live_path_stamps_live_and_does_not_chain(
    db: InfrahubDatabase,
    default_branch: Branch,
    register_core_models_schema: SchemaBranch,
) -> None:
    """The live path persists the value, stamps the event live, and never drives the chain.

    A live pass lets the per-node recompute automations carry the next level, so the dispatcher must
    not submit the coalesced chain when ``coalesced`` is False.
    """
    await load_profile_schema(db=db)
    node = await _make_node(db=db, branch=default_branch, name="n1", peer_name="p1")

    event_recorder = MemoryInfrahubEvent()
    workflow_recorder = WorkflowRecorder()
    schema_branch = registry.schema.get_schema_branch(name=default_branch.name)

    dispatcher = _dispatcher(
        db=db, event_service=event_recorder, workflow=workflow_recorder, schema_branch=schema_branch
    )

    @flow(name="test-dispatch-live")
    async def _run() -> None:
        await dispatcher.dispatch(
            writes=[AttributeValueWrite(node_id=node.id, field=DISPLAY_LABEL_FIELD, value="live label")],
            branch_name=default_branch.name,
            context=_event_context(),
            coalesced=False,
            recompute_depth=0,
        )

    await _run()

    # The value is persisted.
    reloaded = await NodeManager.get_one(db=db, id=node.id, branch=default_branch)
    assert reloaded is not None
    assert await reloaded.get_display_label(db=db) == "live label"

    # The event carries the live origin so cross-node readers still recompute from it.
    assert len(event_recorder.events) == 1
    assert event_recorder.events[0].meta.origin is NodeMutationOrigin.LIVE

    # A live pass never drives the coalesced chain; that guards against an inverted ``if coalesced``.
    assert workflow_recorder.submit_calls == []


async def test_chain_self_terminates_on_a_cyclic_schema(
    db: InfrahubDatabase,
    default_branch: Branch,
    register_core_models_schema: SchemaBranch,
) -> None:
    """A cyclic schema keeps yielding its peer level by level, but the depth bound stops it.

    Feeding each level's submissions forward as the next level's writes, the cycle alternates between
    the two kinds forever. The bound is the only thing that ends it: below it the peer is always
    dispatched, and at the bound the same input yields nothing.
    """
    await load_schema(db=db, schema=CYCLE_SCHEMA, update_db=True)
    schema_branch = registry.schema.get_schema_branch(name=default_branch.name)
    bound = max_recompute_chain_depth(schema_branch)

    # Walk the cycle level by level, manufacturing the next level's writes from what was submitted.
    written = [WrittenNode(node_id="a-node", kind=CYCLE_A.kind, fields=("summary",))]
    kinds_seen: list[str] = []
    depth = 0
    while depth < bound:
        recorder = WorkflowRecorder()
        submissions = await RecomputeChainSubmitter(
            builder=CoalescedRecomputeBuilder(schema_branch=schema_branch),
            submitter=CoalescedRecomputeSubmitter(workflow=recorder),
            python_deriver=DisabledPythonTargetDeriver(),
        ).submit(
            written=written,
            branch=default_branch.name,
            context=_event_context(),
            depth=depth,
        )
        # Below the bound the cyclic peer is always dispatched: the cycle never runs dry on its own.
        assert submissions
        target_kind = submissions[0].target_kind
        kinds_seen.append(target_kind)
        written = [WrittenNode(node_id="next", kind=target_kind, fields=("summary",))]
        depth += 1

    # The cycle really did alternate between the two peers, so termination is the bound's doing.
    assert set(kinds_seen) == {CYCLE_A.kind, CYCLE_B.kind}

    # At the bound the next level would exceed it, so the same cyclic input now yields nothing.
    recorder = WorkflowRecorder()
    submissions = await RecomputeChainSubmitter(
        builder=CoalescedRecomputeBuilder(schema_branch=schema_branch),
        submitter=CoalescedRecomputeSubmitter(workflow=recorder),
        python_deriver=DisabledPythonTargetDeriver(),
    ).submit(
        written=written,
        branch=default_branch.name,
        context=_event_context(),
        depth=bound,
    )
    assert submissions == []
    assert recorder.submit_calls == []


async def test_chain_coalesces_the_next_level_into_one_submission(
    db: InfrahubDatabase,
    default_branch: Branch,
    register_core_models_schema: SchemaBranch,
) -> None:
    # The chain schema has level 3's computed summary read level 2's summary across a relationship.
    await load_chain_schema(db=db, levels=3)
    schema_branch = registry.schema.get_schema_branch(name=default_branch.name)

    recorder = WorkflowRecorder()
    written = [WrittenNode(node_id="l2-node", kind=chain_kind(2), fields=("summary",))]

    submissions = await RecomputeChainSubmitter(
        builder=CoalescedRecomputeBuilder(schema_branch=schema_branch),
        submitter=CoalescedRecomputeSubmitter(workflow=recorder),
        python_deriver=DisabledPythonTargetDeriver(),
    ).submit(
        written=written,
        branch=default_branch.name,
        context=_event_context(),
        depth=0,
    )

    # A single write of level 2's summary chains to exactly one coalesced recompute: level 3's summary.
    computed = recorder.get_submit_calls_for(COMPUTED_ATTRIBUTE_PROCESS_JINJA2)
    assert len(computed) == 1
    assert computed[0]["parameters"]["computed_attribute_kind"] == chain_kind(3)
    assert computed[0]["parameters"]["computed_attribute_name"] == "summary"
    assert computed[0]["parameters"]["object_ids"] == ["l2-node"]
    # The chained level carries the incremented depth so it, in turn, stops at the bound.
    assert computed[0]["parameters"]["recompute_depth"] == 1
    assert all(submission.family == COMPUTED_ATTRIBUTE for submission in submissions)


async def test_chain_dispatches_nothing_when_no_values_were_written(
    db: InfrahubDatabase,
    default_branch: Branch,
    register_core_models_schema: SchemaBranch,
) -> None:
    await load_chain_schema(db=db, levels=3)
    schema_branch = registry.schema.get_schema_branch(name=default_branch.name)

    recorder = WorkflowRecorder()
    submissions = await RecomputeChainSubmitter(
        builder=CoalescedRecomputeBuilder(schema_branch=schema_branch),
        submitter=CoalescedRecomputeSubmitter(workflow=recorder),
        python_deriver=DisabledPythonTargetDeriver(),
    ).submit(
        written=[],
        branch=default_branch.name,
        context=_event_context(),
        depth=0,
    )

    # An empty write set ends the chain: nothing more to recompute.
    assert submissions == []
    assert recorder.submit_calls == []


async def test_chain_stops_at_the_depth_bound(
    db: InfrahubDatabase,
    default_branch: Branch,
    register_core_models_schema: SchemaBranch,
) -> None:
    await load_chain_schema(db=db, levels=3)
    schema_branch = registry.schema.get_schema_branch(name=default_branch.name)

    recorder = WorkflowRecorder()
    written = [WrittenNode(node_id="l2-node", kind=chain_kind(2), fields=("summary",))]

    # Starting at the bound, the next level would exceed it, so a cyclic schema cannot chain without end.
    bound = max_recompute_chain_depth(schema_branch)
    submissions = await RecomputeChainSubmitter(
        builder=CoalescedRecomputeBuilder(schema_branch=schema_branch),
        submitter=CoalescedRecomputeSubmitter(workflow=recorder),
        python_deriver=DisabledPythonTargetDeriver(),
    ).submit(
        written=written,
        branch=default_branch.name,
        context=_event_context(),
        depth=bound,
    )

    assert submissions == []
    assert recorder.submit_calls == []


async def test_chain_bound_scales_with_the_schema_so_deep_chains_are_not_truncated(
    db: InfrahubDatabase,
    default_branch: Branch,
    register_core_models_schema: SchemaBranch,
) -> None:
    """A schema with more targets than the floor raises the bound, so a deep chain is not truncated."""
    await load_chain_schema(db=db, levels=12)
    schema_branch = registry.schema.get_schema_branch(name=default_branch.name)

    assert max_recompute_chain_depth(schema_branch) > RECOMPUTE_CHAIN_DEPTH_FLOOR

    recorder = WorkflowRecorder()
    written = [WrittenNode(node_id="l2-node", kind=chain_kind(2), fields=("summary",))]
    # Level 3 reads level 2's summary; at the floor depth the derived bound still dispatches it.
    submissions = await RecomputeChainSubmitter(
        builder=CoalescedRecomputeBuilder(schema_branch=schema_branch),
        submitter=CoalescedRecomputeSubmitter(workflow=recorder),
        python_deriver=DisabledPythonTargetDeriver(),
    ).submit(
        written=written,
        branch=default_branch.name,
        context=_event_context(),
        depth=RECOMPUTE_CHAIN_DEPTH_FLOOR,
    )

    assert submissions
    assert all(submission.family == COMPUTED_ATTRIBUTE for submission in submissions)
