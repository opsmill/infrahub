from typing import Any, Dict, Optional, Type

from .node_attribute_add import NodeAttributeAddMigration

MIGRATION_MAP: Dict[str, Optional[Type[Any]]] = {
    "node.branch.update": None,
    "node.attribute.add": NodeAttributeAddMigration,
    "node.attribute.remove": None,
    "node.relationship.remove": None,
    "attribute.kind.update": None,
    "attribute.branch.update": None,
    "relationship.branch.update": None,
    "relationship.direction.update": None,
    "relationship.identifier.update": None,
    "relationship.hierarchical.update": None,
}
