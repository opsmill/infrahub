from infrahub.utils import InfrahubStringEnum


class MigrationPhase(InfrahubStringEnum):
    """The phases of the migrations of one schema application, defined in the order they run.

    Order phases by their position in this enum, never by their values, which sort alphabetically.
    """

    KIND_UPDATE = "kind_update"
    NODE_REMOVE = "node_remove"
    FIELD_REMOVE = "field_remove"
    ATTRIBUTE_RENAME = "attribute_rename"
    ATTRIBUTE_KIND_UPDATE = "attribute_kind_update"
    ATTRIBUTE_ADD = "attribute_add"
    PROPERTY_UPDATE = "property_update"
