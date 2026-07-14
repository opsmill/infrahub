from typing import Any

from infrahub.core.constants import UpdateValidationErrorType
from infrahub.core.models import SchemaUpdateValidationResult
from infrahub.core.schema import AttributeSchema, SchemaRoot
from infrahub.core.schema.schema_branch import SchemaBranch

WIDGET_GADGET_SCHEMA: dict[str, Any] = {
    "version": "1.0",
    "nodes": [
        {
            "name": "Widget",
            "namespace": "Test",
            "attributes": [{"name": "name", "kind": "Text", "unique": True}],
            "relationships": [
                {
                    "name": "gadgets",
                    "peer": "TestGadget",
                    "cardinality": "many",
                    "identifier": "widget__gadget",
                    "optional": True,
                }
            ],
        },
        {
            "name": "Gadget",
            "namespace": "Test",
            "attributes": [{"name": "name", "kind": "Text", "unique": True}],
        },
    ],
}


def _build_schema() -> SchemaBranch:
    schema = SchemaBranch(cache={}, name="test")
    schema.load_schema(schema=SchemaRoot(**WIDGET_GADGET_SCHEMA))
    schema.process()
    return schema


async def test_relationship_identifier_update_is_not_supported() -> None:
    """Changing a relationship's identifier must be rejected rather than silently orphaning data."""
    schema = _build_schema()

    candidate = schema.duplicate()
    widget = candidate.get_node(name="TestWidget", duplicate=True)
    relationship = widget.get_relationship(name="gadgets")
    relationship.identifier = "widget__gadget_renamed"
    candidate.set(name="TestWidget", schema=widget)

    diff = schema.diff(other=candidate)
    result = schema.validate_update(other=candidate, diff=diff)

    assert len(result.errors) == 1
    error = result.errors[0]
    assert error.error == UpdateValidationErrorType.NOT_SUPPORTED
    assert error.path.schema_kind == "TestWidget"
    assert error.path.field_name == "gadgets"
    assert error.path.property_name == "identifier"
    assert result.migrations == []


async def test_process_diff_node_removed_and_changed() -> None:
    """A node removed on one side and changed on the other must be treated as a removal.

    Such a node appears in both `removed` and `changed` of the merged 3-way diff. The
    migration calculation runs against the post-merge target schema, from which the node
    is already gone, so processing it as a changed element would raise SchemaNotFoundError.
    """
    initial = _build_schema()

    # Source side removes the node entirely.
    source = initial.duplicate()
    source.delete(name="TestWidget")
    source.process()

    # Destination side keeps the node but modifies it, so it lands in `changed`.
    destination = initial.duplicate()
    widget = destination.get_node(name="TestWidget", duplicate=True)
    widget.attributes.append(AttributeSchema(name="color", kind="Text", optional=True))
    destination.set(name="TestWidget", schema=widget)
    destination.process()

    diff_3way = initial.diff(other=source) + initial.diff(other=destination)
    assert "TestWidget" in diff_3way.removed
    assert "TestWidget" in diff_3way.changed

    # The post-merge target schema no longer contains the removed node.
    target = destination.duplicate()
    target.delete(name="TestWidget")
    target.process()

    result = SchemaUpdateValidationResult.init(diff=diff_3way, schema=target)

    migrations = {(migration.path.schema_kind, migration.migration_name) for migration in result.migrations}
    assert ("TestWidget", "node.remove") in migrations
