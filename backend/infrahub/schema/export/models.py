from __future__ import annotations

from enum import StrEnum

from infrahub_sdk.schema.generated.write import GenericSchemaWrite, InfrahubSchemaWrite, NodeSchemaWrite
from pydantic import Field

SCHEMA_FILE_FORMAT_VERSION = "1.0"


class SchemaExportMode(StrEnum):
    BRIEF = "BRIEF"
    """Leaves out the values that processing produces again when the export is loaded."""

    FULL = "FULL"
    """Writes every value of the user-defined nodes and generics that a schema file can carry."""


class SchemaExportDocument(InfrahubSchemaWrite):
    """Schema file built from the running schema, valid as a schema load payload."""

    infrahub_version: str
    generics: list[GenericSchemaWrite] = Field(default_factory=list)
    nodes: list[NodeSchemaWrite] = Field(default_factory=list)
    extensions: None = None
    """Extensions of exported nodes are written as attributes and relationships of the node."""
