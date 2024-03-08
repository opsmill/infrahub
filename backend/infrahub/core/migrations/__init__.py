from typing import Dict, Optional, Type

from .schema.attribute_name_update import AttributeNameUpdateMigration
from .schema.node_attribute_add import NodeAttributeAddMigration
from .schema.node_attribute_remove import NodeAttributeRemoveMigration
from .schema.node_kind_update import NodeKindUpdateMigration
from .shared import SchemaMigration

MIGRATION_MAP: Dict[str, Optional[Type[SchemaMigration]]] = {
    "node.branch.update": None,
    "node.attribute.add": NodeAttributeAddMigration,
    "node.attribute.remove": NodeAttributeRemoveMigration,
    "node.name.update": NodeKindUpdateMigration,
    "node.namespace.update": NodeKindUpdateMigration,
    "node.relationship.remove": None,
    "attribute.name.update": AttributeNameUpdateMigration,
    "attribute.branch.update": None,
    "relationship.branch.update": None,
    "relationship.direction.update": None,
    "relationship.identifier.update": None,
    "relationship.hierarchical.update": None,
}
