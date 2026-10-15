import pytest
from structlog.testing import capture_logs

from infrahub.core.schema import (
    AttributeSchema,
    NodeSchema,
    RelationshipSchema,
    SchemaRoot,
    core_models,
    internal_schema,
)
from infrahub.core.schema.schema_branch import SchemaBranch


def _deprecated_widget(namespace: str) -> NodeSchema:
    return NodeSchema(
        name="Widget",
        namespace=namespace,
        attributes=[
            AttributeSchema(name="name", kind="Text"),
            AttributeSchema(name="legacy_code", kind="Text", optional=False, deprecation="Use name instead"),
        ],
        relationships=[
            RelationshipSchema(
                name="legacy_peer",
                peer=f"{namespace}Widget",
                cardinality="one",
                optional=False,
                deprecation="No longer tracked",
            ),
        ],
    )


def test_deprecated_fields_of_a_user_node_are_reported_and_made_optional() -> None:
    schema_branch = SchemaBranch(cache={}, name="test")
    schema_branch.load_schema(schema=SchemaRoot(nodes=[_deprecated_widget(namespace="Testing")]))

    with capture_logs() as records:
        schema_branch.process_deprecations()

    assert records == [
        {
            "event": "'legacy_code' for 'TestingWidget' has been marked as deprecated, remember to clean it up",
            "log_level": "warning",
        },
        {
            "event": "'legacy_peer' for 'TestingWidget' has been marked as deprecated, remember to clean it up",
            "log_level": "warning",
        },
    ]
    widget = schema_branch.get_node(name="TestingWidget", duplicate=False)
    assert widget.get_attribute(name="legacy_code").optional is True
    assert widget.get_relationship(name="legacy_peer").optional is True
    assert widget.get_attribute(name="name").optional is False


@pytest.mark.parametrize("namespace", ["Core", "Builtin", "Internal", "Profile", "Template"])
def test_deprecated_fields_of_a_restricted_namespace_node_are_made_optional_without_a_report(namespace: str) -> None:
    schema_branch = SchemaBranch(cache={}, name="test")
    schema_branch.load_schema(schema=SchemaRoot(nodes=[_deprecated_widget(namespace=namespace)]))

    with capture_logs() as records:
        schema_branch.process_deprecations()

    assert records == []
    widget = schema_branch.get_node(name=f"{namespace}Widget", duplicate=False)
    assert widget.get_attribute(name="legacy_code").optional is True
    assert widget.get_relationship(name="legacy_peer").optional is True
    assert widget.get_attribute(name="name").optional is False


def test_processing_the_shipped_schema_reports_no_deprecation() -> None:
    """Infrahub's own deprecated fields must not produce a warning each time a schema is processed."""
    schema_branch = SchemaBranch(cache={}, name="test")
    schema_branch.load_schema(schema=SchemaRoot(**internal_schema))
    schema_branch.load_schema(schema=SchemaRoot(**core_models))
    number_pool = schema_branch.get_node(name="CoreNumberPool", duplicate=False)
    assert number_pool.get_attribute(name="start_range").is_deprecated
    assert number_pool.get_attribute(name="end_range").is_deprecated

    with capture_logs() as records:
        schema_branch.process_deprecations()

    assert records == []
