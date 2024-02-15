import pytest

from infrahub.core.constants import PathType, SchemaPathType
from infrahub.core.path import DataPath, SchemaPath


def test_data_path():
    path1 = DataPath(
        branch="branch",
        path_type=PathType.ATTRIBUTE,
        node_id="12345678-acbd-abcd-1234-1234567890ab",
        kind="TestPerson",
        field_name="height",
        property_name="HAS_VALUE",
    )

    assert str(path1) == "data/12345678-acbd-abcd-1234-1234567890ab/height/value"


@pytest.mark.parametrize(
    "path_type,kind,field_name,prop_name,expected",
    [
        (SchemaPathType.ATTRIBUTE, "TestPerson", "height", None, "schema/TestPerson/height"),
        (SchemaPathType.ATTRIBUTE, "TestPerson", "height", "description", "schema/TestPerson/height/description"),
        (SchemaPathType.RELATIONSHIP, "TestPerson", "cars", None, "schema/TestPerson/cars"),
        (SchemaPathType.NODE, "TestPerson", "height", "height", "schema/TestPerson/height"),
    ],
)
def test_schema_path(path_type, kind, field_name, prop_name, expected):
    path = SchemaPath(
        path_type=path_type,
        schema_kind=kind,
        field_name=field_name,
        property_name=prop_name,
    )
    assert path.get_path() == expected
