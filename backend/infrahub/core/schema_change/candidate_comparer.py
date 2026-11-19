from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic import ValidationError

from infrahub.core.schema_change.enums import SchemaOperationSection
from infrahub.core.schema_change.operations import INSTANCE_ID_KEY, NUMBER_POOL_ID_KEY, PARAMETERS_KEY

if TYPE_CHECKING:
    from infrahub.core.schema import MainSchemaTypes
    from infrahub.core.schema.schema_branch import SchemaBranch


class SchemaCandidateComparer:
    """Compares two processed schemas kind by kind."""

    def differing_kinds(self, *, direct_load_schema: SchemaBranch, applied_schema: SchemaBranch) -> list[str]:
        """Return the sorted kinds whose content differs between the two schemas, or that only one of them has.

        Two kinds with the same content are equal even when an attribute is held in another Python class, or when the
        kind or one of its attributes or relationships has another ID, or a number pool attribute has another pool ID.
        A kind that cannot be parsed again in either schema is returned, and nothing is raised for it.
        """
        direct_load_hashes = self._kind_hashes(schema=direct_load_schema)
        applied_hashes = self._kind_hashes(schema=applied_schema)
        return sorted(
            kind
            for kind in direct_load_hashes.keys() | applied_hashes.keys()
            if direct_load_hashes.get(kind) != applied_hashes.get(kind)
            and not self._same_content(direct_load_schema=direct_load_schema, applied_schema=applied_schema, kind=kind)
        )

    def _kind_hashes(self, schema: SchemaBranch) -> dict[str, str]:
        return {kind: kind_hash for hashes in schema.to_dict().values() for kind, kind_hash in hashes.items()}

    def _same_content(self, *, direct_load_schema: SchemaBranch, applied_schema: SchemaBranch, kind: str) -> bool:
        if not direct_load_schema.has(name=kind) or not applied_schema.has(name=kind):
            return False
        try:
            return self._content_hash(node=direct_load_schema.get(name=kind, duplicate=False)) == self._content_hash(
                node=applied_schema.get(name=kind, duplicate=False)
            )
        except ValidationError:
            return False

    def _content_hash(self, node: MainSchemaTypes) -> str:
        # Saving a schema gives a new kind, element or number pool an ID of its own whatever ID the file set, so IDs are no content.
        definition = node.model_dump()
        definition.pop(INSTANCE_ID_KEY, None)
        for section in SchemaOperationSection:
            for element in definition.get(section.value) or []:
                element.pop(INSTANCE_ID_KEY, None)
                parameters = element.get(PARAMETERS_KEY)
                if isinstance(parameters, dict):
                    parameters.pop(NUMBER_POOL_ID_KEY, None)
        # Parsing the kind again builds each attribute in the class of its attribute kind, as a schema read from the database has it.
        return type(node).model_validate(definition).get_hash()
