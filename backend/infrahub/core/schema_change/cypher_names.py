from infrahub.core.schema_change.enums import SchemaChangeEdgeType, SchemaChangeRecordLabel

CYPHER_NAMES = {
    "schema_change_label": SchemaChangeRecordLabel.SCHEMA_CHANGE.value,
    "operation_label": SchemaChangeRecordLabel.OPERATION.value,
    "application_label": SchemaChangeRecordLabel.APPLICATION.value,
    "migration_label": SchemaChangeRecordLabel.MIGRATION.value,
    "has_operation": SchemaChangeEdgeType.SCHEMA_CHANGE_HAS_OPERATION.value,
    "has_application": SchemaChangeEdgeType.SCHEMA_CHANGE_HAS_APPLICATION.value,
    "has_parent": SchemaChangeEdgeType.SCHEMA_CHANGE_HAS_PARENT.value,
    "has_migration": SchemaChangeEdgeType.SCHEMA_APPLICATION_HAS_MIGRATION.value,
}
"""The labels and edge types that the schema change queries write into their text; none of them comes from user input."""
