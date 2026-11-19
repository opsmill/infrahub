from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from infrahub.core.constants import HashableModelState
from infrahub.core.schema import SchemaWarning, SchemaWarningKind, SchemaWarningType
from infrahub.core.schema.schema_element import SchemaElementType

if TYPE_CHECKING:
    from collections.abc import Iterator, Sequence

    from infrahub.core.schema import (
        AttributeSchema,
        GenericSchema,
        NodeExtensionSchema,
        NodeSchema,
        RelationshipSchema,
        SchemaRoot,
    )
    from infrahub.core.schema.schema_branch import SchemaBranch
    from infrahub.core.schema.schema_element import StoredSchemaElement
    from infrahub.core.schema.submitted_ids.lookup import SchemaElementIdLookup

IGNORED_ID_WARNING = "'id' does not match any schema element, the submitted value is ignored"
SKIPPED_ABSENT_WARNING = "the element marked absent is not on this branch, it is skipped"


@dataclass(frozen=True)
class SubmittedIdResolution:
    """The submitted schemas with their IDs resolved against a branch, and what the resolution reported."""

    schemas: list[SchemaRoot]
    warnings: list[SchemaWarning]
    errors: list[str]


@dataclass(frozen=True)
class _IdHolder:
    """An element of the load given an ID, and what makes two elements of the load the same element."""

    element_type: SchemaElementType
    target_kind: str
    name: str
    label: str

    def is_same_element(self, other: _IdHolder) -> bool:
        return (self.element_type, self.target_kind, self.name) == (other.element_type, other.target_kind, other.name)


@dataclass
class _UnresolvedElement:
    element: NodeSchema | GenericSchema | AttributeSchema | RelationshipSchema
    element_id: str
    kind: str
    field_name: str | None
    owner: _UnresolvedElement | None
    """The node or generic of a field, when that node or generic is unresolved too."""

    stored: StoredSchemaElement | None
    """The stored element that holds the ID on this branch, or None when the branch does not hold it."""

    first_holder: _IdHolder | None = None
    """Another element of the load given the same ID first, or None when this element is the first."""

    skipped: bool = False

    @property
    def label(self) -> str:
        if self.field_name is None:
            return self.kind
        return f"{self.kind}.{self.field_name}"

    @property
    def warning_kind(self) -> SchemaWarningKind:
        return SchemaWarningKind(kind=self.kind, field=self.field_name)


class SubmittedSchemaIdResolver:
    """Checks the IDs of submitted schema elements against the branch schema and the IDs ever stored."""

    def __init__(self, lookup: SchemaElementIdLookup) -> None:
        self.lookup = lookup

    async def resolve(self, branch_schema: SchemaBranch, schemas: Sequence[SchemaRoot]) -> SubmittedIdResolution:
        """Return copies of ``schemas`` without unknown IDs or skipped absent elements, with the warnings and errors."""
        if not any(_has_submitted_id(schema) for schema in schemas):
            return SubmittedIdResolution(schemas=list(schemas), warnings=[], errors=[])

        copies = [schema.duplicate() for schema in schemas]
        unresolved = self._find_unresolved(schemas=copies, stored=branch_schema.get_schema_element_ids())

        pending_ids = {
            element.element_id for element in unresolved if element.stored is None and element.first_holder is None
        }
        existing_ids = await self.lookup.get_existing_ids(pending_ids) if pending_ids else set()

        errors: list[str] = []
        ignored: list[_UnresolvedElement] = []
        skipped: list[_UnresolvedElement] = []
        for element in unresolved:
            if element.first_holder is not None:
                errors.append(
                    f"{element.label}: id '{element.element_id}' is also given to "
                    f"{element.first_holder.element_type.value} '{element.first_holder.label}'"
                )
                continue
            # An owner precedes its fields in the list, so its skipped flag is set before its fields are checked.
            if element.owner is not None and element.owner.skipped:
                continue
            if element.stored is not None:
                errors.append(
                    f"{element.label}: id '{element.element_id}' belongs to "
                    f"{element.stored.element_type.value} '{element.stored.label}'"
                )
            elif element.element_id not in existing_ids:
                element.element.id = None
                ignored.append(element)
            elif element.element.state == HashableModelState.ABSENT:
                element.skipped = True
                skipped.append(element)
            else:
                errors.append(
                    f"{element.label}: id '{element.element_id}' belongs to a schema element that is not on this branch"
                )

        _remove_skipped(schemas=copies, skipped=[element.element for element in skipped])

        warnings = [
            SchemaWarning(
                type=SchemaWarningType.DEPRECATION,
                kinds=[element.warning_kind for element in elements],
                message=message,
            )
            for message, elements in ((IGNORED_ID_WARNING, ignored), (SKIPPED_ABSENT_WARNING, skipped))
            if elements
        ]
        return SubmittedIdResolution(schemas=copies, warnings=warnings, errors=errors)

    def _find_unresolved(
        self, schemas: list[SchemaRoot], stored: dict[str, StoredSchemaElement]
    ) -> list[_UnresolvedElement]:
        # The in-memory load applies every rename by ID before it reads a node by kind, in any file of the load.
        renamed_kinds: dict[str, str] = {}
        for schema in schemas:
            for element_type, element in _main_schemas(schema):
                stored_kind = _stored_kind(stored=stored, element_type=element_type, element_id=element.id)
                if stored_kind is not None:
                    renamed_kinds[element.kind] = stored_kind
        id_holders: dict[str, _IdHolder] = {}

        unresolved: list[_UnresolvedElement] = []
        for schema in schemas:
            for element_type, element in _main_schemas(schema):
                stored_kind = _stored_kind(stored=stored, element_type=element_type, element_id=element.id)
                target_kind = stored_kind or renamed_kinds.get(element.kind, element.kind)
                owner = None
                if element.id is not None:
                    first_holder = _claim_id(
                        id_holders=id_holders,
                        element_id=element.id,
                        holder=_IdHolder(
                            element_type=element_type, target_kind=target_kind, name=element.kind, label=element.kind
                        ),
                    )
                    if first_holder is not None or stored_kind is None:
                        owner = _UnresolvedElement(
                            element=element,
                            element_id=element.id,
                            kind=element.kind,
                            field_name=None,
                            owner=None,
                            stored=stored.get(element.id),
                            first_holder=first_holder,
                        )
                        unresolved.append(owner)
                unresolved.extend(
                    self._find_unresolved_fields(
                        schema=element, target_kind=target_kind, owner=owner, stored=stored, id_holders=id_holders
                    )
                )
            for extension in schema.extensions.nodes:
                unresolved.extend(
                    self._find_unresolved_fields(
                        schema=extension,
                        target_kind=renamed_kinds.get(extension.kind, extension.kind),
                        owner=None,
                        stored=stored,
                        id_holders=id_holders,
                    )
                )
        return unresolved

    def _find_unresolved_fields(
        self,
        schema: NodeSchema | GenericSchema | NodeExtensionSchema,
        target_kind: str,
        owner: _UnresolvedElement | None,
        stored: dict[str, StoredSchemaElement],
        id_holders: dict[str, _IdHolder],
    ) -> list[_UnresolvedElement]:
        unresolved: list[_UnresolvedElement] = []
        for element_type, element in _fields(schema):
            if element.id is None:
                continue
            first_holder = _claim_id(
                id_holders=id_holders,
                element_id=element.id,
                holder=_IdHolder(
                    element_type=element_type,
                    target_kind=target_kind,
                    name=element.name,
                    label=f"{schema.kind}.{element.name}",
                ),
            )
            stored_element = stored.get(element.id)
            if (
                first_holder is None
                and stored_element is not None
                and stored_element.element_type == element_type
                and stored_element.kind == target_kind
            ):
                continue
            unresolved.append(
                _UnresolvedElement(
                    element=element,
                    element_id=element.id,
                    kind=schema.kind,
                    field_name=element.name,
                    owner=owner,
                    stored=stored_element,
                    first_holder=first_holder,
                )
            )
        return unresolved


def _stored_kind(
    stored: dict[str, StoredSchemaElement], element_type: SchemaElementType, element_id: str | None
) -> str | None:
    """Return the stored kind of the node or generic of ``element_type`` that holds ``element_id`` on this branch."""
    if element_id is None:
        return None
    stored_element = stored.get(element_id)
    if stored_element is None or stored_element.element_type != element_type:
        return None
    return stored_element.kind


def _claim_id(id_holders: dict[str, _IdHolder], element_id: str, holder: _IdHolder) -> _IdHolder | None:
    """Record the first element given ``element_id``, and return it when it is another element than ``holder``."""
    first_holder = id_holders.setdefault(element_id, holder)
    if first_holder.is_same_element(holder):
        return None
    return first_holder


type _MainSchemaList = list[GenericSchema] | list[NodeSchema]
type _FieldList = list[AttributeSchema] | list[RelationshipSchema]


def _main_schema_lists(schema: SchemaRoot) -> Iterator[tuple[SchemaElementType, _MainSchemaList]]:
    yield SchemaElementType.GENERIC, schema.generics
    yield SchemaElementType.NODE, schema.nodes


def _field_lists(
    owner: GenericSchema | NodeSchema | NodeExtensionSchema,
) -> Iterator[tuple[SchemaElementType, _FieldList]]:
    yield SchemaElementType.ATTRIBUTE, owner.attributes
    yield SchemaElementType.RELATIONSHIP, owner.relationships


def _main_schemas(schema: SchemaRoot) -> Iterator[tuple[SchemaElementType, GenericSchema | NodeSchema]]:
    for element_type, elements in _main_schema_lists(schema):
        for element in elements:
            yield element_type, element


def _owners(schema: SchemaRoot) -> Iterator[GenericSchema | NodeSchema | NodeExtensionSchema]:
    for _, element in _main_schemas(schema):
        yield element
    yield from schema.extensions.nodes


def _fields(
    owner: GenericSchema | NodeSchema | NodeExtensionSchema,
) -> Iterator[tuple[SchemaElementType, AttributeSchema | RelationshipSchema]]:
    for element_type, elements in _field_lists(owner):
        for element in elements:
            yield element_type, element


def _has_submitted_id(schema: SchemaRoot) -> bool:
    if any(element.id is not None for _, element in _main_schemas(schema)):
        return True
    return any(field.id is not None for owner in _owners(schema) for _, field in _fields(owner))


def _remove_skipped(
    schemas: list[SchemaRoot],
    skipped: list[NodeSchema | GenericSchema | AttributeSchema | RelationshipSchema],
) -> None:
    if not skipped:
        return
    # Schema models compare by value, so two identical elements in different places would be equal.
    skipped_ids = {id(element) for element in skipped}
    for schema in schemas:
        for _, main_schemas in _main_schema_lists(schema):
            _remove_from(elements=main_schemas, skipped_ids=skipped_ids)
        for owner in _owners(schema):
            for _, fields in _field_lists(owner):
                _remove_from(elements=fields, skipped_ids=skipped_ids)


def _remove_from(elements: _MainSchemaList | _FieldList, skipped_ids: set[int]) -> None:
    for index in reversed(range(len(elements))):
        if id(elements[index]) in skipped_ids:
            del elements[index]
