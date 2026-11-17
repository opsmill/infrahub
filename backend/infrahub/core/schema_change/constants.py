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


SCHEMA_OPERATION_FORMAT_VERSION = 1
SCHEMA_CHANGE_NAME_VERSION_DIGITS = 5

SCHEMA_KIND_NAME_PROPERTIES = ("name", "namespace")
"""The properties of a kind that form its kind name, in the order their operations come."""

SCHEMA_ELEMENT_NAME_PROPERTY = "name"
SCHEMA_PROPERTY_PATH_SEPARATOR = "."

SCHEMA_CHANGE_HISTORY_DEFAULT_LIMIT = 10
SCHEMA_CHANGE_HISTORY_MAX_LIMIT = 50
SCHEMA_CHANGE_OPERATIONS_DEFAULT_LIMIT = 50
SCHEMA_CHANGE_OPERATIONS_MAX_LIMIT = 500
