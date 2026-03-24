from dataclasses import dataclass, field

import pytest

from infrahub.core.constants import RelationshipCardinality
from infrahub.core.schema import AttributeSchema, NodeSchema, RelationshipSchema, SchemaRoot
from infrahub.core.schema.schema_branch import SchemaBranch


@dataclass
class DisplayLabelTestCase:
    name: str
    schema_root: SchemaRoot
    display_label: str
    relationship_fields: dict[str, set[str]] = field(default_factory=dict)


DISPLAY_LABEL_CONVERT_TEST_CASES: list[DisplayLabelTestCase] = [
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
    [pytest.param(tc, id=tc.name) for tc in DISPLAY_LABEL_CONVERT_TEST_CASES],
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


DISPLAY_LABEL_RELATIONSHIP_FIELDS_TEST_CASES: list[DisplayLabelTestCase] = [
    DisplayLabelTestCase(
        name="no_relationships",
        schema_root=SchemaRoot(
            nodes=[
                NodeSchema(
                    name="Widget",
                    namespace="Test",
                    attributes=[AttributeSchema(name="name", kind="Text"), AttributeSchema(name="status", kind="Text")],
                    display_labels=["name__value", "status"],
                    display_label="{{ name__value|upper }}: {{ status__value|lower }}",
                ),
            ]
        ),
        display_label="{{ name__value|upper }}: {{ status__value|lower }}",
    ),
    DisplayLabelTestCase(
        name="single_relationship_single_field",
        schema_root=SchemaRoot(
            nodes=[
                NodeSchema(
                    name="Widget",
                    namespace="Test",
                    attributes=[AttributeSchema(name="name", kind="Text"), AttributeSchema(name="status", kind="Text")],
                    relationships=[
                        RelationshipSchema(
                            name="container", peer="TestContainer", cardinality=RelationshipCardinality.ONE
                        )
                    ],
                    display_labels=["name__value", "status"],
                    display_label="{{ name__value|upper }}: {{ status__value|lower }} - {{ container__storage_name__value }}",
                ),
                NodeSchema(
                    name="Container",
                    namespace="Test",
                    attributes=[
                        AttributeSchema(name="storage_name", kind="Text", unique=True, optional=False),
                        AttributeSchema(name="status", kind="Text"),
                    ],
                    display_label="storage_name__value",
                ),
            ]
        ),
        display_label="{{ name__value|upper }}: {{ status__value|lower }}",
        relationship_fields={"container": {"storage_name"}},
    ),
    DisplayLabelTestCase(
        name="single_relationship_dual_fields",
        schema_root=SchemaRoot(
            nodes=[
                NodeSchema(
                    name="Widget",
                    namespace="Test",
                    attributes=[AttributeSchema(name="name", kind="Text"), AttributeSchema(name="status", kind="Text")],
                    relationships=[
                        RelationshipSchema(
                            name="container", peer="TestContainer", cardinality=RelationshipCardinality.ONE
                        )
                    ],
                    display_labels=["name__value", "status"],
                    display_label="{{ name__value }}: {{ status__value }} - {{ container__storage_name__value }}. {{ container__status__value }}",
                ),
                NodeSchema(
                    name="Container",
                    namespace="Test",
                    attributes=[
                        AttributeSchema(name="storage_name", kind="Text", unique=True, optional=False),
                        AttributeSchema(name="status", kind="Text"),
                    ],
                    display_label="storage_name__value",
                ),
            ]
        ),
        display_label="{{ name__value }}: {{ status__value }} - {{ container__storage_name__value }}. {{ container__status__value }}",
        relationship_fields={"container": {"storage_name", "status"}},
    ),
    DisplayLabelTestCase(
        name="dual_relationship_dual_fields",
        schema_root=SchemaRoot(
            nodes=[
                NodeSchema(
                    name="Widget",
                    namespace="Test",
                    attributes=[AttributeSchema(name="name", kind="Text"), AttributeSchema(name="status", kind="Text")],
                    relationships=[
                        RelationshipSchema(
                            name="container", peer="TestContainer", cardinality=RelationshipCardinality.ONE
                        ),
                        RelationshipSchema(name="owner", peer="TestOwner", cardinality=RelationshipCardinality.ONE),
                    ],
                    display_label="{{ owner__family_name__value }}'s {{ name__value }}: - {{ container__storage_name__value }}. {{ container__status__value }}",  # noqa: E501
                ),
                NodeSchema(
                    name="Container",
                    namespace="Test",
                    attributes=[
                        AttributeSchema(name="storage_name", kind="Text", unique=True, optional=False),
                        AttributeSchema(name="status", kind="Text"),
                    ],
                    display_label="storage_name__value",
                ),
                NodeSchema(
                    name="Owner",
                    namespace="Test",
                    attributes=[
                        AttributeSchema(name="family_name", kind="Text", unique=True, optional=False),
                        AttributeSchema(name="description", kind="Text", optional=True),
                    ],
                    display_label="family_name__value",
                ),
            ]
        ),
        display_label="{{ owner__family_name__value }}'s {{ name__value }}: - {{ container__storage_name__value }}. {{ container__status__value }}",
        relationship_fields={"container": {"storage_name", "status"}, "owner": {"family_name"}},
    ),
]


@pytest.mark.parametrize(
    "test_case",
    [pytest.param(tc, id=tc.name) for tc in DISPLAY_LABEL_RELATIONSHIP_FIELDS_TEST_CASES],
)
async def test_expected_relationship_fields(
    test_case: DisplayLabelTestCase,
) -> None:
    """Test that the registered relationship_fields matches the expected value."""
    schema_branch = SchemaBranch(cache={}, name="test")
    schema_branch.load_schema(schema=test_case.schema_root)
    schema_branch.process()
    node = schema_branch.display_labels.get_template_node(kind="TestWidget")
    assert node.relationship_fields == test_case.relationship_fields
