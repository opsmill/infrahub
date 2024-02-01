from typing import Any, Dict, Optional, Type

MIGRATION_MAP: Dict[str, Optional[Type[Any]]] = {
    "node.branch.update": None,
    "node.attribute.add": None,
    "node.attribute.remove": None,
    "node.relationship.remove": None,
    "attribute.kind.update": None,
    "attribute.branch.update": None,
    "relationship.branch.update": None,
    "relationship.direction.update": None,
    "relationship.identifier.update": None,
    "relationship.hierarchical.update": None,
}
