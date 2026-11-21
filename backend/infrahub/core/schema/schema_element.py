from dataclasses import dataclass
from enum import Enum


class SchemaElementType(Enum):
    NODE = "node"
    GENERIC = "generic"
    ATTRIBUTE = "attribute"
    RELATIONSHIP = "relationship"


@dataclass(frozen=True)
class StoredSchemaElement:
    """A schema element identified by its stored ID: what it is and where it sits."""

    element_type: SchemaElementType
    kind: str
    """The kind of the node or generic, or of the node or generic that holds the attribute or relationship."""

    field_name: str | None = None
    """The name of the attribute or relationship; None for a node or generic."""

    @property
    def label(self) -> str:
        if self.field_name is None:
            return self.kind
        return f"{self.kind}.{self.field_name}"
