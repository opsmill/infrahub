from __future__ import annotations

from infrahub.computed_attribute.recompute_resolution import RecomputeResolver
from infrahub.core.constants import ComputedAttributeKind
from infrahub.core.schema import AttributeSchema, NodeSchema
from infrahub.core.schema.computed_attribute import ComputedAttribute
from infrahub.core.schema.schema_branch_computed import ComputedAttributes, PythonDefinition

TRANSFORM_NAME = "compute_description"
TRANSFORM_ID = "17e3f1a2-0000-0000-0000-000000000001"
OTHER_TRANSFORM_NAME = "compute_label"


def _attribute(name: str, transform: str) -> AttributeSchema:
    return AttributeSchema(
        name=name,
        kind="Text",
        optional=True,
        computed_attribute=ComputedAttribute(kind=ComputedAttributeKind.TRANSFORM_PYTHON, transform=transform),
    )


def _mapping(*nodes_attributes: tuple[NodeSchema, AttributeSchema]) -> dict[str, list[PythonDefinition]]:
    computed_attributes = ComputedAttributes()
    for node, attribute in nodes_attributes:
        computed_attributes.add_python_attribute(node=node, attribute=attribute)
    return computed_attributes.python_attributes_by_transform


def test_transform_feeding_one_attribute() -> None:
    node = NodeSchema(name="Car", namespace="Testing")
    attribute = _attribute(name="description", transform=TRANSFORM_NAME)
    resolver = RecomputeResolver(attributes_by_transform=_mapping((node, attribute)))

    resolved = resolver.resolve(transform_name=TRANSFORM_NAME, transform_id=TRANSFORM_ID)

    assert [(definition.kind, definition.attribute.name) for definition in resolved] == [("TestingCar", "description")]


def test_transform_feeding_many_attributes() -> None:
    car = NodeSchema(name="Car", namespace="Testing")
    person = NodeSchema(name="Person", namespace="Testing")
    car_attribute = _attribute(name="description", transform=TRANSFORM_NAME)
    person_attribute = _attribute(name="summary", transform=TRANSFORM_NAME)
    resolver = RecomputeResolver(attributes_by_transform=_mapping((car, car_attribute), (person, person_attribute)))

    resolved = resolver.resolve(transform_name=TRANSFORM_NAME, transform_id=TRANSFORM_ID)

    assert {(definition.kind, definition.attribute.name) for definition in resolved} == {
        ("TestingCar", "description"),
        ("TestingPerson", "summary"),
    }


def test_transform_feeding_zero_attributes() -> None:
    car = NodeSchema(name="Car", namespace="Testing")
    attribute = _attribute(name="description", transform=OTHER_TRANSFORM_NAME)
    resolver = RecomputeResolver(attributes_by_transform=_mapping((car, attribute)))

    resolved = resolver.resolve(transform_name=TRANSFORM_NAME, transform_id=TRANSFORM_ID)

    assert resolved == []


def test_transform_wired_by_id() -> None:
    node = NodeSchema(name="Car", namespace="Testing")
    attribute = _attribute(name="description", transform=TRANSFORM_ID)
    resolver = RecomputeResolver(attributes_by_transform=_mapping((node, attribute)))

    resolved = resolver.resolve(transform_name=TRANSFORM_NAME, transform_id=TRANSFORM_ID)

    assert [(definition.kind, definition.attribute.name) for definition in resolved] == [("TestingCar", "description")]


def test_transform_wired_by_name_and_id_returns_both() -> None:
    car = NodeSchema(name="Car", namespace="Testing")
    person = NodeSchema(name="Person", namespace="Testing")
    by_name = _attribute(name="description", transform=TRANSFORM_NAME)
    by_id = _attribute(name="summary", transform=TRANSFORM_ID)
    resolver = RecomputeResolver(attributes_by_transform=_mapping((car, by_name), (person, by_id)))

    resolved = resolver.resolve(transform_name=TRANSFORM_NAME, transform_id=TRANSFORM_ID)

    assert {(definition.kind, definition.attribute.name) for definition in resolved} == {
        ("TestingCar", "description"),
        ("TestingPerson", "summary"),
    }


def test_transform_feeding_nothing_returns_empty() -> None:
    # An empty mapping (no transform feeds any attribute) resolves to nothing from the lookup alone.
    resolver = RecomputeResolver(attributes_by_transform={})

    resolved = resolver.resolve(transform_name=TRANSFORM_NAME, transform_id=TRANSFORM_ID)

    assert resolved == []
