from __future__ import annotations

from typing import TYPE_CHECKING, Any

from infrahub.core.schema import SchemaRoot, core_models, internal_schema
from infrahub.core.schema.attribute_parameters import get_attribute_parameters_class_for_kind
from infrahub.core.schema.definitions.deprecated import deprecated_models
from infrahub.core.schema.schema_branch import SchemaBranch

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping

    from infrahub_sdk.schema.generated.write import GenericSchemaWrite, NodeSchemaWrite

    from infrahub.schema.export.models import SchemaExportDocument, SchemaExportMode

DEPRECATED_ATTRIBUTE_PARAMETER_FIELDS = ("regex", "min_length", "max_length")
"""Top-level attribute fields that processing keeps equal to the field of the same name in `parameters`."""

NUMBER_POOL_START_FIELD = "start_range"
NUMBER_POOL_END_FIELD = "end_range"


def build_core_schema_baseline(name: str) -> SchemaBranch:
    """Return a new processed schema that holds only the schema Infrahub defines, as on an empty instance.

    The returned schema has a schema cache of its own, so loading into it never changes another schema.
    """
    baseline = SchemaBranch(cache={}, name=name)
    for definitions in (internal_schema, core_models, deprecated_models):
        baseline.load_schema(schema=SchemaRoot(**definitions))
    baseline.process()
    return baseline


def convert_deprecated_attribute_fields(attribute: Mapping[str, Any]) -> dict[str, Any]:
    """Return a copy of a dumped attribute that holds its parameters only in their current form.

    Top-level `regex`, `min_length` and `max_length` move into `parameters` when the parameters of the kind
    support them and do not set them already, and NumberPool `start_range` and `end_range` become one entry
    of `ranges`. The given mapping and the values nested in it are not changed.
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


class SchemaExporter:
    """Builds a schema file from a branch schema without changing that schema."""

    def __init__(self, baseline_factory: Callable[[str], SchemaBranch]) -> None:
        self._baseline_factory = baseline_factory

    def export(
        self, schema_branch: SchemaBranch, mode: SchemaExportMode, namespaces: list[str] | None
    ) -> SchemaExportDocument:
        """Return the user-defined nodes and generics of `schema_branch`, limited to `namespaces` when given."""
        raise NotImplementedError
