"""Stage conflicting changes on the base branch for a ``MatrixContexts``.

Given a ``MatrixContexts`` produced by ``_setup.setup_*`` on the diff branch,
these helpers layer on conflicting changes on the base branch (``default_branch``)
so the diff coordinator produces a conflict for each change type that admits one.

Tests drive these helpers before calling ``diff_coordinator.update_branch_diff``,
then set conflict selection (BASE or DIFF) on every detected conflict, then merge.

The returned ``BaseConflicts`` records the values the base branch landed on so
validators can assert the post-merge state when the conflict is resolved to base
(branch changes discarded).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from infrahub.core.constants import MetadataOptions
from infrahub.core.manager import NodeManager

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.core.node import Node
    from infrahub.database import InfrahubDatabase

    from ._contexts import MatrixContexts


@dataclass
class BaseConflicts:
    """Captures the base-branch-side values staged for each conflicting change.

    Only populated for change types that can actually produce a conflict with the
    branch-side change. ``added_node`` has no conflict (it's a fresh insert);
    ``deleted_node`` conflicts are tracked by ``deleted_node_base_update``.
    """

    deleted_node_base_update: dict[str, Any] = field(default_factory=dict)  # attr_name -> new_value
    deleted_node_base_user: str = ""
    updated_attribute_value_base: dict[tuple[str, str], Any] = field(default_factory=dict)
    # (node_id, attr_name) -> base-branch value
    updated_attribute_value_base_user: str = ""
    cleared_attribute_value_base_value: Any = None
    cleared_attribute_value_base_user: str = ""
    added_relationship_base_peer_ids: dict[tuple[str, str], str] = field(default_factory=dict)
    # (node_id, rel_name) -> base-branch peer_id set
    added_relationship_base_user: str = ""
    cleared_relationship_base_peer_ids: dict[tuple[str, str], str] = field(default_factory=dict)
    cleared_relationship_base_user: str = ""
    updated_attribute_property_base: dict[tuple[str, str, str], Any] = field(default_factory=dict)
    # (node_id, attr_name, property_name) -> base-branch value
    updated_attribute_property_base_user: str = ""
    cleared_attribute_property_base: dict[tuple[str, str, str], Any] = field(default_factory=dict)
    cleared_attribute_property_base_user: str = ""
    updated_relationship_property_base: dict[tuple[str, str, str, str], Any] = field(default_factory=dict)
    # (node_id, rel_name, peer_id, property_name) -> base-branch value
    updated_relationship_property_base_user: str = ""
    cleared_relationship_property_base: dict[tuple[str, str, str, str], Any] = field(default_factory=dict)
    cleared_relationship_property_base_user: str = ""


async def stage_base_conflicts(
    db: InfrahubDatabase,
    default_branch: Branch,
    contexts: MatrixContexts,
    *,
    conflict_peer_node: Node,
    base_user: str,
    conflict_peer_overrides: dict[str, Node] | None = None,
) -> BaseConflicts:
    """Stage one conflicting change on ``default_branch`` for every conflictable context entry.

    ``conflict_peer_node`` is used as the peer value for any peer-valued conflicting
    change (new source/owner/rel peer). Pass a node that is not already the branch-
    side expected peer so the conflict is genuine.

    ``conflict_peer_overrides`` maps ``relationship_name`` -> override peer ``Node``.
    When a staged relationship change's ``relationship_name`` is in the dict, the
    override is used instead of ``conflict_peer_node`` — needed when the peer kind
    differs (e.g. ``manufacturer`` rel needs a TestManufacturer peer, not a
    TestPerson).
    """
    overrides = conflict_peer_overrides or {}
    conflicts = BaseConflicts()

    # deleted_node <-> base-side attr update
    if contexts.deleted_node:
        node = await NodeManager.get_one(db=db, branch=default_branch, id=contexts.deleted_node.node_id)
        # Update a commonly-present attribute. For TestCar, ``color`` works.
        new_value = "#BADBAD"
        node.get_attribute("color").value = new_value
        await node.save(db=db, user_id=base_user)
        conflicts.deleted_node_base_update = {"color": new_value}
        conflicts.deleted_node_base_user = base_user

    # updated_attribute_value <-> base-side competing update (per staged attribute)
    for ctx in contexts.updated_attribute_values:
        node = await NodeManager.get_one(db=db, branch=default_branch, id=ctx.node_id)
        base_value = _conflicting_value(current=ctx.expected_value, original=ctx.original_value)
        node.get_attribute(ctx.attribute_name).value = base_value
        await node.save(db=db, user_id=base_user)
        conflicts.updated_attribute_value_base[ctx.node_id, ctx.attribute_name] = base_value
        conflicts.updated_attribute_value_base_user = base_user

    # cleared_attribute_value <-> base-side competing update (keeps a value instead of clearing)
    if contexts.cleared_attribute_value:
        ctx = contexts.cleared_attribute_value
        node = await NodeManager.get_one(db=db, branch=default_branch, id=ctx.node_id)
        base_value = _conflicting_value(current=None, original=ctx.original_value)
        node.get_attribute(ctx.attribute_name).value = base_value
        await node.save(db=db, user_id=base_user)
        conflicts.cleared_attribute_value_base_value = base_value
        conflicts.cleared_attribute_value_base_user = base_user

    # added_relationship <-> base sets a different peer on the same one-card rel
    for ar in contexts.added_relationships:
        peer_for_rel = overrides.get(ar.relationship_name, conflict_peer_node)
        node = await NodeManager.get_one(db=db, branch=default_branch, id=ar.node_id)
        # Only stage a conflict if the node/rel exists on main and the conflict
        # peer isn't the same as the branch-side peer.
        if peer_for_rel.id == ar.peer_id:
            continue
        await node.get_relationship(ar.relationship_name).update(db=db, data=peer_for_rel.id)
        await node.save(db=db, user_id=base_user)
        conflicts.added_relationship_base_peer_ids[ar.node_id, ar.relationship_name] = peer_for_rel.id
        conflicts.added_relationship_base_user = base_user

    # cleared_relationship <-> base updates the one-card rel to a different peer
    for dr in contexts.deleted_relationships:
        peer_for_rel = overrides.get(dr.relationship_name, conflict_peer_node)
        if peer_for_rel.id == dr.peer_id:
            continue
        node = await NodeManager.get_one(db=db, branch=default_branch, id=dr.node_id)
        assert node is not None, f"deleted_relationship conflict: node {dr.node_id} missing on default_branch"
        await node.get_relationship(dr.relationship_name).update(db=db, data=peer_for_rel.id)
        await node.save(db=db, user_id=base_user)
        conflicts.cleared_relationship_base_peer_ids[dr.node_id, dr.relationship_name] = peer_for_rel.id
        conflicts.cleared_relationship_base_user = base_user

    # updated_attribute_property <-> base sets a different property value.
    # Booleans (is_protected) are skipped — with only two states
    # and "the opposite" being the pre-branch default, the diff coordinator
    # sees no base-side change so no genuine conflict exists.
    for ap in contexts.updated_attribute_properties:
        if ap.property_name not in ("source", "owner"):
            continue
        if conflict_peer_node.id == ap.expected_peer_id:
            continue
        node = await NodeManager.get_one(
            db=db, branch=default_branch, id=ap.node_id, include_metadata=MetadataOptions.LINKED_NODES
        )
        attr = node.get_attribute(ap.attribute_name)
        setattr(attr, ap.property_name, conflict_peer_node)
        conflicts.updated_attribute_property_base[ap.node_id, ap.attribute_name, ap.property_name] = (
            conflict_peer_node.id
        )
        await node.save(db=db, user_id=base_user)
        conflicts.updated_attribute_property_base_user = base_user

    # cleared_attribute_property <-> base sets a different source/owner peer
    for cap in contexts.cleared_attribute_properties:
        node = await NodeManager.get_one(
            db=db, branch=default_branch, id=cap.node_id, include_metadata=MetadataOptions.LINKED_NODES
        )
        attr = node.get_attribute(cap.attribute_name)
        if conflict_peer_node.id == cap.original_peer_id:
            continue
        setattr(attr, cap.property_name, conflict_peer_node)
        await node.save(db=db, user_id=base_user)
        conflicts.cleared_attribute_property_base[cap.node_id, cap.attribute_name, cap.property_name] = (
            conflict_peer_node.id
        )
        conflicts.cleared_attribute_property_base_user = base_user

    # updated_relationship_property <-> base sets a different property value.
    # Booleans are skipped for the same reason as attribute property booleans.
    for rp in contexts.updated_relationship_properties:
        if rp.property_name not in ("source", "owner"):
            continue
        if conflict_peer_node.id == rp.expected_peer_id:
            continue
        node = await NodeManager.get_one(db=db, branch=default_branch, id=rp.node_id)
        data: dict[str, Any] = {"id": rp.peer_id, f"_relation__{rp.property_name}": conflict_peer_node.id}
        conflicts.updated_relationship_property_base[rp.node_id, rp.relationship_name, rp.peer_id, rp.property_name] = (
            conflict_peer_node.id
        )
        await node.get_relationship(rp.relationship_name).update(db=db, data=data)
        await node.save(db=db, user_id=base_user)
        conflicts.updated_relationship_property_base_user = base_user

    # cleared_relationship_property <-> base sets a different source/owner
    for crp in contexts.cleared_relationship_properties:
        node = await NodeManager.get_one(db=db, branch=default_branch, id=crp.node_id)
        if conflict_peer_node.id == crp.original_peer_id:
            continue
        await node.get_relationship(crp.relationship_name).update(
            db=db,
            data={"id": crp.peer_id, f"_relation__{crp.property_name}": conflict_peer_node.id},
        )
        await node.save(db=db, user_id=base_user)
        conflicts.cleared_relationship_property_base[
            crp.node_id, crp.relationship_name, crp.peer_id, crp.property_name
        ] = conflict_peer_node.id
        conflicts.cleared_relationship_property_base_user = base_user

    return conflicts


def _conflicting_value(current: Any, original: Any) -> Any:
    """Pick a value that differs from both ``current`` (branch-side) and ``original``.

    Raises ``ValueError`` for booleans: any value that differs from ``current`` is equal to ``original``
    """
    if isinstance(current, bool) or isinstance(original, bool):
        raise ValueError(
            f"cannot pick a conflicting bool value: current={current!r}, original={original!r}; "
            f"bool has only two states so any 'different' value coincides with one of them"
        )
    if isinstance(current, (int, float)) or isinstance(original, (int, float)):
        base = (current if isinstance(current, (int, float)) else 0) or 0
        return base + 9999
    if isinstance(current, list) or isinstance(original, list):
        return ["conflict-marker"]
    # Default: string marker
    return "#BADBAD"
