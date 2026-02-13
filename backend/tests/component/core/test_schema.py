from dataclasses import dataclass
from typing import Any, Hashable

import pytest
from pydantic import ValidationError

from infrahub.core import registry
from infrahub.core.branch.models import Branch
from infrahub.core.constants import BranchSupportType
from infrahub.core.schema import (
    AttributeSchema,
    DropdownChoice,
    NodeSchema,
    RelationshipSchema,
    SchemaRoot,
    SchemaWarning,
    SchemaWarningKind,
    SchemaWarningType,
    core_models,
    internal_schema,
)
from infrahub.core.schema.attribute_parameters import TextAttributeParameters
from infrahub.core.schema.attribute_schema import TextAttributeSchema
from infrahub.core.schema.generic_schema import GenericSchema
from infrahub.core.schema.schema_branch import SchemaBranch
from infrahub.database import InfrahubDatabase


@dataclass
class SchemaWarningTestCaseData:
    name: str
    schema: SchemaRoot
    warnings: list[SchemaWarning]


SCHEMA_WARNING_TESTCASES: list[SchemaWarningTestCaseData] = [
    SchemaWarningTestCaseData(
        name="use_display_labels",
        schema=SchemaRoot(
            nodes=[
                NodeSchema(
                    namespace="Test",
                    name="Unit",
                    display_labels=["name__value"],
                    attributes=[AttributeSchema(name="name", kind="Text")],
                )
            ]
        ),
        warnings=[
            SchemaWarning(
                type=SchemaWarningType.DEPRECATION,
                kinds=[SchemaWarningKind(kind="TestUnit")],
                message="display_labels are deprecated, use display_label instead",
            )
        ],
    ),
    SchemaWarningTestCaseData(
        name="use_default_filter",
        schema=SchemaRoot(
            nodes=[
                NodeSchema(
                    namespace="Test",
                    name="Unit",
                    default_filter="name__value",
                    attributes=[AttributeSchema(name="name", kind="Text")],
                )
            ]
        ),
        warnings=[
            SchemaWarning(
                type=SchemaWarningType.DEPRECATION,
                kinds=[SchemaWarningKind(kind="TestUnit")],
                message="default_filter is deprecated",
            )
        ],
    ),
    SchemaWarningTestCaseData(
        name="use_default_filter_and_display_labels",
        schema=SchemaRoot(
            nodes=[
                NodeSchema(
                    namespace="Test",
                    name="Unit",
                    default_filter="name__value",
                    display_labels=["name__value"],
                    attributes=[AttributeSchema(name="name", kind="Text")],
                )
            ]
        ),
        warnings=[
            SchemaWarning(
                type=SchemaWarningType.DEPRECATION,
                kinds=[SchemaWarningKind(kind="TestUnit")],
                message="display_labels are deprecated, use display_label instead",
            ),
            SchemaWarning(
                type=SchemaWarningType.DEPRECATION,
                kinds=[SchemaWarningKind(kind="TestUnit")],
                message="default_filter is deprecated",
            ),
        ],
    ),
    SchemaWarningTestCaseData(
        name="use_min_max_length_on_attribute",
        schema=SchemaRoot(
            nodes=[
                NodeSchema(
                    namespace="Test",
                    name="Ticket",
                    attributes=[AttributeSchema(name="name", kind="Text", min_length=1, max_length=40)],
                )
            ]
        ),
        warnings=[
            SchemaWarning(
                type=SchemaWarningType.DEPRECATION,
                kinds=[SchemaWarningKind(kind="TestTicket", field="name")],
                message="Use of 'max_length' on attributes is deprecated, use parameters instead",
            ),
            SchemaWarning(
                type=SchemaWarningType.DEPRECATION,
                kinds=[SchemaWarningKind(kind="TestTicket", field="name")],
                message="Use of 'min_length' on attributes is deprecated, use parameters instead",
            ),
        ],
    ),
    SchemaWarningTestCaseData(
        name="use_min_max_length_in_parameters_no_warning",
        schema=SchemaRoot(
            nodes=[
                NodeSchema(
                    namespace="Test",
                    name="Ticket",
                    attributes=[
                        TextAttributeSchema(
                            name="name",
                            kind="Text",
                            parameters=TextAttributeParameters(min_length=1, max_length=40),
                        )
                    ],
                )
            ]
        ),
        warnings=[],
    ),
    SchemaWarningTestCaseData(
        name="use_regex_in_parameters_no_warning",
        schema=SchemaRoot(
            nodes=[
                NodeSchema(
                    namespace="Test",
                    name="Device",
                    attributes=[
                        TextAttributeSchema(
                            name="hostname",
                            kind="Text",
                            parameters=TextAttributeParameters(regex="^[a-zA-Z][a-zA-Z0-9._-]*$"),
                        )
                    ],
                )
            ]
        ),
        warnings=[],
    ),
]


@pytest.mark.parametrize(
    "test_case",
    [pytest.param(tc, id=tc.name) for tc in SCHEMA_WARNING_TESTCASES],
)
async def test_schema_warnings(
    test_case: SchemaWarningTestCaseData,
) -> None:
    """Validate that the expected warnings show up for each schema."""
    assert test_case.schema.gather_warnings() == test_case.warnings


def test_schema_root_no_generic() -> None:
    FULL_SCHEMA = {
        "nodes": [
            {
                "name": "Criticality",
                "namespace": "Test",
                "default_filter": "name__value",
                "branch": BranchSupportType.AWARE.value,
                "attributes": [
                    {"name": "name", "kind": "Text", "unique": True},
                ],
            }
        ]
    }

    assert SchemaRoot(**FULL_SCHEMA)


def test_node_schema_property_unique_attributes() -> None:
    SCHEMA = {
        "name": "Criticality",
        "namespace": "Test",
        "default_filter": "name__value",
        "branch": BranchSupportType.AWARE.value,
        "attributes": [
            {"name": "name", "kind": "Text", "unique": True},
            {"name": "description", "kind": "Text"},
        ],
    }

    schema = NodeSchema(**SCHEMA)
    assert len(schema.unique_attributes) == 1
    assert schema.unique_attributes[0].name == "name"


async def test_node_schema_hashable() -> None:
    SCHEMA = {
        "name": "Criticality",
        "namespace": "Test",
        "default_filter": "name__value",
        "branch": BranchSupportType.AWARE.value,
        "attributes": [
            {"name": "name", "kind": "Text", "unique": True},
        ],
        "relationships": [
            {"name": "first", "peer": "TestCriticality", "cardinality": "one"},
            {"name": "second", "identifier": "something_unique", "peer": "TestCriticality", "cardinality": "one"},
        ],
    }
    schema = NodeSchema(**SCHEMA)

    assert isinstance(schema, Hashable)
    assert schema.get_hash()


async def test_attribute_schema_hashable() -> None:
    SCHEMA = {"name": "name", "kind": "Text", "unique": True}

    schema = AttributeSchema(**SCHEMA)

    assert isinstance(schema, Hashable)
    assert schema.get_hash()


async def test_relationship_schema_hashable() -> None:
    SCHEMA = {"name": "first", "peer": "Criticality", "identifier": "cardinality__peer", "cardinality": "one"}

    schema = RelationshipSchema(**SCHEMA)

    assert isinstance(schema, Hashable)
    assert schema.get_hash()


async def test_node_schema_generate_fields_for_display_label() -> None:
    SCHEMA = {
        "name": "Criticality",
        "namespace": "Test",
        "default_filter": "name__value",
        "display_labels": ["name__value", "level__value"],
        "branch": BranchSupportType.AWARE.value,
        "attributes": [
            {"name": "name", "kind": "Text", "unique": True},
            {"name": "level", "kind": "Number"},
        ],
        "relationships": [
            {"name": "first", "peer": "TestCriticality", "cardinality": "one"},
        ],
    }

    schema = NodeSchema(**SCHEMA)
    assert schema.generate_fields_for_display_label() == {"level": {"value": None}, "name": {"value": None}}


async def test_node_schema_generate_fields_for_display_label_with_generic(default_branch: Branch) -> None:
    generic_schema = GenericSchema(
        name="ThingGeneric",
        namespace="Test",
        attributes=[
            AttributeSchema(name="name", kind="Text"),
        ],
    )
    node_schema_1 = NodeSchema(
        name="Thing1",
        namespace="Test",
        inherit_from=["TestThingGeneric"],
        display_labels=["name__value", "height__value"],
        attributes=[
            AttributeSchema(name="height", kind="Text"),
        ],
    )
    node_schema_2 = NodeSchema(
        name="Thing2",
        namespace="Test",
        inherit_from=["TestThingGeneric"],
        display_labels=["name"],
        attributes=[
            AttributeSchema(name="color", kind="Text"),
        ],
    )
    schema_root = SchemaRoot(generics=[generic_schema], nodes=[node_schema_1, node_schema_2])
    registry.schema.register_schema(schema=schema_root, branch=default_branch.name)
    schema_branch = registry.schema.get_schema_branch(name=default_branch.name)
    generic_display_label = schema_branch.generate_fields_for_display_label(name="TestThingGeneric")
    assert generic_display_label == {"name": {"value": None}, "height": {"value": None}}


async def test_rel_schema_query_filter(
    db: InfrahubDatabase, default_branch: Branch, car_person_schema: SchemaBranch
) -> None:
    person = registry.schema.get(name="TestPerson")
    rel = person.relationships[0]

    # Filter relationships by NAME__VALUE
    filters, params, matches = await rel.get_query_filter(db=db, filter_name="name__value", filter_value="alice")
    expected_response = [
        "(n)",
        "<-[r1:IS_RELATED]-",
        "(rl:Relationship { name: $rel_cars_rel_name })",
        "<-[r2:IS_RELATED]-",
        "(peer:Node)",
        "-[:HAS_ATTRIBUTE]-",
        "(i:Attribute { name: $attr_name_name })",
        "-[:HAS_VALUE]-",
        "(av:AttributeValueIndexed { value: $attr_name_value })",
    ]
    assert [str(item) for item in filters] == expected_response
    assert params == {"attr_name_name": "name", "attr_name_value": "alice", "rel_cars_rel_name": "testcar__testperson"}
    assert matches == []

    # Filter relationship by ID
    filters, params, matches = await rel.get_query_filter(db=db, name="bob", filter_name="id", filter_value="XXXX-YYYY")
    expected_response = [
        "(n)",
        "<-[r1:IS_RELATED]-",
        "(rl:Relationship { name: $rel_cars_rel_name })",
        "<-[r2:IS_RELATED]-",
        "(peer:Node { uuid: $rel_cars_peer_id })",
    ]
    assert [str(item) for item in filters] == expected_response
    assert params == {"rel_cars_peer_id": "XXXX-YYYY", "rel_cars_rel_name": "testcar__testperson"}
    assert matches == []


async def test_rel_schema_query_filter_no_value(
    db: InfrahubDatabase, default_branch: Branch, car_person_schema: SchemaBranch
) -> None:
    person = registry.schema.get(name="TestPerson")
    rel = person.relationships[0]

    # Filter relationships by NAME__VALUE
    filters, params, matches = await rel.get_query_filter(db=db, filter_name="name__value")
    expected_response = [
        "(n)",
        "<-[r1:IS_RELATED]-",
        "(rl:Relationship { name: $rel_cars_rel_name })",
        "<-[r2:IS_RELATED]-",
        "(peer:Node)",
        "-[:HAS_ATTRIBUTE]-",
        "(i:Attribute { name: $attr_name_name })",
        "-[:HAS_VALUE]-",
        "(av:AttributeValueIndexed)",
    ]
    assert [str(item) for item in filters] == expected_response
    assert params == {"attr_name_name": "name", "rel_cars_rel_name": "testcar__testperson"}
    assert matches == []

    # Filter relationship by ID
    filters, params, matches = await rel.get_query_filter(db=db, name="bob", filter_name="id")
    expected_response = [
        "(n)",
        "<-[r1:IS_RELATED]-",
        "(rl:Relationship { name: $rel_cars_rel_name })",
        "<-[r2:IS_RELATED]-",
        "(peer:Node)",
    ]
    assert [str(item) for item in filters] == expected_response
    assert params == {"rel_cars_rel_name": "testcar__testperson"}
    assert matches == []


async def test_rel_schema_query_filter_large_attribute_type(
    db: InfrahubDatabase, default_branch: Branch, car_person_schema: SchemaBranch
) -> None:
    person = registry.schema.get(name="TestPerson")
    rel = person.relationships[0]
    car_schema = registry.schema.get(name="TestCar", duplicate=False)
    name_attr = car_schema.get_attribute(name="name")
    name_attr.kind = "TextArea"

    # Filter relationships by NAME__VALUE
    filters, params, matches = await rel.get_query_filter(db=db, filter_name="name__value", filter_value="alice")
    expected_response = [
        "(n)",
        "<-[r1:IS_RELATED]-",
        "(rl:Relationship { name: $rel_cars_rel_name })",
        "<-[r2:IS_RELATED]-",
        "(peer:Node)",
        "-[:HAS_ATTRIBUTE]-",
        "(i:Attribute { name: $attr_name_name })",
        "-[:HAS_VALUE]-",
        "(av:AttributeValue { value: $attr_name_value })",
    ]
    assert [str(item) for item in filters] == expected_response
    assert params == {"attr_name_name": "name", "attr_name_value": "alice", "rel_cars_rel_name": "testcar__testperson"}
    assert matches == []


def test_core_models() -> None:
    assert SchemaRoot(**core_models)


def test_internal_schema() -> None:
    assert SchemaRoot(**internal_schema)


async def test_attribute_schema_choices_invalid_kind() -> None:
    SCHEMA = {"name": "name", "kind": "Text", "choices": [DropdownChoice(name="active", color="#AAbb0f")]}

    with pytest.raises(ValidationError) as exc:
        AttributeSchema(**SCHEMA)

    assert "Can only specify 'choices' for kind=Dropdown" in str(exc.value)


async def test_attribute_schema_dropdown_missing_choices() -> None:
    SCHEMA: dict[str, Any] = {"name": "name", "kind": "Dropdown"}

    with pytest.raises(ValidationError) as exc:
        AttributeSchema(**SCHEMA)

    assert "The property 'choices' is required for kind=Dropdown" in str(exc.value)


def test_dropdown_choice_colors() -> None:
    active = DropdownChoice(name="active", color="#AAbb0f")
    assert active.color == "#aabb0f"
    with pytest.raises(ValidationError) as exc:
        DropdownChoice(name="active", color="off-white")

    assert "Color must be a valid HTML color code" in str(exc.value)


def test_dropdown_choice_sort() -> None:
    active = DropdownChoice(name="active", color="#AAbb0f")
    passive = DropdownChoice(name="passive", color="#AAbb0f")
    assert active < passive


def test_dropdown_validation_error_with_invalid_choice_name() -> None:
    """Test that validation errors for dropdown choices include attribute name and nested path.

    This simulates the issue from IFC-2089 where YAML parsing converts 'off' to boolean False,
    and the error message should clearly indicate which attribute and which choice field has the problem.
    """
    SCHEMA_WITH_INVALID_CHOICE: dict[str, Any] = {
        "nodes": [
            {
                "name": "SDP",
                "namespace": "Infra",
                "attributes": [
                    {"name": "name", "kind": "Text", "label": "SDP ID", "optional": False},
                    {
                        "name": "signaling",
                        "kind": "Dropdown",
                        "label": "Signaling",
                        "optional": False,
                        "choices": [
                            {"name": "tldp", "label": "TLDP"},
                            {"name": False, "label": "Off"},  # Boolean instead of string - simulates YAML 'off'
                            {"name": "bgp", "label": "BGP"},
                        ],
                        "default_value": "tldp",
                    },
                ],
            }
        ]
    }

    with pytest.raises(ValidationError) as exc:
        SchemaRoot(**SCHEMA_WITH_INVALID_CHOICE)

    # The error should have the attribute name and nested path in the input field
    errors = exc.value.errors()
    assert len(errors) == 1, "Should have exactly one validation error"
    error = errors[0]
    input_value = str(error.get("input", ""))
    assert "signaling" in input_value, f"Input should contain attribute name 'signaling': {input_value}"
    assert "choices" in input_value, f"Input should contain 'choices': {input_value}"
    assert "name" in input_value, f"Input should contain 'name': {input_value}"
    assert "[signaling.choices.1.name]" in input_value, f"Input should show nested path: {input_value}"


def test_validate_python_keywords_with_attribute_and_relationship() -> None:
    """Test that validate_python_keywords rejects Python keywords in attribute and relationship names."""
    # Test schema with 'from' keyword as attribute name
    SCHEMA_WITH_KEYWORD_ATTR: dict[str, Any] = {
        "nodes": [
            {
                "name": "RoutingPolicy",
                "namespace": "Infra",
                "default_filter": "name__value",
                "branch": BranchSupportType.AWARE.value,
                "attributes": [
                    {"name": "name", "kind": "Text", "unique": True},
                    {"name": "from", "kind": "Text"},  # Python keyword
                ],
            }
        ]
    }

    schema_root = SchemaRoot(**SCHEMA_WITH_KEYWORD_ATTR)
    schema_branch = SchemaBranch(cache={}, name="test")
    schema_branch.load_schema(schema=schema_root)

    with pytest.raises(ValueError) as exc:
        schema_branch.process_validate()

    assert "Python keyword 'from' cannot be used as an attribute name on 'InfraRoutingPolicy'" in str(exc.value)

    # Test schema with 'class' keyword as relationship name
    SCHEMA_WITH_KEYWORD_REL: dict[str, Any] = {
        "nodes": [
            {
                "name": "Device",
                "namespace": "Test",
                "default_filter": "name__value",
                "branch": BranchSupportType.AWARE.value,
                "attributes": [
                    {"name": "name", "kind": "Text", "unique": True},
                ],
                "relationships": [
                    {"name": "class", "peer": "TestType", "cardinality": "one", "optional": True},  # Python keyword
                ],
            },
            {
                "name": "Type",
                "namespace": "Test",
                "default_filter": "name__value",
                "attributes": [
                    {"name": "name", "kind": "Text", "unique": True},
                ],
            },
        ]
    }

    schema_root = SchemaRoot(**SCHEMA_WITH_KEYWORD_REL)
    schema_branch = SchemaBranch(cache={}, name="test")
    schema_branch.load_schema(schema=schema_root)

    with pytest.raises(ValueError) as exc:
        schema_branch.process_validate()

    assert "Python keyword 'class' cannot be used as a relationship name on 'TestDevice' when using strict mode" in str(
        exc.value
    )

    # Test schema with valid names (no keywords)
    SCHEMA_VALID: dict[str, Any] = {
        "nodes": [
            {
                "name": "ValidSchema",
                "namespace": "Test",
                "default_filter": "name__value",
                "branch": BranchSupportType.AWARE.value,
                "attributes": [
                    {"name": "name", "kind": "Text", "unique": True},
                    {"name": "source", "kind": "Text"},  # Not a keyword
                ],
                "relationships": [
                    {"name": "parent", "peer": "TestType", "cardinality": "one", "optional": True},  # Not a keyword
                ],
            },
            {
                "name": "Type",
                "namespace": "Test",
                "default_filter": "name__value",
                "attributes": [
                    {"name": "name", "kind": "Text", "unique": True},
                ],
            },
        ]
    }

    schema_root = SchemaRoot(**SCHEMA_VALID)
    schema_branch = SchemaBranch(cache={}, name="test")
    schema_branch.load_schema(schema=schema_root)

    # This should not raise any exception
    schema_branch.process_validate()


def test_validate_python_keywords_multiple_keywords() -> None:
    """Test that validate_python_keywords catches multiple Python keywords."""
    SCHEMA_WITH_MULTIPLE_KEYWORDS: dict[str, Any] = {
        "nodes": [
            {
                "name": "TestNode",
                "namespace": "Test",
                "default_filter": "name__value",
                "branch": BranchSupportType.AWARE.value,
                "attributes": [
                    {"name": "name", "kind": "Text", "unique": True},
                    {"name": "from", "kind": "Text"},  # Python keyword
                    {"name": "import", "kind": "Text"},  # Python keyword
                ],
                "relationships": [
                    {"name": "class", "peer": "TestType", "cardinality": "one", "optional": True},  # Python keyword
                    {"name": "def", "peer": "TestType", "cardinality": "one", "optional": True},  # Python keyword
                ],
            }
        ]
    }

    schema_root = SchemaRoot(**SCHEMA_WITH_MULTIPLE_KEYWORDS)
    schema_branch = SchemaBranch(cache={}, name="test")
    schema_branch.load_schema(schema=schema_root)

    # Should raise ValueError on the first Python keyword encountered
    with pytest.raises(ValueError) as exc:
        schema_branch.process_validate()

    # Check that at least one Python keyword error is caught
    error_message = str(exc.value)
    keyword_found = False
    for keyword in ["from", "import", "class", "def"]:
        if f"Python keyword '{keyword}' cannot be used as a" in error_message:
            keyword_found = True
            break

    assert keyword_found, f"Expected Python keyword error, got: {error_message}"


def test_validate_generate_template_on_generic_schema() -> None:
    """Test that setting generate_template=True on a GenericSchema raises a validation error."""
    SCHEMA_WITH_GENERIC_TEMPLATE: dict[str, Any] = {
        "generics": [
            {
                "name": "MyGeneric",
                "namespace": "Testing",
                "generate_template": True,
                "attributes": [{"name": "name", "kind": "Text"}],
            },
        ],
    }

    schema_root = SchemaRoot(**SCHEMA_WITH_GENERIC_TEMPLATE)
    schema_branch = SchemaBranch(cache={}, name="test")
    schema_branch.load_schema(schema=schema_root)

    with pytest.raises(
        ValueError,
        match=r"'generate_template' cannot be set to true on a generic. Templates are only supported on node definitions.",
    ):
        schema_branch.validate_generate_template()


def test_validate_namespaces_and_keyword_separation() -> None:
    """Test that namespace and Python keyword validation work separately in their proper contexts."""
    # Test that SchemaRoot.validate_namespaces() only catches namespace issues
    SCHEMA_WITH_NAMESPACE_ISSUE: dict[str, Any] = {
        "nodes": [
            {
                "name": "TestNode",
                "namespace": "Internal",  # Restricted namespace
                "default_filter": "name__value",
                "branch": BranchSupportType.AWARE.value,
                "attributes": [
                    {"name": "name", "kind": "Text", "unique": True},
                    {"name": "from", "kind": "Text"},  # Python keyword (not caught by SchemaRoot.validate)
                ],
            }
        ]
    }

    schema_root = SchemaRoot(**SCHEMA_WITH_NAMESPACE_ISSUE)
    errors = schema_root.validate_namespaces()
    assert len(errors) == 1
    assert "Restricted namespace 'Internal' used on 'TestNode'" in errors[0]

    # Test that SchemaBranch validation catches Python keywords when namespace is valid
    SCHEMA_WITH_KEYWORD_ISSUE: dict[str, Any] = {
        "nodes": [
            {
                "name": "TestNode",
                "namespace": "Test",  # Valid namespace
                "default_filter": "name__value",
                "branch": BranchSupportType.AWARE.value,
                "attributes": [
                    {"name": "name", "kind": "Text", "unique": True},
                    {"name": "from", "kind": "Text"},  # Python keyword
                ],
            }
        ]
    }

    schema_root = SchemaRoot(**SCHEMA_WITH_KEYWORD_ISSUE)
    # SchemaRoot validation should pass (no namespace issues)
    errors = schema_root.validate_namespaces()
    assert len(errors) == 0

    # But SchemaBranch validation should catch the Python keyword
    schema_branch = SchemaBranch(cache={}, name="test")
    schema_branch.load_schema(schema=schema_root)

    with pytest.raises(ValueError) as exc:
        schema_branch.process_validate()

    assert "Python keyword 'from' cannot be used as an attribute name" in str(exc.value)
