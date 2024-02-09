from infrahub.core.constants import PathResourceType, PathType
from infrahub.core.path import InfrahubPath


def test_data_path():
    path1 = InfrahubPath(
        resource_type=PathResourceType.DATA,
        path_type=PathType.ATTRIBUTE,
        node_id="12345678-acbd-abcd-1234-1234567890ab",
        kind="TestPerson",
        field_name="height",
        property_name="HAS_VALUE",
    )

    assert str(path1) == "data/12345678-acbd-abcd-1234-1234567890ab/height/value"
