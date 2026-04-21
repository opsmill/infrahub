import pytest

from infrahub.core.branch import Branch
from infrahub.core.schema import SchemaRoot
from infrahub.core.schema.schema_branch import SchemaBranch
from infrahub.database import InfrahubDatabase


async def test_schema_branch_validate_node_deletion(
    db: InfrahubDatabase, reset_registry: None, default_branch: Branch, register_internal_models_schema: SchemaBranch
) -> None:
    FULL_SCHEMA = {
        "nodes": [
            {
                "name": "Criticality",
                "namespace": "Testing",
                "default_filter": "name__value",
                "label": "Criticality",
                "attributes": [
                    {"name": "name", "kind": "Text", "label": "Name", "unique": True},
                    {"name": "level", "kind": "Number", "label": "Level"},
                    {"name": "color", "kind": "Text", "label": "Color", "default_value": "#444444"},
                    {"name": "description", "kind": "Text", "label": "Description", "optional": True},
                ],
                "relationships": [
                    {
                        "name": "tags",
                        "peer": "TestingTag",
                        "label": "Tags",
                        "optional": True,
                        "cardinality": "many",
                    }
                ],
            },
            {
                "name": "Tag",
                "namespace": "Testing",
                "label": "Tag",
                "default_filter": "name__value",
                "attributes": [
                    {"name": "name", "kind": "Text", "label": "Name", "unique": True},
                    {"name": "description", "kind": "Text", "label": "Description", "optional": True},
                ],
            },
        ]
    }
    schema = SchemaRoot(**FULL_SCHEMA)
    schema.generate_uuid()
    schema_branch = SchemaBranch(cache={}, name="test")
    schema_branch.load_schema(schema=schema)

    FULL_SCHEMA["nodes"].pop(1)

    broken_schema = SchemaRoot(**FULL_SCHEMA)
    broken_schema_branch = SchemaBranch(cache={}, name="test-broken")
    broken_schema_branch.load_schema(schema=broken_schema)

    diff = schema_branch.diff(other=broken_schema_branch)
    assert "TestingTag" in diff.removed

    with pytest.raises(ValueError, match="'TestingTag' has been removed but is still referenced"):
        schema_branch.validate_node_deletions(diff=diff)


async def test_schema_branch_validate_node_deletion_inherit_from(
    db: InfrahubDatabase, reset_registry: None, default_branch: Branch, register_internal_models_schema: SchemaBranch
) -> None:
    """Deleting a generic that is still listed in another node's inherit_from must be rejected."""
    FULL_SCHEMA = {
        "generics": [
            {
                "name": "Parent",
                "namespace": "Testing",
                "attributes": [
                    {"name": "name", "kind": "Text", "label": "Name", "unique": True},
                ],
            },
        ],
        "nodes": [
            {
                "name": "Child",
                "namespace": "Testing",
                "inherit_from": ["TestingParent"],
                "attributes": [
                    {"name": "description", "kind": "Text", "label": "Description", "optional": True},
                ],
            },
        ],
    }
    schema = SchemaRoot(**FULL_SCHEMA)
    schema.generate_uuid()
    schema_branch = SchemaBranch(cache={}, name="test")
    schema_branch.load_schema(schema=schema)

    FULL_SCHEMA["generics"].pop(0)

    broken_schema = SchemaRoot(**FULL_SCHEMA)
    broken_schema_branch = SchemaBranch(cache={}, name="test-broken")
    broken_schema_branch.load_schema(schema=broken_schema)

    diff = schema_branch.diff(other=broken_schema_branch)
    assert "TestingParent" in diff.removed

    with pytest.raises(ValueError, match="'TestingParent' has been removed but is still referenced"):
        schema_branch.validate_node_deletions(diff=diff)


async def test_schema_branch_validate_node_deletion_iterates_generics_safely(
    db: InfrahubDatabase, reset_registry: None, default_branch: Branch, register_internal_models_schema: SchemaBranch
) -> None:
    """validate_node_deletions must iterate every schema kind without touching inherit_from on generics."""
    FULL_SCHEMA = {
        "generics": [
            {
                "name": "KeptGeneric",
                "namespace": "Testing",
                "attributes": [
                    {"name": "name", "kind": "Text", "label": "Name", "unique": True},
                ],
            },
        ],
        "nodes": [
            {
                "name": "Alpha",
                "namespace": "Testing",
                "attributes": [
                    {"name": "name", "kind": "Text", "label": "Name", "unique": True},
                ],
            },
            {
                "name": "Beta",
                "namespace": "Testing",
                "attributes": [
                    {"name": "name", "kind": "Text", "label": "Name", "unique": True},
                ],
            },
        ],
    }
    schema = SchemaRoot(**FULL_SCHEMA)
    schema.generate_uuid()
    schema_branch = SchemaBranch(cache={}, name="test")
    schema_branch.load_schema(schema=schema)

    FULL_SCHEMA["nodes"].pop(0)

    updated_schema = SchemaRoot(**FULL_SCHEMA)
    updated_schema_branch = SchemaBranch(cache={}, name="test-updated")
    updated_schema_branch.load_schema(schema=updated_schema)

    diff = schema_branch.diff(other=updated_schema_branch)
    assert "TestingAlpha" in diff.removed

    schema_branch.validate_node_deletions(diff=diff)


async def test_schema_branch_validate_node_deletion_removes_generic_and_child_together(
    db: InfrahubDatabase, reset_registry: None, default_branch: Branch, register_internal_models_schema: SchemaBranch
) -> None:
    """Removing a generic AND the nodes that inherit from it in the same diff must be accepted."""
    FULL_SCHEMA = {
        "generics": [
            {
                "name": "Parent",
                "namespace": "Testing",
                "attributes": [
                    {"name": "name", "kind": "Text", "label": "Name", "unique": True},
                ],
            },
        ],
        "nodes": [
            {
                "name": "Child",
                "namespace": "Testing",
                "inherit_from": ["TestingParent"],
                "attributes": [
                    {"name": "description", "kind": "Text", "label": "Description", "optional": True},
                ],
            },
            {
                "name": "Sibling",
                "namespace": "Testing",
                "inherit_from": ["TestingParent"],
                "attributes": [
                    {"name": "description", "kind": "Text", "label": "Description", "optional": True},
                ],
            },
        ],
    }
    schema = SchemaRoot(**FULL_SCHEMA)
    schema.generate_uuid()
    schema_branch = SchemaBranch(cache={}, name="test")
    schema_branch.load_schema(schema=schema)

    EMPTY_SCHEMA: dict[str, list[dict]] = {"generics": [], "nodes": []}
    updated_schema = SchemaRoot(**EMPTY_SCHEMA)
    updated_schema_branch = SchemaBranch(cache={}, name="test-updated")
    updated_schema_branch.load_schema(schema=updated_schema)

    diff = schema_branch.diff(other=updated_schema_branch)
    assert {"TestingParent", "TestingChild", "TestingSibling"}.issubset(diff.removed.keys())

    schema_branch.validate_node_deletions(diff=diff)
