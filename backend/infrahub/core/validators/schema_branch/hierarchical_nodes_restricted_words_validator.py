from __future__ import annotations

from typing import TYPE_CHECKING

from infrahub.core.constants import RESERVED_ATTR_REL_HIERARCHICAL_NAMES
from infrahub.core.schema import (
    GenericSchema,
    MainSchemaTypes,
    NodeSchema,
)
from infrahub.core.schema.constants import INTERNAL_SCHEMA_NODE_KINDS

from .interface import SchemaBranchValidator

if TYPE_CHECKING:
    from infrahub.core.schema.schema_branch import SchemaBranch


class HierarchicalNodesRestrictedWords(SchemaBranchValidator):
    def check(self, schema_branch: SchemaBranch) -> None:
        for name in schema_branch.all_names:
            node = schema_branch.get(name=name, duplicate=False)
            if not node.id:
                self._validate_hierarchical_node_restricted_words(node=node)

    def _validate_hierarchical_node_restricted_words(self, node: MainSchemaTypes) -> None:
        is_hierarchical_node = (isinstance(node, GenericSchema) and node.hierarchical) or (
            isinstance(node, NodeSchema) and node.hierarchy
        )

        if (
            not is_hierarchical_node
            or node.kind in INTERNAL_SCHEMA_NODE_KINDS
            or node.namespace in ("Core", "Builtin", "Lineage", "Internal")
        ):
            return

        for attr in node.attributes:
            if attr.name in RESERVED_ATTR_REL_HIERARCHICAL_NAMES:
                raise ValueError(f"{node.kind}: {attr.name} isn't allowed as an attribute name on hierarchical nodes.")

        for rel in node.relationships:
            if rel.name in RESERVED_ATTR_REL_HIERARCHICAL_NAMES:
                raise ValueError(f"{node.kind}: {rel.name} isn't allowed as a relationship name on hierarchical nodes.")
