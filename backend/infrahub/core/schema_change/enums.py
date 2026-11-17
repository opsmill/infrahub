from infrahub.utils import InfrahubStringEnum


class SchemaChangeStatus(InfrahubStringEnum):
    STAGED = "staged"
    RUNNING = "running"
    APPLIED = "applied"
    FAILED = "failed"


class SchemaChangeApplicationStatus(InfrahubStringEnum):
    RUNNING = "running"
    APPLIED = "applied"
    FAILED = "failed"
    ROLLED_BACK = "rolled_back"
    SKIPPED = "skipped"


class SchemaChangeMigrationStatus(InfrahubStringEnum):
    WAITING = "waiting"
    RUNNING = "running"
    APPLIED = "applied"
    FAILED = "failed"
    ROLLED_BACK = "rolled_back"


class SchemaOperationType(InfrahubStringEnum):
    NODE_ADD = "node_add"
    NODE_REMOVE = "node_remove"
    NODE_PROPERTY = "node_property"
    ELEMENT_ADD = "element_add"
    ELEMENT_REMOVE = "element_remove"
    ELEMENT_PROPERTY = "element_property"


class SchemaOperationNodeType(InfrahubStringEnum):
    NODE = "node"
    GENERIC = "generic"


class SchemaOperationSection(InfrahubStringEnum):
    ATTRIBUTES = "attributes"
    RELATIONSHIPS = "relationships"


class SchemaChangeEdgeType(InfrahubStringEnum):
    """Kept out of the graph's edge types because the branch data deletion iterates over that set."""

    SCHEMA_CHANGE_HAS_OPERATION = "SCHEMA_CHANGE_HAS_OPERATION"
    SCHEMA_CHANGE_HAS_APPLICATION = "SCHEMA_CHANGE_HAS_APPLICATION"
    SCHEMA_CHANGE_HAS_PARENT = "SCHEMA_CHANGE_HAS_PARENT"
    SCHEMA_APPLICATION_HAS_MIGRATION = "SCHEMA_APPLICATION_HAS_MIGRATION"
