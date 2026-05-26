import pytest

from infrahub.core.constants import ComputedAttributeKind, RelationshipCardinality
from infrahub.core.node.constraints.uniqueness_violation_message import UniquenessViolationMessageBuilder
from infrahub.core.schema import AttributeSchema, NodeSchema, RelationshipSchema, SchemaRoot
from infrahub.core.schema.computed_attribute import ComputedAttribute
from infrahub.core.schema.schema_branch import SchemaBranch


@pytest.fixture
def schema_root() -> SchemaRoot:
    car = NodeSchema(
        name="Car",
        namespace="Test",
        human_friendly_id=["name__value"],
        attributes=[
            AttributeSchema(
                name="name",
                kind="Text",
                unique=True,
                read_only=True,
                optional=False,
                computed_attribute=ComputedAttribute(
                    kind=ComputedAttributeKind.JINJA2,
                    jinja2_template="{{ model__value | upper }}-CAR",
                ),
            ),
            AttributeSchema(name="model", kind="Text"),
            AttributeSchema(
                name="badge",
                kind="Text",
                read_only=True,
                optional=True,
                computed_attribute=ComputedAttribute(
                    kind=ComputedAttributeKind.JINJA2,
                    jinja2_template="{{ owner__name__value }} :: {{ model__value }}",
                ),
            ),
        ],
        relationships=[
            RelationshipSchema(
                name="owner",
                peer="TestPerson",
                cardinality=RelationshipCardinality.ONE,
                optional=False,
            ),
        ],
    )
    person = NodeSchema(
        name="Person",
        namespace="Test",
        human_friendly_id=["name__value"],
        attributes=[AttributeSchema(name="name", kind="Text", unique=True)],
    )
    return SchemaRoot(nodes=[car, person])


@pytest.fixture
def schema_branch(schema_root: SchemaRoot) -> SchemaBranch:
    branch = SchemaBranch(cache={}, name="test")
    branch.load_schema(schema=schema_root)
    branch.process()
    return branch


@pytest.fixture
def builder(schema_branch: SchemaBranch) -> UniquenessViolationMessageBuilder:
    return UniquenessViolationMessageBuilder(schema_branch=schema_branch)


def test_non_computed_field_has_no_suffix(
    builder: UniquenessViolationMessageBuilder, schema_branch: SchemaBranch
) -> None:
    car = schema_branch.get(name="TestCar", duplicate=False)
    message = builder.build(node_schema=car, fields=["model"])
    assert message == "Violates uniqueness constraint 'model'"


def test_computed_attribute_input_is_named_in_suffix(
    builder: UniquenessViolationMessageBuilder, schema_branch: SchemaBranch
) -> None:
    car = schema_branch.get(name="TestCar", duplicate=False)
    message = builder.build(node_schema=car, fields=["name"])
    assert message == "Violates uniqueness constraint 'name' (computed from: model)"


def test_relationship_input_uses_dotted_form(
    builder: UniquenessViolationMessageBuilder, schema_branch: SchemaBranch
) -> None:
    car = schema_branch.get(name="TestCar", duplicate=False)
    message = builder.build(node_schema=car, fields=["badge"])
    assert message == "Violates uniqueness constraint 'badge' (computed from: model, owner.name)"


def test_multiple_computed_fields_deduplicate_shared_inputs(
    builder: UniquenessViolationMessageBuilder, schema_branch: SchemaBranch
) -> None:
    car = schema_branch.get(name="TestCar", duplicate=False)
    message = builder.build(node_schema=car, fields=["name", "badge"])
    assert message == "Violates uniqueness constraint 'name-badge' (computed from: model, owner.name)"


def test_unknown_field_is_skipped_silently(
    builder: UniquenessViolationMessageBuilder, schema_branch: SchemaBranch
) -> None:
    car = schema_branch.get(name="TestCar", duplicate=False)
    message = builder.build(node_schema=car, fields=["does_not_exist"])
    assert message == "Violates uniqueness constraint 'does_not_exist'"
