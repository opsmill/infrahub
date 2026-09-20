"""Lookup of a single Python transform computed attribute on a processed schema branch."""

from __future__ import annotations

from infrahub.core.constants import ComputedAttributeKind
from infrahub.core.schema import AttributeSchema, NodeSchema, SchemaRoot
from infrahub.core.schema.computed_attribute import ComputedAttribute
from infrahub.core.schema.schema_branch import SchemaBranch

WIDGET_KIND = "TestingWidget"


def _python_attribute(name: str, transform: str) -> AttributeSchema:
    return AttributeSchema(
        name=name,
        kind="Text",
        optional=True,
        read_only=True,
        computed_attribute=ComputedAttribute(kind=ComputedAttributeKind.TRANSFORM_PYTHON, transform=transform),
    )


def _schema_branch() -> SchemaBranch:
    """A kind carrying two Python computed attributes, plus a Jinja2 one."""
    schema_branch = SchemaBranch(cache={}, name="test")
    schema_branch.load_schema(
        schema=SchemaRoot(
            nodes=[
                NodeSchema(
                    name="Widget",
                    namespace="Testing",
                    default_filter="name__value",
                    attributes=[
                        AttributeSchema(name="name", kind="Text", optional=False, unique=True),
                        _python_attribute("pitch", "WidgetPitch"),
                        _python_attribute("slogan", "WidgetSlogan"),
                        AttributeSchema(
                            name="label",
                            kind="Text",
                            optional=True,
                            read_only=True,
                            computed_attribute=ComputedAttribute(
                                kind=ComputedAttributeKind.JINJA2, jinja2_template="{{ name__value }}"
                            ),
                        ),
                    ],
                )
            ]
        )
    )
    schema_branch.process()
    return schema_branch


def test_only_the_requested_python_attribute_is_selected() -> None:
    """A kind with two attributes would otherwise run its transform twice per submission."""
    computed_attributes = _schema_branch().computed_attributes

    pitch = computed_attributes.get_python_transform_attribute(WIDGET_KIND, "pitch")
    slogan = computed_attributes.get_python_transform_attribute(WIDGET_KIND, "slogan")

    assert pitch is not None
    assert pitch.transform == "WidgetPitch"
    assert slogan is not None
    assert slogan.transform == "WidgetSlogan"


def test_a_name_that_is_not_a_python_transform_selects_nothing() -> None:
    """The caller only knows how to run a transform, so a Jinja2 or absent name is nobody's work."""
    computed_attributes = _schema_branch().computed_attributes

    assert computed_attributes.get_python_transform_attribute(WIDGET_KIND, "label") is None
    assert computed_attributes.get_python_transform_attribute(WIDGET_KIND, "name") is None
    assert computed_attributes.get_python_transform_attribute(WIDGET_KIND, "missing") is None
    assert computed_attributes.get_python_transform_attribute("TestingUnknown", "pitch") is None
