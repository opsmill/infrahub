from infrahub.core.constants import SchemaAttributeDisplay
from infrahub.core.schema import AttributeSchema, RelationshipSchema


def test_attribute_schema_display_defaults_to_default() -> None:
    attr = AttributeSchema(name="test", kind="Text")
    assert attr.display == SchemaAttributeDisplay.DEFAULT


def test_relationship_schema_display_defaults_to_default() -> None:
    rel = RelationshipSchema(name="test", peer="TestNode")
    assert rel.display == SchemaAttributeDisplay.DEFAULT


def test_attribute_schema_display_can_be_set_to_extra() -> None:
    attr = AttributeSchema(name="test", kind="Text", display=SchemaAttributeDisplay.EXTRA)
    assert attr.display == SchemaAttributeDisplay.EXTRA


def test_relationship_schema_display_can_be_set_to_extra() -> None:
    rel = RelationshipSchema(name="test", peer="TestNode", display=SchemaAttributeDisplay.EXTRA)
    assert rel.display == SchemaAttributeDisplay.EXTRA
