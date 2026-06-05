"""Context dataclasses returned by setup helpers and consumed by validators.

Each context captures the identifying information needed to locate the changed
element on the default branch after the merge, plus the expected values and
metadata (actor, timestamp ranges) that validators assert against.

The same context shapes are used across all scenarios (clean merge, conflicts,
migrations). Scenario-specific expectations (e.g. "branch changes were discarded"
or "the node kind was renamed") are applied by the scenario helper that wraps
the default-branch-side setup, and are surfaced through the optional fields on
each context.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Literal

if TYPE_CHECKING:
    from infrahub.core.timestamp import Timestamp


@dataclass
class TimestampRange:
    """Half-open timestamp window used to bracket when a save happened.

    Validators use these to assert `before < actual < after` for timestamps
    that are captured by save() rather than by the merge operation.
    """

    before: Timestamp
    after: Timestamp


@dataclass
class AddedNodeCtx:
    """A new node created on the diff branch (expected to exist on main after merge)."""

    kind: str
    expected_kind: str  # may differ from `kind` if a node-kind migration applies
    attribute_values: dict[str, Any]
    one_relationship_peers: dict[str, str]  # relationship name -> peer id
    many_relationship_peers: dict[str, list[str]]  # relationship name -> list of peer ids
    branch_user: str
    node_id: str = ""  # populated after save()


@dataclass
class DeletedNodeCtx:
    """An existing node deleted on the diff branch."""

    node_id: str
    expected_kind: str
    original_created_at: Timestamp
    original_created_by: str
    branch_user: str
    # peers whose relationships to the deleted node should also be removed
    peer_node_ids: list[str] = field(default_factory=list)
    # Pre-branch metadata of the node. Used by rollback validators to assert the
    # node's metadata was restored to its pre-merge state.
    original_updated_at: Timestamp | None = None
    original_updated_by: str | None = None


@dataclass
class UpdatedAttributeValueCtx:
    """An attribute whose value is set on the diff branch.

    Covers both 'set from previously-null' and 'overwrite existing value'; clearing is
    DeletedAttributeValueCtx.
    """

    node_id: str
    attribute_name: str
    expected_value: Any
    original_value: Any  # pre-branch value; rollback validator uses this
    original_created_at: Timestamp
    original_created_by: str
    branch_user: str
    original_updated_at: Timestamp | None = None
    original_updated_by: str | None = None


@dataclass
class ClearedAttributeValueCtx:
    """An optional attribute whose value is cleared (set to None) on the diff branch."""

    node_id: str
    attribute_name: str
    original_value: Any  # pre-branch value; rollback validator uses this
    original_created_at: Timestamp
    original_created_by: str
    branch_user: str
    original_updated_at: Timestamp | None = None
    original_updated_by: str | None = None


@dataclass
class AddedRelationshipCtx:
    """A new relationship peer added on the diff branch.

    Use for both one-cardinality (previously unset or replacing) and many-cardinality
    (appending a peer) relationships.
    """

    node_id: str
    relationship_name: str
    peer_id: str
    branch_user: str
    # For one-card replacements, the peer that was there before (None if relationship was unset).
    replaced_peer_id: str | None = None


@dataclass
class DeletedRelationshipCtx:
    """An existing relationship peer removed on the diff branch.

    For many-cardinality, `peer_id` is the peer removed.
    For one-cardinality (optional), represents clearing to null.
    """

    node_id: str
    relationship_name: str
    peer_id: str
    branch_user: str
    # Pre-branch metadata of the relationship. Used by rollback validators.
    original_updated_at: Timestamp | None = None
    original_updated_by: str | None = None


@dataclass
class UpdatedAttributePropertyCtx:
    """An attribute property (source, owner, is_protected) set on the diff branch.

    For node/peer-valued properties (source, owner), `expected_peer_id` holds the peer node id.
    For boolean properties (is_protected), `expected_bool` holds the new value.

    ``original_*`` captures the pre-branch value for rollback validation.
    """

    node_id: str
    attribute_name: str
    property_name: Literal["source", "owner", "is_protected"]
    expected_peer_id: str | None = None
    expected_bool: bool | None = None
    original_peer_id: str | None = None  # for source/owner
    original_bool: bool | None = None  # for is_protected
    branch_user: str = ""
    original_updated_at: Timestamp | None = None
    original_updated_by: str | None = None


@dataclass
class ClearedAttributePropertyCtx:
    """An attribute's source/owner was cleared on the diff branch (was previously set)."""

    node_id: str
    attribute_name: str
    property_name: Literal["source", "owner"]
    original_peer_id: str = ""  # pre-branch peer; rollback validator asserts this is restored
    branch_user: str = ""
    original_updated_at: Timestamp | None = None
    original_updated_by: str | None = None


@dataclass
class UpdatedRelationshipPropertyCtx:
    """A relationship property set on the diff branch."""

    node_id: str
    relationship_name: str
    peer_id: str  # which relationship instance (identify by peer)
    property_name: Literal["source", "owner", "is_protected"]
    expected_peer_id: str | None = None
    expected_bool: bool | None = None
    original_peer_id: str | None = None
    original_bool: bool | None = None
    branch_user: str = ""
    original_updated_at: Timestamp | None = None
    original_updated_by: str | None = None


@dataclass
class ClearedRelationshipPropertyCtx:
    """A relationship's source/owner was cleared on the diff branch."""

    node_id: str
    relationship_name: str
    peer_id: str
    property_name: Literal["source", "owner"]
    original_peer_id: str = ""
    branch_user: str = ""
    original_updated_at: Timestamp | None = None
    original_updated_by: str | None = None


@dataclass
class MatrixContexts:
    """Aggregate bag of all change-type contexts produced by a single setup run.

    Matrix tests build one of these, run the merge, then pass it to
    validators.validate_all(...) which iterates each field.
    """

    added_node: AddedNodeCtx | None = None
    deleted_node: DeletedNodeCtx | None = None
    updated_attribute_values: list[UpdatedAttributeValueCtx] = field(default_factory=list)
    cleared_attribute_value: ClearedAttributeValueCtx | None = None
    added_relationships: list[AddedRelationshipCtx] = field(default_factory=list)
    deleted_relationships: list[DeletedRelationshipCtx] = field(default_factory=list)
    updated_attribute_properties: list[UpdatedAttributePropertyCtx] = field(default_factory=list)
    cleared_attribute_properties: list[ClearedAttributePropertyCtx] = field(default_factory=list)
    updated_relationship_properties: list[UpdatedRelationshipPropertyCtx] = field(default_factory=list)
    cleared_relationship_properties: list[ClearedRelationshipPropertyCtx] = field(default_factory=list)
