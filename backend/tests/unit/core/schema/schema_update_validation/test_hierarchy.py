from typing import Any

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


LOCATION_GENERIC: dict[str, Any] = {
    "name": "Generic",
    "namespace": "Location",
    "attributes": [{"name": "name", "kind": "Text", "unique": True}],
}
REGION_SITE_HIERARCHY: dict[str, dict[str, str]] = {
    "LocationRegion": {"parent": "", "children": "LocationSite"},
    "LocationSite": {"parent": "LocationRegion", "children": ""},
}


def _location_root(hierarchical: bool, nodes: list[dict[str, Any]]) -> SchemaRoot:
    return SchemaRoot(version="1.0", generics=[{**LOCATION_GENERIC, "hierarchical": hierarchical}], nodes=nodes)


def _location_nodes(hierarchy: bool, extra: dict[str, dict[str, Any]] | None = None) -> list[dict[str, Any]]:
    nodes = []
    for kind, hierarchy_fields in REGION_SITE_HIERARCHY.items():
        node: dict[str, Any] = {"name": kind.removeprefix("Location"), "namespace": "Location"}
        node["inherit_from"] = ["LocationGeneric"]
        if hierarchy:
            node.update(hierarchy_fields)
        node.update((extra or {}).get(kind, {}))
        nodes.append(node)
    return nodes


def _stored_schema(root: SchemaRoot) -> SchemaBranch:
    """Return a processed schema whose kinds carry an id, as they do once saved in the database."""
    schema = SchemaBranch(cache={}, name="test")
    schema.load_schema(schema=root)
    schema.process()
    for kind in list(schema.nodes) + list(schema.generics):
        stored = schema.get(name=kind)
        stored.id = f"id-{kind}"
        schema.set(name=kind, schema=stored)
    return schema


def _load_on_top(schema: SchemaBranch, root: SchemaRoot) -> tuple[SchemaBranch, list[str]]:
    candidate = schema.duplicate()
    candidate.load_schema(schema=root)
    candidate.process()
    result = schema.validate_update(other=candidate, diff=schema.diff(other=candidate))
    return candidate, [error.to_string() for error in result.errors]


def test_empty_parent_and_children_restrict_kinds_that_become_hierarchical() -> None:
    """Existing kinds joining a hierarchy keep an empty parent or children instead of falling back to the generic."""
    schema = _stored_schema(_location_root(hierarchical=False, nodes=_location_nodes(hierarchy=False)))

    candidate, errors = _load_on_top(schema, _location_root(hierarchical=True, nodes=_location_nodes(hierarchy=True)))

    assert errors == []
    region = candidate.get_node(name="LocationRegion")
    site = candidate.get_node(name="LocationSite")
    assert (region.parent, region.children) == ("", "LocationSite")
    assert (site.parent, site.children) == ("LocationRegion", "")
