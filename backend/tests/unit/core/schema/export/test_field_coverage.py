"""Every field a schema file can set is exercised by an export round trip, or says why it needs none.

A field added to the schema models fails here until a round-trip schema sets it, so the export rules cannot
drift from the models without a decision.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

import yaml
from infrahub_sdk.schema.generated import write

from tests.helpers.schema import CAR_SCHEMA, DEVICE_SCHEMA, LOCATION_SCHEMA, SNOW_TICKET_SCHEMA

if TYPE_CHECKING:
    from pydantic import BaseModel

RULE_SCHEMAS = Path(__file__).parent / "schemas"

PARAMETERS_BY_KIND: dict[str, type[BaseModel]] = {
    "Text": write.TextAttributeParametersWrite,
    "TextArea": write.TextAttributeParametersWrite,
    "Number": write.NumberAttributeParametersWrite,
    "List": write.ListAttributeParametersWrite,
    "NumberPool": write.NumberPoolParametersWrite,
}
COMPUTED_ATTRIBUTE_BY_KIND: dict[str, type[BaseModel]] = {
    "User": write.ComputedAttributeUserWrite,
    "Jinja2": write.ComputedAttributeJinja2Write,
    "TransformPython": write.ComputedAttributeTransformPythonWrite,
}
EXPORTED_MODELS: list[type[BaseModel]] = [
    write.NodeSchemaWrite,
    write.GenericSchemaWrite,
    write.AttributeSchemaBaseWrite,
    write.RelationshipSchemaWrite,
    write.DropdownChoiceWrite,
    write.NumberPoolRangeWrite,
    *dict.fromkeys(PARAMETERS_BY_KIND.values()),
    *COMPUTED_ATTRIBUTE_BY_KIND.values(),
]

NOT_TESTED: dict[tuple[str, str], str] = {
    ("NodeSchemaWrite", "id"): "never exported",
    ("NodeSchemaWrite", "state"): "never exported",
    ("GenericSchemaWrite", "id"): "never exported",
    ("GenericSchemaWrite", "state"): "never exported",
    ("AttributeSchemaBaseWrite", "id"): "never exported",
    ("AttributeSchemaBaseWrite", "state"): "never exported",
    ("RelationshipSchemaWrite", "id"): "never exported",
    ("RelationshipSchemaWrite", "state"): "never exported",
    ("NumberPoolParametersWrite", "number_pool_id"): "identifies a pool of one instance, never exported",
    ("AttributeSchemaBaseWrite", "regex"): "deprecated alias, exported under parameters",
    ("AttributeSchemaBaseWrite", "min_length"): "deprecated alias, exported under parameters",
    ("AttributeSchemaBaseWrite", "max_length"): "deprecated alias, exported under parameters",
    ("NumberPoolParametersWrite", "allocation_scope"): "needs a resource pool scope, copied as stored",
    ("ComputedAttributeTransformPythonWrite", "kind"): "needs a Python transform in a repository",
    ("ComputedAttributeTransformPythonWrite", "transform"): "needs a Python transform in a repository",
}
"""Fields whose round trip proves nothing about the export, with the reason; a schema may still set them."""


def _round_trip_sources() -> list[dict[str, Any]]:
    fixtures = [
        root.model_dump(mode="json", exclude_unset=True)
        for root in (CAR_SCHEMA, DEVICE_SCHEMA, LOCATION_SCHEMA, SNOW_TICKET_SCHEMA)
    ]
    files = [yaml.safe_load(path.read_text()) for path in sorted(RULE_SCHEMAS.glob("*.yml"))]
    return fixtures + files


def _fields_set(document: dict[str, Any]) -> set[tuple[str, str]]:
    found: set[tuple[str, str]] = set()
    for section, model in (("generics", write.GenericSchemaWrite), ("nodes", write.NodeSchemaWrite)):
        for element in document.get(section, []):
            found |= {(model.__name__, name) for name in element}
            for attribute in element.get("attributes", []):
                found |= {(write.AttributeSchemaBaseWrite.__name__, name) for name in attribute}
                if parameters := attribute.get("parameters"):
                    parameters_model = PARAMETERS_BY_KIND[attribute["kind"]]
                    found |= {(parameters_model.__name__, name) for name in parameters}
                    for number_range in parameters.get("ranges") or []:
                        found |= {(write.NumberPoolRangeWrite.__name__, name) for name in number_range}
                for choice in attribute.get("choices") or []:
                    found |= {(write.DropdownChoiceWrite.__name__, name) for name in choice}
                if computed := attribute.get("computed_attribute"):
                    found |= {(COMPUTED_ATTRIBUTE_BY_KIND[computed["kind"]].__name__, name) for name in computed}
            for relationship in element.get("relationships", []):
                found |= {(write.RelationshipSchemaWrite.__name__, name) for name in relationship}
    return found


def _all_fields() -> set[tuple[str, str]]:
    fields = {(model.__name__, name) for model in EXPORTED_MODELS for name in model.model_fields}
    # Each attribute kind adds only `parameters` to the shared attribute fields.
    fields.add((write.AttributeSchemaBaseWrite.__name__, "parameters"))
    return fields


def test_every_field_is_set_by_a_round_trip_schema_or_needs_no_test() -> None:
    covered = set().union(*(_fields_set(document=source) for source in _round_trip_sources()))

    assert _all_fields() - covered - NOT_TESTED.keys() == set()


def test_fields_that_need_no_test_are_still_schema_fields() -> None:
    assert NOT_TESTED.keys() - _all_fields() == set()
