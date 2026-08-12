from enum import StrEnum


class MigrationIdentifier(StrEnum):
    """Names under which schema migrations are registered in the migration map."""

    NODE_INHERIT_FROM_UPDATE = "node.inherit_from.update"
    NODE_NAME_UPDATE = "node.name.update"
    NODE_NAMESPACE_UPDATE = "node.namespace.update"
