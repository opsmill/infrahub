from __future__ import annotations

from typing import TYPE_CHECKING

from infrahub.core.schema import GenericSchema
from infrahub.core.validators.enum import ConstraintIdentifier
from infrahub.exceptions import SchemaNotFoundError

if TYPE_CHECKING:
    from infrahub.core.models import SchemaUpdateConstraintInfo
    from infrahub.core.schema import MainSchemaTypes
    from infrahub.core.schema.schema_branch import SchemaBranch

UNIQUENESS_CONSTRAINT_NAME = ConstraintIdentifier.NODE_UNIQUENESS_CONSTRAINTS_UPDATE.value


class UniquenessConstraintDeduplicator:
    """Drop node-level uniqueness checks already covered by an implicated generic.

    A generic's uniqueness query spans every implementing node, so when a generic and one of its
    implementations are both slated to validate uniqueness, the implementation's check is redundant.
    It is dropped only when the generic covers every one of the node's constraint groups and its
    validation scope covers the node's, so neither a node-specific group nor a broader
    (full-population) check is ever lost.
    """

    def __init__(self, schema_branch: SchemaBranch) -> None:
        self.schema_branch = schema_branch

    def deduplicate(self, constraints: list[SchemaUpdateConstraintInfo]) -> list[SchemaUpdateConstraintInfo]:
        uniqueness_infos = {
            constraint.path.schema_kind: constraint
            for constraint in constraints
            if constraint.constraint_name == UNIQUENESS_CONSTRAINT_NAME
        }
        # a node can only be redundant against a generic, so there is nothing to collapse below two
        if len(uniqueness_infos) < 2:
            return list(constraints)

        redundant_kinds = {
            kind
            for kind, info in uniqueness_infos.items()
            if self._is_covered_by_generic(kind=kind, info=info, uniqueness_infos=uniqueness_infos)
        }
        if not redundant_kinds:
            return list(constraints)

        return [
            constraint
            for constraint in constraints
            if constraint.constraint_name != UNIQUENESS_CONSTRAINT_NAME
            or constraint.path.schema_kind not in redundant_kinds
        ]

    def _is_covered_by_generic(
        self, kind: str, info: SchemaUpdateConstraintInfo, uniqueness_infos: dict[str, SchemaUpdateConstraintInfo]
    ) -> bool:
        schema = self._get_schema_or_none(kind=kind)
        if schema is None or isinstance(schema, GenericSchema):
            # a generic is the coverer, never the covered
            return False
        node_groups = self._constraint_groups(schema)
        if not node_groups:
            return False

        covered_groups: set[frozenset[str]] = set()
        for generic_kind in schema.inherit_from or []:
            generic_info = uniqueness_infos.get(generic_kind)
            if generic_info is None:
                continue
            if not self._scope_covers(node_info=info, generic_info=generic_info):
                continue
            generic_schema = self._get_schema_or_none(kind=generic_kind)
            if generic_schema is None:
                continue
            covered_groups |= self._constraint_groups(generic_schema)
        return node_groups <= covered_groups

    def _scope_covers(self, node_info: SchemaUpdateConstraintInfo, generic_info: SchemaUpdateConstraintInfo) -> bool:
        """Return True if the generic's validation scope covers the node's.

        A full-population generic covers everything. A scoped generic cannot stand in for a
        full-population node (that would silently narrow the check), and otherwise must validate a
        superset of the node's nodes.
        """
        if generic_info.node_uuids is None:
            return True
        if node_info.node_uuids is None:
            return False
        return set(generic_info.node_uuids) >= set(node_info.node_uuids)

    def _constraint_groups(self, schema: MainSchemaTypes) -> set[frozenset[str]]:
        return {frozenset(group) for group in schema.uniqueness_constraints or []}

    def _get_schema_or_none(self, kind: str) -> MainSchemaTypes | None:
        try:
            return self.schema_branch.get(name=kind, duplicate=False)
        except SchemaNotFoundError:
            return None
