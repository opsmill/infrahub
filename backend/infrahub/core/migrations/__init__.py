from typing import Dict, Optional, Type

from .schema.attribute_kind_update import AttributeKindUpdateMigration
from .schema.node_attribute_add import NodeAttributeAddMigration
from .shared import SchemaMigration

MIGRATION_MAP: Dict[str, Optional[Type[SchemaMigration]]] = {
    "node.branch.update": None,
    "node.attribute.add": NodeAttributeAddMigration,
    "node.attribute.remove": None,
    "node.relationship.remove": None,
    "attribute.kind.update": AttributeKindUpdateMigration,
    "attribute.branch.update": None,
    "relationship.branch.update": None,
    "relationship.direction.update": None,
    "relationship.identifier.update": None,
    "relationship.hierarchical.update": None,
}
