from __future__ import annotations

import copy
import functools
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from infrahub_sdk.schema.generated.contract import KEEP_IN_EXPORT_FIELDS
from infrahub_sdk.schema.generated.write import GenericSchemaWrite, NodeSchemaWrite

from infrahub import __version__
from infrahub.core.constants import RESTRICTED_NAMESPACES, RelationshipKind
from infrahub.core.schema import GenericSchema, NodeSchema, SchemaRoot, core_models, internal_schema
from infrahub.core.schema.attribute_parameters import get_attribute_parameters_class_for_kind
from infrahub.core.schema.definitions.deprecated import deprecated_models
from infrahub.core.schema.node_inheritance_handler import PROPERTIES_INHERITED_FROM_GENERIC
from infrahub.core.schema.schema_branch import SchemaBranch
from infrahub.exceptions import SchemaNamespaceNotFoundError, ValidationError
from infrahub.log import get_logger
from infrahub.schema.export.models import SCHEMA_FILE_FORMAT_VERSION, SchemaExportDocument, SchemaExportMode

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable, Mapping

    from infrahub_sdk.schema.generated.write import AttributeSchemaWrite
    from pydantic import BaseModel

log = get_logger()

DEPRECATED_ATTRIBUTE_PARAMETER_FIELDS = ("regex", "min_length", "max_length")
"""Top-level attribute fields that processing keeps equal to the field of the same name in `parameters`."""

NUMBER_POOL_START_FIELD = "start_range"
NUMBER_POOL_END_FIELD = "end_range"

ATTRIBUTES_FIELD = "attributes"
RELATIONSHIPS_FIELD = "relationships"
PARAMETERS_FIELD = "parameters"
ID_FIELD = "id"
ELEMENT_COLLECTIONS = (ATTRIBUTES_FIELD, RELATIONSHIPS_FIELD)

GENERATED_RELATIONSHIP_KINDS = frozenset(
    {RelationshipKind.GROUP, RelationshipKind.PROFILE, RelationshipKind.HIERARCHY, RelationshipKind.TEMPLATE}
)
"""Kinds of the relationships that processing adds to nodes and generics."""

CORE_SCHEMA_DEFINITIONS = (internal_schema, core_models, deprecated_models)
CORE_SCHEMA_BASELINE_NAME = "core-schema-baseline"


def _defined_kinds(definitions: Iterable[Mapping[str, Any]]) -> frozenset[str]:
    return frozenset(
        f"{element['namespace']}{element['name']}"
        for schema in definitions
        for element_type in ("nodes", "generics")
        for element in schema.get(element_type, [])
    )


CORE_SCHEMA_KINDS = _defined_kinds(CORE_SCHEMA_DEFINITIONS)
"""Kinds of the nodes and generics that Infrahub defines, whatever their namespace."""


def build_core_schema_baseline(name: str) -> SchemaBranch:
    """Return a new processed schema that holds only the schema Infrahub defines, as on an empty instance.

    The returned schema has a schema cache of its own, so loading into it never changes another schema.
    """
    baseline = SchemaBranch(cache={}, name=name)
    for definitions in CORE_SCHEMA_DEFINITIONS:
        baseline.load_schema(schema=SchemaRoot(**definitions))
    baseline.process()
    return baseline


@functools.cache
def _processed_core_schema() -> SchemaBranch:
    return build_core_schema_baseline(name=CORE_SCHEMA_BASELINE_NAME)


def copy_core_schema_baseline(name: str) -> SchemaBranch:
    """Return a copy of the processed core schema, which is built once per process, that a load can change.

    Processing replaces the schema objects it changes rather than changing them in place, so the copies share the
    cached objects and only the copy's own cache and kind lists grow.
    """
    return _processed_core_schema().duplicate_with_own_cache(name=name)


def convert_deprecated_attribute_fields(attribute: Mapping[str, Any]) -> dict[str, Any]:
    """Return a copy of a dumped attribute that holds its parameters only in their current form.

    Top-level `regex`, `min_length` and `max_length` are removed when the parameters of the kind support them,
    and their value is written into `parameters` only when `parameters` does not set it already. NumberPool
    `start_range` and `end_range` become one entry of `ranges`. The given mapping and the values nested in it
    are not changed.
    """
    converted = dict(attribute)
    parameters = dict(converted.get("parameters") or {})
    parameter_fields = get_attribute_parameters_class_for_kind(converted["kind"]).model_fields

    for field_name in DEPRECATED_ATTRIBUTE_PARAMETER_FIELDS:
        if field_name not in parameter_fields or field_name not in converted:
            continue
        value = converted.pop(field_name)
        if value is not None and parameters.get(field_name) is None:
            parameters[field_name] = value

    start = parameters.pop(NUMBER_POOL_START_FIELD, None)
    end = parameters.pop(NUMBER_POOL_END_FIELD, None)
    if start is not None or end is not None:
        bounds = {"start": start, "end": end}
        parameters["ranges"] = [{key: value for key, value in bounds.items() if value is not None}]

    if parameters or converted.get("parameters"):
        converted["parameters"] = parameters
    return converted


def normalize_element_for_comparison(
    element: Mapping[str, Any], write_model: type[NodeSchemaWrite | GenericSchemaWrite]
) -> dict[str, Any]:
    """Return the fields of a dumped node or generic that a schema file can carry, without IDs.

    The attributes are converted to their current form first, so the deprecated and the current form of the
    same value compare equal.
    """
    converted = dict(element)
    converted["attributes"] = [
        convert_deprecated_attribute_fields(attribute) for attribute in element.get("attributes", [])
    ]
    normalized = write_model.model_validate(converted).model_dump()
    normalized.pop("id", None)
    for attribute in normalized["attributes"]:
        attribute.pop("id", None)
    for relationship in normalized["relationships"]:
        relationship.pop("id", None)
    return normalized


@dataclass(frozen=True)
class ExportedField:
    """One field of a node or generic, or of one of its attributes or relationships, in a schema file."""

    kind: str
    collection: str | None
    """`attributes` or `relationships` for a field of an attribute or relationship, `None` for one of the node."""

    element_name: str | None
    field: str
    """The name of the field, as `parameters.<name>` for an attribute parameter."""

    def describe(self) -> dict[str, str | None]:
        return {"kind": self.kind, "element": self.element_name, "field": self.field}


def _element_kind(element: Mapping[str, Any]) -> str:
    return f"{element['namespace']}{element['name']}"


def _field_values(element: Mapping[str, Any]) -> dict[str, Any]:
    """Return the fields of one dumped element, with the attribute parameters as `parameters.<name>`."""
    values = {
        name: value
        for name, value in element.items()
        if name not in ELEMENT_COLLECTIONS and name not in {PARAMETERS_FIELD, ID_FIELD}
    }
    for name, value in (element.get(PARAMETERS_FIELD) or {}).items():
        values[f"{PARAMETERS_FIELD}.{name}"] = value
    return values


def _display_order(item: Mapping[str, Any]) -> tuple[bool, int, str]:
    """Sort key that orders attributes or relationships by order weight, then by name."""
    order_weight = item.get("order_weight")
    return (order_weight is None, order_weight or 0, item["name"])


def _find_item(element: Mapping[str, Any], collection: str, name: str) -> dict[str, Any] | None:
    for item in element.get(collection, []):
        if item["name"] == name:
            return item
    return None


def _removable_fields(model: BaseModel, element: Mapping[str, Any], kept: Iterable[str]) -> set[str]:
    """Return the optional fields of a dumped element that a schema export may leave out.

    A field in `kept` or marked to stay in an export is left out only when it holds its default value, which a
    load sets again.
    """
    model_fields = type(model).model_fields
    always_kept = KEEP_IN_EXPORT_FIELDS.get(type(model).__name__, frozenset()) | set(kept)
    return {
        name
        for name, value in element.items()
        if not model_fields[name].is_required()
        and (name not in always_kept or value == model_fields[name].get_default(call_default_factory=True))
    }


def _remove_optional_fields(model: BaseModel, element: dict[str, Any], kept: Iterable[str]) -> None:
    for name in _removable_fields(model=model, element=element, kept=kept):
        del element[name]


def _remove_optional_attribute_fields(model: AttributeSchemaWrite, attribute: dict[str, Any]) -> None:
    _remove_optional_fields(model=model, element=attribute, kept={PARAMETERS_FIELD})
    parameters = attribute.get(PARAMETERS_FIELD)
    parameters_model = model.parameters
    if parameters is None or parameters_model is None:
        return
    _remove_optional_fields(model=parameters_model, element=parameters, kept=())
    if not parameters:
        del attribute[PARAMETERS_FIELD]


class SchemaExporter:
    """Builds a schema file from a branch schema without changing that schema."""

    def __init__(self, baseline_factory: Callable[[str], SchemaBranch]) -> None:
        self._baseline_factory = baseline_factory

    def export(
        self, schema_branch: SchemaBranch, mode: SchemaExportMode, namespaces: list[str] | None
    ) -> SchemaExportDocument:
        """Return the user-defined nodes and generics of `schema_branch`, never changing `schema_branch`.

        With `namespaces`, the document holds only the nodes and generics of those namespaces, each with the values
        it has in an export without the filter.

        Raises:
            SchemaNamespaceNotFoundError: When a namespace in `namespaces` does not exist on the branch, or is a
                restricted namespace.

        """
        if namespaces:
            self._check_namespaces(schema_branch=schema_branch, namespaces=namespaces)
        started = time.monotonic()
        full_document = self._build_full_document(schema_branch=schema_branch)
        document = full_document
        passes = 0
        if mode == SchemaExportMode.BRIEF:
            document, passes = self._reduce(schema_branch=schema_branch, full_document=full_document)
        if namespaces:
            document = self._select_namespaces(document=document, namespaces=namespaces)

        log.debug(
            "Schema export built",
            branch=schema_branch.name,
            mode=mode.value,
            namespaces=namespaces,
            passes=passes,
            duration_seconds=round(time.monotonic() - started, 3),
        )
        return document

    @staticmethod
    def _check_namespaces(schema_branch: SchemaBranch, namespaces: Iterable[str]) -> None:
        """Raise one error that names every namespace of `namespaces` an export cannot select.

        Raises:
            SchemaNamespaceNotFoundError: When a namespace does not exist on the branch, or is a restricted namespace.

        """
        existing = {namespace.name for namespace in schema_branch.get_namespaces(include_internal=True)}
        namespace_messages: dict[str, str] = {}
        for namespace in dict.fromkeys(namespaces):
            if namespace in RESTRICTED_NAMESPACES:
                namespace_messages[namespace] = (
                    f"The namespace '{namespace}' is reserved for Infrahub and cannot be exported"
                )
            elif namespace not in existing:
                namespace_messages[namespace] = (
                    f"The namespace '{namespace}' does not exist on the branch '{schema_branch.name}'"
                )
        if namespace_messages:
            raise SchemaNamespaceNotFoundError(namespace_messages=namespace_messages)

    @staticmethod
    def _select_namespaces(document: SchemaExportDocument, namespaces: Iterable[str]) -> SchemaExportDocument:
        selected = set(namespaces)
        return document.model_copy(
            update={
                "generics": [generic for generic in document.generics if generic.namespace in selected],
                "nodes": [node for node in document.nodes if node.namespace in selected],
            }
        )

    def _build_full_document(self, schema_branch: SchemaBranch) -> SchemaExportDocument:
        generics = [
            self._export_element(element=element, write_model=GenericSchemaWrite)
            for element in self._user_elements(schema_branch=schema_branch, kinds=schema_branch.generics)
        ]
        nodes = [
            self._export_element(element=element, write_model=NodeSchemaWrite)
            for element in self._user_elements(schema_branch=schema_branch, kinds=schema_branch.nodes)
        ]
        return SchemaExportDocument.model_validate(
            {
                "version": SCHEMA_FILE_FORMAT_VERSION,
                "infrahub_version": __version__,
                "generics": generics,
                "nodes": nodes,
            }
        )

    @staticmethod
    def _user_elements(schema_branch: SchemaBranch, kinds: Iterable[str]) -> list[NodeSchema | GenericSchema]:
        elements: list[NodeSchema | GenericSchema] = []
        for kind in sorted(kinds):
            if kind in CORE_SCHEMA_KINDS:
                continue
            element = schema_branch.get(name=kind, duplicate=False)
            if not isinstance(element, NodeSchema | GenericSchema) or element.namespace in RESTRICTED_NAMESPACES:
                continue
            elements.append(element)
        return elements

    @staticmethod
    def _export_element(
        element: NodeSchema | GenericSchema, write_model: type[NodeSchemaWrite | GenericSchemaWrite]
    ) -> dict[str, Any]:
        """Return the write-visible values of a stored node or generic, read from a dump so the element never changes.

        Attributes and relationships are written in display order, because the order a schema read back from the
        database holds them in can change between reads.
        """
        is_node = isinstance(element, NodeSchema)
        dump = element.model_dump()
        dump[ATTRIBUTES_FIELD] = sorted(
            (
                convert_deprecated_attribute_fields(attribute)
                for attribute in dump[ATTRIBUTES_FIELD]
                if not (is_node and attribute["inherited"])
            ),
            key=_display_order,
        )
        dump[RELATIONSHIPS_FIELD] = sorted(
            (
                relationship
                for relationship in dump[RELATIONSHIPS_FIELD]
                if not (is_node and relationship["inherited"])
                and relationship["kind"] not in GENERATED_RELATIONSHIP_KINDS
            ),
            key=_display_order,
        )
        exported = write_model.model_validate(dump).model_dump(exclude_none=True)
        exported.pop(ID_FIELD, None)
        for collection in ELEMENT_COLLECTIONS:
            for item in exported[collection]:
                item.pop(ID_FIELD, None)
        return exported

    def _reduce(
        self, schema_branch: SchemaBranch, full_document: SchemaExportDocument
    ) -> tuple[SchemaExportDocument, int]:
        """Return the document that leaves out every value processing produces again, and the number of passes."""
        full_data = full_document.model_dump(exclude_unset=True)
        candidate = copy.deepcopy(full_data)
        for model, element in zip(full_document.nodes, candidate["nodes"], strict=True):
            pinned = self._pinned_properties(schema_branch=schema_branch, kind=model.kind)
            self._remove_optional_element_fields(model=model, element=element, pinned=pinned)
        for model, element in zip(full_document.generics, candidate["generics"], strict=True):
            self._remove_optional_element_fields(model=model, element=element, pinned=set())

        full_elements = {_element_kind(element): element for element in full_data["nodes"] + full_data["generics"]}
        candidate_elements = {_element_kind(element): element for element in candidate["nodes"] + candidate["generics"]}
        stored_elements = {
            kind: self._normalize(schema_branch=schema_branch, kind=kind) for kind in sorted(full_elements)
        }

        passes = 0
        while True:
            passes += 1
            baseline = self._baseline_factory(schema_branch.name)
            try:
                self._load_candidate(baseline=baseline, candidate=candidate)
            except (ValueError, ValidationError) as exc:
                log.warning(
                    "A schema export candidate failed validation, the export holds every value instead",
                    branch=schema_branch.name,
                    error=str(exc),
                )
                return full_document, passes

            differences = self._find_differences(
                stored_elements=stored_elements, processed=baseline, full_elements=full_elements
            )
            restored = [
                difference
                for difference in differences
                if self._put_back(
                    difference=difference, candidate_elements=candidate_elements, full_elements=full_elements
                )
            ]
            for difference in restored:
                log.debug(
                    "Schema export put back a value that processing changes",
                    branch=schema_branch.name,
                    **difference.describe(),
                )
            if not restored:
                break

        if differences:
            log.warning(
                "The schema export loads to values that differ from the stored schema",
                branch=schema_branch.name,
                differences=[difference.describe() for difference in differences],
            )
        return SchemaExportDocument.model_validate(candidate), passes

    @staticmethod
    def _pinned_properties(schema_branch: SchemaBranch, kind: str) -> set[str]:
        """Return the properties a node holds with the value of the first generic in `inherit_from` that sets it."""
        node = schema_branch.get_node(name=kind, duplicate=False)
        node_values = node.model_dump(include=set(PROPERTIES_INHERITED_FROM_GENERIC))
        generic_values = [
            schema_branch.get_generic(name=generic_kind, duplicate=False).model_dump(
                include=set(PROPERTIES_INHERITED_FROM_GENERIC)
            )
            for generic_kind in node.inherit_from
        ]
        pinned: set[str] = set()
        for property_name in PROPERTIES_INHERITED_FROM_GENERIC:
            inherited_value = next((values[property_name] for values in generic_values if values[property_name]), None)
            if inherited_value and node_values[property_name] == inherited_value:
                pinned.add(property_name)
        return pinned

    @staticmethod
    def _remove_optional_element_fields(
        model: NodeSchemaWrite | GenericSchemaWrite, element: dict[str, Any], pinned: set[str]
    ) -> None:
        _remove_optional_fields(model=model, element=element, kept={*ELEMENT_COLLECTIONS, *pinned})
        for attribute_model, attribute in zip(model.attributes, element.get(ATTRIBUTES_FIELD, []), strict=True):
            _remove_optional_attribute_fields(model=attribute_model, attribute=attribute)
        for relationship_model, relationship in zip(
            model.relationships, element.get(RELATIONSHIPS_FIELD, []), strict=True
        ):
            _remove_optional_fields(model=relationship_model, element=relationship, kept=())

    @staticmethod
    def _load_candidate(baseline: SchemaBranch, candidate: Mapping[str, Any]) -> None:
        """Load and process the candidate as a schema load does.

        Raises:
            ValueError: When the candidate does not pass the schema validation.
            ValidationError: When a kind of the candidate conflicts with a kind of the baseline.

        """
        schema = SchemaRoot(
            version=candidate["version"],
            nodes=copy.deepcopy(candidate["nodes"]),
            generics=copy.deepcopy(candidate["generics"]),
        )
        baseline.load_schema(schema=schema)
        baseline.process()

    @staticmethod
    def _normalize(schema_branch: SchemaBranch, kind: str) -> dict[str, Any]:
        element = schema_branch.get(name=kind, duplicate=False)
        write_model = NodeSchemaWrite if isinstance(element, NodeSchema) else GenericSchemaWrite
        return normalize_element_for_comparison(element.model_dump(), write_model=write_model)

    def _find_differences(
        self,
        stored_elements: Mapping[str, Mapping[str, Any]],
        processed: SchemaBranch,
        full_elements: Mapping[str, Mapping[str, Any]],
    ) -> list[ExportedField]:
        """Return each write-visible field of an exported element whose processed value differs from the stored one."""
        differences: list[ExportedField] = []
        for kind, full_element in full_elements.items():
            stored = stored_elements[kind]
            processed_element = self._normalize(schema_branch=processed, kind=kind)
            differences.extend(
                ExportedField(kind=kind, collection=None, element_name=None, field=field)
                for field in self._differing_fields(stored=stored, processed=processed_element)
            )
            for collection in ELEMENT_COLLECTIONS:
                for item in full_element[collection]:
                    name = item["name"]
                    differences.extend(
                        ExportedField(kind=kind, collection=collection, element_name=name, field=field)
                        for field in self._differing_fields(
                            stored=_find_item(stored, collection, name) or {},
                            processed=_find_item(processed_element, collection, name) or {},
                        )
                    )
        return differences

    @staticmethod
    def _differing_fields(stored: Mapping[str, Any], processed: Mapping[str, Any]) -> list[str]:
        stored_values = _field_values(stored)
        processed_values = _field_values(processed)
        return [
            field
            for field in sorted(stored_values.keys() | processed_values.keys())
            if stored_values.get(field) != processed_values.get(field)
        ]

    @staticmethod
    def _put_back(
        difference: ExportedField,
        candidate_elements: Mapping[str, dict[str, Any]],
        full_elements: Mapping[str, Mapping[str, Any]],
    ) -> bool:
        """Copy a field from the `FULL` document into the candidate, and return whether the candidate lacked it."""
        candidate_item: dict[str, Any] | None = candidate_elements[difference.kind]
        full_item: Mapping[str, Any] | None = full_elements[difference.kind]
        if difference.collection is not None and difference.element_name is not None:
            candidate_item = _find_item(
                candidate_elements[difference.kind], difference.collection, difference.element_name
            )
            full_item = _find_item(full_elements[difference.kind], difference.collection, difference.element_name)
        if candidate_item is None or full_item is None:
            return False

        full_values = _field_values(full_item)
        if difference.field not in full_values or difference.field in _field_values(candidate_item):
            return False

        value = copy.deepcopy(full_values[difference.field])
        parameters_prefix = f"{PARAMETERS_FIELD}."
        if difference.field.startswith(parameters_prefix):
            candidate_item.setdefault(PARAMETERS_FIELD, {})[difference.field.removeprefix(parameters_prefix)] = value
        else:
            candidate_item[difference.field] = value
        return True
