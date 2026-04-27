"""Validators that assert post-merge state on the default branch.

Each validator consumes a context from ``_contexts.py`` and asserts the state
on the default branch matches what the matrix test expects after the merge.

The "clean merge" baseline is encoded here: when the branch change is applied
verbatim, the default branch shows the new value with ``updated_at == merge_at``
and ``updated_by == branch_user``. Scenario tests call these validators with
context values that already reflect scenario-specific expectations (e.g. an
``expected_kind`` that differs from the created kind, or a context that was
omitted from the matrix because the scenario discarded that change).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from infrahub.core.constants import MetadataOptions
from infrahub.core.manager import NodeManager
from infrahub.core.metadata.model import MetadataQueryOptions
from infrahub.core.metadata.query.node_metadata import NodeMetadataDefaultBranchQuery
from infrahub.exceptions import NodeNotFoundError

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.core.timestamp import Timestamp
    from infrahub.database import InfrahubDatabase

    from ._conflict_setup import BaseConflicts
    from ._contexts import (
        AddedNodeCtx,
        AddedRelationshipCtx,
        ClearedAttributePropertyCtx,
        ClearedAttributeValueCtx,
        ClearedRelationshipPropertyCtx,
        DeletedNodeCtx,
        DeletedRelationshipCtx,
        MatrixContexts,
        UpdatedAttributePropertyCtx,
        UpdatedAttributeValueCtx,
        UpdatedRelationshipPropertyCtx,
    )

_ALL_METADATA = MetadataQueryOptions(
    node_level=MetadataOptions.USER_TIMESTAMPS | MetadataOptions.LINKED_NODES,
    attribute_level=MetadataOptions.USER_TIMESTAMPS | MetadataOptions.LINKED_NODES,
    relationship_level=MetadataOptions.USER_TIMESTAMPS | MetadataOptions.LINKED_NODES,
)


async def _fetch_rel(
    *,
    db: InfrahubDatabase,
    branch: Branch,
    node_id: str,
    relationship_name: str,
    peer_id: str,
):
    """Return the single RelationshipPeer matching ``peer_id`` for ``relationship_name`` on ``node_id``."""
    node = await NodeManager.get_one(
        db=db, branch=branch, id=node_id, include_metadata=_ALL_METADATA, prefetch_relationships=True
    )
    peers = await node.get_relationship(relationship_name).get_relationships(db=db)
    matched = [p for p in peers if p.peer_id == peer_id]
    assert len(matched) == 1, f"expected 1 {relationship_name} peer {peer_id} on {node_id}, got {len(matched)}"
    return matched[0]


async def validate_added_node(db: InfrahubDatabase, branch: Branch, ctx: AddedNodeCtx, merge_at: Timestamp) -> None:
    node = await NodeManager.get_one(
        db=db, branch=branch, id=ctx.node_id, include_metadata=_ALL_METADATA, prefetch_relationships=True
    )
    assert node is not None, f"expected node {ctx.node_id} to exist on {branch.name}"
    assert node.get_kind() == ctx.expected_kind

    for attr_name, expected_value in ctx.attribute_values.items():
        attr = node.get_attribute(attr_name)
        assert attr.value == expected_value, (
            f"{ctx.expected_kind}.{attr_name}: expected {expected_value!r}, got {attr.value!r}"
        )
        assert attr._get_created_at() == merge_at
        assert attr._get_created_by() == ctx.branch_user
        assert attr._get_updated_at() == merge_at
        assert attr._get_updated_by() == ctx.branch_user

    for rel_name, peer_id in ctx.one_relationship_peers.items():
        rel = await node.get_relationship(rel_name).get(db=db)
        assert rel.peer_id == peer_id
        assert rel._get_created_at() == merge_at
        assert rel._get_created_by() == ctx.branch_user
        assert rel._get_updated_at() == merge_at
        assert rel._get_updated_by() == ctx.branch_user

    for rel_name, peer_ids in ctx.many_relationship_peers.items():
        peers = await node.get_relationship(rel_name).get_relationships(db=db)
        assert {p.peer_id for p in peers} == set(peer_ids)
        for peer in peers:
            assert peer._get_created_at() == merge_at
            assert peer._get_created_by() == ctx.branch_user

    assert node._get_created_at() == merge_at
    assert node._get_created_by() == ctx.branch_user
    assert node._get_updated_at() == merge_at
    assert node._get_updated_by() == ctx.branch_user


async def validate_added_node_missing(db: InfrahubDatabase, branch: Branch, ctx: AddedNodeCtx) -> None:
    """For scenarios where the added-node change was discarded."""
    node = await NodeManager.get_one(db=db, branch=branch, id=ctx.node_id)
    assert node is None, f"expected node {ctx.node_id} to be absent from {branch.name}"


async def validate_deleted_node(db: InfrahubDatabase, branch: Branch, ctx: DeletedNodeCtx, merge_at: Timestamp) -> None:
    with pytest.raises(NodeNotFoundError):
        await NodeManager.get_one(db=db, branch=branch, id=ctx.node_id, raise_on_error=True)

    node_metadata_query = await NodeMetadataDefaultBranchQuery.init(db=db, branch=branch, node_uuids=[ctx.node_id])
    await node_metadata_query.execute(db=db)
    metadatas = node_metadata_query.get_metadatas()
    assert len(metadatas) == 1
    meta = metadatas[0]
    assert meta.is_deleted is True
    assert meta.created_at == ctx.original_created_at
    assert meta.created_by == ctx.original_created_by
    assert meta.updated_at == merge_at
    assert meta.updated_by == ctx.branch_user
    for attr in meta.attributes:
        assert attr.is_deleted is True
        assert attr.updated_at == merge_at
        assert attr.updated_by == ctx.branch_user
    # Every relationship from the deleted node to a peer we know about should
    # be cascade-deleted with merge timestamps; unknown peers are ignored.
    expected_peer_ids = set(ctx.peer_node_ids)
    found_peer_ids: set[str] = set()
    for rel in meta.relationships:
        if rel.peer_uuid not in expected_peer_ids:
            continue
        found_peer_ids.add(rel.peer_uuid)
        assert rel.is_deleted is True, f"rel to {rel.peer_uuid} should be deleted after node delete"
        assert rel.updated_at == merge_at
        assert rel.updated_by == ctx.branch_user
    missing = expected_peer_ids - found_peer_ids
    assert not missing, f"expected deleted rels to peers {missing}, none found in metadata"


async def validate_deleted_node_restored(db: InfrahubDatabase, branch: Branch, ctx: DeletedNodeCtx) -> None:
    """For scenarios where the delete was discarded (node should still exist)."""
    node = await NodeManager.get_one(db=db, branch=branch, id=ctx.node_id)
    assert node is not None


async def validate_updated_attribute_value(
    db: InfrahubDatabase,
    branch: Branch,
    ctx: UpdatedAttributeValueCtx,
    merge_at: Timestamp,
) -> None:
    node = await NodeManager.get_one(
        db=db, branch=branch, id=ctx.node_id, include_metadata=_ALL_METADATA, prefetch_relationships=True
    )
    attr = node.get_attribute(ctx.attribute_name)
    assert attr.value == ctx.expected_value, (
        f"{ctx.node_id}.{ctx.attribute_name}: expected {ctx.expected_value!r}, got {attr.value!r}"
    )
    assert attr._get_created_at() == ctx.original_created_at, (
        f"{ctx.node_id}.{ctx.attribute_name}.created_at: "
        f"expected {ctx.original_created_at}, got {attr._get_created_at()}"
    )
    assert attr._get_created_by() == ctx.original_created_by
    assert attr._get_updated_at() == merge_at
    assert attr._get_updated_by() == ctx.branch_user


async def validate_cleared_attribute_value(
    db: InfrahubDatabase,
    branch: Branch,
    ctx: ClearedAttributeValueCtx,
    merge_at: Timestamp,
) -> None:
    node = await NodeManager.get_one(
        db=db, branch=branch, id=ctx.node_id, include_metadata=_ALL_METADATA, prefetch_relationships=True
    )
    attr = node.get_attribute(ctx.attribute_name)
    assert attr.value is None
    assert attr._get_created_at() == ctx.original_created_at
    assert attr._get_created_by() == ctx.original_created_by
    assert attr._get_updated_at() == merge_at
    assert attr._get_updated_by() == ctx.branch_user


async def validate_added_relationship(
    db: InfrahubDatabase,
    branch: Branch,
    ctx: AddedRelationshipCtx,
    merge_at: Timestamp,
) -> None:
    peer = await _fetch_rel(
        db=db,
        branch=branch,
        node_id=ctx.node_id,
        relationship_name=ctx.relationship_name,
        peer_id=ctx.peer_id,
    )
    assert peer._get_created_at() == merge_at
    assert peer._get_created_by() == ctx.branch_user
    assert peer._get_updated_at() == merge_at
    assert peer._get_updated_by() == ctx.branch_user


async def validate_deleted_relationship(
    db: InfrahubDatabase,
    branch: Branch,
    ctx: DeletedRelationshipCtx,
) -> None:
    node = await NodeManager.get_one(db=db, branch=branch, id=ctx.node_id, prefetch_relationships=True)
    peers = await node.get_relationship(ctx.relationship_name).get_relationships(db=db)
    assert all(p.peer_id != ctx.peer_id for p in peers), (
        f"expected {ctx.relationship_name} peer {ctx.peer_id} to be removed from {ctx.node_id}"
    )


async def validate_updated_attribute_property(
    db: InfrahubDatabase,
    branch: Branch,
    ctx: UpdatedAttributePropertyCtx,
    merge_at: Timestamp,
) -> None:
    node = await NodeManager.get_one(
        db=db, branch=branch, id=ctx.node_id, include_metadata=_ALL_METADATA, prefetch_relationships=True
    )
    attr = node.get_attribute(ctx.attribute_name)
    if ctx.property_name == "source":
        assert attr.source_id == ctx.expected_peer_id, (
            f"{ctx.node_id}.{ctx.attribute_name}.source: expected {ctx.expected_peer_id}, got {attr.source_id}"
        )
    elif ctx.property_name == "owner":
        assert attr.owner_id == ctx.expected_peer_id
    elif ctx.property_name == "is_protected":
        assert attr.is_protected == ctx.expected_bool
    assert attr._get_updated_at() == merge_at
    assert attr._get_updated_by() == ctx.branch_user


async def validate_cleared_attribute_property(
    db: InfrahubDatabase,
    branch: Branch,
    ctx: ClearedAttributePropertyCtx,
    merge_at: Timestamp,
) -> None:
    node = await NodeManager.get_one(
        db=db, branch=branch, id=ctx.node_id, include_metadata=_ALL_METADATA, prefetch_relationships=True
    )
    attr = node.get_attribute(ctx.attribute_name)
    if ctx.property_name == "source":
        assert attr.source_id is None
    elif ctx.property_name == "owner":
        assert attr.owner_id is None
    assert attr._get_updated_at() == merge_at
    assert attr._get_updated_by() == ctx.branch_user


async def validate_updated_relationship_property(
    db: InfrahubDatabase,
    branch: Branch,
    ctx: UpdatedRelationshipPropertyCtx,
    merge_at: Timestamp,
) -> None:
    rel = await _fetch_rel(
        db=db,
        branch=branch,
        node_id=ctx.node_id,
        relationship_name=ctx.relationship_name,
        peer_id=ctx.peer_id,
    )
    if ctx.property_name == "source":
        assert rel.source_id == ctx.expected_peer_id, (
            f"{ctx.node_id}.{ctx.relationship_name}[{ctx.peer_id}].source: "
            f"expected {ctx.expected_peer_id}, got {rel.source_id}"
        )
    elif ctx.property_name == "owner":
        assert rel.owner_id == ctx.expected_peer_id
    elif ctx.property_name == "is_protected":
        assert rel.is_protected == ctx.expected_bool
    assert rel._get_updated_at() == merge_at
    assert rel._get_updated_by() == ctx.branch_user


async def validate_cleared_relationship_property(
    db: InfrahubDatabase,
    branch: Branch,
    ctx: ClearedRelationshipPropertyCtx,
    merge_at: Timestamp,
) -> None:
    rel = await _fetch_rel(
        db=db,
        branch=branch,
        node_id=ctx.node_id,
        relationship_name=ctx.relationship_name,
        peer_id=ctx.peer_id,
    )
    if ctx.property_name == "source":
        assert rel.source_id is None
    elif ctx.property_name == "owner":
        assert rel.owner_id is None


async def validate_all_applied(
    db: InfrahubDatabase,
    branch: Branch,
    contexts: MatrixContexts,
    merge_at: Timestamp,
) -> None:
    """Validate the clean-merge baseline: every staged change landed on the default branch."""
    if contexts.added_node:
        await validate_added_node(db=db, branch=branch, ctx=contexts.added_node, merge_at=merge_at)
    if contexts.deleted_node:
        await validate_deleted_node(db=db, branch=branch, ctx=contexts.deleted_node, merge_at=merge_at)
    for uav_ctx in contexts.updated_attribute_values:
        await validate_updated_attribute_value(db=db, branch=branch, ctx=uav_ctx, merge_at=merge_at)
    if contexts.cleared_attribute_value:
        await validate_cleared_attribute_value(
            db=db, branch=branch, ctx=contexts.cleared_attribute_value, merge_at=merge_at
        )
    for ctx in contexts.added_relationships:
        await validate_added_relationship(db=db, branch=branch, ctx=ctx, merge_at=merge_at)
    for del_ctx in contexts.deleted_relationships:
        await validate_deleted_relationship(db=db, branch=branch, ctx=del_ctx)
    for ap_ctx in contexts.updated_attribute_properties:
        await validate_updated_attribute_property(db=db, branch=branch, ctx=ap_ctx, merge_at=merge_at)
    for cap_ctx in contexts.cleared_attribute_properties:
        await validate_cleared_attribute_property(db=db, branch=branch, ctx=cap_ctx, merge_at=merge_at)
    for rp_ctx in contexts.updated_relationship_properties:
        await validate_updated_relationship_property(db=db, branch=branch, ctx=rp_ctx, merge_at=merge_at)
    for crp_ctx in contexts.cleared_relationship_properties:
        await validate_cleared_relationship_property(db=db, branch=branch, ctx=crp_ctx, merge_at=merge_at)


async def validate_rolled_back_added_node(db: InfrahubDatabase, branch: Branch, ctx: AddedNodeCtx) -> None:
    node = await NodeManager.get_one(db=db, branch=branch, id=ctx.node_id)
    assert node is None, f"added node {ctx.node_id} should be gone after rollback"


async def validate_rolled_back_deleted_node(db: InfrahubDatabase, branch: Branch, ctx: DeletedNodeCtx) -> None:
    node = await NodeManager.get_one(
        db=db, branch=branch, id=ctx.node_id, include_metadata=MetadataOptions.USER_TIMESTAMPS
    )
    assert node is not None, f"deleted node {ctx.node_id} should be restored after rollback"
    assert node.get_kind() == ctx.expected_kind
    if ctx.original_updated_at is not None:
        assert node._get_updated_at() == ctx.original_updated_at, (
            f"{ctx.node_id} node.updated_at after rollback: "
            f"expected {ctx.original_updated_at}, got {node._get_updated_at()}"
        )
    if ctx.original_updated_by is not None:
        assert node._get_updated_by() == ctx.original_updated_by


async def validate_rolled_back_updated_attribute_value(
    db: InfrahubDatabase, branch: Branch, ctx: UpdatedAttributeValueCtx
) -> None:
    node = await NodeManager.get_one(
        db=db, branch=branch, id=ctx.node_id, include_metadata=MetadataOptions.USER_TIMESTAMPS
    )
    attr = node.get_attribute(ctx.attribute_name)
    assert attr.value == ctx.original_value, (
        f"{ctx.node_id}.{ctx.attribute_name} after rollback: expected {ctx.original_value!r}, got {attr.value!r}"
    )
    if ctx.original_updated_at is not None:
        assert attr._get_updated_at() == ctx.original_updated_at, (
            f"{ctx.node_id}.{ctx.attribute_name} attr.updated_at after rollback: "
            f"expected {ctx.original_updated_at}, got {attr._get_updated_at()}"
        )
    if ctx.original_updated_by is not None:
        assert attr._get_updated_by() == ctx.original_updated_by


async def validate_rolled_back_cleared_attribute_value(
    db: InfrahubDatabase, branch: Branch, ctx: ClearedAttributeValueCtx
) -> None:
    node = await NodeManager.get_one(
        db=db, branch=branch, id=ctx.node_id, include_metadata=MetadataOptions.USER_TIMESTAMPS
    )
    attr = node.get_attribute(ctx.attribute_name)
    assert attr.value == ctx.original_value, (
        f"{ctx.node_id}.{ctx.attribute_name} after rollback: expected {ctx.original_value!r}, got {attr.value!r}"
    )
    if ctx.original_updated_at is not None:
        assert attr._get_updated_at() == ctx.original_updated_at
    if ctx.original_updated_by is not None:
        assert attr._get_updated_by() == ctx.original_updated_by


async def validate_rolled_back_added_relationship(
    db: InfrahubDatabase, branch: Branch, ctx: AddedRelationshipCtx
) -> None:
    node = await NodeManager.get_one(db=db, branch=branch, id=ctx.node_id, prefetch_relationships=True)
    peers = await node.get_relationship(ctx.relationship_name).get_relationships(db=db)
    peer_ids = {p.peer_id for p in peers}
    assert ctx.peer_id not in peer_ids, (
        f"{ctx.relationship_name}[{ctx.peer_id}] on {ctx.node_id} should be absent after rollback"
    )
    if ctx.replaced_peer_id is not None:
        assert ctx.replaced_peer_id in peer_ids


async def validate_rolled_back_deleted_relationship(
    db: InfrahubDatabase, branch: Branch, ctx: DeletedRelationshipCtx
) -> None:
    rel = await _fetch_rel(
        db=db,
        branch=branch,
        node_id=ctx.node_id,
        relationship_name=ctx.relationship_name,
        peer_id=ctx.peer_id,
    )
    if ctx.original_updated_at is not None:
        assert rel._get_updated_at() == ctx.original_updated_at, (
            f"{ctx.relationship_name}[{ctx.peer_id}] on {ctx.node_id} rel.updated_at after rollback: "
            f"expected {ctx.original_updated_at}, got {rel._get_updated_at()}"
        )
    if ctx.original_updated_by is not None:
        assert rel._get_updated_by() == ctx.original_updated_by


async def validate_rolled_back_updated_attribute_property(
    db: InfrahubDatabase, branch: Branch, ctx: UpdatedAttributePropertyCtx
) -> None:
    node = await NodeManager.get_one(db=db, branch=branch, id=ctx.node_id, include_metadata=_ALL_METADATA)
    attr = node.get_attribute(ctx.attribute_name)
    if ctx.property_name == "source":
        assert attr.source_id == ctx.original_peer_id
    elif ctx.property_name == "owner":
        assert attr.owner_id == ctx.original_peer_id
    elif ctx.property_name == "is_protected":
        assert attr.is_protected == ctx.original_bool
    if ctx.original_updated_at is not None:
        assert attr._get_updated_at() == ctx.original_updated_at
    if ctx.original_updated_by is not None:
        assert attr._get_updated_by() == ctx.original_updated_by


async def validate_rolled_back_cleared_attribute_property(
    db: InfrahubDatabase, branch: Branch, ctx: ClearedAttributePropertyCtx
) -> None:
    node = await NodeManager.get_one(db=db, branch=branch, id=ctx.node_id, include_metadata=_ALL_METADATA)
    attr = node.get_attribute(ctx.attribute_name)
    if ctx.property_name == "source":
        assert attr.source_id == ctx.original_peer_id
    elif ctx.property_name == "owner":
        assert attr.owner_id == ctx.original_peer_id
    if ctx.original_updated_at is not None:
        assert attr._get_updated_at() == ctx.original_updated_at
    if ctx.original_updated_by is not None:
        assert attr._get_updated_by() == ctx.original_updated_by


async def validate_rolled_back_updated_relationship_property(
    db: InfrahubDatabase, branch: Branch, ctx: UpdatedRelationshipPropertyCtx
) -> None:
    rel = await _fetch_rel(
        db=db,
        branch=branch,
        node_id=ctx.node_id,
        relationship_name=ctx.relationship_name,
        peer_id=ctx.peer_id,
    )
    if ctx.property_name in ("source", "owner"):
        current = rel.source_id if ctx.property_name == "source" else rel.owner_id
        assert current == ctx.original_peer_id
    if ctx.property_name == "is_protected":
        assert rel.is_protected == ctx.original_bool
    if ctx.original_updated_at is not None:
        assert rel._get_updated_at() == ctx.original_updated_at
    if ctx.original_updated_by is not None:
        assert rel._get_updated_by() == ctx.original_updated_by


async def validate_rolled_back_cleared_relationship_property(
    db: InfrahubDatabase, branch: Branch, ctx: ClearedRelationshipPropertyCtx
) -> None:
    rel = await _fetch_rel(
        db=db,
        branch=branch,
        node_id=ctx.node_id,
        relationship_name=ctx.relationship_name,
        peer_id=ctx.peer_id,
    )
    current = rel.source_id if ctx.property_name == "source" else rel.owner_id
    assert current == ctx.original_peer_id
    if ctx.original_updated_at is not None:
        assert rel._get_updated_at() == ctx.original_updated_at
    if ctx.original_updated_by is not None:
        assert rel._get_updated_by() == ctx.original_updated_by


async def validate_all_applied_with_conflict_to_base(  # noqa: C901
    db: InfrahubDatabase,
    branch: Branch,
    contexts: MatrixContexts,
    base_conflicts: BaseConflicts,
    merge_at: Timestamp,
    *,
    added_node_state: str = "applied",
) -> None:
    """Validate post-merge state when every conflict was resolved toward the base branch.

    For each change type that admits a conflict, the branch change was discarded,
    so the default branch shows the base-branch value (with base-user metadata).
    The non-conflictable ``added_node`` change is still applied (new insert) unless
    overridden via ``added_node_state`` — set to ``"missing"`` to validate the
    post-rollback state where the added node has been undone.
    """
    # added_node: no conflict path — applied as in clean merge
    if contexts.added_node:
        if added_node_state == "applied":
            await validate_added_node(db=db, branch=branch, ctx=contexts.added_node, merge_at=merge_at)
        elif added_node_state == "missing":
            await validate_rolled_back_added_node(db=db, branch=branch, ctx=contexts.added_node)

    # deleted_node: base-side attr update prevents the delete; node is alive with base's attr value
    if contexts.deleted_node:
        node = await NodeManager.get_one(
            db=db, branch=branch, id=contexts.deleted_node.node_id, include_metadata=_ALL_METADATA
        )
        assert node is not None, "node deletion should be discarded when conflict resolved to base"
        for attr_name, expected in base_conflicts.deleted_node_base_update.items():
            assert node.get_attribute(attr_name).value == expected

    # attribute value: base's value prevails (per staged attribute)
    for uav_ctx in contexts.updated_attribute_values:
        base_val = base_conflicts.updated_attribute_value_base.get((uav_ctx.node_id, uav_ctx.attribute_name))
        if base_val is None:
            continue
        node = await NodeManager.get_one(db=db, branch=branch, id=uav_ctx.node_id)
        assert node.get_attribute(uav_ctx.attribute_name).value == base_val
    if contexts.cleared_attribute_value:
        ctx2 = contexts.cleared_attribute_value
        node = await NodeManager.get_one(db=db, branch=branch, id=ctx2.node_id)
        assert node.get_attribute(ctx2.attribute_name).value == base_conflicts.cleared_attribute_value_base_value

    # relationships: base's peer prevails
    for ar in contexts.added_relationships:
        base_peer = base_conflicts.added_relationship_base_peer_ids.get((ar.node_id, ar.relationship_name))
        if base_peer is None:
            continue  # no base-side conflict staged for this rel
        node = await NodeManager.get_one(db=db, branch=branch, id=ar.node_id, prefetch_relationships=True)
        peers = await node.get_relationship(ar.relationship_name).get_relationships(db=db)
        assert any(p.peer_id == base_peer for p in peers)
        assert all(p.peer_id != ar.peer_id for p in peers)
    for dr in contexts.deleted_relationships:
        base_peer = base_conflicts.cleared_relationship_base_peer_ids.get((dr.node_id, dr.relationship_name))
        if base_peer is None:
            continue
        node = await NodeManager.get_one(db=db, branch=branch, id=dr.node_id, prefetch_relationships=True)
        peers = await node.get_relationship(dr.relationship_name).get_relationships(db=db)
        assert any(p.peer_id == base_peer for p in peers)

    # attribute properties
    for ap in contexts.updated_attribute_properties:
        base_val = base_conflicts.updated_attribute_property_base.get((ap.node_id, ap.attribute_name, ap.property_name))
        if base_val is None:
            continue
        node = await NodeManager.get_one(db=db, branch=branch, id=ap.node_id, include_metadata=_ALL_METADATA)
        attr = node.get_attribute(ap.attribute_name)
        if ap.property_name == "source":
            assert attr.source_id == base_val
        elif ap.property_name == "owner":
            assert attr.owner_id == base_val
        elif ap.property_name == "is_protected":
            assert attr.is_protected == base_val
    for cap in contexts.cleared_attribute_properties:
        base_val = base_conflicts.cleared_attribute_property_base.get(
            (cap.node_id, cap.attribute_name, cap.property_name)
        )
        if base_val is None:
            continue
        node = await NodeManager.get_one(db=db, branch=branch, id=cap.node_id, include_metadata=_ALL_METADATA)
        attr = node.get_attribute(cap.attribute_name)
        if cap.property_name == "source":
            assert attr.source_id == base_val
        else:
            assert attr.owner_id == base_val

    # relationship properties
    for rp in contexts.updated_relationship_properties:
        base_val = base_conflicts.updated_relationship_property_base.get(
            (rp.node_id, rp.relationship_name, rp.peer_id, rp.property_name)
        )
        if base_val is None:
            continue
        rel = await _fetch_rel(
            db=db,
            branch=branch,
            node_id=rp.node_id,
            relationship_name=rp.relationship_name,
            peer_id=rp.peer_id,
        )
        if rp.property_name in ("source", "owner"):
            current = rel.source_id if rp.property_name == "source" else rel.owner_id
            assert current == base_val
        else:
            assert rel.is_protected == base_val
    for crp in contexts.cleared_relationship_properties:
        base_val = base_conflicts.cleared_relationship_property_base.get(
            (crp.node_id, crp.relationship_name, crp.peer_id, crp.property_name)
        )
        if base_val is None:
            continue
        rel = await _fetch_rel(
            db=db,
            branch=branch,
            node_id=crp.node_id,
            relationship_name=crp.relationship_name,
            peer_id=crp.peer_id,
        )
        current = rel.source_id if crp.property_name == "source" else rel.owner_id
        assert current == base_val


async def validate_all_rolled_back(
    db: InfrahubDatabase,
    branch: Branch,
    contexts: MatrixContexts,
) -> None:
    """After rollback of a clean merge, every staged change should be undone."""
    if contexts.added_node:
        await validate_rolled_back_added_node(db=db, branch=branch, ctx=contexts.added_node)
    if contexts.deleted_node:
        await validate_rolled_back_deleted_node(db=db, branch=branch, ctx=contexts.deleted_node)
    for uav_ctx in contexts.updated_attribute_values:
        await validate_rolled_back_updated_attribute_value(db=db, branch=branch, ctx=uav_ctx)
    if contexts.cleared_attribute_value:
        await validate_rolled_back_cleared_attribute_value(db=db, branch=branch, ctx=contexts.cleared_attribute_value)
    for ctx in contexts.added_relationships:
        await validate_rolled_back_added_relationship(db=db, branch=branch, ctx=ctx)
    for del_ctx in contexts.deleted_relationships:
        await validate_rolled_back_deleted_relationship(db=db, branch=branch, ctx=del_ctx)
    for ap_ctx in contexts.updated_attribute_properties:
        await validate_rolled_back_updated_attribute_property(db=db, branch=branch, ctx=ap_ctx)
    for cap_ctx in contexts.cleared_attribute_properties:
        await validate_rolled_back_cleared_attribute_property(db=db, branch=branch, ctx=cap_ctx)
    for rp_ctx in contexts.updated_relationship_properties:
        await validate_rolled_back_updated_relationship_property(db=db, branch=branch, ctx=rp_ctx)
    for crp_ctx in contexts.cleared_relationship_properties:
        await validate_rolled_back_cleared_relationship_property(db=db, branch=branch, ctx=crp_ctx)
