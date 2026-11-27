"""Every field a schema file can set is used by a test schema, or recorded as not needing one."""

from __future__ import annotations

import types
from collections import defaultdict
from dataclasses import dataclass
from typing import Annotated, Any, Union, get_args, get_origin, get_type_hints

from infrahub_sdk.schema.generated.write import (
    AttributeParametersWrite,
    ComputedAttributeJinja2Write,
    ComputedAttributeTransformPythonWrite,
    ComputedAttributeUserWrite,
    DropdownChoiceWrite,
    GenericAttributeWrite,
    GenericSchemaWrite,
    InfrahubSchemaWrite,
    ListAttributeParametersWrite,
    ListAttributeWrite,
    NodeSchemaWrite,
    NumberAttributeParametersWrite,
    NumberAttributeWrite,
    NumberPoolAttributeWrite,
    NumberPoolParametersWrite,
    NumberPoolRangeWrite,
    RelationshipSchemaWrite,
    TextAttributeParametersWrite,
    TextAttributeWrite,
)
from pydantic import BaseModel

from tests.helpers.schema.export_variations import (
    ATTRIBUTE_SETTINGS,
    BRANCH_OVERRIDE,
    DEPRECATED_DISPLAY_FIELDS,
    DEPRECATED_VALIDATION_FIELDS,
    DERIVED_FROM_UNIQUE_ATTRIBUTE,
    HIERARCHY,
    INHERITED_PROPERTIES,
    NUMBER_POOL_RANGES,
    PROFILE_AND_TEMPLATE,
    RELATIONSHIP_SETTINGS,
    VariationSchema,
)


@dataclass(frozen=True)
class CoveredBy:
    variation: VariationSchema


@dataclass(frozen=True)
class NoTestNeeded:
    reason: str


Coverage = CoveredBy | NoTestNeeded

ID_NOT_NEEDED = NoTestNeeded(reason="IDs identify an element on one instance only, so a test schema never sets one")
SHARED_ATTRIBUTE_FIELD = NoTestNeeded(
    reason="declared once for every attribute kind and covered on Text attributes, which share its definition"
)

TEXT_ATTRIBUTE_COVERAGE: dict[str, Coverage] = {
    "id": ID_NOT_NEEDED,
    "name": CoveredBy(variation=ATTRIBUTE_SETTINGS),
    "kind": CoveredBy(variation=ATTRIBUTE_SETTINGS),
    "enum": CoveredBy(variation=ATTRIBUTE_SETTINGS),
    "computed_attribute": CoveredBy(variation=ATTRIBUTE_SETTINGS),
    "choices": NoTestNeeded(reason="only Dropdown attributes take choices, covered on GenericAttributeWrite"),
    "regex": CoveredBy(variation=DEPRECATED_VALIDATION_FIELDS),
    "max_length": CoveredBy(variation=DEPRECATED_VALIDATION_FIELDS),
    "min_length": CoveredBy(variation=DEPRECATED_VALIDATION_FIELDS),
    "label": CoveredBy(variation=ATTRIBUTE_SETTINGS),
    "description": CoveredBy(variation=ATTRIBUTE_SETTINGS),
    "read_only": CoveredBy(variation=ATTRIBUTE_SETTINGS),
    "unique": CoveredBy(variation=DERIVED_FROM_UNIQUE_ATTRIBUTE),
    "optional": CoveredBy(variation=ATTRIBUTE_SETTINGS),
    "branch": CoveredBy(variation=BRANCH_OVERRIDE),
    "order_weight": CoveredBy(variation=ATTRIBUTE_SETTINGS),
    "ordered": NoTestNeeded(reason="only the values of List and JSON attributes have an order, covered on List"),
    "default_value": CoveredBy(variation=ATTRIBUTE_SETTINGS),
    "state": CoveredBy(variation=ATTRIBUTE_SETTINGS),
    "allow_override": CoveredBy(variation=ATTRIBUTE_SETTINGS),
    "deprecation": CoveredBy(variation=ATTRIBUTE_SETTINGS),
    "display": CoveredBy(variation=ATTRIBUTE_SETTINGS),
    "parameters": CoveredBy(variation=ATTRIBUTE_SETTINGS),
}


def _other_attribute_kind_coverage(**own_coverage: Coverage) -> dict[str, Coverage]:
    shared = dict.fromkeys(TEXT_ATTRIBUTE_COVERAGE, SHARED_ATTRIBUTE_FIELD)
    shared["id"] = ID_NOT_NEEDED
    return shared | own_coverage


NODE_AND_GENERIC_COVERAGE: dict[str, Coverage] = {
    "id": ID_NOT_NEEDED,
    "name": CoveredBy(variation=INHERITED_PROPERTIES),
    "namespace": CoveredBy(variation=INHERITED_PROPERTIES),
    "description": CoveredBy(variation=ATTRIBUTE_SETTINGS),
    "label": CoveredBy(variation=ATTRIBUTE_SETTINGS),
    "branch": CoveredBy(variation=BRANCH_OVERRIDE),
    "default_filter": CoveredBy(variation=DEPRECATED_DISPLAY_FIELDS),
    "human_friendly_id": CoveredBy(variation=ATTRIBUTE_SETTINGS),
    "display_label": CoveredBy(variation=ATTRIBUTE_SETTINGS),
    "display_labels": CoveredBy(variation=DEPRECATED_DISPLAY_FIELDS),
    "include_in_menu": CoveredBy(variation=ATTRIBUTE_SETTINGS),
    "menu_placement": CoveredBy(variation=ATTRIBUTE_SETTINGS),
    "icon": CoveredBy(variation=ATTRIBUTE_SETTINGS),
    "order_by": CoveredBy(variation=ATTRIBUTE_SETTINGS),
    "uniqueness_constraints": CoveredBy(variation=ATTRIBUTE_SETTINGS),
    "documentation": CoveredBy(variation=ATTRIBUTE_SETTINGS),
    "state": CoveredBy(variation=ATTRIBUTE_SETTINGS),
    "attributes": CoveredBy(variation=ATTRIBUTE_SETTINGS),
    "relationships": CoveredBy(variation=RELATIONSHIP_SETTINGS),
}

FIELD_COVERAGE: dict[type[BaseModel], dict[str, Coverage]] = {
    NodeSchemaWrite: NODE_AND_GENERIC_COVERAGE
    | {
        "inherit_from": CoveredBy(variation=INHERITED_PROPERTIES),
        "generate_profile": CoveredBy(variation=PROFILE_AND_TEMPLATE),
        "generate_template": CoveredBy(variation=PROFILE_AND_TEMPLATE),
        "parent": CoveredBy(variation=HIERARCHY),
        "children": CoveredBy(variation=HIERARCHY),
    },
    GenericSchemaWrite: NODE_AND_GENERIC_COVERAGE
    | {
        "description": CoveredBy(variation=DEPRECATED_DISPLAY_FIELDS),
        "label": CoveredBy(variation=DEPRECATED_DISPLAY_FIELDS),
        "branch": CoveredBy(variation=DEPRECATED_DISPLAY_FIELDS),
        "human_friendly_id": CoveredBy(variation=INHERITED_PROPERTIES),
        "display_label": CoveredBy(variation=INHERITED_PROPERTIES),
        "include_in_menu": CoveredBy(variation=DEPRECATED_DISPLAY_FIELDS),
        "menu_placement": CoveredBy(variation=INHERITED_PROPERTIES),
        "icon": CoveredBy(variation=INHERITED_PROPERTIES),
        "order_by": CoveredBy(variation=INHERITED_PROPERTIES),
        "uniqueness_constraints": CoveredBy(variation=INHERITED_PROPERTIES),
        "documentation": CoveredBy(variation=DEPRECATED_DISPLAY_FIELDS),
        "state": CoveredBy(variation=DEPRECATED_DISPLAY_FIELDS),
        "attributes": CoveredBy(variation=INHERITED_PROPERTIES),
        "relationships": CoveredBy(variation=INHERITED_PROPERTIES),
        "hierarchical": CoveredBy(variation=HIERARCHY),
        "generate_profile": CoveredBy(variation=DEPRECATED_DISPLAY_FIELDS),
        "restricted_namespaces": CoveredBy(variation=DEPRECATED_DISPLAY_FIELDS),
    },
    TextAttributeWrite: TEXT_ATTRIBUTE_COVERAGE,
    NumberAttributeWrite: _other_attribute_kind_coverage(parameters=CoveredBy(variation=ATTRIBUTE_SETTINGS)),
    ListAttributeWrite: _other_attribute_kind_coverage(
        regex=CoveredBy(variation=DEPRECATED_VALIDATION_FIELDS),
        min_length=CoveredBy(variation=DEPRECATED_VALIDATION_FIELDS),
        max_length=CoveredBy(variation=DEPRECATED_VALIDATION_FIELDS),
        ordered=CoveredBy(variation=ATTRIBUTE_SETTINGS),
        parameters=CoveredBy(variation=ATTRIBUTE_SETTINGS),
    ),
    NumberPoolAttributeWrite: _other_attribute_kind_coverage(
        read_only=CoveredBy(variation=NUMBER_POOL_RANGES),
        parameters=CoveredBy(variation=NUMBER_POOL_RANGES),
    ),
    GenericAttributeWrite: _other_attribute_kind_coverage(
        choices=CoveredBy(variation=ATTRIBUTE_SETTINGS),
        parameters=NoTestNeeded(reason="the parameters of these attribute kinds have no fields"),
    ),
    RelationshipSchemaWrite: {
        "id": ID_NOT_NEEDED,
        "name": CoveredBy(variation=RELATIONSHIP_SETTINGS),
        "peer": CoveredBy(variation=RELATIONSHIP_SETTINGS),
        "kind": CoveredBy(variation=RELATIONSHIP_SETTINGS),
        "label": CoveredBy(variation=RELATIONSHIP_SETTINGS),
        "description": CoveredBy(variation=RELATIONSHIP_SETTINGS),
        "identifier": CoveredBy(variation=RELATIONSHIP_SETTINGS),
        "cardinality": CoveredBy(variation=RELATIONSHIP_SETTINGS),
        "min_count": CoveredBy(variation=RELATIONSHIP_SETTINGS),
        "max_count": CoveredBy(variation=RELATIONSHIP_SETTINGS),
        "common_parent": CoveredBy(variation=RELATIONSHIP_SETTINGS),
        "common_relatives": CoveredBy(variation=RELATIONSHIP_SETTINGS),
        "order_weight": CoveredBy(variation=RELATIONSHIP_SETTINGS),
        "optional": CoveredBy(variation=RELATIONSHIP_SETTINGS),
        "branch": CoveredBy(variation=BRANCH_OVERRIDE),
        "direction": CoveredBy(variation=RELATIONSHIP_SETTINGS),
        "state": CoveredBy(variation=RELATIONSHIP_SETTINGS),
        "on_delete": CoveredBy(variation=RELATIONSHIP_SETTINGS),
        "allow_override": CoveredBy(variation=RELATIONSHIP_SETTINGS),
        "read_only": CoveredBy(variation=RELATIONSHIP_SETTINGS),
        "deprecation": CoveredBy(variation=RELATIONSHIP_SETTINGS),
        "display": CoveredBy(variation=RELATIONSHIP_SETTINGS),
    },
    AttributeParametersWrite: {},
    TextAttributeParametersWrite: {
        "regex": CoveredBy(variation=ATTRIBUTE_SETTINGS),
        "min_length": CoveredBy(variation=ATTRIBUTE_SETTINGS),
        "max_length": CoveredBy(variation=ATTRIBUTE_SETTINGS),
    },
    ListAttributeParametersWrite: {"regex": CoveredBy(variation=ATTRIBUTE_SETTINGS)},
    NumberAttributeParametersWrite: {
        "min_value": CoveredBy(variation=ATTRIBUTE_SETTINGS),
        "max_value": CoveredBy(variation=ATTRIBUTE_SETTINGS),
        "excluded_values": CoveredBy(variation=ATTRIBUTE_SETTINGS),
    },
    NumberPoolParametersWrite: {
        "start_range": CoveredBy(variation=NUMBER_POOL_RANGES),
        "end_range": CoveredBy(variation=NUMBER_POOL_RANGES),
        "ranges": CoveredBy(variation=NUMBER_POOL_RANGES),
        "allocation_scope": CoveredBy(variation=NUMBER_POOL_RANGES),
    },
    NumberPoolRangeWrite: {
        "start": CoveredBy(variation=NUMBER_POOL_RANGES),
        "end": CoveredBy(variation=NUMBER_POOL_RANGES),
        "weight": CoveredBy(variation=NUMBER_POOL_RANGES),
    },
    DropdownChoiceWrite: {
        "name": CoveredBy(variation=ATTRIBUTE_SETTINGS),
        "description": CoveredBy(variation=ATTRIBUTE_SETTINGS),
        "color": CoveredBy(variation=ATTRIBUTE_SETTINGS),
        "label": CoveredBy(variation=ATTRIBUTE_SETTINGS),
        "state": CoveredBy(variation=ATTRIBUTE_SETTINGS),
    },
    ComputedAttributeUserWrite: {"kind": CoveredBy(variation=ATTRIBUTE_SETTINGS)},
    ComputedAttributeJinja2Write: {
        "kind": CoveredBy(variation=ATTRIBUTE_SETTINGS),
        "jinja2_template": CoveredBy(variation=ATTRIBUTE_SETTINGS),
    },
    ComputedAttributeTransformPythonWrite: {
        "kind": CoveredBy(variation=ATTRIBUTE_SETTINGS),
        "transform": CoveredBy(variation=ATTRIBUTE_SETTINGS),
    },
}

ROOT_WRITE_MODELS: tuple[type[BaseModel], ...] = (NodeSchemaWrite, GenericSchemaWrite)


def _models_in_annotation(annotation: Any) -> list[type[BaseModel]]:
    if isinstance(annotation, type) and issubclass(annotation, BaseModel):
        return [annotation]
    if get_origin(annotation) in {Annotated, Union, types.UnionType, list}:
        return [model for argument in get_args(annotation) for model in _models_in_annotation(argument)]
    return []


def _write_models_reachable_from(roots: tuple[type[BaseModel], ...]) -> set[type[BaseModel]]:
    reached: set[type[BaseModel]] = set()
    pending = list(roots)
    while pending:
        model = pending.pop()
        if model in reached:
            continue
        reached.add(model)
        # Pydantic keeps an annotation that names a later definition of the module as an unresolved forward reference.
        annotations = get_type_hints(model, include_extras=True)
        for field_name in model.model_fields:
            pending.extend(_models_in_annotation(annotations[field_name]))
    return reached


def _fields_set_per_model(value: object, fields_set: dict[type[BaseModel], set[str]]) -> None:
    if isinstance(value, BaseModel):
        fields_set[type(value)].update(value.model_fields_set)
        for field_name in value.model_fields_set:
            _fields_set_per_model(getattr(value, field_name), fields_set)
    elif isinstance(value, list):
        for item in value:
            _fields_set_per_model(item, fields_set)


def _fields_set_by(variation: VariationSchema) -> dict[type[BaseModel], set[str]]:
    fields_set: dict[type[BaseModel], set[str]] = defaultdict(set)
    _fields_set_per_model(InfrahubSchemaWrite.model_validate(variation.payload()), fields_set)
    return fields_set


def test_every_write_model_field_has_a_coverage_entry() -> None:
    write_models = _write_models_reachable_from(ROOT_WRITE_MODELS)

    missing = sorted(
        f"{model.__name__}.{field_name}"
        for model in write_models
        for field_name in model.model_fields
        if field_name not in FIELD_COVERAGE.get(model, {})
    )

    assert missing == []


def test_every_coverage_entry_names_an_existing_field() -> None:
    write_models = _write_models_reachable_from(ROOT_WRITE_MODELS)

    unknown = sorted(
        f"{model.__name__}.{field_name}"
        for model, coverage in FIELD_COVERAGE.items()
        for field_name in coverage
        if model not in write_models or field_name not in model.model_fields
    )
    unknown_models = sorted(model.__name__ for model in FIELD_COVERAGE if model not in write_models)

    assert unknown == []
    assert unknown_models == []


def test_every_covering_test_schema_sets_the_field() -> None:
    fields_set_by_variation: dict[str, dict[type[BaseModel], set[str]]] = {}
    not_set: list[str] = []
    for model, coverage in FIELD_COVERAGE.items():
        for field_name, entry in coverage.items():
            if not isinstance(entry, CoveredBy):
                continue
            variation = entry.variation
            if variation.name not in fields_set_by_variation:
                fields_set_by_variation[variation.name] = _fields_set_by(variation)
            if field_name not in fields_set_by_variation[variation.name].get(model, set()):
                not_set.append(f"{model.__name__}.{field_name} in {variation.name}")

    assert sorted(not_set) == []
