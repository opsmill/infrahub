from dataclasses import dataclass, field
from typing import Any

import pytest

from infrahub.core.constants import RelationshipCardinality
from infrahub.core.schema import AttributeSchema, NodeSchema, RelationshipSchema, SchemaRoot
from infrahub.core.schema.schema_branch import SchemaBranch
from infrahub.exceptions import ValidationError


@dataclass
class HFIDTestCase:
    name: str
    schema_root: SchemaRoot
    relationship_fields: dict[str, set[str]] = field(default_factory=dict)


_SCHEMA: dict[str, Any] = {
    "nodes": [
        {
            "name": "Car",
            "namespace": "Test",
            "attributes": [
                {"name": "name", "kind": "Text"},
                {"name": "nbr_seats", "kind": "Number"},
            ],
            "relationships": [
                {
                    "name": "owner",
                    "label": "Commander of Car",
                    "peer": "TestPerson",
                    "optional": False,
                    "cardinality": "one",
                    "direction": "outbound",
                },
                {
                    "name": "driver",
                    "label": "Driver of Car",
                    "peer": "TestPerson",
                    "optional": False,
                    "cardinality": "one",
                    "direction": "outbound",
                    "identifier": "drive_rel",
                },
            ],
        },
        {
            "name": "Person",
            "namespace": "Test",
            "attributes": [
                {"name": "name", "kind": "Text", "optional": False},
                {"name": "age", "kind": "Number"},
                {"name": "salary", "kind": "Number"},
            ],
            "relationships": [
                {"name": "cars_owned", "peer": "TestCar", "cardinality": "many", "direction": "inbound"},
                {
                    "name": "cars_driven",
                    "peer": "TestCar",
                    "cardinality": "many",
                    "direction": "inbound",
                    "identifier": "drive_rel",
                },
            ],
        },
    ],
}


@pytest.mark.parametrize(
    "human_friendly_id, uniqueness_constraints, should_raise",
    [
        # Valid hfid
        (["name__value", "owner__name__value"], [["name__value"]], False),
        (["owner__name__value", "owner__age__value"], [["name__value", "age__value"]], False),
        (["owner__name__value", "owner__age__value"], [["name__value"]], False),
        (["owner__name__value", "owner__age__value"], [["name__value"], ["age__value"]], False),
        (
            ["owner__name__value", "owner__age__value", "driver__name__value", "driver__age__value"],
            [["name__value"], ["age__value"]],
            False,
        ),
        (["owner__name__value", "owner__age__value", "owner__salary__value"], [["name__value", "age__value"]], False),
        # Non-valid hfid
        (["name__value", "owner__name__value"], None, True),
        (["name__value", "owner__name__value"], [["age__value"]], True),
        (
            ["owner__name__value", "owner__age__value"],
            [["age__value", "salary__value"], ["name__value", "salary__value"]],
            True,
        ),
        (["owner__name__value", "owner__age__value", "driver__name__value"], [["name__value", "age__value"]], True),
    ],
)
async def test_schema_constraints(human_friendly_id, uniqueness_constraints, should_raise):
    schema_root = SchemaRoot(**_SCHEMA)

    person_schema = schema_root.get(name="TestPerson")
    car_schema = schema_root.get(name="TestCar")

    car_schema.human_friendly_id = human_friendly_id
    person_schema.uniqueness_constraints = uniqueness_constraints

    schema_branch = SchemaBranch(cache={}, name="test")

    if should_raise:
        with pytest.raises(
            ValidationError,
            match=r"HFID of TestCar refers to peer TestPerson with a non-unique combination of attributes",
        ):
            schema_branch.load_schema(schema=schema_root)
            schema_branch.process()
    else:
        schema_branch.load_schema(schema=schema_root)
        schema_branch.process()


HFID_RELATIONSHIP_FIELDS_TEST_CASES: list[HFIDTestCase] = [
    HFIDTestCase(
        name="no_relationships",
        schema_root=SchemaRoot(
            nodes=[
                NodeSchema(
                    name="Widget",
                    namespace="Test",
                    attributes=[AttributeSchema(name="name", kind="Text"), AttributeSchema(name="status", kind="Text")],
                    display_label="{{ name__value|upper }}: {{ status__value|lower }}",
                    human_friendly_id=["name__value", "status__value"],
                ),
            ]
        ),
    ),
    HFIDTestCase(
        name="single_relationship_single_field",
        schema_root=SchemaRoot(
            nodes=[
                NodeSchema(
                    name="Widget",
                    namespace="Test",
                    attributes=[AttributeSchema(name="name", kind="Text"), AttributeSchema(name="status", kind="Text")],
                    relationships=[
                        RelationshipSchema(
                            name="container",
                            peer="TestContainer",
                            cardinality=RelationshipCardinality.ONE,
                            optional=False,
                        )
                    ],
                    display_label="{{ name__value|upper }}: {{ status__value|lower }} - {{ container__storage_name__value }}",
                    human_friendly_id=["name__value", "status__value", "container__storage_name__value"],
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
        relationship_fields={"container": {"storage_name"}},
    ),
    HFIDTestCase(
        name="single_relationship_dual_fields",
        schema_root=SchemaRoot(
            nodes=[
                NodeSchema(
                    name="Widget",
                    namespace="Test",
                    attributes=[AttributeSchema(name="name", kind="Text"), AttributeSchema(name="status", kind="Text")],
                    relationships=[
                        RelationshipSchema(
                            name="container",
                            peer="TestContainer",
                            cardinality=RelationshipCardinality.ONE,
                            optional=False,
                        )
                    ],
                    display_label="{{ name__value }}: {{ status__value }} - {{ container__storage_name__value }}. {{ container__status__value }}",
                    human_friendly_id=[
                        "name__value",
                        "status__value",
                        "container__storage_name__value",
                        "container__status__value",
                    ],
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
        relationship_fields={"container": {"storage_name", "status"}},
    ),
    HFIDTestCase(
        name="dual_relationship_dual_fields",
        schema_root=SchemaRoot(
            nodes=[
                NodeSchema(
                    name="Widget",
                    namespace="Test",
                    attributes=[AttributeSchema(name="name", kind="Text"), AttributeSchema(name="status", kind="Text")],
                    relationships=[
                        RelationshipSchema(
                            name="container",
                            peer="TestContainer",
                            cardinality=RelationshipCardinality.ONE,
                            optional=False,
                        ),
                        RelationshipSchema(
                            name="owner",
                            peer="TestOwner",
                            cardinality=RelationshipCardinality.ONE,
                            optional=False,
                        ),
                    ],
                    display_label="{{ owner__family_name__value }}'s {{ name__value }}",
                    human_friendly_id=[
                        "name__value",
                        "status__value",
                        "container__storage_name__value",
                        "container__status__value",
                        "owner__family_name__value",
                    ],
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
        relationship_fields={"container": {"storage_name", "status"}, "owner": {"family_name"}},
    ),
]


@pytest.mark.parametrize(
    "test_case",
    [pytest.param(tc, id=tc.name) for tc in HFID_RELATIONSHIP_FIELDS_TEST_CASES],
)
async def test_expected_relationship_fields(
    test_case: HFIDTestCase,
) -> None:
    """Test that the registered relationship_fields matches the expected value."""
    schema_branch = SchemaBranch(cache={}, name="test")
    schema_branch.load_schema(schema=test_case.schema_root)
    schema_branch.process()
    node = schema_branch.hfids.get_node_definition(kind="TestWidget")
    assert node.relationship_fields == test_case.relationship_fields
