import pytest

from infrahub.core.branch import Branch
from infrahub.core.constants import HashableModelState
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
    schema_branch.process()

    candidate_schema = schema_branch.duplicate()
    tag = candidate_schema.get(name="TestingTag", duplicate=True)
    tag.state = HashableModelState.ABSENT
    candidate_schema.set(name="TestingTag", schema=tag)

    with pytest.raises(ValueError, match="Relationship 'tags' is referring an invalid peer 'TestingTag'"):
        candidate_schema.process()


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
    schema_branch.process()

    candidate_schema = schema_branch.duplicate()
    parent = candidate_schema.get(name="TestingParent", duplicate=True)
    parent.state = HashableModelState.ABSENT
    candidate_schema.set(name="TestingParent", schema=parent)
    candidate_schema.process()

    schema_diff = schema_branch.diff(other=candidate_schema)
    assert "TestingParent" in schema_diff.removed

    with pytest.raises(ValueError, match="'TestingParent' has been removed but is still referenced"):
        candidate_schema.validate_node_deletions(diff=schema_diff)


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
    schema_branch.process()

    candidate_schema = schema_branch.duplicate()
    alpha = candidate_schema.get(name="TestingAlpha", duplicate=True)
    alpha.state = HashableModelState.ABSENT
    candidate_schema.set(name="TestingAlpha", schema=alpha)
    candidate_schema.process()

    schema_diff = schema_branch.diff(other=candidate_schema)
    assert "TestingAlpha" in schema_diff.removed

    candidate_schema.validate_node_deletions(diff=schema_diff)


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
    schema_branch.process()

    candidate_schema = schema_branch.duplicate()
    for kind in ("TestingParent", "TestingChild", "TestingSibling"):
        node = candidate_schema.get(name=kind, duplicate=True)
        node.state = HashableModelState.ABSENT
        candidate_schema.set(name=kind, schema=node)
    candidate_schema.process()

    schema_diff = schema_branch.diff(other=candidate_schema)
    assert {"TestingParent", "TestingChild", "TestingSibling"}.issubset(schema_diff.removed.keys())

    candidate_schema.validate_node_deletions(diff=schema_diff)
