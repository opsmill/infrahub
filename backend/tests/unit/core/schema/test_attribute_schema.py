from infrahub.core.schema import AttributeSchema


def test_attribute_schema_update_clears_default_value() -> None:
    """Verify that AttributeSchema.update() clears default_value when the source has explicit default_value=None."""
    existing = AttributeSchema(name="color", kind="Text", default_value="#444444", optional=True)
    assert existing.default_value == "#444444"

    update_source = AttributeSchema(name="color", kind="Text", default_value=None, optional=False)
    assert "default_value" in update_source.model_fields_set

    existing.update(update_source)

    assert existing.default_value is None
    assert existing.optional is False


def test_attribute_schema_update_preserves_default_value() -> None:
    """Verify AttributeSchema.update() preserves default_value when source omits it (not in model_fields_set)."""
    existing = AttributeSchema(name="color", kind="Text", default_value="#444444", optional=True)
    assert existing.default_value == "#444444"

    update_source = AttributeSchema(name="color", kind="Text", optional=True)
    assert "default_value" not in update_source.model_fields_set

    existing.update(update_source)
    assert existing.default_value == "#444444"


def test_attribute_schema_update_default_value_type_distinction() -> None:
    """Verify AttributeSchema.update() correctly distinguishes default_value=None (clears) from falsy values (preserves)."""
    attr1 = AttributeSchema(name="val", kind="Text", default_value="hello")
    attr1.update(AttributeSchema(name="val", kind="Text", default_value=None))
    assert attr1.default_value is None

    attr2 = AttributeSchema(name="val", kind="Text", default_value="hello")
    attr2.update(AttributeSchema(name="val", kind="Text", default_value=""))
    assert not attr2.default_value

    attr3 = AttributeSchema(name="val", kind="Number", default_value=42)
    attr3.update(AttributeSchema(name="val", kind="Number", default_value=0))
    assert attr3.default_value == 0

    attr4 = AttributeSchema(name="val", kind="Boolean", default_value=True)
    attr4.update(AttributeSchema(name="val", kind="Boolean", default_value=False))
    assert attr4.default_value is False


def test_attribute_schema_update_to_mandatory_triggers_migration() -> None:
    """Verify that updating optional from True to False is detected as a diff change."""
    existing = AttributeSchema(name="role", kind="Text", default_value="spine", optional=True)
    assert existing.optional is True

    update_source = AttributeSchema(name="role", kind="Text", optional=False, default_value=None)
    assert "default_value" in update_source.model_fields_set

    existing.update(update_source)

    assert existing.optional is False
    assert existing.default_value is None

    original = AttributeSchema(name="role", kind="Text", default_value="spine", optional=True)
    diff = original.diff(existing)
    assert "optional" in diff.changed
    assert "default_value" in diff.changed


def test_attribute_schema_roundtrip_mandatory_optional_mandatory() -> None:
    """Verify an attribute can go mandatory -> optional and default -> mandatory through sequential updates."""
    attr = AttributeSchema(name="role", kind="Text", optional=False)
    assert attr.optional is False
    assert attr.default_value is None

    attr.update(AttributeSchema(name="role", kind="Text", optional=True, default_value="leaf"))
    assert attr.optional is True
    assert attr.default_value == "leaf"

    attr.update(AttributeSchema(name="role", kind="Text", optional=False, default_value=None))
    assert attr.optional is False
    assert attr.default_value is None
