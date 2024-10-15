import enum

from infrahub.core.enums import generate_python_enum


def test_generate_python_enum():
    enum_class = generate_python_enum(name="Color", options=["blue", "red"])
    assert isinstance(enum_class, enum.EnumType)

    enum_blue = enum_class("blue")
    assert isinstance(enum_blue, enum.Enum)
    assert {enum.name for enum in enum_class} == {"RED", "BLUE"}


def test_generate_python_enum_with_integers():
    enum_class = generate_python_enum(name="DHGroup", options=[2, 5, 14])
    assert isinstance(enum_class, enum.EnumType)

    enum_two = enum_class(2)
    assert isinstance(enum_two, enum.Enum)
    assert {enum.name for enum in enum_class} == {"2", "5", "14"}
    assert {enum.value for enum in enum_class} == {2, 5, 14}
