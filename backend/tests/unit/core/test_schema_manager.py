import pytest

from infrahub.core.constants import BranchSupportType
from infrahub.core.schema import SchemaRoot
from infrahub.core.schema_manager import SchemaBranch


async def test_schema_menu_placement_errors():
    """Validate that menu placements points to objects that exists in the schema."""
    FULL_SCHEMA = {
        "version": "1.0",
        "nodes": [
            {
                "name": "Criticality",
                "namespace": "Test",
                "default_filter": "name__value",
                "branch": BranchSupportType.AWARE.value,
                "attributes": [
                    {"name": "name", "kind": "Text", "unique": True},
                ],
            },
            {
                "name": "SubObject",
                "namespace": "Test",
                "menu_placement": "NoSuchObject",
                "default_filter": "name__value",
                "branch": BranchSupportType.AWARE.value,
                "attributes": [
                    {"name": "name", "kind": "Text", "unique": True},
                ],
            },
        ],
    }

    schema = SchemaBranch(cache={})
    schema.load_schema(schema=SchemaRoot(**FULL_SCHEMA))

    with pytest.raises(ValueError) as exc:
        schema.process()

    assert str(exc.value) == "TestSubObject: NoSuchObject is not a valid menu placement"
