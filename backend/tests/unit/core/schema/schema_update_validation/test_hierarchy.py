from infrahub.core.schema import SchemaRoot
from infrahub.core.schema.schema_branch import SchemaBranch


def _location_schema(hierarchical: bool) -> SchemaBranch:
    hierarchy_fields: dict[str, dict[str, str]] = {
        "Region": {"parent": "", "children": "LocationSite"},
        "Site": {"parent": "LocationRegion", "children": ""},
    }
    schema = SchemaBranch(cache={}, name="test")
    schema.load_schema(
        schema=SchemaRoot(
            version="1.0",
            generics=[
                {
                    "name": "Generic",
                    "namespace": "Location",
                    "hierarchical": hierarchical,
                    "attributes": [{"name": "name", "kind": "Text", "unique": True}],
                }
            ],
            nodes=[
                {
                    "name": name,
                    "namespace": "Location",
                    "inherit_from": ["LocationGeneric"],
                    **(fields if hierarchical else {}),
                }
                for name, fields in hierarchy_fields.items()
            ],
        )
    )
    schema.process()
    return schema


async def test_making_existing_kinds_hierarchical_is_validated_rather_than_refused() -> None:
    """Turning a generic and the nodes inheriting from it into a hierarchy is checked against stored data, not refused outright."""
    schema = _location_schema(hierarchical=False)
    candidate = _location_schema(hierarchical=True)

    diff = schema.diff(other=candidate)
    result = schema.validate_update(other=candidate, diff=diff)

    assert result.errors == []
