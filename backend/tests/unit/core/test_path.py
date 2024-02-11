from infrahub.core.constants import PathType
from infrahub.core.path import DataPath, SchemaPath


def test_data_path():
    path1 = DataPath(
        path_type=PathType.ATTRIBUTE,
        node_id="12345678-acbd-abcd-1234-1234567890ab",
        kind="TestPerson",
        field_name="height",
        property_name="HAS_VALUE",
    )

    assert str(path1) == "data/12345678-acbd-abcd-1234-1234567890ab/height/value"


def test_schema_path():
    path1 = SchemaPath(
        path_type=PathType.ATTRIBUTE,
        schema_kind="TestPerson",
        field_name="height",
    )
    assert path1.get_path() == "schema/TestPerson/height"

    path1 = SchemaPath(
        path_type=PathType.ATTRIBUTE, schema_kind="TestPerson", field_name="height", property_name="description"
    )
    assert path1.get_path() == "schema/TestPerson/height/description"
