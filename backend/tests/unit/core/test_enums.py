import enum

from infrahub.core.enums import generate_python_enum


def test_generate_python_enum():
    enum_class = generate_python_enum(name="Color", options=["blue", "red"])
    assert isinstance(enum_class, enum.EnumType)

    enum_blue = enum_class("blue")
    assert isinstance(enum_blue, enum.Enum)
