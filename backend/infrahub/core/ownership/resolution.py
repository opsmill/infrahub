from __future__ import annotations

from typing import TYPE_CHECKING

from .models import NODE_HOLDER, OwnerOrigin, ResolvedOwnership, given_holder

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

    from .models import HolderKey, StoredNodeOwnership


def sort_profiles(profiles: Sequence[tuple[str, int | None]]) -> list[str]:
    """Return the profile IDs in the order of their priority: the lowest number first, then no priority, then by ID."""
    return [profile_id for profile_id, _ in sorted(profiles, key=lambda item: (item[1] is None, item[1] or 0, item[0]))]


def resolve_node_ownership(
    lineage: Sequence[StoredNodeOwnership], profiles: Mapping[str, StoredNodeOwnership]
) -> ResolvedOwnership:
    """Return the owners that apply to a node, from the first level of the lineage that has owners or "no owner".

    Each level looks at its own state, then at its profiles by priority, then at its copy from an object template.

    Args:
        lineage: The node, then each parent above it, the nearest parent first.
        profiles: The stored states of the profiles of the lineage, by profile ID. A profile that is left out gives
            nothing.

    """
    state = lineage[0].get(NODE_HOLDER).state
    for position, node in enumerate(lineage):
        if found := _own_levels(node=node, profiles=profiles):
            origin, origin_node_id, owner_ids = found
            if position:
                origin, origin_node_id = OwnerOrigin.PARENT, node.node_id
            return ResolvedOwnership(state=state, owner_ids=owner_ids, origin=origin, origin_node_id=origin_node_id)
    return ResolvedOwnership(state=state, owner_ids=(), origin=None, origin_node_id=None)


def resolve_field_ownership(
    node: StoredNodeOwnership,
    holder: HolderKey,
    profiles: Mapping[str, StoredNodeOwnership],
    node_ownership: ResolvedOwnership,
) -> ResolvedOwnership:
    """Return the owners that apply to one field of a node.

    The field looks at its own state, then at its profiles by priority, then at its copy from an object template,
    then at the owners that apply to its node.

    Args:
        node: The stored states of the node.
        holder: The holder of the owners of the field.
        profiles: The stored states of the profiles of the node, by profile ID.
        node_ownership: The owners that apply to the node.

    """
    state = node.get(holder).state
    if found := _own_levels(node=node, profiles=profiles, holder=holder):
        origin, origin_node_id, owner_ids = found
        return ResolvedOwnership(state=state, owner_ids=owner_ids, origin=origin, origin_node_id=origin_node_id)
    if node_ownership.origin is None:
        return ResolvedOwnership(state=state, owner_ids=(), origin=None, origin_node_id=None)
    return ResolvedOwnership(
        state=state, owner_ids=node_ownership.owner_ids, origin=OwnerOrigin.OBJECT, origin_node_id=node.node_id
    )


def resolve_target_ownership(node: StoredNodeOwnership, holder: HolderKey = NODE_HOLDER) -> ResolvedOwnership:
    """Return the owners that a profile or an object template gives to a holder of its nodes, as it stores them."""
    given = node.get(given_holder(holder))
    gives = given.owner_ids is not None
    return ResolvedOwnership(
        state=given.state,
        owner_ids=given.owner_ids or (),
        origin=OwnerOrigin.SELF if gives else None,
        origin_node_id=node.node_id if gives else None,
    )


def _own_levels(
    node: StoredNodeOwnership, profiles: Mapping[str, StoredNodeOwnership], holder: HolderKey = NODE_HOLDER
) -> tuple[OwnerOrigin, str, tuple[str, ...]] | None:
    own = node.get(holder)
    if own.owner_ids is not None and own.template_id is None:
        return OwnerOrigin.SELF, node.node_id, own.owner_ids
    for profile_id in sort_profiles(profiles=node.profiles):
        given = profiles[profile_id].get(given_holder(holder)) if profile_id in profiles else None
        if given is not None and given.owner_ids is not None:
            return OwnerOrigin.PROFILE, profile_id, given.owner_ids
    if own.owner_ids is not None and own.template_id is not None:
        return OwnerOrigin.TEMPLATE, own.template_id, own.owner_ids
    return None
