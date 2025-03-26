from .schema.attribute_name_update import AttributeNameUpdateMigration
from .schema.node_attribute_add import NodeAttributeAddMigration
from .schema.node_attribute_remove import NodeAttributeRemoveMigration
from .schema.node_kind_update import NodeKindUpdateMigration
from .schema.node_remove import NodeRemoveMigration
from .schema.placeholder_dummy import PlaceholderDummyMigration
from .shared import SchemaMigration

MIGRATION_MAP: dict[str, type[SchemaMigration] | None] = {
    "node.remove": NodeRemoveMigration,
    "node.branch.update": None,
    "node.attribute.add": NodeAttributeAddMigration,
    "node.attribute.remove": NodeAttributeRemoveMigration,
    "node.inherit_from.update": NodeKindUpdateMigration,
    "node.name.update": NodeKindUpdateMigration,
    "node.namespace.update": NodeKindUpdateMigration,
    "node.relationship.remove": PlaceholderDummyMigration,
    "attribute.name.update": AttributeNameUpdateMigration,
    "attribute.branch.update": None,
    "relationship.branch.update": None,
    "relationship.direction.update": None,
    "relationship.identifier.update": PlaceholderDummyMigration,
    "relationship.hierarchical.update": None,
}
