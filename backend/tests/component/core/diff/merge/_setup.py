"""Setup helpers that perform one specific kind of change on the diff branch.

Each helper:
- Performs the branch-side mutation (save/delete).
- Returns a context dataclass describing the change so validators can assert it.

The helpers accept the diff branch explicitly; they do not know about scenarios.
Scenario-specific actions (e.g. creating a conflicting change on the base
branch, or running a node-kind migration) are layered on by the test itself.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from infrahub.core.constants import MetadataOptions
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node

from ._contexts import (
    AddedNodeCtx,
    AddedRelationshipCtx,
    ClearedAttributePropertyCtx,
    ClearedAttributeValueCtx,
    ClearedRelationshipPropertyCtx,
    DeletedNodeCtx,
    DeletedRelationshipCtx,
    UpdatedAttributePropertyCtx,
    UpdatedAttributeValueCtx,
    UpdatedRelationshipPropertyCtx,
)

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.database import InfrahubDatabase


async def setup_added_node(
    db: InfrahubDatabase,
    branch: Branch,
    *,
    kind: str,
    attribute_values: dict[str, Any],
    one_relationship_peers: dict[str, str] | None = None,
    many_relationship_peers: dict[str, list[str]] | None = None,
    branch_user: str,
    expected_kind: str | None = None,
) -> AddedNodeCtx:
    one_rel = one_relationship_peers or {}
    many_rel = many_relationship_peers or {}
    kwargs: dict[str, Any] = {**attribute_values, **one_rel}
    kwargs.update(dict(many_rel.items()))

    node = await Node.init(db=db, schema=kind, branch=branch)
    await node.new(db=db, **kwargs)
    await node.save(db=db, user_id=branch_user)

    return AddedNodeCtx(
        kind=kind,
        expected_kind=expected_kind or kind,
        attribute_values=attribute_values,
        one_relationship_peers=one_rel,
        many_relationship_peers=many_rel,
        branch_user=branch_user,
        node_id=node.id,
    )


async def setup_deleted_node(
    db: InfrahubDatabase,
    branch: Branch,
    *,
    node_to_delete: Node,
    branch_user: str,
    peer_node_ids: list[str] | None = None,
    expected_kind: str | None = None,
) -> DeletedNodeCtx:
    main_node = await NodeManager.get_one(db=db, id=node_to_delete.id, include_metadata=MetadataOptions.USER_TIMESTAMPS)
    branch_node = await NodeManager.get_one(db=db, branch=branch, id=node_to_delete.id)
    await branch_node.delete(db=db, user_id=branch_user)
    return DeletedNodeCtx(
        node_id=node_to_delete.id,
        expected_kind=expected_kind or node_to_delete.get_kind(),
        original_created_at=node_to_delete._get_created_at(),
        original_created_by=node_to_delete._get_created_by(),
        branch_user=branch_user,
        peer_node_ids=peer_node_ids or [],
        original_updated_at=main_node._get_updated_at(),
        original_updated_by=main_node._get_updated_by(),
    )


async def setup_updated_attribute_value(
    db: InfrahubDatabase,
    branch: Branch,
    *,
    node_on_main: Node,
    attribute_name: str,
    new_value: Any,
    branch_user: str,
) -> UpdatedAttributeValueCtx:
    main_node = await NodeManager.get_one(db=db, id=node_on_main.id, include_metadata=MetadataOptions.USER_TIMESTAMPS)
    main_attr = main_node.get_attribute(attribute_name)
    original_value = main_attr.value

    branch_node = await NodeManager.get_one(db=db, branch=branch, id=node_on_main.id)
    branch_node.get_attribute(attribute_name).value = new_value
    await branch_node.save(db=db, user_id=branch_user)
    return UpdatedAttributeValueCtx(
        node_id=node_on_main.id,
        attribute_name=attribute_name,
        expected_value=new_value,
        original_value=original_value,
        original_created_at=node_on_main._get_created_at(),
        original_created_by=node_on_main._get_created_by(),
        branch_user=branch_user,
        original_updated_at=main_attr._get_updated_at(),
        original_updated_by=main_attr._get_updated_by(),
    )


async def setup_cleared_attribute_value(
    db: InfrahubDatabase,
    branch: Branch,
    *,
    node_on_main: Node,
    attribute_name: str,
    branch_user: str,
) -> ClearedAttributeValueCtx:
    main_node = await NodeManager.get_one(db=db, id=node_on_main.id, include_metadata=MetadataOptions.USER_TIMESTAMPS)
    main_attr = main_node.get_attribute(attribute_name)
    original_value = main_attr.value

    branch_node = await NodeManager.get_one(db=db, branch=branch, id=node_on_main.id)
    branch_node.get_attribute(attribute_name).value = None
    await branch_node.save(db=db, user_id=branch_user)
    return ClearedAttributeValueCtx(
        node_id=node_on_main.id,
        attribute_name=attribute_name,
        original_value=original_value,
        original_created_at=node_on_main._get_created_at(),
        original_created_by=node_on_main._get_created_by(),
        branch_user=branch_user,
        original_updated_at=main_attr._get_updated_at(),
        original_updated_by=main_attr._get_updated_by(),
    )


async def setup_added_one_relationship(
    db: InfrahubDatabase,
    branch: Branch,
    *,
    node_on_main: Node,
    relationship_name: str,
    new_peer_id: str,
    branch_user: str,
) -> AddedRelationshipCtx:
    """Set a one-cardinality relationship (from previously unset, or replacing an existing peer)."""
    branch_node = await NodeManager.get_one(db=db, branch=branch, id=node_on_main.id)
    await branch_node.get_relationship(relationship_name).update(db=db, data=new_peer_id)
    await branch_node.save(db=db, user_id=branch_user)
    return AddedRelationshipCtx(
        node_id=node_on_main.id,
        relationship_name=relationship_name,
        peer_id=new_peer_id,
        branch_user=branch_user,
    )


async def setup_added_many_relationship_peer(
    db: InfrahubDatabase,
    branch: Branch,
    *,
    node_on_main: Node,
    relationship_name: str,
    peer_id_to_add: str,
    existing_peer_ids: list[str],
    branch_user: str,
) -> AddedRelationshipCtx:
    """Append a peer to a many-cardinality relationship."""
    branch_node = await NodeManager.get_one(db=db, branch=branch, id=node_on_main.id)
    await branch_node.get_relationship(relationship_name).update(db=db, data=[*existing_peer_ids, peer_id_to_add])
    await branch_node.save(db=db, user_id=branch_user)
    return AddedRelationshipCtx(
        node_id=node_on_main.id,
        relationship_name=relationship_name,
        peer_id=peer_id_to_add,
        branch_user=branch_user,
    )


async def setup_cleared_one_relationship(
    db: InfrahubDatabase,
    branch: Branch,
    *,
    node_on_main: Node,
    relationship_name: str,
    existing_peer_id: str,
    branch_user: str,
) -> DeletedRelationshipCtx:
    """Clear an optional one-cardinality relationship (set to None)."""
    original_updated_at, original_updated_by = await _fetch_rel_timestamps(
        db=db, node_id=node_on_main.id, relationship_name=relationship_name, peer_id=existing_peer_id
    )
    branch_node = await NodeManager.get_one(db=db, branch=branch, id=node_on_main.id)
    await branch_node.get_relationship(relationship_name).update(db=db, data=None)
    await branch_node.save(db=db, user_id=branch_user)
    return DeletedRelationshipCtx(
        node_id=node_on_main.id,
        relationship_name=relationship_name,
        peer_id=existing_peer_id,
        branch_user=branch_user,
        original_updated_at=original_updated_at,
        original_updated_by=original_updated_by,
    )


async def setup_removed_many_relationship_peer(
    db: InfrahubDatabase,
    branch: Branch,
    *,
    node_on_main: Node,
    relationship_name: str,
    peer_id_to_remove: str,
    remaining_peer_ids: list[str],
    branch_user: str,
) -> DeletedRelationshipCtx:
    original_updated_at, original_updated_by = await _fetch_rel_timestamps(
        db=db, node_id=node_on_main.id, relationship_name=relationship_name, peer_id=peer_id_to_remove
    )
    branch_node = await NodeManager.get_one(db=db, branch=branch, id=node_on_main.id)
    await branch_node.get_relationship(relationship_name).update(db=db, data=remaining_peer_ids)
    await branch_node.save(db=db, user_id=branch_user)
    return DeletedRelationshipCtx(
        node_id=node_on_main.id,
        relationship_name=relationship_name,
        peer_id=peer_id_to_remove,
        branch_user=branch_user,
        original_updated_at=original_updated_at,
        original_updated_by=original_updated_by,
    )


async def _fetch_rel_timestamps(
    *, db: InfrahubDatabase, node_id: str, relationship_name: str, peer_id: str
) -> tuple[Any, Any]:
    """Return (updated_at, updated_by) for a single relationship peer on main.

    Uses ``prefetch_relationships=True`` + USER_TIMESTAMPS to populate timestamp
    fields on Relationship objects.
    """
    main_node = await NodeManager.get_one(
        db=db,
        id=node_id,
        include_metadata=MetadataOptions.USER_TIMESTAMPS,
        prefetch_relationships=True,
    )
    peers = await main_node.get_relationship(relationship_name).get_relationships(db=db)
    matched = next((p for p in peers if p.peer_id == peer_id), None)
    if matched is None:
        return None, None
    return matched._get_updated_at(), matched._get_updated_by()


async def setup_updated_attribute_property(
    db: InfrahubDatabase,
    branch: Branch,
    *,
    node_on_main: Node,
    attribute_name: str,
    property_name: str,
    peer_node: Node | None = None,
    bool_value: bool | None = None,
    branch_user: str,
) -> UpdatedAttributePropertyCtx:
    # Capture original property value from a fresh read of the main-branch node.
    # Source/owner need LINKED_NODES and attribute timestamps need USER_TIMESTAMPS.
    main_node = await NodeManager.get_one(
        db=db,
        id=node_on_main.id,
        include_metadata=MetadataOptions.LINKED_NODES | MetadataOptions.USER_TIMESTAMPS,
    )
    main_attr = main_node.get_attribute(attribute_name)
    original_peer_id = (
        main_attr.source_id if property_name == "source" else (main_attr.owner_id if property_name == "owner" else None)
    )
    original_bool = main_attr.is_protected if property_name == "is_protected" else None

    branch_node = await NodeManager.get_one(db=db, branch=branch, id=node_on_main.id)
    attr = branch_node.get_attribute(attribute_name)
    if property_name in ("source", "owner"):
        assert peer_node is not None
        setattr(attr, property_name, peer_node)
    elif property_name == "is_protected":
        assert bool_value is not None
        setattr(attr, property_name, bool_value)
    else:
        raise ValueError(f"Unknown property: {property_name}")
    await branch_node.save(db=db, user_id=branch_user)
    return UpdatedAttributePropertyCtx(
        node_id=node_on_main.id,
        attribute_name=attribute_name,
        property_name=property_name,
        expected_peer_id=peer_node.id if peer_node else None,
        expected_bool=bool_value,
        original_peer_id=original_peer_id,
        original_bool=original_bool,
        branch_user=branch_user,
        original_updated_at=main_attr._get_updated_at(),
        original_updated_by=main_attr._get_updated_by(),
    )


async def setup_cleared_attribute_property(
    db: InfrahubDatabase,
    branch: Branch,
    *,
    node_on_main: Node,
    attribute_name: str,
    property_name: str,
    branch_user: str,
) -> ClearedAttributePropertyCtx:
    main_node = await NodeManager.get_one(
        db=db,
        id=node_on_main.id,
        include_metadata=MetadataOptions.LINKED_NODES | MetadataOptions.USER_TIMESTAMPS,
    )
    main_attr = main_node.get_attribute(attribute_name)
    original_peer_id = main_attr.source_id if property_name == "source" else main_attr.owner_id
    assert original_peer_id, f"cleared_attribute_property expects {attribute_name}.{property_name} to be set on main"

    branch_node = await NodeManager.get_one(db=db, branch=branch, id=node_on_main.id)
    attr = branch_node.get_attribute(attribute_name)
    if property_name == "source":
        attr.clear_source()
    elif property_name == "owner":
        attr.clear_owner()
    else:
        raise ValueError(f"Cannot clear property {property_name}; only source/owner supported")
    await branch_node.save(db=db, user_id=branch_user)
    return ClearedAttributePropertyCtx(
        node_id=node_on_main.id,
        attribute_name=attribute_name,
        property_name=property_name,
        original_peer_id=original_peer_id,
        branch_user=branch_user,
        original_updated_at=main_attr._get_updated_at(),
        original_updated_by=main_attr._get_updated_by(),
    )


async def setup_updated_relationship_property(
    db: InfrahubDatabase,
    branch: Branch,
    *,
    node_on_main: Node,
    relationship_name: str,
    peer_id: str,
    property_name: str,
    property_peer_node: Node | None = None,
    bool_value: bool | None = None,
    branch_user: str,
) -> UpdatedRelationshipPropertyCtx:
    # Capture original property + timestamps from a fresh read of the main-branch relationship.
    original_peer_id: str | None = None
    original_bool: bool | None = None
    main_node = await NodeManager.get_one(
        db=db,
        id=node_on_main.id,
        include_metadata=MetadataOptions.USER_TIMESTAMPS,
        prefetch_relationships=True,
    )
    main_rel = next(
        (
            r
            for r in await main_node.get_relationship(relationship_name).get_relationships(db=db)
            if r.peer_id == peer_id
        ),
        None,
    )
    assert main_rel is not None
    original_updated_at = main_rel._get_updated_at()
    original_updated_by = main_rel._get_updated_by()
    if property_name in ("source", "owner"):
        # prefetch_relationships=True drops peer-valued properties; re-fetch without prefetch.
        main_node_peers = await NodeManager.get_one(db=db, id=node_on_main.id)
        main_rel_peers = next(
            (
                r
                for r in await main_node_peers.get_relationship(relationship_name).get_relationships(db=db)
                if r.peer_id == peer_id
            ),
            None,
        )
        assert main_rel_peers is not None
        original_peer_id = main_rel_peers.source_id if property_name == "source" else main_rel_peers.owner_id
    elif property_name == "is_protected":
        original_bool = main_rel.is_protected

    branch_node = await NodeManager.get_one(db=db, branch=branch, id=node_on_main.id)
    data: dict[str, Any] = {"id": peer_id}
    if property_name in ("source", "owner"):
        assert property_peer_node is not None
        data[f"_relation__{property_name}"] = property_peer_node.id
    elif property_name == "is_protected":
        assert bool_value is not None
        data[f"_relation__{property_name}"] = bool_value
    else:
        raise ValueError(f"Unknown property: {property_name}")
    await branch_node.get_relationship(relationship_name).update(db=db, data=data)
    await branch_node.save(db=db, user_id=branch_user)
    return UpdatedRelationshipPropertyCtx(
        node_id=node_on_main.id,
        relationship_name=relationship_name,
        peer_id=peer_id,
        property_name=property_name,
        expected_peer_id=property_peer_node.id if property_peer_node else None,
        expected_bool=bool_value,
        original_peer_id=original_peer_id,
        original_bool=original_bool,
        branch_user=branch_user,
        original_updated_at=original_updated_at,
        original_updated_by=original_updated_by,
    )


async def setup_cleared_relationship_property(
    db: InfrahubDatabase,
    branch: Branch,
    *,
    node_on_main: Node,
    relationship_name: str,
    peer_id: str,
    property_name: str,
    branch_user: str,
) -> ClearedRelationshipPropertyCtx:
    """Clear a source/owner on an existing relationship.

    Calls ``clear_source()`` / ``clear_owner()`` on the Relationship instance
    rather than ``.update(data={...: None})`` because the latter is a no-op
    for property clearing.
    """
    if property_name not in ("source", "owner"):
        raise ValueError(f"Cannot clear property {property_name}; only source/owner supported")

    # prefetch_relationships=True for timestamps; drops peer-valued props so we re-fetch for source/owner below.
    main_node_ts = await NodeManager.get_one(
        db=db,
        id=node_on_main.id,
        include_metadata=MetadataOptions.USER_TIMESTAMPS,
        prefetch_relationships=True,
    )
    main_rel_ts = next(
        (
            r
            for r in await main_node_ts.get_relationship(relationship_name).get_relationships(db=db)
            if r.peer_id == peer_id
        ),
        None,
    )
    assert main_rel_ts is not None
    original_updated_at = main_rel_ts._get_updated_at()
    original_updated_by = main_rel_ts._get_updated_by()

    main_node = await NodeManager.get_one(db=db, id=node_on_main.id)
    main_rels = await main_node.get_relationship(relationship_name).get_relationships(db=db)
    main_rel = next((r for r in main_rels if r.peer_id == peer_id), None)
    assert main_rel is not None
    original_peer_id = main_rel.source_id if property_name == "source" else main_rel.owner_id
    assert original_peer_id, (
        f"cleared_relationship_property expects {relationship_name}[{peer_id}].{property_name} to be set on main"
    )

    branch_node = await NodeManager.get_one(db=db, branch=branch, id=node_on_main.id)
    rels = await branch_node.get_relationship(relationship_name).get_relationships(db=db)
    matched = [r for r in rels if r.peer_id == peer_id]
    assert len(matched) == 1, f"expected {relationship_name} peer {peer_id}, got {len(matched)}"
    if property_name == "source":
        matched[0].clear_source()
    else:
        matched[0].clear_owner()
    await branch_node.save(db=db, user_id=branch_user)
    return ClearedRelationshipPropertyCtx(
        node_id=node_on_main.id,
        relationship_name=relationship_name,
        peer_id=peer_id,
        property_name=property_name,
        original_peer_id=original_peer_id,
        branch_user=branch_user,
        original_updated_at=original_updated_at,
        original_updated_by=original_updated_by,
    )
