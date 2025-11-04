from dataclasses import dataclass

import pytest

from infrahub.core.schema import AttributeSchema, NodeSchema, SchemaRoot
from infrahub.core.schema.schema_branch import SchemaBranch


@dataclass
class DisplayLabelTestCase:
    name: str
    schema_root: SchemaRoot
    display_label: str


DISPLAY_LABEL_TEST_CASES: list[DisplayLabelTestCase] = [
    DisplayLabelTestCase(
        name="single_attribute_label_no_value",
        schema_root=SchemaRoot(
            nodes=[
                NodeSchema(
                    name="Widget",
                    namespace="Test",
                    attributes=[AttributeSchema(name="name", kind="Text"), AttributeSchema(name="status", kind="Text")],
                    display_labels=["name"],
                )
            ]
        ),
        display_label="name__value",
    ),
    DisplayLabelTestCase(
        name="single_attribute_label_with_value",
        schema_root=SchemaRoot(
            nodes=[
                NodeSchema(
                    name="Widget",
                    namespace="Test",
                    attributes=[AttributeSchema(name="name", kind="Text"), AttributeSchema(name="status", kind="Text")],
                    display_labels=["name__value"],
                )
            ]
        ),
        display_label="name__value",
    ),
    DisplayLabelTestCase(
        name="dual_attribute_label_no_value",
        schema_root=SchemaRoot(
            nodes=[
                NodeSchema(
                    name="Widget",
                    namespace="Test",
                    attributes=[AttributeSchema(name="name", kind="Text"), AttributeSchema(name="status", kind="Text")],
                    display_labels=["name", "status"],
                )
            ]
        ),
        display_label="{{ name__value }} {{ status__value }}",
    ),
    DisplayLabelTestCase(
        name="dual_attribute_label_mixed_value",
        schema_root=SchemaRoot(
            nodes=[
                NodeSchema(
                    name="Widget",
                    namespace="Test",
                    attributes=[AttributeSchema(name="name", kind="Text"), AttributeSchema(name="status", kind="Text")],
                    display_labels=["name__value", "status"],
                )
            ]
        ),
        display_label="{{ name__value }} {{ status__value }}",
    ),
    DisplayLabelTestCase(
        name="defined_display_label",
        schema_root=SchemaRoot(
            nodes=[
                NodeSchema(
                    name="Widget",
                    namespace="Test",
                    attributes=[AttributeSchema(name="name", kind="Text"), AttributeSchema(name="status", kind="Text")],
                    display_labels=["name__value", "status"],
                    display_label="{{ name__value|upper }}: {{ status__value|lower }}",
                )
            ]
        ),
        display_label="{{ name__value|upper }}: {{ status__value|lower }}",
    ),
]


@pytest.mark.parametrize(
    "test_case",
    [pytest.param(tc, id=tc.name) for tc in DISPLAY_LABEL_TEST_CASES],
)
async def test_expected_final_display_label(
    test_case: DisplayLabelTestCase,
) -> None:
    """Test that the final computed display label matches the expected value."""
    schema_branch = SchemaBranch(cache={}, name="test")
    schema_branch.load_schema(schema=test_case.schema_root)
    schema_branch.process()
    node = schema_branch.get_node(name="TestWidget", duplicate=False)
    assert node.display_label == test_case.display_label
