from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from infrahub.core.schema import AttributePathParsingError, GenericSchema
from infrahub.log import get_logger

LOG = get_logger(__name__)

if TYPE_CHECKING:
    from infrahub.core.schema import MainSchemaTypes
    from infrahub.core.schema.schema_branch import SchemaBranch
    from infrahub.core.validators.node_diff_index import NodeDiffIndex

    from .dependent_resolver import UniquenessDependentResolverInterface


@dataclass
class CrossKindPeerChange:
    """A change to a peer kind that can break the uniqueness of the kind pointing at it.

    Reached from a constraint path such as "owner__name": the peer kind's attribute changed, so the
    nodes of the constrained kind related through ``relationship_identifier`` to those peers must be
    resolved and re-validated. ``changed_peer_uuids`` are uuids of the PEER kind, not the constrained
    kind.
    """

    relationship_identifier: str
    changed_peer_uuids: set[str]


@dataclass
class UniquenessScopeForKind:
    """How a data diff implicates a single kind's uniqueness."""

    # whether any diffed field participates in the kind's uniqueness (if False, no need to validate)
    requires_validation: bool = False
    # uuids of directly-changed nodes of the kind whose changed field participates in its uniqueness
    object_uuids: set[str] = field(default_factory=set)
    # peer-kind changes reached across a relationship, still to be resolved into this kind's nodes
    cross_kind_peer_changes: list[CrossKindPeerChange] = field(default_factory=list)


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
        is implicated when an implementation's copy of the field is what changed in the diff. A
        generic knows its implementing kinds through `used_by`; the diff check then keeps only the
        kinds actually present in the diff.
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

        Uniqueness spans single unique attributes and multi-field constraint groups. A group
        element such as "owner__name" reads an attribute of a related peer, so a data change on
        the peer kind can create a violation without any change to the constrained kind itself:
        that case yields a cross-kind peer change. Directly changed nodes of the constrained kind
        are collected as object uuids.
        """
        scope = UniquenessScopeForKind()
        for attribute_schema in schema.unique_attributes:
            attr_kinds = self._diffed_kinds_with_field(
                schema=schema, field_name=attribute_schema.name, is_relationship=False
            )
            if attr_kinds:
                scope.requires_validation = True
                scope.object_uuids |= self._uuids_for_field(
                    kinds=attr_kinds, field_name=attribute_schema.name, is_relationship=False
                )
        for constraint_group in schema.uniqueness_constraints or []:
            for constraint_path in constraint_group:
                try:
                    schema_path = schema.parse_schema_path(path=constraint_path, schema=self.schema_branch)
                except AttributePathParsingError:
                    LOG.warning(f"Cannot parse {schema.kind}.uniqueness_constraints element '{constraint_path}'")
                    continue
                if schema_path.relationship_schema is not None:
                    rel_kinds = self._diffed_kinds_with_field(
                        schema=schema, field_name=schema_path.relationship_schema.name, is_relationship=True
                    )
                    if rel_kinds:
                        scope.requires_validation = True
                        scope.object_uuids |= self._uuids_for_field(
                            kinds=rel_kinds, field_name=schema_path.relationship_schema.name, is_relationship=True
                        )
                    if schema_path.attribute_schema is not None and schema_path.related_schema is not None:
                        peer_kinds = self._diffed_kinds_with_field(
                            schema=schema_path.related_schema,
                            field_name=schema_path.attribute_schema.name,
                            is_relationship=False,
                        )
                        if peer_kinds:
                            scope.requires_validation = True
                            scope.cross_kind_peer_changes.append(
                                CrossKindPeerChange(
                                    relationship_identifier=schema_path.relationship_schema.get_identifier(),
                                    changed_peer_uuids=self._uuids_for_field(
                                        kinds=peer_kinds,
                                        field_name=schema_path.attribute_schema.name,
                                        is_relationship=False,
                                    ),
                                )
                            )
                elif schema_path.attribute_schema is not None:
                    attr_kinds = self._diffed_kinds_with_field(
                        schema=schema, field_name=schema_path.attribute_schema.name, is_relationship=False
                    )
                    if attr_kinds:
                        scope.requires_validation = True
                        scope.object_uuids |= self._uuids_for_field(
                            kinds=attr_kinds, field_name=schema_path.attribute_schema.name, is_relationship=False
                        )
        return scope
