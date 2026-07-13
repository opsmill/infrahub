"""The bulk recompute writer persists all three derived-value families and chains coalesced."""

from __future__ import annotations

from typing import TYPE_CHECKING

from infrahub.core.manager import NodeManager
from infrahub.core.merge.recompute_coalescing import (
    COMPUTED_ATTRIBUTE,
    MAX_RECOMPUTE_CHAIN_DEPTH,
    submit_recompute_chain,
)
from infrahub.core.node import Node
from infrahub.core.recompute.bulk_write import (
    DISPLAY_LABEL_FIELD,
    HFID_FIELD,
    AttributeValueWrite,
    BulkRecomputeWriter,
    WrittenNode,
)
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

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.core.schema.schema_branch import SchemaBranch
    from infrahub.database import InfrahubDatabase


def _event_context() -> EventContext:
    return EventContext(branch=EventBranchContext(name="main"), account_id="")


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

    # One coalesced event per node (not one per value), carrying every changed field, live-origin by
    # default so values reading these still recompute through the per-node automations.
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


async def test_bulk_writer_skips_a_no_op_write_so_it_does_not_fan_out(
    db: InfrahubDatabase,
    default_branch: Branch,
    register_core_models_schema: SchemaBranch,
) -> None:
    await load_profile_schema(db=db)
    node = await _make_node(db=db, branch=default_branch, name="n1", peer_name="p1")

    writer = BulkRecomputeWriter(db=db, event_service=MemoryInfrahubEvent())
    await writer.write(
        branch=default_branch,
        writes=[AttributeValueWrite(node_id=node.id, field=DISPLAY_LABEL_FIELD, value="custom label")],
        context=_event_context(),
    )

    # Re-writing the stored value persists nothing, so no event is emitted and no node is returned to
    # chain the next level.
    recorder = MemoryInfrahubEvent()
    rewriter = BulkRecomputeWriter(db=db, event_service=recorder)
    written = await rewriter.write(
        branch=default_branch,
        writes=[AttributeValueWrite(node_id=node.id, field=DISPLAY_LABEL_FIELD, value="custom label")],
        context=_event_context(),
    )

    assert written == []
    assert recorder.events == []


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

    submissions = await submit_recompute_chain(
        written=written,
        schema_branch=schema_branch,
        branch=default_branch.name,
        workflow=recorder,
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
    submissions = await submit_recompute_chain(
        written=[],
        schema_branch=schema_branch,
        branch=default_branch.name,
        workflow=recorder,
        context=_event_context(),
        depth=0,
    )

    # An empty write set is the chain's fixpoint: nothing more to recompute.
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

    # At the bound the next level would exceed it, so a cyclic schema cannot chain without end.
    submissions = await submit_recompute_chain(
        written=written,
        schema_branch=schema_branch,
        branch=default_branch.name,
        workflow=recorder,
        context=_event_context(),
        depth=MAX_RECOMPUTE_CHAIN_DEPTH,
    )

    assert submissions == []
    assert recorder.submit_calls == []
