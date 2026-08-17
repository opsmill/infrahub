from infrahub.core.constants import MigrationIdentifier

from .schema.attribute_kind_update import AttributeKindUpdateMigration
from .schema.attribute_name_update import AttributeNameUpdateMigration
from .schema.attribute_supports_generated_schema import AttributeSupportsGeneratedSchemaMigration
from .schema.node_attribute_add import NodeAttributeAddMigration
from .schema.node_attribute_remove import NodeAttributeRemoveMigration
from .schema.node_kind_update import (
    NodeInheritFromUpdateMigration,
    NodeNamespaceUpdateMigration,
    NodeNameUpdateMigration,
)
from .schema.node_remove import NodeRemoveMigration
from .schema.node_uniqueness_constraints_update import NodeUniquenessConstraintsUpdateMigration
from .schema.placeholder_dummy import PlaceholderDummyMigration
from .shared import SchemaMigration

MIGRATION_MAP: dict[str, type[SchemaMigration] | None] = {
    "node.remove": NodeRemoveMigration,
    "node.branch.update": None,
    "node.attribute.add": NodeAttributeAddMigration,
    "node.attribute.remove": NodeAttributeRemoveMigration,
    MigrationIdentifier.NODE_INHERIT_FROM_UPDATE.value: NodeInheritFromUpdateMigration,
    MigrationIdentifier.NODE_NAME_UPDATE.value: NodeNameUpdateMigration,
    MigrationIdentifier.NODE_NAMESPACE_UPDATE.value: NodeNamespaceUpdateMigration,
    "node.relationship.remove": PlaceholderDummyMigration,
    "node.uniqueness_constraints.update": NodeUniquenessConstraintsUpdateMigration,
    "attribute.name.update": AttributeNameUpdateMigration,
    "attribute.branch.update": None,
    "attribute.kind.update": AttributeKindUpdateMigration,
    "attribute.optional.update": AttributeSupportsGeneratedSchemaMigration,
    "attribute.read_only.update": AttributeSupportsGeneratedSchemaMigration,
    "attribute.unique.update": AttributeSupportsGeneratedSchemaMigration,
    "relationship.branch.update": None,
    "relationship.direction.update": None,
    "relationship.identifier.update": None,
    "relationship.hierarchical.update": None,
}
