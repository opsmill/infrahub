from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from infrahub.core.schema import AttributePathParsingError, GenericSchema
from infrahub.log import get_logger

LOG = get_logger(__name__)

if TYPE_CHECKING:
    from infrahub.core.schema import AttributeSchema, MainSchemaTypes, RelationshipSchema
    from infrahub.core.schema.basenode_schema import SchemaAttributePath
    from infrahub.core.schema.schema_branch import SchemaBranch
    from infrahub.core.validators.node_diff_index import NodeDiffIndex

    from .dependent_resolver import UniquenessDependentResolverInterface


@dataclass(frozen=True)
class CrossKindPeerChange:
    """A change to a peer kind that can break the uniqueness of the kind pointing at it.

    Reached from a constraint path such as "owner__name": the peer kind's attribute changed, so the
    nodes of the constrained kind related through ``relationship_identifier`` to those peers must be
    resolved and re-validated. ``changed_peer_uuids`` are uuids of the PEER kind, not the constrained
    kind.
    """

    relationship_identifier: str
    changed_peer_uuids: frozenset[str]


@dataclass(frozen=True)
class UniquenessScopeFragment:
    """How a data diff implicates one element of a kind's uniqueness.

    A fragment is produced only for an element the diff actually touches, so the existence of a
    fragment is what makes validation necessary — both payloads can be empty when the element
    changed but the nodes behind the change are unknown.
    """

    # uuids of directly-changed nodes of the constrained kind
    object_uuids: frozenset[str] = frozenset()
    # peer-kind changes reached across a relationship, still to be resolved into the constrained kind
    cross_kind_peer_changes: tuple[CrossKindPeerChange, ...] = ()


@dataclass(frozen=True)
class UniquenessScopeForKind:
    """How a data diff implicates a single kind's uniqueness."""

    # whether any diffed field participates in the kind's uniqueness (if False, no need to validate)
    requires_validation: bool = False
    # uuids of directly-changed nodes of the kind whose changed field participates in its uniqueness
    object_uuids: frozenset[str] = frozenset()
    # peer-kind changes reached across a relationship, still to be resolved into this kind's nodes
    cross_kind_peer_changes: tuple[CrossKindPeerChange, ...] = ()


class UniquenessConstraintScoper:
    """Identify which nodes a data change can make violate a kind's uniqueness.

    Directly changed nodes of the constrained kind are collected from the diff; when a constraint
    reads a peer's attribute (e.g. "owner__name") the changed peers are handed to the dependent
    resolver to find the constrained nodes pointing at them. The affected set is returned, or None
    when validation must fall back to the full population because the affected nodes cannot be
    identified.
    """

    def __init__(
        self,
        schema_branch: SchemaBranch,
        dependent_resolver: UniquenessDependentResolverInterface,
        node_diff_index: NodeDiffIndex,
    ) -> None:
        self.schema_branch = schema_branch
        self.dependent_resolver = dependent_resolver
        self.node_diff_index = node_diff_index
        # scopes are recomputed for the same kind across the trigger check and the uuid resolution;
        # the cache is valid only for the node-diff index's current contents
        self._scope_cache: dict[str, UniquenessScopeForKind] = {}

    def reset(self) -> None:
        """Drop cached scopes so the next lookup recomputes against the current node-diff index."""
        self._scope_cache = {}

    def requires_validation(self, schema: MainSchemaTypes) -> bool:
        return self._scope(schema=schema).requires_validation

    async def affected_node_uuids(self, schema: MainSchemaTypes) -> list[str] | None:
        scope = self._scope(schema=schema)
        node_uuids = set(scope.object_uuids)
        for peer_change in scope.cross_kind_peer_changes:
            if not peer_change.changed_peer_uuids:
                # the changed peers are not identified, so the constrained nodes cannot be either
                return None
            node_uuids |= await self.dependent_resolver.resolve(
                node_kind=schema.kind,
                relationship_identifier=peer_change.relationship_identifier,
                peer_uuids=sorted(peer_change.changed_peer_uuids),
            )
        if not node_uuids:
            return None
        return sorted(node_uuids)

    def _diffed_kinds_with_field(self, schema: MainSchemaTypes, field_name: str, is_relationship: bool) -> set[str]:
        """Return the diffed kinds where `field_name` changed, on `schema` or a kind that inherits it.

        An inherited field keeps its name on the implementing kind, so a generic-level constraint
        is implicated when an implementation's copy of the field is what changed in the diff.
        """
        kinds = {schema.kind}
        if isinstance(schema, GenericSchema):
            kinds.update(schema.used_by)
        check = (
            self.node_diff_index.has_relationship_diff if is_relationship else self.node_diff_index.has_attribute_diff
        )
        return {kind for kind in kinds if check(kind=kind, name=field_name)}

    def _uuids_for_field(self, kinds: set[str], field_name: str, is_relationship: bool) -> set[str]:
        """UUIDs of the nodes that changed `field_name`, across the given kinds.

        Scoped to the specific field, so an unrelated change to another field of the same node's
        kind does not pull that node into the uniqueness scope.
        """
        uuids: set[str] = set()
        for kind in kinds:
            if is_relationship:
                uuids |= self.node_diff_index.get_uuids_for_relationship(kind=kind, name=field_name)
            else:
                uuids |= self.node_diff_index.get_uuids_for_attribute(kind=kind, name=field_name)
        return uuids

    def _scope(self, schema: MainSchemaTypes) -> UniquenessScopeForKind:
        cached = self._scope_cache.get(schema.kind)
        if cached is None:
            cached = self._compute_scope(schema=schema)
            self._scope_cache[schema.kind] = cached
        return cached

    def _compute_scope(self, schema: MainSchemaTypes) -> UniquenessScopeForKind:
        """Compute why and how a data change implicates `schema`'s uniqueness.

        Uniqueness spans single unique attributes and multi-field constraint groups, each element of
        which is scoped on its own. Validation is required as soon as one element is implicated, even
        when no node behind it could be identified.
        """
        fragments = [
            *self._unique_attribute_fragments(schema=schema),
            *self._uniqueness_constraint_fragments(schema=schema),
        ]
        return UniquenessScopeForKind(
            requires_validation=bool(fragments),
            object_uuids=frozenset(uuid for fragment in fragments for uuid in fragment.object_uuids),
            cross_kind_peer_changes=tuple(
                peer_change for fragment in fragments for peer_change in fragment.cross_kind_peer_changes
            ),
        )

    def _unique_attribute_fragments(self, schema: MainSchemaTypes) -> list[UniquenessScopeFragment]:
        fragments = (
            self._direct_change_fragment(schema=schema, field_name=attribute_schema.name, is_relationship=False)
            for attribute_schema in schema.unique_attributes
        )
        return [fragment for fragment in fragments if fragment is not None]

    def _uniqueness_constraint_fragments(self, schema: MainSchemaTypes) -> list[UniquenessScopeFragment]:
        fragments: list[UniquenessScopeFragment] = []
        for constraint_group in schema.uniqueness_constraints or []:
            for constraint_path in constraint_group:
                try:
                    schema_path = schema.parse_schema_path(path=constraint_path, schema=self.schema_branch)
                except AttributePathParsingError:
                    LOG.warning(f"Cannot parse {schema.kind}.uniqueness_constraints element '{constraint_path}'")
                    continue
                fragments.extend(self._constraint_path_fragments(schema=schema, schema_path=schema_path))
        return fragments

    def _constraint_path_fragments(
        self, schema: MainSchemaTypes, schema_path: SchemaAttributePath
    ) -> list[UniquenessScopeFragment]:
        """Scope one element of a uniqueness constraint group.

        An element such as "owner__name" reads an attribute of a related peer, so it is implicated
        both by a change to the relationship on the constrained kind and by a change to the peer's
        attribute — the latter creating a violation without any change to the constrained kind.
        """
        fragments: list[UniquenessScopeFragment | None] = []
        if schema_path.relationship_schema is None:
            if schema_path.attribute_schema is not None:
                fragments.append(
                    self._direct_change_fragment(
                        schema=schema, field_name=schema_path.attribute_schema.name, is_relationship=False
                    )
                )
        else:
            fragments.append(
                self._direct_change_fragment(
                    schema=schema, field_name=schema_path.relationship_schema.name, is_relationship=True
                )
            )
            if schema_path.attribute_schema is not None and schema_path.related_schema is not None:
                fragments.append(
                    self._peer_change_fragment(
                        relationship_schema=schema_path.relationship_schema,
                        related_schema=schema_path.related_schema,
                        attribute_schema=schema_path.attribute_schema,
                    )
                )
        return [fragment for fragment in fragments if fragment is not None]

    def _direct_change_fragment(
        self, schema: MainSchemaTypes, field_name: str, is_relationship: bool
    ) -> UniquenessScopeFragment | None:
        """Scope a uniqueness field carried by the constrained kind itself, None if it did not change."""
        kinds = self._diffed_kinds_with_field(schema=schema, field_name=field_name, is_relationship=is_relationship)
        if not kinds:
            return None
        return UniquenessScopeFragment(
            object_uuids=frozenset(
                self._uuids_for_field(kinds=kinds, field_name=field_name, is_relationship=is_relationship)
            )
        )

    def _peer_change_fragment(
        self,
        relationship_schema: RelationshipSchema,
        related_schema: MainSchemaTypes,
        attribute_schema: AttributeSchema,
    ) -> UniquenessScopeFragment | None:
        """Scope the peer attribute a constraint element reads, None if the peers did not change."""
        peer_kinds = self._diffed_kinds_with_field(
            schema=related_schema, field_name=attribute_schema.name, is_relationship=False
        )
        if not peer_kinds:
            return None
        return UniquenessScopeFragment(
            cross_kind_peer_changes=(
                CrossKindPeerChange(
                    relationship_identifier=relationship_schema.get_identifier(),
                    changed_peer_uuids=frozenset(
                        self._uuids_for_field(kinds=peer_kinds, field_name=attribute_schema.name, is_relationship=False)
                    ),
                ),
            )
        )
