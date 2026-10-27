from __future__ import annotations

from typing import TYPE_CHECKING

from infrahub_sdk.schema.generated.write import InfrahubSchemaWrite

from infrahub.core.constants import SchemaExportMode
from infrahub.core.schema import SchemaRoot, core_models, internal_schema
from infrahub.core.schema.definitions.deprecated import deprecated_models
from infrahub.core.schema.schema_branch import SchemaBranch

from .minimizer import COPYABLE_NODE_PROPERTIES, BriefSchemaMinimizer
from .serializer import SchemaExportSerializer

if TYPE_CHECKING:
    from .document import ExportDocument

SCHEMA_FILE_VERSION = "1.0"


class SchemaExporter:
    """Export the user-defined schema of a branch in the schema file format."""

    def __init__(
        self, serializer: SchemaExportSerializer, minimizer: BriefSchemaMinimizer, infrahub_version: str
    ) -> None:
        self.serializer = serializer
        self.minimizer = minimizer
        self.infrahub_version = infrahub_version

    def export(
        self, schema_branch: SchemaBranch, namespaces: list[str] | None, mode: SchemaExportMode
    ) -> InfrahubSchemaWrite:
        """Export the given namespaces, or every user namespace when none are given.

        Raises:
            SchemaExportError: When the brief export would not process back into the same schema.

        """
        user_namespaces = self.serializer.user_namespaces(schema_branch=schema_branch)
        selected = [namespace for namespace in user_namespaces if not namespaces or namespace in namespaces]
        document = self.serializer.serialize(schema_branch=schema_branch, namespaces=selected)

        if mode == SchemaExportMode.BRIEF:
            context = self.serializer.serialize(
                schema_branch=schema_branch,
                namespaces=[namespace for namespace in user_namespaces if namespace not in selected],
            )
            document = self.minimizer.minimize(
                full=document,
                context=context,
                copied_properties=self._copied_properties(schema_branch=schema_branch, document=document),
            )

        return InfrahubSchemaWrite.model_validate(
            {
                "version": SCHEMA_FILE_VERSION,
                "infrahub_version": self.infrahub_version,
                "generics": document.generics,
                "nodes": document.nodes,
            }
        )

    def _copied_properties(self, schema_branch: SchemaBranch, document: ExportDocument) -> dict[str, frozenset[str]]:
        copied: dict[str, frozenset[str]] = {}
        for node in document.nodes:
            kind = f"{node['namespace']}{node['name']}"
            copied[kind] = frozenset(
                name
                for generic in node.get("inherit_from", [])
                for name, value in schema_branch.get_generic(name=generic, duplicate=False)
                .model_dump(include=set(COPYABLE_NODE_PROPERTIES))
                .items()
                if value
            )
        return copied


def build_base_schema_branch() -> SchemaBranch:
    """Return the schema an empty instance starts with: internal, core and deprecated models, not processed."""
    schema_branch = SchemaBranch(cache={}, name="schema-export")
    for models in (internal_schema, core_models, deprecated_models):
        schema_branch.load_schema(schema=SchemaRoot(**models))
    return schema_branch


def build_schema_exporter(infrahub_version: str) -> SchemaExporter:
    serializer = SchemaExportSerializer(shipped_kinds=frozenset(build_base_schema_branch().all_names))
    return SchemaExporter(
        serializer=serializer,
        minimizer=BriefSchemaMinimizer(serializer=serializer, base_branch_factory=build_base_schema_branch),
        infrahub_version=infrahub_version,
    )
