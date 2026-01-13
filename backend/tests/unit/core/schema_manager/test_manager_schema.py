import copy
import json
import re
import uuid
from dataclasses import dataclass
from typing import Any

import pytest
from infrahub_sdk.utils import compare_lists

from infrahub.core import registry
from infrahub.core.branch import Branch
from infrahub.core.constants import (
    OBJECT_TEMPLATE_NAME_ATTR,
    OBJECT_TEMPLATE_RELATIONSHIP_NAME,
    RESERVED_ATTR_REL_HIERARCHICAL_NAMES,
    AllowOverrideType,
    BranchSupportType,
    HashableModelState,
    InfrahubKind,
    MetadataOptions,
    RelationshipCardinality,
    RelationshipDeleteBehavior,
    RelationshipKind,
    SchemaPathType,
)
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.core.schema import (
    AttributeSchema,
    GenericSchema,
    NodeSchema,
    RelationshipSchema,
    SchemaRoot,
    core_models,
    internal_schema,
)
from infrahub.core.schema.attribute_parameters import TextAttributeParameters
from infrahub.core.schema.computed_attribute import ComputedAttribute
from infrahub.core.schema.definitions.core.template import core_object_component_template, core_object_template
from infrahub.core.schema.manager import SchemaManager
from infrahub.core.schema.schema_branch import SchemaBranch
from infrahub.core.timestamp import Timestamp
from infrahub.database import InfrahubDatabase
from infrahub.exceptions import SchemaNotFoundError, ValidationError
from tests.conftest import TestHelper
from tests.constants import TestKind
from tests.helpers.schema import CHILD, DEVICE, DEVICE_SCHEMA, THING
from tests.helpers.schema.device import LAG_INTERFACE

from .conftest import _get_schema_by_kind


async def test_schema_branch_set() -> None:
    SCHEMA = {
        "name": "Criticality",
        "namespace": "Testing",
        "default_filter": "name__value",
        "attributes": [
            {"name": "name", "kind": "Text", "unique": True},
            {"name": "description", "kind": "Text"},
        ],
    }
    schema = NodeSchema(**SCHEMA)

    schema_branch = SchemaBranch(cache={}, name="test")

    schema_branch.set(name="schema1", schema=schema)
    assert schema.get_hash() in schema_branch._cache
    assert len(schema_branch._cache) == 1

    schema_branch.set(name="schema2", schema=schema)
    assert len(schema_branch._cache) == 1


async def test_schema_branch_get(default_branch: Branch) -> None:
    SCHEMA = {
        "name": "Criticality",
        "namespace": "Testing",
        "default_filter": "name__value",
        "attributes": [
            {"name": "name", "kind": "Text", "unique": True},
            {"name": "description", "kind": "Text"},
        ],
    }
    schema = NodeSchema(**SCHEMA)

    schema_branch = SchemaBranch(cache={}, name="test")

    schema_branch.set(name="schema1", schema=schema)
    assert len(schema_branch._cache) == 1

    schema11 = schema_branch.get(name="schema1")
    assert schema11 == schema


async def test_schema_branch_load_schema_initial(schema_all_in_one) -> None:
    schema = SchemaBranch(cache={}, name="test")
    schema.load_schema(schema=SchemaRoot(**schema_all_in_one))

    assert isinstance(schema.get(name="TestingCriticality"), NodeSchema)
    assert isinstance(schema.get(name="InfraGenericInterface"), GenericSchema)


async def test_schema_branch_process_inheritance(schema_all_in_one) -> None:
    schema = SchemaBranch(cache={}, name="test")
    schema.load_schema(schema=SchemaRoot(**schema_all_in_one))

    schema.process_inheritance()

    generic = schema.get(name="InfraGenericInterface")
    assert generic.used_by == ["TestingCriticality"]

    criticality = schema.get(name="TestingCriticality")
    assert criticality.get_relationship(name="status")
    assert criticality.get_relationship(name="status").inherited
    assert criticality.get_attribute(name="my_generic_name")
    assert criticality.get_attribute(name="my_generic_name").inherited
    assert criticality.get_attribute(name="mybool")
    assert criticality.get_attribute(name="mybool").inherited
    assert criticality.get_attribute(name="color")
    assert criticality.get_attribute(name="color").inherited is False
    assert criticality.get_attribute(name="description")
    assert criticality.get_attribute(name="description").inherited is False

    core_node = schema.get(name="CoreNode")
    assert set(core_node.used_by) == {
        "TestingCriticality",
        "TestingTag",
        "TestingStatus",
        "TestingBadge",
        "CoreStandardGroup",
        "InfraTinySchema",
    }


async def test_schema_process_inheritance_different_generic_attribute_types(schema_diff_attr_inheritance_types) -> None:
    """Test that we raise an exception if a node is inheriting from two generics with different attribute types for a specific attribute."""
    schema = SchemaBranch(cache={}, name="test")
    schema.load_schema(schema=SchemaRoot(**schema_diff_attr_inheritance_types))

    with pytest.raises(ValueError) as exc:
        schema.process_inheritance()

    assert exc.value.args[0] == 'TestWidget.choice inherited from TestStatus must be the same kind ["Number", "Text"]'


async def test_schema_process_inheritance_different_generic_attribute_types_on_node(
    schema_diff_attr_inheritance_types,
) -> None:
    """Test that we raise an exception if a node is inheriting an attribute with different attribute type that already exists on node."""
    schema = SchemaBranch(cache={}, name="test")
    schema_new = copy.deepcopy(schema_diff_attr_inheritance_types)
    schema_new["generics"].pop()
    schema_new["nodes"][0]["inherit_from"].pop()
    schema_new["nodes"][0]["attributes"].append({"name": "choice", "kind": "List"})
    schema.load_schema(schema=SchemaRoot(**schema_new))

    with pytest.raises(ValueError) as exc:
        schema.process_inheritance()

    assert exc.value.args[0] == 'TestWidget.choice inherited from TestAdapter must be the same kind ["Text", "List"]'


async def test_schema_branch_process_inheritance_node_level(animal_person_schema_dict) -> None:
    schema = SchemaBranch(cache={}, name="test")
    schema.load_schema(schema=SchemaRoot(**animal_person_schema_dict))

    schema.process_inheritance()

    animal = schema.get(name="TestAnimal")
    assert sorted(animal.used_by) == ["TestCat", "TestDog"]

    dog = schema.get(name="TestDog")
    cat = schema.get(name="TestCat")
    assert dog.human_friendly_id == animal.human_friendly_id
    assert cat.human_friendly_id != animal.human_friendly_id

    assert dog.display_labels == animal.display_labels
    assert cat.display_labels != animal.display_labels

    assert dog.order_by == animal.order_by
    assert cat.order_by != animal.order_by

    assert dog.icon == animal.icon


async def test_schema_branch_process_inheritance_update_inherited_elements(animal_person_schema_dict) -> None:
    schema = SchemaBranch(cache={}, name="test")
    schema.load_schema(schema=SchemaRoot(**animal_person_schema_dict))

    schema.process_inheritance()

    dog = schema.get(name="TestDog")
    assert dog.get_attribute(name="name").description is None
    assert dog.get_relationship(name="owner").optional is False

    updated_schema = animal_person_schema_dict
    updated_schema["generics"][0]["attributes"][0]["description"] = "new description"
    updated_schema["generics"][0]["relationships"][0]["optional"] = True

    schema.load_schema(schema=SchemaRoot(**updated_schema))
    schema.process_inheritance()

    dog = schema.get(name="TestDog")
    assert dog.get_attribute(name="name").description == "new description"
    assert dog.get_relationship(name="owner").optional is True


@pytest.mark.parametrize(
    ["uniqueness_constraints", "unique_attributes", "human_friendly_id"],
    [
        (None, [], ["name__value"]),
        ([["breed__value"]], [], ["name__value"]),
        (None, ["breed"], ["name__value"]),
        ([["name__value", "breed__value"]], ["breed"], ["name__value"]),
        (None, ["name"], ["name__value"]),
        (None, [], ["name__value", "breed__value"]),
    ],
)
async def test_validate_human_friendly_id_assign_uniquess_constraints(
    uniqueness_constraints: list[list[str]] | None,
    unique_attributes: list[str],
    human_friendly_id: list[str] | None,
    animal_person_schema_dict,
) -> None:
    schema = SchemaBranch(cache={}, name="test")
    animal_schema = animal_person_schema_dict["generics"][0]
    assert animal_schema["name"] == "Animal"
    assert animal_schema["namespace"] == "Test"
    animal_schema["uniqueness_constraints"] = None
    animal_schema["human_friendly_id"] = None

    dog_schema = animal_person_schema_dict["nodes"][0]
    assert dog_schema["name"] == "Dog"
    assert dog_schema["namespace"] == "Test"
    dog_schema["uniqueness_constraints"] = uniqueness_constraints
    dog_schema["human_friendly_id"] = human_friendly_id
    expected_uniqueness_constraints = []
    for attr_schema in dog_schema["attributes"]:
        attr_schema["unique"] = attr_schema["name"] in unique_attributes
        if attr_schema["unique"]:
            expected_uniqueness_constraints.append([attr_schema["name"] + "__value"])

    schema.load_schema(schema=SchemaRoot(**animal_person_schema_dict))
    schema.process()

    dog_node = schema.get("TestDog")
    if uniqueness_constraints:
        expected_uniqueness_constraints += uniqueness_constraints
    if human_friendly_id:
        expected_uniqueness_constraints += [human_friendly_id]

    assert {tuple(uc) for uc in dog_node.uniqueness_constraints} == {
        tuple(uc) for uc in expected_uniqueness_constraints
    }


@pytest.mark.parametrize(
    ["uniqueness_constraints", "unique_attributes", "human_friendly_id"],
    [
        (None, ["name"], ["name__value"]),
        (None, ["name"], ["name__value", "breed__value"]),
        ([["name__value"]], [], ["name__value", "breed__value"]),
        ([["name__value", "owner"], ["breed__value"]], [], ["name__value", "breed__value"]),
    ],
)
async def test_validate_human_friendly_id_uniqueness_success(
    uniqueness_constraints: list[list[str]] | None,
    unique_attributes: list[str],
    human_friendly_id: list[str] | None,
    animal_person_schema_dict,
) -> None:
    schema = SchemaBranch(cache={}, name="test")
    for node_schema in animal_person_schema_dict["generics"]:
        if node_schema["name"] == "Animal" and node_schema["namespace"] == "Test":
            node_schema["uniqueness_constraints"] = None
            node_schema["human_friendly_id"] = None
            for attr_schema in node_schema["attributes"]:
                attr_schema["unique"] = attr_schema["name"] in unique_attributes
    for node_schema in animal_person_schema_dict["nodes"]:
        if node_schema["name"] == "Dog" and node_schema["namespace"] == "Test":
            node_schema["uniqueness_constraints"] = uniqueness_constraints
            node_schema["human_friendly_id"] = human_friendly_id
            for attr_schema in node_schema["attributes"]:
                attr_schema["unique"] = attr_schema["name"] in unique_attributes
    schema.load_schema(schema=SchemaRoot(**animal_person_schema_dict))

    schema.process_inheritance()
    schema.sync_uniqueness_constraints_and_unique_attributes()
    schema.validate_human_friendly_id()

    dog_schema = schema.get("TestDog", duplicate=False)
    assert dog_schema.human_friendly_id == human_friendly_id

    dog_schema.human_friendly_id = ["name__value", "breed__value", "name__value"]
    with pytest.raises(ValidationError, match=r"cannot use the same path more than once"):
        schema.validate_human_friendly_id()


async def test_schema_branch_process_human_friendly_id(animal_person_schema_dict) -> None:
    schema = SchemaBranch(cache={}, name="test")
    schema.load_schema(schema=SchemaRoot(**animal_person_schema_dict))

    schema.process_inheritance()
    schema.process_human_friendly_id()

    animal = schema.get(name="TestAnimal")

    assert sorted(animal.used_by) == ["TestCat", "TestDog"]

    dog = schema.get(name="TestDog")
    person = schema.get(name="TestPerson")

    assert person.human_friendly_id == ["name__value"]
    assert dog.uniqueness_constraints == [["owner", "name__value"]]


async def test_schema_branch_infer_human_friendly_id_from_uniqueness_constraints(animal_person_schema_dict) -> None:
    for node_schema_dict in animal_person_schema_dict["nodes"]:
        if node_schema_dict["name"] == "Dog" and node_schema_dict["namespace"] == "Test":
            node_schema_dict["uniqueness_constraints"] = [["name__value"]]
        if node_schema_dict["name"] == "Cat" and node_schema_dict["namespace"] == "Test":
            node_schema_dict["uniqueness_constraints"] = [["name__value", "owner"]]
            node_schema_dict["human_friendly_id"] = None
        if node_schema_dict["name"] == "Person" and node_schema_dict["namespace"] == "Test":
            node_schema_dict["uniqueness_constraints"] = [["name__value"]]
            node_schema_dict["human_friendly_id"] = ["name__value", "other_name__value"]
    for generic_schema_dict in animal_person_schema_dict["generics"]:
        if generic_schema_dict["name"] == "Animal" and generic_schema_dict["namespace"] == "Test":
            generic_schema_dict["human_friendly_id"] = None

    schema = SchemaBranch(cache={}, name="test")
    schema.load_schema(schema=SchemaRoot(**animal_person_schema_dict))

    schema.process_inheritance()
    schema.process_human_friendly_id()

    animal = schema.get(name="TestAnimal")
    assert sorted(animal.used_by) == ["TestCat", "TestDog"]

    cat = schema.get(name="TestCat")
    dog = schema.get(name="TestDog")
    person = schema.get(name="TestPerson")

    # cat human friendly ID remains None b/c uniqueness_constraint has multiple values
    assert cat.human_friendly_id is None
    assert cat.uniqueness_constraints == [["name__value", "owner"]]
    # dog human friendly ID is set to name__value b/c there is a uniqueness constraint with 1 attribute value
    assert dog.uniqueness_constraints == [["name__value"]]
    assert dog.human_friendly_id == ["name__value"]
    # person human friendly ID and uniqueness_constraints remain as they were set
    assert person.human_friendly_id == ["name__value", "other_name__value"]
    assert person.uniqueness_constraints == [["name__value"], ["name__value", "other_name__value"]]


async def test_schema_branch_process_branch_support(schema_all_in_one) -> None:
    schema = SchemaBranch(cache={}, name="test")
    schema.load_schema(schema=SchemaRoot(**schema_all_in_one))

    schema.process_inheritance()
    schema.process_branch_support()

    criticality = schema.get(name="TestingCriticality")
    assert criticality.get_attribute(name="name").branch == BranchSupportType.AGNOSTIC
    assert criticality.get_attribute(name="level").branch == BranchSupportType.AWARE
    assert criticality.get_attribute(name="local_attr").branch == BranchSupportType.LOCAL
    assert criticality.get_relationship(name="tags").branch == BranchSupportType.AWARE
    assert criticality.get_relationship(name="status").branch == BranchSupportType.AGNOSTIC
    assert criticality.get_relationship(name="badges").branch == BranchSupportType.LOCAL

    criticality = schema.get(name="TestingTag")
    assert criticality.get_attribute(name="name").branch == BranchSupportType.AWARE
    assert criticality.get_attribute(name="description").branch == BranchSupportType.AGNOSTIC


async def test_schema_branch_process_default_values(schema_all_in_one) -> None:
    schema = SchemaBranch(cache={}, name="test")
    schema.load_schema(schema=SchemaRoot(**schema_all_in_one))

    schema.process_default_values()

    generic = schema.get(name="InfraGenericInterface")
    assert generic.get_attribute(name="mybool").optional is True
    assert generic.get_attribute(name="my_generic_name").optional is False

    criticality = schema.get(name="TestingCriticality")
    assert criticality.get_attribute(name="color").optional is True


async def test_schema_branch_reconcile_text_attribute_parameters() -> None:
    """Test that SchemaBranch.load_schema() syncs top-level and parameters fields for Text attributes."""
    regex = "abc"
    min_length = 3
    max_length = 5

    # Test reconciliation when parameters are set (new style)
    SCHEMA_WITH_PARAMS: dict[str, Any] = {
        "nodes": [
            {
                "name": "Device",
                "namespace": "Test",
                "default_filter": "name__value",
                "branch": BranchSupportType.AWARE.value,
                "attributes": [
                    {"name": "name", "kind": "Text", "unique": True},
                    {
                        "name": "description",
                        "kind": "Text",
                        "parameters": {"regex": regex, "min_length": min_length, "max_length": max_length},
                    },
                ],
            }
        ]
    }

    schema_root = SchemaRoot(**SCHEMA_WITH_PARAMS)
    schema_branch = SchemaBranch(cache={}, name="test")
    schema_branch.load_schema(schema=schema_root)

    # After load_schema, both deprecated fields and parameters should be synced
    node = schema_branch.get(name="TestDevice", duplicate=False)
    desc_attr = node.get_attribute(name="description")
    assert desc_attr.parameters.regex == desc_attr.regex == regex
    assert desc_attr.parameters.min_length == desc_attr.min_length == min_length
    assert desc_attr.parameters.max_length == desc_attr.max_length == max_length

    # Test reconciliation when top-level fields are set (deprecated style)
    SCHEMA_WITH_TOP_LEVEL: dict[str, Any] = {
        "nodes": [
            {
                "name": "Router",
                "namespace": "Test",
                "default_filter": "name__value",
                "branch": BranchSupportType.AWARE.value,
                "attributes": [
                    {"name": "name", "kind": "Text", "unique": True},
                    {
                        "name": "hostname",
                        "kind": "Text",
                        "regex": regex,
                        "min_length": min_length,
                        "max_length": max_length,
                    },
                ],
            }
        ]
    }

    schema_root = SchemaRoot(**SCHEMA_WITH_TOP_LEVEL)
    schema_branch = SchemaBranch(cache={}, name="test")
    schema_branch.load_schema(schema=schema_root)

    # After load_schema, both deprecated fields and parameters should be synced
    node = schema_branch.get(name="TestRouter", duplicate=False)
    hostname_attr = node.get_attribute(name="hostname")
    assert hostname_attr.parameters.regex == hostname_attr.regex == regex
    assert hostname_attr.parameters.min_length == hostname_attr.min_length == min_length
    assert hostname_attr.parameters.max_length == hostname_attr.max_length == max_length


async def test_schema_branch_add_groups(schema_all_in_one) -> None:
    schema = SchemaBranch(cache={}, name="test")
    schema.load_schema(schema=SchemaRoot(**schema_all_in_one))

    schema.process_inheritance()
    schema.add_groups()

    criticality = schema.get(name="TestingCriticality")
    assert criticality.get_relationship(name="member_of_groups")
    assert criticality.get_relationship(name="subscriber_of_groups")

    std_group = schema.get(name=InfrahubKind.STANDARDGROUP)
    assert std_group.get_relationship_or_none(name="member_of_groups") is None
    assert std_group.get_relationship_or_none(name="subscriber_of_groups") is None


async def test_schema_branch_cleanup_inherited_elements(schema_all_in_one) -> None:
    schema = SchemaBranch(cache={}, name="test")
    schema.load_schema(schema=SchemaRoot(**schema_all_in_one))

    schema.process_inheritance()

    schema = SchemaBranch(cache={}, name="test")
    schema.load_schema(schema=SchemaRoot(**schema_all_in_one))
    schema.process()

    generic = schema.get(name="InfraGenericInterface")
    attr1 = generic.get_attribute(name="mybool")
    attr1.state = HashableModelState.ABSENT
    rel1 = generic.get_relationship(name="primary_tag")
    rel1.state = HashableModelState.ABSENT
    schema.set(name=generic.kind, schema=generic)

    node = schema.get(name="TestingCriticality")
    attr1_node = node.get_attribute(name="mybool")
    assert attr1_node.inherited is True
    assert attr1_node.state == HashableModelState.PRESENT
    rel1_node = node.get_relationship(name="primary_tag")
    assert rel1_node.inherited is True
    assert rel1_node.state == HashableModelState.PRESENT

    schema.cleanup_inherited_elements()
    node = schema.get(name="TestingCriticality")
    attr1_node = node.get_attribute(name="mybool")
    assert attr1_node.inherited is True
    assert attr1_node.state == HashableModelState.ABSENT
    rel1_node = node.get_relationship(name="primary_tag")
    assert rel1_node.inherited is True
    assert rel1_node.state == HashableModelState.ABSENT


@pytest.mark.parametrize(
    "schema_dict,expected_error",
    [
        (
            {
                "nodes": [
                    {
                        "name": "Criticality",
                        "namespace": "Test",
                        "inherit_from": ["InfraGenericInterface"],
                        "default_filter": "name__value",
                        "branch": BranchSupportType.AGNOSTIC.value,
                        "attributes": [{"name": "name", "kind": "Text", "unique": True}],
                    },
                    {
                        "name": "Status",
                        "namespace": "Test",
                        "branch": BranchSupportType.AGNOSTIC.value,
                        "attributes": [{"name": "name", "kind": "Text", "label": "Name", "unique": True}],
                    },
                ],
                "generics": [
                    {
                        "name": "GenericInterface",
                        "namespace": "Infra",
                        "attributes": [{"name": "name", "kind": "Text", "allow_override": AllowOverrideType.NONE}],
                        "relationships": [
                            {"name": "status", "peer": "TestStatus", "optional": True, "cardinality": "one"}
                        ],
                    },
                ],
            },
            "TestCriticality's attribute name inherited from InfraGenericInterface cannot be overriden",
        ),
        (
            {
                "nodes": [
                    {
                        "name": "Criticality",
                        "namespace": "Test",
                        "inherit_from": ["InfraGenericInterface"],
                        "default_filter": "name__value",
                        "branch": BranchSupportType.AGNOSTIC.value,
                        "relationships": [
                            {"name": "status", "peer": "TestingStatus", "optional": True, "cardinality": "one"}
                        ],
                    },
                    {
                        "name": "Status",
                        "namespace": "Test",
                        "branch": BranchSupportType.AGNOSTIC.value,
                        "attributes": [{"name": "name", "kind": "Text", "label": "Name", "unique": True}],
                    },
                ],
                "generics": [
                    {
                        "name": "GenericInterface",
                        "namespace": "Infra",
                        "attributes": [{"name": "name", "kind": "Text"}],
                        "relationships": [
                            {
                                "name": "status",
                                "peer": "TestStatus",
                                "optional": True,
                                "cardinality": "one",
                                "allow_override": AllowOverrideType.NONE,
                            }
                        ],
                    },
                ],
            },
            "TestCriticality's relationship status inherited from InfraGenericInterface cannot be overriden",
        ),
        (
            {
                "nodes": [
                    {
                        "name": "Criticality",
                        "namespace": "Test",
                        "inherit_from": ["InfraGenericInterface"],
                        "default_filter": "name__value",
                        "branch": BranchSupportType.AGNOSTIC.value,
                        "relationships": [
                            {"name": "status", "peer": "TestState", "optional": True, "cardinality": "one"}
                        ],
                    },
                    {
                        "name": "Status",
                        "namespace": "Test",
                        "branch": BranchSupportType.AGNOSTIC.value,
                        "attributes": [{"name": "name", "kind": "Text", "label": "Name", "unique": True}],
                    },
                    {
                        "name": "State",
                        "namespace": "Test",
                        "branch": BranchSupportType.AGNOSTIC.value,
                        "attributes": [{"name": "name", "kind": "Text", "label": "Name", "unique": True}],
                    },
                ],
                "generics": [
                    {
                        "name": "GenericInterface",
                        "namespace": "Infra",
                        "attributes": [{"name": "name", "kind": "Text"}],
                        "relationships": [
                            {
                                "name": "status",
                                "peer": "TestStatus",
                                "optional": True,
                                "cardinality": "one",
                            }
                        ],
                    },
                ],
            },
            "TestCriticality's relationship status inherited from InfraGenericInterface must have the same peer (TestStatus != TestState)",
        ),
    ],
)
async def test_schema_protected_generics(schema_dict, expected_error) -> None:
    schema = SchemaBranch(cache={}, name="test")
    schema.load_schema(schema=SchemaRoot(**schema_dict))

    with pytest.raises(ValueError) as exc:
        schema.process_inheritance()

    assert str(exc.value) == expected_error


async def test_schema_branch_generate_weight(schema_all_in_one) -> None:
    def extract_weights(schema: SchemaBranch):
        weights = []
        for node in schema.get_all().values():
            if not isinstance(node, NodeSchema | GenericSchema):
                continue
            for item in node.attributes + node.relationships:
                weights.append(f"{node.name}__{item.name}__{item.order_weight}")
                assert item.order_weight
        return weights

    schema = SchemaBranch(cache={}, name="test")
    schema.load_schema(schema=SchemaRoot(**schema_all_in_one))
    schema.generate_weight()

    initial_weights = extract_weights(schema)

    # Add a new item with a specific value
    new_schema = copy.deepcopy(schema_all_in_one)
    new_schema["nodes"][0]["attributes"].insert(1, {"name": "new_attr", "kind": "Number", "order_weight": 555})
    new_attr_id = f"{new_schema['nodes'][0]['name']}__new_attr__555"
    schema.load_schema(schema=SchemaRoot(**new_schema))
    schema.generate_weight()

    second_weights = extract_weights(schema)

    in_both, in_first, in_second = compare_lists(initial_weights, second_weights)
    assert in_first == []
    assert sorted(in_both) == sorted(initial_weights)
    assert in_second == [new_attr_id]

    # Add another item without a value
    new_schema2 = copy.deepcopy(schema_all_in_one)
    new_schema2["nodes"][0]["attributes"].insert(3, {"name": "new_attr2", "kind": "Number"})
    new_attr2_partial_id = f"{new_schema['nodes'][0]['name']}__new_attr2__"
    schema.load_schema(schema=SchemaRoot(**new_schema2))
    schema.generate_weight()

    third_weights = extract_weights(schema)

    in_both, in_first, in_second = compare_lists(second_weights, third_weights)
    assert in_first == []
    assert sorted(in_both) == sorted(second_weights)
    assert len(in_second) == 1
    assert in_second[0].startswith(new_attr2_partial_id)


def test_schema_branch_processes_generic_template_schema_weight(register_core_models_schema) -> None:
    schema = {
        "generics": [
            {
                "name": "GenericDevice",
                "namespace": "Dcim",
                "description": "Generic Device object.",
                "label": "Device",
                "icon": "mdi:server",
                "human_friendly_id": ["name__value"],
                "order_by": ["name__value"],
                "display_labels": ["name__value"],
                "generate_template": True,
                "attributes": [
                    {"name": "name", "kind": "Text", "unique": True, "order_weight": 7000},
                    {"name": "description", "kind": "Text", "optional": True, "order_weight": 8000},
                    {"name": "os_version", "kind": "Text", "optional": True, "order_weight": 5200},
                ],
                "relationships": [
                    {
                        "name": "tags",
                        "peer": "TestingTag",
                        "optional": True,
                        "cardinality": "many",
                        "kind": "Attribute",
                        "order_weight": 3000,
                    },
                ],
            },
            core_object_template,
            core_object_component_template,
        ],
        "nodes": [
            {
                "name": "Tag",
                "namespace": "Testing",
                "label": "Tag",
                "default_filter": "name__value",
                "attributes": [
                    {"name": "name", "kind": "Text", "label": "Name", "unique": True},
                    {
                        "name": "description",
                        "kind": "Text",
                        "label": "Description",
                        "optional": True,
                        "branch": BranchSupportType.AGNOSTIC.value,
                    },
                ],
            },
        ],
    }
    schema_branch = SchemaBranch(cache={}, name="test")
    schema_branch.load_schema(schema=SchemaRoot(**schema))
    schema_branch.process()

    template = schema_branch.get(name="TemplateDcimGenericDevice", duplicate=False)
    dcim_generic_device = schema_branch.get(name="DcimGenericDevice", duplicate=False)

    assert template.get_attribute(name="template_name").order_weight == 1000
    assert (
        template.get_attribute(name="description").order_weight
        == dcim_generic_device.get_attribute(name="description").order_weight
        == 8000
    )
    assert (
        template.get_attribute(name="os_version").order_weight
        == dcim_generic_device.get_attribute(name="os_version").order_weight
        == 5200
    )
    assert (
        template.get_relationship(name="tags").order_weight
        == dcim_generic_device.get_relationship(name="tags").order_weight
        == 3000
    )

    schema_2 = copy.deepcopy(schema)
    schema_2["generics"][0]["attributes"] = [
        {"name": "name", "kind": "Text", "unique": False},
        {"name": "description", "kind": "Text", "optional": True},
        {"name": "os_version", "kind": "Text", "optional": True},
    ]
    schema_branch.load_schema(schema=SchemaRoot(**schema_2))
    schema_branch.process()

    template = schema_branch.get(name="TemplateDcimGenericDevice", duplicate=False)
    dcim_generic_device = schema_branch.get(name="DcimGenericDevice", duplicate=False)

    assert (
        template.get_attribute(name="name").order_weight == dcim_generic_device.get_attribute(name="name").order_weight
    )
    assert (
        template.get_attribute(name="description").order_weight
        == dcim_generic_device.get_attribute(name="description").order_weight
    )
    assert (
        template.get_attribute(name="os_version").order_weight
        == dcim_generic_device.get_attribute(name="os_version").order_weight
    )


async def test_schema_branch_add_profile_schema(schema_all_in_one) -> None:
    core_profile_schema = _get_schema_by_kind(core_models, kind=InfrahubKind.PROFILE)
    schema_all_in_one["generics"].append(core_profile_schema)

    schema = SchemaBranch(cache={}, name="test")
    schema.load_schema(schema=SchemaRoot(**schema_all_in_one))
    schema.process_inheritance()
    schema.manage_profile_schemas()

    node_profile = schema.get(name="ProfileTestingCriticality", duplicate=False)
    assert node_profile.get_attribute("profile_name").branch == BranchSupportType.AGNOSTIC.value
    assert node_profile.get_attribute("profile_priority").branch == BranchSupportType.AGNOSTIC.value
    assert set(node_profile.attribute_names) == {
        "profile_name",
        "profile_priority",
        "level",
        "color",
        "description",
        "my_generic_name",
        "mybool",
        "local_attr",
    }
    assert set(node_profile.relationship_names) == {"badges", "primary_tag", "related_nodes", "status", "tags"}
    generic_profile = schema.get(name="ProfileInfraGenericInterface", duplicate=False)
    assert set(generic_profile.attribute_names) == {
        "profile_name",
        "profile_priority",
        "my_generic_name",
        "mybool",
        "local_attr",
    }
    assert set(generic_profile.relationship_names) == {"badges", "primary_tag", "related_nodes", "status"}
    core_profile_schema = schema.get("CoreProfile")
    core_node_schema = schema.get("CoreNode")
    assert set(core_profile_schema.used_by) == {
        "ProfileTestingCriticality",
        "ProfileTestingTag",
        "ProfileTestingStatus",
        "ProfileTestingBadge",
        "ProfileInfraTinySchema",
        "ProfileInfraGenericInterface",
    }

    assert set(core_node_schema.used_by) == {
        "TestingBadge",
        "TestingCriticality",
        "TestingStatus",
        "TestingTag",
        "CoreStandardGroup",
        "InfraTinySchema",
        "ProfileTestingCriticality",
        "ProfileTestingTag",
        "ProfileTestingStatus",
        "ProfileTestingBadge",
        "ProfileInfraTinySchema",
        "ProfileInfraGenericInterface",
    }


async def test_schema_branch_diff_core_profile(schema_all_in_one) -> None:
    core_profile_schema = _get_schema_by_kind(core_models, kind=InfrahubKind.PROFILE)
    schema_all_in_one["generics"].append(core_profile_schema)

    schema = SchemaBranch(cache={}, name="test")
    schema.load_schema(schema=SchemaRoot(**schema_all_in_one))
    schema.process_inheritance()
    schema.manage_profile_schemas()

    new_schema = schema.duplicate()
    profile_schema = new_schema.get(name=InfrahubKind.PROFILE, duplicate=True)
    profile_schema.description = "New description"
    new_schema.set(name=InfrahubKind.PROFILE, schema=profile_schema)

    diff = new_schema.diff(other=schema)
    assert diff.all == ["CoreProfile"]


async def test_schema_branch_add_profile_schema_respects_flag(schema_all_in_one) -> None:
    core_profile_schema = _get_schema_by_kind(core_models, kind=InfrahubKind.PROFILE)
    schema_all_in_one["generics"].append(core_profile_schema)
    builtin_tag_schema = _get_schema_by_kind(schema_all_in_one, kind="TestingTag")
    builtin_tag_schema["generate_profile"] = False
    generic_interface_schema = schema_all_in_one["generics"][0]
    generic_interface_schema["generate_profile"] = False

    schema = SchemaBranch(cache={}, name="test")
    schema.load_schema(schema=SchemaRoot(**schema_all_in_one))
    schema.manage_profile_schemas()

    with pytest.raises(SchemaNotFoundError):
        schema.get(name="ProfileTestingTag")
    builtin_tag_schema = schema.get_node(name="TestingTag", duplicate=False)
    with pytest.raises(ValueError):
        builtin_tag_schema.get_relationship("profiles")
    core_profile_schema = schema.get("CoreProfile")
    assert set(core_profile_schema.used_by) == {
        "ProfileTestingCriticality",
        "ProfileTestingStatus",
        "ProfileTestingBadge",
        "ProfileInfraTinySchema",
    }


async def test_schema_branch_add_profile_schema_exclude_relationships_in_uniqueness_constraint(
    schema_all_in_one,
) -> None:
    """Test that relationships included in uniqueness constraints are not added to profile schemas."""
    core_profile_schema = _get_schema_by_kind(core_models, kind=InfrahubKind.PROFILE)
    schema_all_in_one["generics"].append(core_profile_schema)

    test_node_schema = {
        "name": "Criticality",
        "namespace": "Test",
        "attributes": [{"name": "name", "kind": "Text", "unique": True}],
        "relationships": [
            {
                "name": "status",
                "peer": "TestingStatus",
                "optional": False,
                "cardinality": RelationshipCardinality.ONE,
            },
            {
                "name": "primary_tag",
                "peer": "TestingTag",
                "optional": True,
                "cardinality": RelationshipCardinality.ONE,
            },
        ],
        "uniqueness_constraints": [["status", "name__value"]],
    }
    schema_all_in_one["nodes"].append(test_node_schema)

    schema = SchemaBranch(cache={}, name="test")
    schema.load_schema(schema=SchemaRoot(**schema_all_in_one))
    schema.process()

    profile_schema = schema.get(name="ProfileTestCriticality", duplicate=False)
    assert "status" not in profile_schema.relationship_names
    assert "primary_tag" in profile_schema.relationship_names


async def test_schema_branch_generate_identifiers(schema_all_in_one) -> None:
    schema = SchemaBranch(cache={}, name="test")
    schema.load_schema(schema=SchemaRoot(**schema_all_in_one))

    schema.generate_identifiers()

    generic = schema.get(name="InfraGenericInterface")
    assert generic.relationships[1].identifier == "infragenericinterface__testingstatus"


@dataclass
class SchemaBranchValidateNamesTestCaseData:
    name: str
    schema: dict[str, Any]
    expected_error: str


SCHEMA_BRANCH_VALIDATE_NAMES_TEST_CASES = [
    SchemaBranchValidateNamesTestCaseData(
        name="attribute-uniqueness-test",
        schema={
            "nodes": [
                {
                    "name": "Criticality",
                    "namespace": "Test",
                    "default_filter": "name__value",
                    "branch": BranchSupportType.AWARE.value,
                    "attributes": [
                        {"name": "name", "kind": "Text", "unique": True},
                        {"name": "name", "kind": "Text", "unique": True},
                    ],
                }
            ]
        },
        expected_error="TestCriticality: Names of attributes and relationships must be unique : ['name']",
    ),
    SchemaBranchValidateNamesTestCaseData(
        name="relationship-uniqueness-test",
        schema={
            "nodes": [
                {
                    "name": "Criticality",
                    "namespace": "Test",
                    "default_filter": "name__value",
                    "branch": BranchSupportType.AWARE.value,
                    "attributes": [
                        {"name": "name", "kind": "Text", "unique": True},
                        {"name": "dupname", "kind": "Text"},
                    ],
                    "relationships": [
                        {"name": "dupname", "peer": "Criticality", "cardinality": "one"},
                    ],
                }
            ]
        },
        expected_error="TestCriticality: Names of attributes and relationships must be unique : ['dupname']",
    ),
    SchemaBranchValidateNamesTestCaseData(
        name="relationship-reserved-names-test",
        schema={
            "nodes": [
                {
                    "name": "Criticality",
                    "namespace": "Test",
                    "default_filter": "name__value",
                    "branch": BranchSupportType.AWARE.value,
                    "attributes": [
                        {"name": "name", "kind": "Text", "unique": True},
                    ],
                    "relationships": [
                        {"name": "save", "peer": "Criticality", "cardinality": "one"},
                    ],
                }
            ]
        },
        expected_error="TestCriticality: save isn't allowed as a relationship name.",
    ),
    SchemaBranchValidateNamesTestCaseData(
        name="attribute-reserved-names-test",
        schema={
            "nodes": [
                {
                    "name": "Criticality",
                    "namespace": "Test",
                    "default_filter": "name__value",
                    "branch": BranchSupportType.AWARE.value,
                    "attributes": [
                        {"name": "save", "kind": "Text", "unique": True},
                    ],
                    "relationships": [
                        {"name": "name", "peer": "Criticality", "cardinality": "one"},
                    ],
                }
            ]
        },
        expected_error="TestCriticality: save isn't allowed as an attribute name.",
    ),
]


@pytest.mark.parametrize(
    "test_case",
    [pytest.param(tc, id=tc.name) for tc in SCHEMA_BRANCH_VALIDATE_NAMES_TEST_CASES],
)
async def test_schema_branch_validate_names(test_case: SchemaBranchValidateNamesTestCaseData):
    schema = SchemaBranch(cache={}, name="test")
    schema.load_schema(schema=SchemaRoot(**test_case.schema))

    with pytest.raises(ValueError) as exc:
        schema.validate_names()

    assert str(exc.value) == test_case.expected_error


@pytest.mark.parametrize(
    "index,reserved_name",
    [
        pytest.param(index, reserved_name, id=reserved_name)
        for index, reserved_name in enumerate(RESERVED_ATTR_REL_HIERARCHICAL_NAMES)
    ],
)
async def test_schema_validate_hierarchical_nodes_restricted_words_when_loading_from_api(
    index: int, reserved_name: str
):
    schema1 = {
        "generics": [
            {
                "name": "Location",
                "namespace": "Generic",
                "hierarchical": True,
                "attributes": [{"name": f"name_location_{index}", "unique": True, "optional": False, "kind": "Text"}],
            }
        ],
        "nodes": [
            {
                "name": "Site",
                "namespace": "Location",
                "inherit_from": ["GenericLocation"],
                "children": "TestingParent",
                "parent": "",
            },
            {
                "name": "Parent",
                "namespace": "Testing",
                "inherit_from": ["GenericLocation"],
                "children": "",
                "parent": "LocationSite",
                "relationships": [
                    {
                        "name": reserved_name,
                        "kind": "Generic",
                        "optional": True,
                        "peer": "TestingChild",
                        "cardinality": "many",
                    }
                ],
            },
            {
                "name": "Child",
                "namespace": "Testing",
                "attributes": [{"name": f"name_{index}", "unique": True, "optional": False, "kind": "Text"}],
                "relationships": [
                    {
                        "name": f"relation_{index}",
                        "kind": "Attribute",
                        "optional": False,
                        "peer": "TestingParent",
                        "cardinality": "one",
                    }
                ],
            },
        ],
    }
    schema = SchemaBranch(cache={}, name=f"test_{index}")
    schema.load_schema(schema=SchemaRoot(**schema1), loading_from_api=True)

    with pytest.raises(ValueError) as exc:
        schema.process()

    assert (
        str(exc.value) == f"TestingParent: {reserved_name} isn't allowed as a relationship name on hierarchical nodes."
    )

    schema2 = {
        "generics": [
            {
                "name": "Location",
                "namespace": "Generic",
                "hierarchical": True,
                "attributes": [{"name": f"name_location_{index}", "unique": True, "optional": False, "kind": "Text"}],
            }
        ],
        "nodes": [
            {
                "name": "Site",
                "namespace": "Location",
                "inherit_from": ["GenericLocation"],
                "children": "TestingParent",
                "parent": "",
            },
            {
                "name": "Parent",
                "namespace": "Testing",
                "inherit_from": ["GenericLocation"],
                "children": "",
                "parent": "LocationSite",
                "attributes": [{"name": reserved_name, "unique": True, "optional": False, "kind": "Text"}],
                "relationships": [
                    {
                        "name": f"relationship_{index}",
                        "kind": "Generic",
                        "optional": True,
                        "peer": "TestingChild",
                        "cardinality": "many",
                    }
                ],
            },
            {
                "name": "Child",
                "namespace": "Testing",
                "attributes": [{"name": f"sample_{index}", "unique": True, "optional": False, "kind": "Text"}],
                "relationships": [
                    {
                        "name": f"child_name_{index}",
                        "kind": "Attribute",
                        "optional": False,
                        "peer": "TestingParent",
                        "cardinality": "one",
                    }
                ],
            },
        ],
    }
    schema = SchemaBranch(cache={}, name=f"test_{index}")
    schema.load_schema(schema=SchemaRoot(**schema2), loading_from_api=True)

    with pytest.raises(ValueError) as exc:
        schema.process()

    assert str(exc.value) == f"TestingParent: {reserved_name} isn't allowed as an attribute name on hierarchical nodes."


async def test_schema_branch_validate_identifiers() -> None:
    SCHEMA1 = {
        "name": "Criticality",
        "namespace": "Test",
        "default_filter": "name__value",
        "branch": BranchSupportType.AWARE.value,
        "attributes": [
            {"name": "name", "kind": "Text", "unique": True},
        ],
        "relationships": [
            {"name": "first", "peer": "TestCriticality", "cardinality": "one"},
            {"name": "second", "peer": "TestCriticality", "cardinality": "one"},
        ],
    }

    schema = SchemaBranch(cache={}, name="test")
    schema.load_schema(schema=SchemaRoot(nodes=[SCHEMA1]))
    schema.generate_identifiers()

    with pytest.raises(ValueError) as exc:
        schema.validate_identifiers()

    assert (
        str(exc.value) == "TestCriticality: Identifier of relationships must be unique for a given direction > "
        "'testcriticality__testcriticality' : [('first', 'bidirectional'), ('second', 'bidirectional')]"
    )

    SCHEMA2 = {
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
    schema = SchemaBranch(cache={}, name="test")
    schema.load_schema(schema=SchemaRoot(nodes=[SCHEMA2]))
    schema.generate_identifiers()
    schema.validate_identifiers()


async def test_schema_branch_validate_identifiers_direction() -> None:
    SCHEMA1 = {
        "name": "Criticality",
        "namespace": "Test",
        "default_filter": "name__value",
        "branch": BranchSupportType.AWARE.value,
        "attributes": [
            {"name": "name", "kind": "Text", "unique": True},
        ],
        "relationships": [
            {"name": "first", "peer": "TestCriticality", "cardinality": "one", "direction": "outbound"},
            {"name": "second", "peer": "TestCriticality", "cardinality": "one", "direction": "inbound"},
        ],
    }

    schema = SchemaBranch(cache={}, name="test")
    schema.load_schema(schema=SchemaRoot(nodes=[SCHEMA1]))
    schema.generate_identifiers()
    schema.validate_identifiers()

    SCHEMA2 = {
        "name": "Criticality",
        "namespace": "Test",
        "default_filter": "name__value",
        "branch": BranchSupportType.AWARE.value,
        "attributes": [
            {"name": "name", "kind": "Text", "unique": True},
        ],
        "relationships": [
            {"name": "first", "peer": "TestCriticality", "cardinality": "one", "direction": "bidirectional"},
            {"name": "second", "peer": "TestCriticality", "cardinality": "one", "direction": "inbound"},
        ],
    }

    schema = SchemaBranch(cache={}, name="test")
    schema.load_schema(schema=SchemaRoot(nodes=[SCHEMA2]))
    schema.generate_identifiers()
    with pytest.raises(ValueError) as exc:
        schema.validate_identifiers()

    assert (
        str(exc.value) == "TestCriticality: Identifier of relationships must be unique for a given direction > "
        "'testcriticality__testcriticality' : [('first', 'bidirectional'), ('second', 'inbound')]"
    )


async def test_schema_branch_validate_identifiers_matching_direction() -> None:
    SCHEMA = {
        "nodes": [
            {
                "name": "Criticality",
                "namespace": "Test",
                "default_filter": "name__value",
                "branch": BranchSupportType.AWARE.value,
                "attributes": [
                    {"name": "name", "kind": "Text", "unique": True},
                ],
                "relationships": [
                    {"name": "first", "peer": "TestOther", "cardinality": "one", "direction": "outbound"},
                ],
            },
            {
                "name": "Other",
                "namespace": "Test",
                "default_filter": "name__value",
                "branch": BranchSupportType.AWARE.value,
                "attributes": [
                    {"name": "name", "kind": "Text", "unique": True},
                ],
                "relationships": [
                    {"name": "first", "peer": "TestCriticality", "cardinality": "one", "direction": "outbound"},
                ],
            },
        ]
    }

    schema = SchemaBranch(cache={}, name="test")
    schema.load_schema(schema=SchemaRoot(**SCHEMA))
    schema.generate_identifiers()
    with pytest.raises(ValueError) as exc:
        schema.validate_identifiers()

    assert (
        str(exc.value)
        == "TestOther: Incompatible direction detected on Reverse Relationship for 'first' ('testcriticality__testother') "
        "outbound <> outbound"
    )

    SCHEMA["nodes"][0]["relationships"][0]["direction"] = "bidirectional"
    schema = SchemaBranch(cache={}, name="test")
    schema.load_schema(schema=SchemaRoot(**SCHEMA))
    schema.generate_identifiers()
    with pytest.raises(ValueError) as exc:
        schema.validate_identifiers()

    assert (
        str(exc.value)
        == "TestOther: Incompatible direction detected on Reverse Relationship for 'first' ('testcriticality__testother') "
        "bidirectional <> outbound"
    )

    # Validation is good with inbound <> outbound
    SCHEMA["nodes"][0]["relationships"][0]["direction"] = "inbound"
    schema = SchemaBranch(cache={}, name="test")
    schema.load_schema(schema=SchemaRoot(**SCHEMA))
    schema.generate_identifiers()
    schema.validate_identifiers()

    # Validation is good with bidirectional <> bidirectional
    SCHEMA["nodes"][0]["relationships"][0]["direction"] = "bidirectional"
    SCHEMA["nodes"][1]["relationships"][0]["direction"] = "bidirectional"
    schema = SchemaBranch(cache={}, name="test")
    schema.load_schema(schema=SchemaRoot(**SCHEMA))
    schema.generate_identifiers()
    schema.validate_identifiers()

    assert True

    SCHEMA = {
        "nodes": [
            {
                "name": "Criticality",
                "namespace": "Test",
                "default_filter": "name__value",
                "branch": BranchSupportType.AWARE.value,
                "attributes": [
                    {"name": "name", "kind": "Text", "unique": True},
                ],
                "relationships": [
                    {"name": "first", "peer": "TestOther", "cardinality": "one", "direction": "outbound"},
                    {"name": "second", "peer": "TestOther", "cardinality": "one", "direction": "inbound"},
                ],
            },
            {
                "name": "Other",
                "namespace": "Test",
                "default_filter": "name__value",
                "branch": BranchSupportType.AWARE.value,
                "attributes": [
                    {"name": "name", "kind": "Text", "unique": True},
                ],
                "relationships": [
                    {"name": "first", "peer": "TestCriticality", "cardinality": "one", "direction": "bidirectional"},
                ],
            },
        ]
    }

    schema = SchemaBranch(cache={}, name="test")
    schema.load_schema(schema=SchemaRoot(**SCHEMA))
    schema.generate_identifiers()
    with pytest.raises(ValueError) as exc:
        schema.validate_identifiers()

    assert (
        str(exc.value)
        == "TestOther: Incompatible direction detected on Reverse Relationship for 'first' ('testcriticality__testother')  > bidirectional "
    )


async def test_schema_branch_validate_kinds_peer() -> None:
    SCHEMA1 = {
        "name": "Criticality",
        "namespace": "Test",
        "default_filter": "name__value",
        "branch": BranchSupportType.AWARE.value,
        "attributes": [
            {"name": "name", "kind": "Text", "unique": True},
        ],
        "relationships": [
            {"name": "first", "peer": "TestNotPresent", "cardinality": "one"},
        ],
    }

    schema = SchemaBranch(cache={}, name="test")
    schema.load_schema(schema=SchemaRoot(nodes=[SCHEMA1]))

    with pytest.raises(ValueError) as exc:
        schema.validate_kinds()

    assert str(exc.value) == "TestCriticality: Relationship 'first' is referring an invalid peer 'TestNotPresent'"


async def test_schema_branch_validate_kinds_common_relatives() -> None:
    schema_with_lag = copy.deepcopy(DEVICE_SCHEMA)
    lag_interface_schema = copy.deepcopy(LAG_INTERFACE)
    lag_interface_schema.relationships[0].common_parent = None
    lag_interface_schema.relationships[0].common_relatives = ["doesnotexist"]
    schema_with_lag.nodes.append(lag_interface_schema)

    schema = SchemaBranch(cache={}, name="test")
    schema.load_schema(schema=schema_with_lag)

    with pytest.raises(ValueError) as exc:
        schema.validate_kinds()

    assert str(exc.value) == (
        "TestingLinkAggegrationInterface: Relationship 'members' set 'common_relatives' with invalid relationship from "
        "'TestingPhysicalInterface'"
    )


async def test_schema_branch_validate_common_parent() -> None:
    schema_with_lag = copy.deepcopy(DEVICE_SCHEMA)
    lag_interface_schema = copy.deepcopy(LAG_INTERFACE)
    lag_interface_schema.relationships[0].common_parent = "device"
    schema_with_lag.nodes.append(lag_interface_schema)

    schema = SchemaBranch(cache={}, name="test")
    schema.load_schema(schema=schema_with_lag)
    schema.process_inheritance()
    schema.validate_kinds()


async def test_schema_branch_validate_common_parent_without_valid_parent() -> None:
    schema_with_lag = copy.deepcopy(DEVICE_SCHEMA)
    lag_interface_schema = copy.deepcopy(LAG_INTERFACE)
    lag_interface_schema.relationships[0].common_parent = "device"
    schema_with_lag.nodes.append(lag_interface_schema)

    schema = SchemaBranch(cache={}, name="test")
    schema.load_schema(schema=schema_with_lag)
    schema.process_inheritance()
    schema.get(name=TestKind.LAG_INTERFACE, duplicate=False).get_relationship("device").kind = RelationshipKind.GENERIC

    with pytest.raises(ValueError) as exc:
        schema.validate_kinds()

    assert str(exc.value) == (
        "TestingLinkAggegrationInterface: Relationship 'members' defines 'common_parent' but node does not have a parent relationship"
    )


async def test_schema_branch_validate_common_parent_invalid_relationship_name() -> None:
    schema_with_lag = copy.deepcopy(DEVICE_SCHEMA)
    lag_interface_schema = copy.deepcopy(LAG_INTERFACE)
    lag_interface_schema.relationships[0].common_parent = "foo"
    schema_with_lag.nodes.append(lag_interface_schema)

    schema = SchemaBranch(cache={}, name="test")
    schema.load_schema(schema=schema_with_lag)
    schema.process_inheritance()

    with pytest.raises(ValueError) as exc:
        schema.validate_kinds()

    assert str(exc.value) == (
        "TestingLinkAggegrationInterface: Relationship 'members' defines 'common_parent' but 'TestingPhysicalInterface.foo' does not exist"
    )


async def test_schema_branch_validate_common_parent_invalid_relationship_kind() -> None:
    schema_with_lag = copy.deepcopy(DEVICE_SCHEMA)
    lag_interface_schema = copy.deepcopy(LAG_INTERFACE)
    lag_interface_schema.relationships[0].common_parent = "device"
    schema_with_lag.nodes.append(lag_interface_schema)

    schema = SchemaBranch(cache={}, name="test")
    schema.load_schema(schema=schema_with_lag)
    schema.process_inheritance()
    schema.get(name=TestKind.PHYSICAL_INTERFACE, duplicate=False).get_relationship(
        "device"
    ).kind = RelationshipKind.GENERIC

    with pytest.raises(ValueError) as exc:
        schema.validate_kinds()

    assert str(exc.value) == (
        "TestingLinkAggegrationInterface: Relationship 'members' defines 'common_parent' but 'TestingPhysicalInterface.device is not of kind 'parent'"
    )


async def test_schema_branch_validate_kinds_inherit() -> None:
    SCHEMA1 = {
        "name": "Criticality",
        "namespace": "Test",
        "default_filter": "name__value",
        "branch": BranchSupportType.AWARE.value,
        "inherit_from": ["TestNotPresent"],
        "attributes": [
            {"name": "name", "kind": "Text", "unique": True},
        ],
    }

    schema = SchemaBranch(cache={}, name="test")
    schema.load_schema(schema=SchemaRoot(nodes=[SCHEMA1]))

    with pytest.raises(ValueError) as exc:
        schema.validate_kinds()

    assert str(exc.value) == "TestCriticality: 'TestNotPresent' is not a invalid Generic to inherit from"

    SCHEMA2 = {
        "name": "Criticality",
        "namespace": "Test",
        "default_filter": "name__value",
        "branch": BranchSupportType.AWARE.value,
        "attributes": [
            {"name": "name", "kind": "Text", "unique": True},
        ],
    }

    SCHEMA3 = {
        "name": "Other",
        "namespace": "Test",
        "default_filter": "name__value",
        "branch": BranchSupportType.AWARE.value,
        "inherit_from": ["TestCriticality"],
        "attributes": [
            {"name": "name", "kind": "Text", "unique": True},
        ],
    }

    schema = SchemaBranch(cache={}, name="test")
    schema.load_schema(schema=SchemaRoot(nodes=[SCHEMA2, SCHEMA3]))

    with pytest.raises(ValueError) as exc:
        schema.validate_kinds()

    assert (
        str(exc.value)
        == "TestOther: Only generic model can be used as part of inherit_from, 'TestCriticality' is not a valid entry."
    )


async def test_schema_branch_validate_kinds_core(register_core_models_schema: SchemaBranch) -> None:
    SCHEMA1 = {
        "name": "Criticality",
        "namespace": "Test",
        "default_filter": "name__value",
        "branch": BranchSupportType.AWARE.value,
        "inherit_from": ["LineageOwner"],
        "attributes": [
            {"name": "name", "kind": "Text", "unique": True},
        ],
        "relationships": [
            {"name": "first", "peer": "CoreNode", "cardinality": "one"},
        ],
    }

    register_core_models_schema.load_schema(schema=SchemaRoot(nodes=[SCHEMA1]))
    register_core_models_schema.validate_kinds()


@pytest.mark.parametrize(
    "uniqueness_constraints",
    [
        [["my_generic_name__value"], ["mybool__value"]],
        [["my_generic_name__value", "primary_tag"]],
    ],
)
async def test_validate_uniqueness_constraints_success(schema_all_in_one, uniqueness_constraints) -> None:
    schema_dict = _get_schema_by_kind(schema_all_in_one, "InfraGenericInterface")
    schema_dict["uniqueness_constraints"] = uniqueness_constraints

    schema = SchemaBranch(cache={}, name="test")
    schema.load_schema(schema=SchemaRoot(**schema_all_in_one))

    schema.validate_uniqueness_constraints()


@pytest.mark.parametrize(
    ["uniqueness_constraints", "unique_attributes", "expected_constraints", "expected_unique_attributes"],
    [
        (None, [], None, []),
        # name is on the generic and we don't add inherited unique attribute to the uniqueness constraints
        (None, ["name"], None, ["name"]),
        ([["name__value"]], ["name"], [["name__value"]], ["name"]),
        ([["name__value"]], [], [["name__value"]], ["name"]),
        ([["name__value"]], ["breed"], [["name__value"], ["breed__value"]], ["name", "breed"]),
        ([["name__value", "owner"]], ["breed"], [["name__value", "owner"], ["breed__value"]], ["breed"]),
        ([["owner"]], ["name"], [["owner"]], ["name"]),
        (None, ["name", "color"], [["color__value"]], ["name", "color"]),
        ([["color__value"], ["name__value"]], [], [["color__value"], ["name__value"]], ["name", "color"]),
    ],
)
async def test_synchronize_uniqueness_constraints_and_attributes(
    uniqueness_constraints: list[list[str]] | None,
    unique_attributes: list[str],
    expected_constraints: list[list[str]] | None,
    expected_unique_attributes: list[str],
    animal_person_schema_dict,
) -> None:
    schema = SchemaBranch(cache={}, name="test")
    for node_schema in animal_person_schema_dict["generics"]:
        if node_schema["name"] == "Animal" and node_schema["namespace"] == "Test":
            node_schema["uniqueness_constraints"] = None
            for attr_schema in node_schema["attributes"]:
                attr_schema["unique"] = attr_schema["name"] in unique_attributes
    for node_schema in animal_person_schema_dict["nodes"]:
        if node_schema["name"] == "Dog" and node_schema["namespace"] == "Test":
            node_schema["uniqueness_constraints"] = uniqueness_constraints
            for attr_schema in node_schema["attributes"]:
                attr_schema["unique"] = attr_schema["name"] in unique_attributes
    schema.load_schema(schema=SchemaRoot(**animal_person_schema_dict))

    schema.process_inheritance()
    schema.sync_uniqueness_constraints_and_unique_attributes()

    dog_schema = schema.get("TestDog", duplicate=False)
    assert dog_schema.uniqueness_constraints == expected_constraints
    assert {attr_schema.name for attr_schema in dog_schema.unique_attributes} == set(expected_unique_attributes)


async def test_validate_exception_ipam_ip_namespace(
    db: InfrahubDatabase, default_branch: Branch, register_core_models_schema
) -> None:
    SCHEMA: dict = {
        "nodes": [
            {
                "name": "IPPrefix",
                "namespace": "Ipam",
                "default_filter": "prefix__value",
                "order_by": ["prefix__value"],
                "display_labels": ["prefix__value"],
                "human_friendly_id": ["ip_namespace__name__value", "prefix__value"],
                "branch": BranchSupportType.AWARE.value,
                "inherit_from": [InfrahubKind.IPPREFIX],
            },
            {
                "name": "IPAddress",
                "namespace": "Ipam",
                "default_filter": "address__value",
                "order_by": ["address__value"],
                "display_labels": ["address__value"],
                "uniqueness_constraints": [["ip_namespace", "address__value"]],
                "branch": BranchSupportType.AWARE.value,
                "inherit_from": [InfrahubKind.IPADDRESS],
            },
        ],
    }

    ipam_schema = SchemaRoot(**SCHEMA)

    schema = registry.schema.get_schema_branch(name=default_branch.name)
    schema.load_schema(schema=ipam_schema)
    schema.process()

    ip_prefix_schema = schema.get(name="IpamIPPrefix")
    assert ip_prefix_schema.uniqueness_constraints


@pytest.mark.parametrize(
    "uniqueness_constraints,expected_error",
    [
        (
            [["mybool__value", "notanattribute__value"]],
            "InfraGenericInterface.uniqueness_constraints: notanattribute__value is invalid on schema InfraGenericInterface",
        ),
        (
            [["my_generic_name__something"]],
            "InfraGenericInterface.uniqueness_constraints: something is not a valid property of my_generic_name",
        ),
        (
            [["status__value"]],
            "InfraGenericInterface.uniqueness_constraints: value is not a valid attribute of TestingStatus",
        ),
        (
            [["badges__name__value"]],
            "InfraGenericInterface.uniqueness_constraints: cannot use badges relationship, relationship must be of cardinality one",
        ),
        (
            [["mybool__value", "badges"]],
            "InfraGenericInterface.uniqueness_constraints: cannot use badges relationship, relationship must be of cardinality one",
        ),
        (
            [["primary_tag__name__value"]],
            "InfraGenericInterface.uniqueness_constraints: cannot use attributes of related node, only the relationship",
        ),
        (
            [["mybool__value", "status__name__value"]],
            "InfraGenericInterface.uniqueness_constraints: cannot use status relationship, relationship must be mandatory. (`status__name__value`)",
        ),
        (
            [["mybool", "status__name__value"]],
            "InfraGenericInterface.uniqueness_constraints: invalid attribute, "
            "it must end with one of the following properties: value. (`mybool`)",
        ),
        (
            [["status__name"]],
            "InfraGenericInterface.uniqueness_constraints: cannot use status relationship, "
            "relationship must be mandatory. (`status__name`)",
        ),
    ],
)
async def test_validate_uniqueness_constraints_error(schema_all_in_one, uniqueness_constraints, expected_error) -> None:
    schema_dict = _get_schema_by_kind(schema_all_in_one, "InfraGenericInterface")
    schema_dict["uniqueness_constraints"] = uniqueness_constraints

    schema = SchemaBranch(cache={}, name="test")
    schema.load_schema(schema=SchemaRoot(**schema_all_in_one))

    with pytest.raises(ValueError, match=re.escape(expected_error)):
        schema.validate_uniqueness_constraints()


@pytest.mark.parametrize("display_labels", [["my_generic_name__value", "mybool__value"], ["my_generic_name__value"]])
async def test_validate_display_labels_success(schema_all_in_one, display_labels) -> None:
    schema_dict = _get_schema_by_kind(schema_all_in_one, "InfraGenericInterface")
    schema_dict["display_labels"] = display_labels

    schema = SchemaBranch(cache={}, name="test")
    schema.load_schema(schema=SchemaRoot(**schema_all_in_one))

    schema.validate_display_labels()


@pytest.mark.parametrize(
    "display_label", ["{{ my_generic_name__value }} {{ mybool__value }}", "my_generic_name__value"]
)
async def test_validate_display_label_success(schema_all_in_one, display_label: str) -> None:
    schema_dict = _get_schema_by_kind(schema_all_in_one, "InfraGenericInterface")
    schema_dict["display_label"] = display_label

    schema = SchemaBranch(cache={}, name="test")
    schema.load_schema(schema=SchemaRoot(**schema_all_in_one))

    schema.validate_display_label()


@pytest.mark.parametrize(
    "display_labels,expected_error",
    [
        (
            ["mybool__value", "notanattribute__value"],
            "InfraGenericInterface.display_labels: notanattribute__value is invalid on schema InfraGenericInterface",
        ),
        (
            ["my_generic_name__something"],
            "InfraGenericInterface.display_labels: something is not a valid property of my_generic_name",
        ),
        (
            ["status__value"],
            "InfraGenericInterface.display_labels: value is not a valid attribute of TestingStatus",
        ),
        (["badges__name__value"], "InfraGenericInterface.display_labels: this property only supports attributes"),
        (["badges"], "InfraGenericInterface.display_labels: this property only supports attributes, not relationships"),
        (["primary_tag__name__value"], "InfraGenericInterface.display_labels: this property only supports attributes"),
        (
            ["mybool__value", "status__name__value"],
            "InfraGenericInterface.display_labels: this property only supports attributes",
        ),
    ],
)
async def test_validate_display_labels_error(schema_all_in_one, display_labels, expected_error) -> None:
    schema_dict = _get_schema_by_kind(schema_all_in_one, "InfraGenericInterface")
    schema_dict["display_labels"] = display_labels

    schema = SchemaBranch(cache={}, name="test")
    schema.load_schema(schema=SchemaRoot(**schema_all_in_one))

    with pytest.raises(ValueError, match=expected_error):
        schema.validate_display_labels()


@pytest.mark.parametrize(
    "display_label,expected_error",
    [
        (
            "{{ mybool }}",
            re.escape(
                "InfraGenericInterface.display_label: invalid attribute, it must end with one of the following properties: value. (`mybool`)"
            ),
        ),
        (
            "{{ mybool__value }} {{ notanattribute__value }}",
            "InfraGenericInterface.display_label: notanattribute__value is invalid on schema InfraGenericInterface",
        ),
        (
            "my_generic_name__something",
            "InfraGenericInterface.display_label - non Jinja2: something is not a valid property of my_generic_name",
        ),
        (
            "status__value",
            "InfraGenericInterface.display_label - non Jinja2: value is not a valid attribute of TestingStatus",
        ),
        (
            "badges__name__value",
            "InfraGenericInterface.display_label - non Jinja2: this property only supports attributes, not relationships",
        ),
        (
            "badges",
            "InfraGenericInterface.display_label - non Jinja2: this property only supports attributes, not relationships",
        ),
    ],
)
async def test_validate_display_label_error(schema_all_in_one, display_label: str, expected_error: str) -> None:
    schema_dict = _get_schema_by_kind(schema_all_in_one, "InfraGenericInterface")
    schema_dict["display_label"] = display_label

    schema = SchemaBranch(cache={}, name="test")
    schema.load_schema(schema=SchemaRoot(**schema_all_in_one))

    with pytest.raises(ValueError, match=expected_error):
        schema.validate_display_label()


@pytest.mark.parametrize(
    "order_by",
    [
        ["my_generic_name__value", "mybool__value"],
        ["my_generic_name__value"],
        ["primary_tag__name__value"],
        ["status__name__value", "mybool__value"],
    ],
)
async def test_validate_order_by_success(schema_all_in_one, order_by) -> None:
    schema_dict = _get_schema_by_kind(schema_all_in_one, "InfraGenericInterface")
    schema_dict["order_by"] = order_by

    schema = SchemaBranch(cache={}, name="test")
    schema.load_schema(schema=SchemaRoot(**schema_all_in_one))

    schema.validate_order_by()


@pytest.mark.parametrize(
    "order_by,expected_error",
    [
        (
            ["mybool__value", "notanattribute__value"],
            "InfraGenericInterface.order_by: notanattribute__value is invalid on schema InfraGenericInterface",
        ),
        (
            ["my_generic_name__something"],
            "InfraGenericInterface.order_by: something is not a valid property of my_generic_name",
        ),
        (["status__value"], "InfraGenericInterface.order_by: value is not a valid attribute of TestingStatus"),
        (["badges__name__value"], "InfraGenericInterface.order_by: cannot use badges relationship"),
        (
            ["badges"],
            "InfraGenericInterface.order_by: cannot use badges relationship, relationship must be of cardinality one",
        ),
        (["status__name__nothing"], "InfraGenericInterface.order_by: nothing is not a valid property of name"),
        (
            ["my_generic_name"],
            "InfraGenericInterface.order_by: invalid attribute, it must end "
            "with one of the following properties: value. (`my_generic_name`)",
        ),
    ],
)
async def test_validate_order_by_error(schema_all_in_one, order_by, expected_error) -> None:
    schema_dict = _get_schema_by_kind(schema_all_in_one, "InfraGenericInterface")
    schema_dict["order_by"] = order_by

    schema = SchemaBranch(cache={}, name="test")
    schema.load_schema(schema=SchemaRoot(**schema_all_in_one))

    with pytest.raises(ValueError, match=re.escape(expected_error)):
        schema.validate_order_by()


@pytest.mark.parametrize(
    "default_filter",
    ["my_generic_name__value"],
)
async def test_validate_default_filter_success(schema_all_in_one, default_filter) -> None:
    schema_dict = _get_schema_by_kind(schema_all_in_one, "InfraGenericInterface")
    schema_dict["default_filter"] = default_filter

    schema = SchemaBranch(cache={}, name="test")
    schema.load_schema(schema=SchemaRoot(**schema_all_in_one))

    schema.validate_default_filters()


@pytest.mark.parametrize(
    "default_filter,expected_error",
    [
        (
            "notanattribute__value",
            "InfraGenericInterface.default_filter: notanattribute__value is invalid on schema InfraGenericInterface",
        ),
        (
            "my_generic_name__something",
            "InfraGenericInterface.default_filter: something is not a valid property of my_generic_name",
        ),
        (
            "badges__name__value",
            "InfraGenericInterface.default_filter: this property only supports attributes, not relationships",
        ),
        ("badges", "InfraGenericInterface.default_filter: this property only supports attributes, not relationships"),
        ("status__name__nothing", "InfraGenericInterface.default_filter: nothing is not a valid property of name"),
        (
            "primary_tag__name__value",
            "InfraGenericInterface.default_filter: this property only supports attributes, not relationship",
        ),
        (
            "status__name__value",
            "InfraGenericInterface.default_filter: this property only supports attributes, not relationship",
        ),
    ],
)
async def test_validate_default_filter_error(schema_all_in_one, default_filter, expected_error) -> None:
    schema_dict = _get_schema_by_kind(schema_all_in_one, "InfraGenericInterface")
    schema_dict["default_filter"] = default_filter

    schema = SchemaBranch(cache={}, name="test")
    schema.load_schema(schema=SchemaRoot(**schema_all_in_one))

    with pytest.raises(ValueError, match=expected_error):
        schema.validate_default_filters()


@pytest.mark.parametrize(
    "default_value_attr",
    [
        {"name": "something", "kind": "Number", "optional": True, "default_value": 0},
        {"name": "something", "kind": "Text", "optional": True, "default_value": "abcdef"},
    ],
)
async def test_validate_default_value_success(schema_all_in_one, default_value_attr) -> None:
    schema_dict = _get_schema_by_kind(schema_all_in_one, "InfraTinySchema")
    schema_dict["attributes"].append(default_value_attr)

    schema = SchemaBranch(cache={}, name="test")
    schema.load_schema(schema=SchemaRoot(**schema_all_in_one))

    schema.validate_default_values()


@pytest.mark.parametrize(
    "default_value_attr,expected_error",
    [
        (
            {"name": "something", "kind": "DateTime", "optional": True, "default_value": 0},
            "InfraTinySchema: default value 0 is not a valid DateTime",
        ),
        (
            {"name": "something", "kind": "IPHost", "optional": True, "default_value": "abcdef"},
            "InfraTinySchema: default value abcdef is not a valid IPHost",
        ),
        (
            {"name": "something", "kind": "Number", "optional": True, "default_value": "abcdef"},
            "InfraTinySchema: default value abcdef is not a valid Number",
        ),
    ],
)
async def test_validate_default_value_error(schema_all_in_one, default_value_attr, expected_error) -> None:
    schema_dict = _get_schema_by_kind(schema_all_in_one, "InfraTinySchema")
    schema_dict["attributes"].append(default_value_attr)

    schema = SchemaBranch(cache={}, name="test")
    schema.load_schema(schema=SchemaRoot(**schema_all_in_one))

    with pytest.raises(ValidationError, match=expected_error):
        schema.validate_default_values()


async def test_schema_branch_load_schema_extension(
    db: InfrahubDatabase, default_branch, builtin_schema, helper: TestHelper
) -> None:
    schema = SchemaRoot(**core_models)

    schema_branch = SchemaBranch(cache={}, name="test")
    schema_branch.load_schema(schema=schema)
    schema_branch.load_schema(schema=builtin_schema)
    schema_branch.load_schema(schema=SchemaRoot(**helper.schema_file("infra_simple_01.json")))

    schema_branch.process()

    org = schema_branch.get(name="TestingOrganization")
    initial_nbr_relationships = len(org.relationships)

    schema_branch.load_schema(schema=SchemaRoot(**helper.schema_file("infra_w_extensions_01.json")))

    org = schema_branch.get(name="TestingOrganization")
    assert len(org.relationships) == initial_nbr_relationships + 1
    assert schema_branch.get(name="InfraDevice")

    # Load it a second time to check if it's idempotent
    schema_branch.load_schema(schema=SchemaRoot(**helper.schema_file("infra_w_extensions_01.json")))
    org = schema_branch.get(name="TestingOrganization")
    assert len(org.relationships) == initial_nbr_relationships + 1
    assert schema_branch.get(name="InfraDevice")


async def test_schema_branch_validate_count_against_cardinality_valid(organization_schema) -> None:
    SCHEMA1 = {
        "name": "Criticality",
        "namespace": "Test",
        "default_filter": "name__value",
        "branch": BranchSupportType.AWARE.value,
        "attributes": [
            {"name": "name", "kind": "Text", "unique": True},
        ],
        "relationships": [
            {"name": "first", "peer": "CoreOrganization", "cardinality": "one"},
            {"name": "second", "peer": "CoreOrganization", "cardinality": "many"},
            {"name": "third", "peer": "CoreOrganization", "cardinality": "many", "min_count": 2, "max_count": 10},
            {"name": "fourth", "peer": "CoreOrganization", "cardinality": "many", "min_count": 0, "max_count": 10},
            {"name": "fifth", "peer": "CoreOrganization", "cardinality": "many", "min_count": 5, "max_count": 0},
            {"name": "sixth", "peer": "CoreOrganization", "cardinality": "many", "min_count": 5, "max_count": 5},
            {"name": "seventh", "peer": "CoreOrganization", "cardinality": "many", "min_count": 1, "max_count": 0},
            {"name": "eighth", "peer": "CoreOrganization", "cardinality": "many", "min_count": 1},
            {"name": "nineth", "peer": "CoreOrganization", "cardinality": "one", "optional": True},
            {
                "name": "tenth",
                "peer": "CoreOrganization",
                "cardinality": "one",
                "optional": True,
                "min_count": 0,
                "max_count": 0,
            },
            {"name": "eleventh", "peer": "CoreOrganization", "cardinality": "one", "min_count": 2, "max_count": 2},
        ],
    }

    copy_core_models = copy.deepcopy(core_models)
    copy_core_models["nodes"].append(SCHEMA1)
    schema = SchemaRoot(**copy_core_models)

    schema_branch = SchemaBranch(cache={}, name="test")
    schema_branch.load_schema(schema=schema)
    schema_branch.load_schema(schema=organization_schema)

    schema_branch.process_pre_validation()
    assert schema_branch.validate_count_against_cardinality() is None


@pytest.mark.parametrize(
    "relationship",
    (
        {"name": "second", "peer": "CoreOrganization", "cardinality": "many", "min_count": 10, "max_count": 2},
        {"name": "third", "peer": "CoreOrganization", "cardinality": "many", "min_count": 0, "max_count": 1},
    ),
)
async def test_schema_branch_validate_count_against_cardinality_invalid(relationship, organization_schema) -> None:
    SCHEMA1 = {
        "name": "Criticality",
        "namespace": "Test",
        "default_filter": "name__value",
        "branch": BranchSupportType.AWARE.value,
        "attributes": [
            {"name": "name", "kind": "Text", "unique": True},
        ],
        "relationships": [
            relationship,
        ],
    }

    copy_core_models = copy.deepcopy(core_models)
    copy_core_models["nodes"].append(SCHEMA1)
    schema = SchemaRoot(**copy_core_models)

    schema_branch = SchemaBranch(cache={}, name="test")
    schema_branch.load_schema(schema=schema)
    schema_branch.load_schema(schema=organization_schema)

    schema_branch.process_pre_validation()
    with pytest.raises(ValueError):
        schema_branch.validate_count_against_cardinality()


async def test_schema_branch_from_dict_schema_object() -> None:
    schema_branch = SchemaBranch(cache={}, name="test")

    # Load the core models and a model with a computed_attribute
    schema_branch.load_schema(schema=SchemaRoot(**core_models))
    schema_branch.load_schema(schema=SchemaRoot(nodes=[CHILD, THING]))

    exported = schema_branch.to_dict_schema_object()

    exported_json = json.dumps(exported, default=lambda x: x.model_dump())

    exported_dict = json.loads(exported_json)
    schema_branch_after = SchemaBranch.from_dict_schema_object(data=exported_dict)

    assert (
        schema_branch_after.get_node(name="BuiltinTag").get_hash()
        == schema_branch.get_node(name="BuiltinTag").get_hash()
    )


async def test_process_relationships_on_delete_defaults_set(schema_all_in_one) -> None:
    schema_dict = _get_schema_by_kind(schema_all_in_one, "TestingCriticality")
    schema_dict["relationships"][0]["kind"] = "Component"
    schema = SchemaBranch(cache={}, name="test")
    schema.load_schema(schema=SchemaRoot(**schema_all_in_one))

    schema.process_relationships()

    processed_criticality = schema.get(name="TestingCriticality", duplicate=False)
    processed_relationship = processed_criticality.get_relationship(name="tags")
    assert processed_relationship.on_delete == RelationshipDeleteBehavior.CASCADE
    for node_schema in schema.get_all(duplicate=False).values():
        for relationship in node_schema.relationships:
            if relationship.kind != RelationshipKind.COMPONENT:
                assert relationship.on_delete == RelationshipDeleteBehavior.NO_ACTION


async def test_process_relationships_component_can_be_overridden(schema_all_in_one) -> None:
    schema_dict = _get_schema_by_kind(schema_all_in_one, "TestingCriticality")
    schema_dict["relationships"][0]["kind"] = "Component"
    schema_dict["relationships"][0]["on_delete"] = "no-action"
    schema = SchemaBranch(cache={}, name="test")
    schema.load_schema(schema=SchemaRoot(**schema_all_in_one))

    schema.process_relationships()

    processed_criticality = schema.get(name="TestingCriticality", duplicate=False)
    processed_relationship = processed_criticality.get_relationship(name="tags")
    assert processed_relationship.on_delete == RelationshipDeleteBehavior.NO_ACTION


async def test_hierarchy_update(hierarchical_location_schema_simple: SchemaRoot) -> None:
    schema = SchemaBranch(cache={}, name="test")
    schema.load_schema(schema=hierarchical_location_schema_simple)
    schema.process_inheritance()
    schema.process_hierarchy()
    schema.add_hierarchy_generic()
    schema.add_hierarchy_node()

    site_schema = schema.get("LocationSite", duplicate=False)
    assert site_schema.parent == "LocationRegion"
    parent_rel = site_schema.get_relationship(name="parent")
    assert parent_rel.peer == "LocationRegion"
    region_schema = schema.get("LocationRegion", duplicate=False)
    assert region_schema.children == "LocationSite"
    children_rel = region_schema.get_relationship(name="children")
    assert children_rel.peer == "LocationSite"

    updated_schema = hierarchical_location_schema_simple.model_copy(deep=True)
    updated_schema.nodes.append(
        NodeSchema(
            name="Country",
            namespace="Location",
            inherit_from=["LocationGeneric"],
            children="LocationSite",
            parent="LocationRegion",
        )
    )
    site_schema = updated_schema.get("LocationSite")
    site_schema.parent = "LocationCountry"
    region_schema = updated_schema.get("LocationRegion")
    region_schema.children = "LocationCountry"
    schema.load_schema(updated_schema)

    schema.process_inheritance()
    schema.process_hierarchy()
    schema.add_hierarchy_generic()
    schema.add_hierarchy_node()

    site_schema = schema.get("LocationSite", duplicate=False)
    assert site_schema.parent == "LocationCountry"
    parent_rel = site_schema.get_relationship(name="parent")
    assert parent_rel.peer == "LocationCountry"
    region_schema = schema.get("LocationRegion", duplicate=False)
    assert region_schema.children == "LocationCountry"
    children_rel = region_schema.get_relationship(name="children")
    assert children_rel.peer == "LocationCountry"
    country_schema = schema.get("LocationCountry", duplicate=False)
    children_rel = country_schema.get_relationship(name="children")
    assert children_rel.peer == "LocationSite"
    parent_rel = country_schema.get_relationship(name="parent")
    assert parent_rel.peer == "LocationRegion"
    generic_schema = schema.get("LocationGeneric", duplicate=False)
    assert set(generic_schema.used_by) == {"LocationRegion", "LocationCountry", "LocationSite", "LocationRack"}


async def test_schema_branch_copy(
    db: InfrahubDatabase, reset_registry, default_branch: Branch, register_internal_models_schema
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
                    },
                    {
                        "name": "primary_tag",
                        "peer": "TestingTag",
                        "label": "Primary Tag",
                        "identifier": "primary_tag__criticality",
                        "optional": True,
                        "cardinality": "one",
                    },
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

    schema_branch = SchemaBranch(cache={}, name="test")
    schema_branch.load_schema(schema=SchemaRoot(**FULL_SCHEMA))
    new_schema = schema_branch.duplicate()

    assert id(new_schema.nodes) != id(schema_branch.nodes)
    assert new_schema.get_hash() == schema_branch.get_hash()

    new_schema.process()
    assert new_schema.get_hash() != schema_branch.get_hash()


async def test_schema_branch_diff_attribute(
    db: InfrahubDatabase, reset_registry, default_branch: Branch, register_internal_models_schema
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
                    },
                    {
                        "name": "primary_tag",
                        "peer": "TestingTag",
                        "label": "Primary Tag",
                        "identifier": "primary_tag__criticality",
                        "optional": True,
                        "cardinality": "one",
                    },
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
    new_schema = schema_branch.duplicate()

    node = new_schema.get(name="TestingCriticality")
    node.attributes[0].unique = False
    new_schema.set(name="TestingCriticality", schema=node)

    diff = schema_branch.diff(other=new_schema)
    assert diff.model_dump() == {
        "added": {},
        "changed": {
            "TestingCriticality": {
                "added": {},
                "changed": {
                    "attributes": {
                        "added": {},
                        "changed": {
                            "name": {"added": {}, "changed": {"unique": None}, "removed": {}},
                        },
                        "removed": {},
                    },
                },
                "removed": {},
            },
        },
        "removed": {},
    }


async def test_schema_branch_diff_rename_element(
    db: InfrahubDatabase, reset_registry, default_branch: Branch, register_internal_models_schema
) -> None:
    FULL_SCHEMA = {
        "nodes": [
            {
                "id": str(uuid.uuid4()),
                "name": "Criticality",
                "namespace": "Testing",
                "default_filter": "name__value",
                "label": "Criticality",
                "attributes": [
                    {"id": str(uuid.uuid4()), "name": "name", "kind": "Text", "label": "Name", "unique": True},
                    {"id": str(uuid.uuid4()), "name": "level", "kind": "Number", "label": "Level"},
                    {
                        "id": str(uuid.uuid4()),
                        "name": "color",
                        "kind": "Text",
                        "label": "Color",
                        "default_value": "#444444",
                    },
                    {
                        "id": str(uuid.uuid4()),
                        "name": "description",
                        "kind": "Text",
                        "label": "Description",
                        "optional": True,
                    },
                ],
                "relationships": [
                    {
                        "id": str(uuid.uuid4()),
                        "name": "tags",
                        "peer": "TestingTag",
                        "label": "Tags",
                        "optional": True,
                        "cardinality": "many",
                    },
                    {
                        "id": str(uuid.uuid4()),
                        "name": "primary_tag",
                        "peer": "TestingTag",
                        "label": "Primary Tag",
                        "identifier": "primary_tag__criticality",
                        "optional": True,
                        "cardinality": "one",
                    },
                ],
            },
            {
                "id": str(uuid.uuid4()),
                "name": "Tag",
                "namespace": "Testing",
                "label": "Tag",
                "default_filter": "name__value",
                "attributes": [
                    {"id": str(uuid.uuid4()), "name": "name", "kind": "Text", "label": "Name", "unique": True},
                    {
                        "id": str(uuid.uuid4()),
                        "name": "description",
                        "kind": "Text",
                        "label": "Description",
                        "optional": True,
                    },
                ],
            },
        ]
    }

    schema_branch = SchemaBranch(cache={}, name="test")
    schema_branch.load_schema(schema=SchemaRoot(**FULL_SCHEMA))
    new_schema = schema_branch.duplicate()

    criticality = new_schema.get(name="TestingCriticality")
    criticality.attributes[0].name = f"new-{criticality.attributes[0].name}"
    criticality.relationships[0].name = f"new-{criticality.relationships[0].name}"
    new_schema.set(name="TestingCriticality", schema=criticality)

    tag = new_schema.get(name="TestingTag")
    tag.name = "NewTag"
    new_schema.delete(name="TestingTag")
    new_schema.set(name="TestingNewTag", schema=tag)

    diff = schema_branch.diff(other=new_schema)
    assert diff.model_dump() == {
        "added": {},
        "changed": {
            "TestingCriticality": {
                "added": {},
                "changed": {
                    "attributes": {
                        "added": {},
                        "changed": {
                            "new-name": {
                                "added": {},
                                "changed": {"name": None},
                                "removed": {},
                            },
                        },
                        "removed": {},
                    },
                    "relationships": {
                        "added": {},
                        "changed": {
                            "new-tags": {
                                "added": {},
                                "changed": {"name": None},
                                "removed": {},
                            },
                        },
                        "removed": {},
                    },
                },
                "removed": {},
            },
            "TestingNewTag": {"added": {}, "changed": {"name": None}, "removed": {}},
        },
        "removed": {},
    }


async def test_schema_branch_diff_add_node_relationship(
    db: InfrahubDatabase, reset_registry, default_branch: Branch, register_internal_models_schema
) -> None:
    SCHEMA1 = {
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
            },
        ]
    }

    SCHEMA2 = {
        "nodes": [
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
        ],
        "extensions": {
            "nodes": [
                {
                    "kind": "TestingCriticality",
                    "relationships": [
                        {
                            "name": "tags",
                            "peer": "TestingTag",
                            "label": "Tags",
                            "optional": True,
                            "cardinality": "many",
                        },
                        {
                            "name": "primary_tag",
                            "peer": "TestingTag",
                            "label": "Primary Tag",
                            "identifier": "primary_tag__criticality",
                            "optional": True,
                            "cardinality": "one",
                        },
                    ],
                }
            ]
        },
    }

    schema1 = SchemaRoot(**SCHEMA1)
    schema1.generate_uuid()
    schema2 = SchemaRoot(**SCHEMA2)
    schema2.generate_uuid()

    schema_branch = SchemaBranch(cache={}, name="test")
    schema_branch.load_schema(schema=schema1)
    new_schema = schema_branch.duplicate()
    new_schema.load_schema(schema=schema2)

    diff = schema_branch.diff(other=new_schema)
    assert diff.model_dump() == {
        "added": {"TestingTag": {"added": {}, "changed": {}, "removed": {}}},
        "changed": {
            "TestingCriticality": {
                "added": {},
                "changed": {
                    "relationships": {
                        "added": {"primary_tag": None, "tags": None},
                        "changed": {},
                        "removed": {},
                    }
                },
                "removed": {},
            },
        },
        "removed": {},
    }


async def test_schema_branch_validate_check_missing(
    db: InfrahubDatabase, reset_registry, default_branch: Branch, register_internal_models_schema
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
                    },
                    {
                        "name": "primary_tag",
                        "peer": "TestingTag",
                        "label": "Primary Tag",
                        "identifier": "primary_tag__criticality",
                        "optional": True,
                        "cardinality": "one",
                    },
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
    new_schema = schema_branch.duplicate()

    node = new_schema.get(name="TestingCriticality")
    node.attributes[0].unique = False
    new_schema.set(name="TestingCriticality", schema=node)

    diff = schema_branch.diff(other=new_schema)
    result = schema_branch.validate_update(other=new_schema, diff=diff)
    assert result.model_dump(exclude=["diff"]) == {
        "constraints": [
            {
                "constraint_name": "attribute.unique.update",
                "path": {
                    "field_name": "name",
                    "path_type": SchemaPathType.ATTRIBUTE,
                    "property_name": "unique",
                    "schema_id": None,
                    "schema_kind": "TestingCriticality",
                },
            },
        ],
        "enforce_update_support": True,
        "errors": [],
        "migrations": [],
    }


async def test_schema_branch_validate_node_deletion(
    db: InfrahubDatabase, reset_registry, default_branch: Branch, register_internal_models_schema
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


async def test_schema_branch_validate_add_node_relationships(
    db: InfrahubDatabase, reset_registry, default_branch: Branch, register_internal_models_schema
) -> None:
    SCHEMA1 = {
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
            },
        ]
    }

    SCHEMA2 = {
        "nodes": [
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
        ],
        "extensions": {
            "nodes": [
                {
                    "kind": "TestingCriticality",
                    "relationships": [
                        {
                            "name": "tags",
                            "peer": "TestingTag",
                            "label": "Tags",
                            "optional": True,
                            "cardinality": "many",
                        },
                        {
                            "name": "primary_tag",
                            "peer": "TestingTag",
                            "label": "Primary Tag",
                            "identifier": "primary_tag__criticality",
                            "optional": True,
                            "cardinality": "one",
                        },
                    ],
                }
            ]
        },
    }

    schema1 = SchemaRoot(**SCHEMA1)
    schema1.generate_uuid()
    schema2 = SchemaRoot(**SCHEMA2)
    schema2.generate_uuid()

    schema_branch = SchemaBranch(cache={}, name="test")
    schema_branch.load_schema(schema=schema1)
    new_schema = schema_branch.duplicate()
    new_schema.load_schema(schema=schema2)

    diff = schema_branch.diff(other=new_schema)
    result = schema_branch.validate_update(other=new_schema, diff=diff)
    assert result.model_dump(exclude=["diff"]) == {
        "constraints": [
            {
                "constraint_name": "node.relationship.add",
                "path": {
                    "field_name": "primary_tag",
                    "path_type": SchemaPathType.RELATIONSHIP,
                    "property_name": None,
                    "schema_id": None,
                    "schema_kind": "TestingCriticality",
                },
            },
            {
                "constraint_name": "node.relationship.add",
                "path": {
                    "field_name": "tags",
                    "path_type": SchemaPathType.RELATIONSHIP,
                    "property_name": None,
                    "schema_id": None,
                    "schema_kind": "TestingCriticality",
                },
            },
        ],
        "enforce_update_support": True,
        "errors": [],
        "migrations": [],
    }


# -----------------------------------------------------------------
# SchemaManager
# -----------------------------------------------------------------
async def test_schema_manager_set() -> None:
    SCHEMA = {
        "name": "Criticality",
        "namespace": "Testing",
        "default_filter": "name__value",
        "attributes": [
            {"name": "name", "kind": "Text", "unique": True},
            {"name": "description", "kind": "Text"},
        ],
    }
    schema = NodeSchema(**SCHEMA)
    manager = SchemaManager()

    manager.set(name="schema1", schema=schema)
    assert len(manager._cache) > 0
    cache_size = len(manager._cache)

    manager.set(name="schema2", schema=schema)
    assert len(manager._cache) == cache_size


async def test_schema_manager_get(default_branch: Branch) -> None:
    SCHEMA = {
        "name": "Criticality",
        "namespace": "Testing",
        "default_filter": "name__value",
        "attributes": [
            {"name": "name", "kind": "Text", "unique": True},
            {"name": "description", "kind": "Text"},
        ],
    }
    schema = NodeSchema(**SCHEMA)

    manager = SchemaManager()

    manager.set(name="schema1", schema=schema)
    assert len(manager._cache) > 0

    schema11 = manager.get(name="schema1")
    assert schema11.namespace == schema.namespace


async def test_schema_manager_purge(default_branch: Branch, reset_registry: None) -> None:
    criticality_schema = NodeSchema(
        name="Criticality",
        namespace="Test",
        default_filter="name__value",
        attributes=[
            AttributeSchema(name="name", kind="Text", unique=True),
            AttributeSchema(name="description", kind="Text"),
        ],
    )

    person_schema = NodeSchema(
        name="Person",
        namespace="Test",
        default_filter="name__value",
        attributes=[
            AttributeSchema(name="name", kind="Text", unique=True),
            AttributeSchema(name="description", kind="Text"),
        ],
    )

    dog_schema = NodeSchema(
        name="Dog",
        namespace="Test",
        default_filter="name__value",
        attributes=[
            AttributeSchema(name="name", kind="Text", unique=True),
            AttributeSchema(name="description", kind="Text"),
        ],
    )

    manager = SchemaManager()

    manager.set(name="criticality_schema", schema=criticality_schema)
    manager.set(name="criticality_schema", schema=criticality_schema, branch="main")
    manager.set(name="criticality_schema", schema=criticality_schema, branch="branch1")
    manager.set(name="criticality_schema", schema=criticality_schema, branch="branch2")
    manager.set(name="criticality_schema", schema=criticality_schema, branch="branch3")
    manager.set(name="person_schema", schema=person_schema, branch="main")
    manager.set(name="person_schema", schema=person_schema, branch="branch1")
    manager.set(name="person_schema", schema=person_schema, branch="branch2")
    manager.set(name="person_schema", schema=person_schema, branch="branch3")
    manager.set(name="criticality_schema", schema=criticality_schema, branch="branch4")
    manager.set(name="dog_schema", schema=dog_schema, branch="branch4")
    assert len(manager._cache) == 3
    assert criticality_schema.get_hash() in manager._cache
    assert person_schema.get_hash() in manager._cache
    assert dog_schema.get_hash() in manager._cache
    purged = manager.purge_inactive_branches(active_branches=["main", "branch1", "branch2"])
    assert purged == ["branch3", "branch4"]
    assert len(manager._cache) == 2
    assert criticality_schema.get_hash() in manager._cache
    assert person_schema.get_hash() in manager._cache
    assert dog_schema.get_hash() not in manager._cache


# -----------------------------------------------------------------


async def test_load_node_to_db_node_schema(db: InfrahubDatabase, default_branch: Branch) -> None:
    registry.schema = SchemaManager()
    registry.schema.register_schema(schema=SchemaRoot(**internal_schema), branch=default_branch.name)

    node = NodeSchema(
        name="Criticality",
        namespace="Testing",
        default_filter="name__value",
        attributes=[
            AttributeSchema(name="name", kind="Text", unique=True),
            AttributeSchema(name="level", kind="Number"),
            AttributeSchema(name="color", kind="Text", default_value="default_value"),
            AttributeSchema(
                name="description",
                kind="Text",
                optional=True,
                computed_attribute=ComputedAttribute(kind="Jinja2", jinja2_template="{{ name__value }}"),
            ),
        ],
        relationships=[RelationshipSchema(name="others", peer="TestingCriticality", optional=True, cardinality="many")],
    )
    await registry.schema.load_node_to_db(node=node, db=db, branch=default_branch, at=Timestamp(), user_id="user-id")

    node2 = registry.schema.get(name=node.kind, branch=default_branch)
    assert node2.id
    assert node2.relationships[0].id
    assert node2.attributes[0].id

    node_from_db = await SchemaManager.get_one(db=db, id=node2.id, branch=default_branch)
    assert node_from_db


async def test_load_node_to_db_generic_schema(db: InfrahubDatabase, default_branch) -> None:
    registry.schema = SchemaManager()
    registry.schema.register_schema(schema=SchemaRoot(**internal_schema), branch=default_branch.name)

    SCHEMA = {
        "name": "GenericInterface",
        "namespace": "Infra",
        "attributes": [
            {"name": "my_generic_name", "kind": "Text"},
        ],
    }
    node = GenericSchema(**SCHEMA)
    await registry.schema.load_node_to_db(node=node, db=db, branch=default_branch, at=Timestamp(), user_id="user-id")

    results = await SchemaManager.query(
        schema="SchemaGeneric", filters={"kind__value": "InfraGenericInterface"}, branch=default_branch, db=db
    )
    assert len(results) == 1


async def test_get_incorrect_kinds(default_branch: Branch) -> None:
    person_schema = NodeSchema(
        name="Person",
        namespace="Test",
        default_filter="name__value",
        attributes=[
            AttributeSchema(name="name", kind="Text", unique=True),
            AttributeSchema(name="description", kind="Text"),
        ],
    )

    house_generic = GenericSchema(
        name="House", namespace="Test", attributes=[AttributeSchema(name="name", kind="Text", unique=True)]
    )
    manager = SchemaManager()

    manager.set(name="TestPerson", schema=person_schema, branch=default_branch.name)
    manager.set(name="TestHouse", schema=house_generic, branch=default_branch.name)

    with pytest.raises(ValueError, match="The selected node is not of type NodeSchema"):
        manager.get_node_schema(name="TestHouse", branch=default_branch.name, duplicate=False)

    with pytest.raises(ValueError, match="The selected node is not of type GenericSchema"):
        manager.get_generic_schema(name="TestPerson", branch=default_branch.name, duplicate=False)


async def test_update_node_in_db_node_schema(db: InfrahubDatabase, default_branch: Branch) -> None:
    SCHEMA = {
        "name": "Criticality",
        "namespace": "Testing",
        "default_filter": "name__value",
        "attributes": [
            {"name": "name", "kind": "Text", "unique": True},
            {"name": "level", "kind": "Number"},
            {"name": "color", "kind": "Text", "default_value": "#444444"},
            {"name": "description", "kind": "Text", "optional": True},
        ],
        "relationships": [
            {"name": "others", "peer": "TestingCriticality", "optional": True, "cardinality": "many"},
        ],
    }

    registry.schema = SchemaManager()
    registry.schema.register_schema(schema=SchemaRoot(**internal_schema), branch=default_branch.name)
    await registry.schema.load_node_to_db(
        node=NodeSchema(**SCHEMA), db=db, branch=default_branch, at=Timestamp(), user_id="user-id"
    )

    node = registry.schema.get(name="TestingCriticality", branch=default_branch)

    new_node = node.duplicate()

    new_node.default_filter = "kind__value"
    new_node.attributes[0].unique = False

    await registry.schema.update_node_in_db(
        node=new_node, db=db, branch=default_branch, at=Timestamp(), user_id="user-id"
    )

    results = await SchemaManager.get_many(ids=[node.id, new_node.attributes[0].id], db=db)

    assert results[new_node.id].default_filter.value == "kind__value"
    assert results[new_node.attributes[0].id].unique.value is False


async def test_load_schema_to_db_internal_models(db: InfrahubDatabase, default_branch: Branch) -> None:
    schema = SchemaRoot(**internal_schema)
    new_schema = registry.schema.register_schema(schema=schema, branch=default_branch.name)

    await registry.schema.load_schema_to_db(schema=new_schema, db=db, branch=default_branch.name, at=Timestamp())

    node_schema = registry.schema.get(name="SchemaNode", branch=default_branch)
    results = await SchemaManager.query(schema=node_schema, db=db)
    assert len(results) > 1
    assert all(r for r in results if r.namespace.value != "Profile")


async def test_load_schema_to_db_core_models(
    db: InfrahubDatabase, default_branch: Branch, register_internal_models_schema
) -> None:
    schema = SchemaRoot(**core_models)
    new_schema = registry.schema.register_schema(schema=schema, branch=default_branch.name)

    await registry.schema.load_schema_to_db(schema=new_schema, db=db, at=Timestamp())

    node_schema = registry.schema.get(name="SchemaGeneric")
    results = await SchemaManager.query(schema=node_schema, db=db)
    assert len(results) > 1
    assert all(r for r in results if r.namespace.value != "Profile")


async def test_clean_diff_after_reload_from_db(
    db: InfrahubDatabase, default_branch: Branch, register_internal_models_schema
) -> None:
    schema = SchemaRoot(**core_models)
    new_schema = registry.schema.register_schema(schema=schema, branch=default_branch.name)

    await registry.schema.load_schema_to_db(schema=new_schema, db=db, at=Timestamp())

    schema_branch = registry.schema.get_schema_branch(name=default_branch.name)
    schema_pre = schema_branch.duplicate()

    await registry.schema.load_schema_from_db(db=db, branch=default_branch, schema=schema_branch)

    assert not schema_pre.diff(other=schema_branch).all


async def test_load_schema_to_db_simple_01(
    db: InfrahubDatabase,
    default_branch: Branch,
    register_core_models_schema: SchemaBranch,
    register_builtin_models_schema: SchemaBranch,
    helper,
) -> None:
    schema = SchemaRoot(**helper.schema_file("infra_simple_01.json"))
    new_schema = registry.schema.register_schema(schema=schema, branch=default_branch.name)
    await registry.schema.load_schema_to_db(schema=new_schema, db=db, branch=default_branch)

    node_schema = registry.schema.get(name="SchemaNode")
    results = await SchemaManager.query(
        schema=node_schema, filters={"name__value": "Device"}, db=db, branch=default_branch
    )
    assert len(results) == 1


async def test_load_schema_to_db_includes_metadata(
    db: InfrahubDatabase,
    default_branch: Branch,
    register_internal_models_schema: SchemaBranch,
    branch: Branch,
    schema_criticality_tag: dict,
) -> None:
    """Verify that SchemaNode, SchemaAttribute, and SchemaRelationship metadata is properly set."""
    test_user_id = "test-user-id-12345"

    # Record time window around schema load
    time_before = Timestamp()

    # Register and load the schema with a specific user_id
    schema = SchemaRoot(**schema_criticality_tag)
    new_schema = registry.schema.register_schema(schema=schema, branch=branch.name)
    await registry.schema.load_schema_to_db(schema=new_schema, db=db, branch=branch, user_id=test_user_id)

    time_after = Timestamp()

    # Query the SchemaNode (TestingCriticality) with metadata
    node_schema = registry.schema.get(name="SchemaNode")
    results = await SchemaManager.query(
        schema=node_schema,
        filters={"name__value": "Criticality"},
        db=db,
        branch=branch,
        include_metadata=MetadataOptions.USER_TIMESTAMPS,
    )
    assert len(results) == 1

    schema_node = results[0]

    # Verify SchemaNode metadata with time window
    assert time_before < schema_node._get_created_at() < time_after
    assert schema_node._get_created_by() == test_user_id
    assert time_before < schema_node._get_updated_at() < time_after
    assert schema_node._get_updated_by() == test_user_id

    # Get attribute Relationship edges and peers using query_peers with fetch_peers=True
    attributes_rel_schema = node_schema.get_relationship(name="attributes")
    attr_edge_results = await NodeManager.query_peers(
        db=db,
        branch=branch,
        ids=[schema_node.id],
        source_kind="SchemaNode",
        schema=attributes_rel_schema,
        filters={},
        include_metadata=MetadataOptions.USER_TIMESTAMPS,
        fetch_peers=True,
    )
    assert len(attr_edge_results) > 0

    # Verify metadata on the first attribute edge (Relationship object)
    first_attr_edge = attr_edge_results[0]
    assert time_before < first_attr_edge._get_created_at() < time_after
    assert first_attr_edge._get_created_by() == test_user_id
    assert time_before < first_attr_edge._get_updated_at() < time_after
    assert first_attr_edge._get_updated_by() == test_user_id

    # Verify metadata on the peer (SchemaAttribute node) retrieved from the relationship
    first_attr = await first_attr_edge.get_peer(db=db)
    assert time_before < first_attr._get_created_at() < time_after
    assert first_attr._get_created_by() == test_user_id
    assert time_before < first_attr._get_updated_at() < time_after
    assert first_attr._get_updated_by() == test_user_id

    # Verify metadata on an attribute of first_attr (SchemaAttribute.name)
    first_attr_name = first_attr.get_attribute("name")
    assert time_before < first_attr_name._get_created_at() < time_after
    assert first_attr_name._get_created_by() == test_user_id
    assert time_before < first_attr_name._get_updated_at() < time_after
    assert first_attr_name._get_updated_by() == test_user_id

    # Get relationship Relationship edges and peers using query_peers with fetch_peers=True
    relationships_rel_schema = node_schema.get_relationship(name="relationships")
    rel_edge_results = await NodeManager.query_peers(
        db=db,
        branch=branch,
        ids=[schema_node.id],
        source_kind="SchemaNode",
        schema=relationships_rel_schema,
        filters={},
        include_metadata=MetadataOptions.USER_TIMESTAMPS,
        fetch_peers=True,
    )
    assert len(rel_edge_results) > 0

    # Verify metadata on the first relationship edge (Relationship object)
    first_rel_edge = rel_edge_results[0]
    assert time_before < first_rel_edge._get_created_at() < time_after
    assert first_rel_edge._get_created_by() == test_user_id
    assert time_before < first_rel_edge._get_updated_at() < time_after
    assert first_rel_edge._get_updated_by() == test_user_id

    # Verify metadata on the peer (SchemaRelationship node) retrieved from the relationship
    first_rel = await first_rel_edge.get_peer(db=db)
    assert time_before < first_rel._get_created_at() < time_after
    assert first_rel._get_created_by() == test_user_id
    assert time_before < first_rel._get_updated_at() < time_after
    assert first_rel._get_updated_by() == test_user_id

    # Verify metadata on an attribute of first_rel (SchemaRelationship.name)
    first_rel_name = first_rel.get_attribute("name")
    assert time_before < first_rel_name._get_created_at() < time_after
    assert first_rel_name._get_created_by() == test_user_id
    assert time_before < first_rel_name._get_updated_at() < time_after
    assert first_rel_name._get_updated_by() == test_user_id

    time_before_str = time_before.to_string()
    time_after_str = time_after.to_string()

    query_params = {
        "branch": branch.name,
        "time_before": time_before_str,
        "time_after": time_after_str,
        "user_id": test_user_id,
    }
    find_illegal_schema_edges_query = """
// ------------
// Start with all SchemaNode, SchemaAttribute, and SchemaRelationship vertices
// and check all linked edges
// ------------
MATCH (n:SchemaNode|SchemaAttribute|SchemaRelationship)
CALL (n) {
    OPTIONAL MATCH (n)-[r]-(peer)
    WHERE r.status <> "active"
    OR r.branch <> $branch
    OR r.from < $time_before
    OR r.from > $time_after
    OR r.from_user_id <> $user_id
    RETURN r, peer
}
WITH n, collect(
    CASE WHEN r IS NOT NULL OR peer IS NOT NULL THEN {
        edge_type: type(r),
        edge_from: r.from,
        edge_from_user_id: r.from_user_id,
        peer_labels: labels(peer),
        peer_uuid: peer.uuid
    }
    ELSE NULL
    END
) AS illegal_node_edges
// ------------
// For each SchemaNode, SchemaAttribute, and SchemaRelationship, check all linked Attribute/Relationship vertices
// and their linked edges
// ------------
MATCH (n)-[:HAS_ATTRIBUTE|IS_RELATED]-(field:Attribute|Relationship)
WITH DISTINCT n, illegal_node_edges, field
CALL (field) {
    OPTIONAL MATCH (field)-[r]-(prop)
    WHERE r.status <> "active"
    OR r.branch <> $branch
    OR r.from < $time_before
    OR r.from > $time_after
    OR r.from_user_id <> $user_id
    RETURN r, prop
}
WITH n, illegal_node_edges, collect (
    CASE WHEN r IS NOT NULL OR prop IS NOT NULL THEN {
        edge_type: type(r),
        edge_from: r.from,
        edge_from_user_id: r.from_user_id,
        peer_labels: labels(prop),
        peer_value: COALESCE(prop.uuid, prop.value)
    }
    ELSE NULL
    END
) AS illegal_field_edges
WITH n, illegal_node_edges, illegal_field_edges
WHERE size(illegal_node_edges) > 0 OR size(illegal_field_edges) > 0
RETURN n.uuid AS node_uuid, n.kind AS node_kind, illegal_node_edges, illegal_field_edges
    """

    records = await db.execute_query(query=find_illegal_schema_edges_query, params=query_params)

    # The query only returns records with illegal edges, so any results indicate a failure
    error_messages = []
    for record in records:
        node_uuid = record.get("node_uuid")
        node_kind = record.get("node_kind")

        illegal_node_edges = [e for e in record.get("illegal_node_edges", []) if e is not None]
        illegal_field_edges = [e for e in record.get("illegal_field_edges", []) if e is not None]

        for edge in illegal_node_edges:
            error_messages.append(
                f"Illegal edge on {node_kind} '{node_uuid}': "
                f"type={edge.get('edge_type')}, from={edge.get('edge_from')}, "
                f"from_user_id={edge.get('edge_from_user_id')}, "
                f"peer_labels={edge.get('peer_labels')}, peer_uuid={edge.get('peer_uuid')}"
            )

        for edge in illegal_field_edges:
            error_messages.append(
                f"Illegal field edge on {node_kind} '{node_uuid}': "
                f"type={edge.get('edge_type')}, from={edge.get('edge_from')}, "
                f"from_user_id={edge.get('edge_from_user_id')}, "
                f"peer_labels={edge.get('peer_labels')}, peer_value={edge.get('peer_value')}"
            )

    assert not error_messages, "Found illegal edges:\n" + "\n".join(error_messages)


async def test_load_schema_to_db_w_generics_01(
    db: InfrahubDatabase,
    default_branch: Branch,
    register_core_models_schema: SchemaBranch,
    register_builtin_models_schema: SchemaBranch,
    helper,
) -> None:
    schema = SchemaRoot(**helper.schema_file("infra_w_generics_01.json"))
    new_schema = registry.schema.register_schema(schema=schema, branch=default_branch.name)
    await registry.schema.load_schema_to_db(schema=new_schema, db=db, branch=default_branch)

    node_schema = registry.schema.get(name="SchemaNode")
    results = await SchemaManager.query(
        schema=node_schema, filters={"name__value": "InterfaceL3"}, db=db, branch=default_branch
    )
    assert len(results) == 1


async def test_load_schema_from_db(
    db: InfrahubDatabase, reset_registry, default_branch: Branch, register_internal_models_schema
) -> None:
    FULL_SCHEMA = {
        "nodes": [
            {
                "namespace": "Test",
                "name": "Criticality",
                "default_filter": "name__value",
                "human_friendly_id": ["name__value"],
                "label": "Criticality",
                "include_in_menu": True,
                "attributes": [
                    {"name": "name", "kind": "Text", "label": "Name", "unique": True},
                    {"name": "level", "kind": "Number", "label": "Level"},
                    {"name": "color", "kind": "Text", "label": "Color", "default_value": "#444444"},
                    {
                        "name": "description",
                        "kind": "Text",
                        "label": "Description",
                        "optional": True,
                        "read_only": True,
                        "computed_attribute": {"kind": "Jinja2", "jinja2_template": "{{ name__value }}"},
                    },
                ],
                "relationships": [
                    {
                        "name": "tags",
                        "peer": "TestingTag",
                        "label": "Tags",
                        "optional": True,
                        "cardinality": "many",
                    },
                    {
                        "name": "primary_tag",
                        "peer": "TestingTag",
                        "label": "Primary Tag",
                        "identifier": "primary_tag__criticality",
                        "optional": True,
                        "cardinality": "one",
                    },
                ],
            },
            {
                "namespace": "Testing",
                "name": "Tag",
                "label": "Tag",
                "include_in_menu": False,
                "default_filter": "name__value",
                "human_friendly_id": ["name__value"],
                "attributes": [
                    {"name": "name", "kind": "Text", "label": "Name", "unique": True},
                    {"name": "description", "kind": "Text", "label": "Description", "optional": True},
                ],
            },
        ],
        "generics": [
            {
                "namespace": "Test",
                "name": "GenericInterface",
                "label": "Generic Interface",
                "include_in_menu": True,
                "attributes": [
                    {"name": "my_generic_name", "kind": "Text", "label": "My Generic String"},
                ],
            },
        ],
    }

    schema1 = registry.schema.register_schema(schema=SchemaRoot(**FULL_SCHEMA), branch=default_branch.name)
    crit_schema = schema1.get(name="TestCriticality", duplicate=False)

    await registry.schema.load_schema_to_db(schema=schema1, db=db, branch=default_branch.name)
    start_crit_schema = schema1.get(name="TestCriticality", duplicate=False)
    start_crit_hash = start_crit_schema.get_hash()
    schema11 = registry.schema.get_schema_branch(name=default_branch.name)
    schema2 = await registry.schema.load_schema_from_db(db=db, branch=default_branch.name)

    assert len(schema2.nodes) == 6
    assert set(schema2.generics.keys()) == {"CoreProfile", "TestGenericInterface"}
    assert set(schema2.profiles.keys()) == {
        "ProfileTestingTag",
        "ProfileTestCriticality",
        "ProfileTestGenericInterface",
    }

    crit_schema = schema2.get(name="TestCriticality", duplicate=False)
    profiles_rel_schema = crit_schema.get_relationship("profiles")
    assert profiles_rel_schema.peer == InfrahubKind.PROFILE
    assert start_crit_hash == crit_schema.get_hash()
    assert schema11.get(name="TestCriticality").get_hash() == crit_schema.get_hash()
    assert schema11.get(name="TestingTag").get_hash() == schema2.get(name="TestingTag").get_hash()
    assert schema11.get(name="TestGenericInterface").get_hash() == schema2.get(name="TestGenericInterface").get_hash()

    description_schema = crit_schema.get_attribute("description")
    assert description_schema.computed_attribute is not None
    assert description_schema.computed_attribute.jinja2_template == "{{ name__value }}"


async def test_load_schema(
    db: InfrahubDatabase, reset_registry, default_branch: Branch, register_internal_models_schema
) -> None:
    FULL_SCHEMA = {
        "nodes": [
            {
                "namespace": "Test",
                "name": "Criticality",
                "default_filter": "name__value",
                "label": "Criticality",
                "include_in_menu": True,
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
                    },
                    {
                        "name": "primary_tag",
                        "peer": "TestingTag",
                        "label": "Primary Tag",
                        "identifier": "primary_tag__criticality",
                        "optional": True,
                        "cardinality": "one",
                    },
                ],
            },
            {
                "namespace": "Testing",
                "name": "Tag",
                "label": "Tag",
                "default_filter": "name__value",
                "include_in_menu": True,
                "attributes": [
                    {"name": "name", "kind": "Text", "label": "Name", "unique": True},
                    {"name": "description", "kind": "Text", "label": "Description", "optional": True},
                ],
            },
        ],
        "generics": [
            {
                "namespace": "Test",
                "name": "GenericInterface",
                "label": "Generic Interface",
                "include_in_menu": True,
                "attributes": [
                    {"name": "my_generic_name", "kind": "Text", "label": "My Generic String"},
                ],
            },
        ],
    }

    schema1 = registry.schema.register_schema(schema=SchemaRoot(**FULL_SCHEMA), branch=default_branch.name)
    await registry.schema.load_schema_to_db(schema=schema1, db=db, branch=default_branch.name)
    default_branch.update_schema_hash()
    schema11 = registry.schema.get_schema_branch(name=default_branch.name)
    schema2 = await registry.schema.load_schema(db=db, branch=default_branch.name)

    assert len(schema2.nodes) == 6
    assert set(schema2.generics.keys()) == {"CoreProfile", "TestGenericInterface"}
    assert set(schema2.profiles.keys()) == {
        "ProfileTestingTag",
        "ProfileTestCriticality",
        "ProfileTestGenericInterface",
    }

    assert schema11.get(name="TestCriticality").get_hash() == schema2.get(name="TestCriticality").get_hash()
    assert schema11.get(name="TestingTag").get_hash() == schema2.get(name="TestingTag").get_hash()
    assert schema11.get(name="TestGenericInterface").get_hash() == schema2.get(name="TestGenericInterface").get_hash()


@pytest.mark.parametrize(
    "attr_details",
    [
        {
            "parameters": {"regex": "^#[0-9a-f]{0,6}$", "min_length": 7, "max_length": 7},
        },
        {"regex": "^#[0-9a-f]{0,6}$", "min_length": 7, "max_length": 7},
        {
            "parameters": {"regex": "^#[0-9a-f]{0,6}$", "min_length": 7, "max_length": 7},
            "regex": "old",
            "min_length": 1,
            "max_length": 2,
        },
    ],
)
async def test_load_schema_with_parameters(
    db: InfrahubDatabase, reset_registry, register_internal_models_schema, default_branch: Branch, attr_details
) -> None:
    color_attr_dict = {
        "name": "color",
        "kind": "Text",
        "label": "Color",
        "default_value": "#444444",
    }
    color_attr_dict.update(attr_details)

    FULL_SCHEMA = {
        "nodes": [
            {
                "namespace": "Test",
                "name": "Criticality",
                "default_filter": "name__value",
                "label": "Criticality",
                "include_in_menu": True,
                "attributes": [
                    color_attr_dict,
                    {"name": "name", "kind": "Text", "label": "Name", "unique": True},
                    {"name": "level", "kind": "Number", "label": "Level"},
                    {"name": "description", "kind": "Text", "label": "Description", "optional": True},
                ],
            },
        ],
    }

    schema1 = registry.schema.register_schema(schema=SchemaRoot(**FULL_SCHEMA), branch=default_branch.name)
    await registry.schema.load_schema_to_db(schema=schema1, db=db, branch=default_branch.name)
    default_branch.update_schema_hash()
    loaded_schema = await registry.schema.load_schema(db=db, branch=default_branch.name)

    crit_schema = loaded_schema.get("TestCriticality", duplicate=False)
    color_attr_schema = crit_schema.get_attribute("color")
    assert isinstance(color_attr_schema.parameters, TextAttributeParameters)
    assert color_attr_schema.parameters.regex == "^#[0-9a-f]{0,6}$"
    assert color_attr_schema.parameters.min_length == 7
    assert color_attr_schema.parameters.max_length == 7
    assert color_attr_schema.regex == "^#[0-9a-f]{0,6}$"
    assert color_attr_schema.min_length == 7
    assert color_attr_schema.max_length == 7


async def test_load_schemas(
    db: InfrahubDatabase, reset_registry, default_branch: Branch, register_internal_models_schema
) -> None:
    part1 = SchemaRoot(
        extensions={
            "nodes": [
                {
                    "kind": "RandomOrganization",
                    "relationships": [
                        {
                            "cardinality": "many",
                            "identifier": "organization__model",
                            "kind": "Component",
                            "label": "Device Models",
                            "name": "models",
                            "optional": True,
                            "peer": "RandomModel",
                        }
                    ],
                }
            ]
        },
        nodes=[
            {
                "attributes": [
                    {"kind": "Text", "name": "name", "unique": True},
                    {"kind": "Text", "name": "description", "optional": True},
                ],
                "default_filter": "name__value",
                "display_labels": ["name__value"],
                "human_friendly_id": ["name__value"],
                "name": "Model",
                "namespace": "Random",
                "order_by": ["name__value"],
                "relationships": [
                    {
                        "cardinality": "one",
                        "identifier": "organization__model",
                        "kind": "Attribute",
                        "name": "organization",
                        "peer": "RandomOrganization",
                    }
                ],
            }
        ],
        version="1.0",
    )
    part2 = SchemaRoot(
        nodes=[
            {
                "attributes": [
                    {"kind": "Text", "name": "name", "unique": True},
                    {"kind": "Text", "name": "description", "optional": True},
                ],
                "name": "Organization",
                "namespace": "Random",
            }
        ],
        version="1.0",
    )
    merged = part1.merge(schema=part2)

    assert len(merged.nodes) == 2
    assert merged.extensions == part1.extensions

    schema_branch = SchemaBranch(cache={}, name="test")
    schema_branch.load_schema(schema=merged)

    random_org_schema = schema_branch.get(name="RandomOrganization", duplicate=False)
    try:
        random_org_schema.get_attribute("name")
    except ValueError:
        pytest.fail(reason="Attribute 'name' must be present in 'RandomOrganization'")
    try:
        random_org_schema.get_relationship("models")
    except ValueError:
        pytest.fail(reason="Relationship 'models' must be present in 'RandomOrganization'")


def test_schema_branch_load_schema_append_to_list(schema_all_in_one) -> None:
    schema_branch = SchemaBranch(cache={}, name="test")
    schema_branch.load_schema(schema=SchemaRoot(**schema_all_in_one))
    core_group_schema = _get_schema_by_kind(schema_all_in_one, "CoreGroup")
    core_group_schema["display_labels"] = ["label__value", "name__value"]

    schema_branch.load_schema(schema=SchemaRoot(**schema_all_in_one))

    updated_core_group_schema = schema_branch.get(name="CoreGroup", duplicate=False)
    assert updated_core_group_schema.display_labels == ["label__value", "name__value"]


def test_schema_branch_load_schema_remove_from_list(schema_all_in_one) -> None:
    schema_branch = SchemaBranch(cache={}, name="test")
    schema_branch.load_schema(schema=SchemaRoot(**schema_all_in_one))
    core_group_schema = _get_schema_by_kind(schema_all_in_one, "CoreGroup")
    core_group_schema["display_labels"] = ["name__value"]

    schema_branch.load_schema(schema=SchemaRoot(**schema_all_in_one))

    updated_core_group_schema = schema_branch.get(name="CoreGroup", duplicate=False)
    assert updated_core_group_schema.display_labels == ["name__value"]


def test_schema_branch_load_schema_empty_list(schema_all_in_one) -> None:
    schema_branch = SchemaBranch(cache={}, name="test")
    schema_branch.load_schema(schema=SchemaRoot(**schema_all_in_one))
    core_group_schema = _get_schema_by_kind(schema_all_in_one, "CoreGroup")
    core_group_schema["display_labels"] = []

    schema_branch.load_schema(schema=SchemaRoot(**schema_all_in_one))

    updated_core_group_schema = schema_branch.get(name="CoreGroup", duplicate=False)
    assert updated_core_group_schema.display_labels == []


def test_schema_branch_load_schema_set_nested_list(schema_all_in_one) -> None:
    schema_branch = SchemaBranch(cache={}, name="test")
    schema_branch.load_schema(schema=SchemaRoot(**schema_all_in_one))
    generic_interface_schema = _get_schema_by_kind(schema_all_in_one, "InfraGenericInterface")
    generic_interface_schema["uniqueness_constraints"] = [["my_generic_name", "mybool"], ["primary_tag", "status"]]

    schema_branch.load_schema(schema=SchemaRoot(**schema_all_in_one))

    updated_core_group_schema = schema_branch.get(name="InfraGenericInterface", duplicate=False)
    assert updated_core_group_schema.uniqueness_constraints == [
        ["my_generic_name", "mybool"],
        ["primary_tag", "status"],
    ]


def test_schema_branch_load_schema_append_to_nested_list(schema_all_in_one) -> None:
    schema_branch = SchemaBranch(cache={}, name="test")
    generic_interface_schema = _get_schema_by_kind(schema_all_in_one, "InfraGenericInterface")
    generic_interface_schema["uniqueness_constraints"] = [["primary_tag", "status"]]
    schema_branch.load_schema(schema=SchemaRoot(**schema_all_in_one))
    generic_interface_schema["uniqueness_constraints"] = [["primary_tag", "status"], ["my_generic_name", "mybool"]]

    schema_branch.load_schema(schema=SchemaRoot(**schema_all_in_one))

    updated_core_group_schema = schema_branch.get(name="InfraGenericInterface", duplicate=False)
    assert updated_core_group_schema.uniqueness_constraints == [
        ["primary_tag", "status"],
        ["my_generic_name", "mybool"],
    ]


def test_schema_branch_load_schema_remove_from_nested_list(schema_all_in_one) -> None:
    schema_branch = SchemaBranch(cache={}, name="test")
    generic_interface_schema = _get_schema_by_kind(schema_all_in_one, "InfraGenericInterface")
    generic_interface_schema["uniqueness_constraints"] = [["primary_tag", "status"], ["my_generic_name", "mybool"]]
    schema_branch.load_schema(schema=SchemaRoot(**schema_all_in_one))
    generic_interface_schema["uniqueness_constraints"] = [["primary_tag", "status"]]

    schema_branch.load_schema(schema=SchemaRoot(**schema_all_in_one))

    updated_core_group_schema = schema_branch.get(name="InfraGenericInterface", duplicate=False)
    assert updated_core_group_schema.uniqueness_constraints == [["primary_tag", "status"]]


def test_schema_branch_load_schema_update_nested_list(schema_all_in_one) -> None:
    schema_branch = SchemaBranch(cache={}, name="test")
    generic_interface_schema = _get_schema_by_kind(schema_all_in_one, "InfraGenericInterface")
    generic_interface_schema["uniqueness_constraints"] = [
        ["primary_tag", "status", "mybool"],
        ["my_generic_name", "mybool"],
    ]
    schema_branch.load_schema(schema=SchemaRoot(**schema_all_in_one))
    generic_interface_schema["uniqueness_constraints"] = [
        ["primary_tag", "status"],
        ["my_generic_name", "mybool", "status"],
    ]

    schema_branch.load_schema(schema=SchemaRoot(**schema_all_in_one))

    updated_core_group_schema = schema_branch.get(name="InfraGenericInterface", duplicate=False)
    assert updated_core_group_schema.uniqueness_constraints == [
        ["primary_tag", "status"],
        ["my_generic_name", "mybool", "status"],
    ]


def test_schema_branch_conflicting_required_relationships(schema_all_in_one) -> None:
    tag_schema = _get_schema_by_kind(full_schema=schema_all_in_one, kind="TestingTag")
    tag_schema["relationships"] = [
        {
            "name": "crits",
            "peer": "TestingCriticality",
            "label": "Crits",
            "optional": False,
            "cardinality": "many",
        },
    ]
    crit_schema = _get_schema_by_kind(full_schema=schema_all_in_one, kind="TestingCriticality")
    crit_schema["relationships"] = [
        {
            "name": "tags",
            "peer": "TestingTag",
            "label": "Tags",
            "optional": False,
            "cardinality": "many",
        },
    ]

    schema = SchemaBranch(cache={}, name="test")
    schema.load_schema(schema=SchemaRoot(**schema_all_in_one))

    with pytest.raises(ValueError) as exc:
        schema.validate_required_relationships()

    assert "TestingTag" in exc.value.args[0]
    assert "TestingCriticality" in exc.value.args[0]
    assert "cannot both have required relationships" in exc.value.args[0]


@dataclass
class InheritedRelationshipsTestData:
    name: str
    schema: dict[str, Any]
    error_message: str


INHERITED_RELATIONSHIPS_TEST_CASES = [
    *[
        InheritedRelationshipsTestData(
            name=f"inherit-from-2-generics-{test_data['property']}-fail",
            schema={
                "generics": [
                    {
                        "name": "GenericInterface",
                        "namespace": "Network",
                        "description": "Generic Network Interface",
                        "label": "Interface",
                        "include_in_menu": False,
                        "display_labels": ["name__value"],
                        "order_by": ["device__name__value", "name__value"],
                        "uniqueness_constraints": [["device", "name__value"]],
                        "human_friendly_id": ["device__name__value", "name__value"],
                        "attributes": [
                            {
                                "name": "name",
                                "kind": "Text",
                                "description": "Name of the interface",
                                "order_weight": 1000,
                            }
                        ],
                        "relationships": [test_data["relationships"][0]],
                    },
                    {
                        "name": "IndexedInterface",
                        "namespace": "Logical",
                        "description": "Generic for an interface that is part of a logical device and has an index",
                        "include_in_menu": False,
                        "human_friendly_id": ["device__name__value", "index__value"],
                        "uniqueness_constraints": [["device", "index__value"]],
                        "attributes": [
                            {
                                "name": "index",
                                "kind": "Number",
                                "description": "Index of the interface in the device",
                            }
                        ],
                        "relationships": [test_data["relationships"][1]],
                    },
                    {
                        "name": "Device",
                        "namespace": "Logical",
                        "description": "Generic for a logical device that could be part of a logical network",
                        "include_in_menu": False,
                        "attributes": [
                            {
                                "name": "index",
                                "kind": "Number",
                                "description": "Index of the device in the network",
                            },
                        ],
                    },
                ],
                "nodes": [
                    {
                        "name": "Device",
                        "namespace": "Network",
                        "label": "Network device",
                        "description": "Physical network port on a device",
                        "attributes": [
                            {
                                "name": "name",
                                "kind": "Text",
                                "description": "Name of the interface",
                                "unique": True,
                                "optional": False,
                                "order_weight": 1000,
                            }
                        ],
                    },
                    {
                        "name": "Physical",
                        "namespace": "Interface",
                        "label": "Physical Interface",
                        "description": "Physical network port on a device",
                        "inherit_from": [
                            "NetworkGenericInterface",
                            "LogicalIndexedInterface",
                        ],
                    },
                ],
            },
            error_message=(
                "InterfacePhysical inherits from 'NetworkGenericInterface' & 'LogicalIndexedInterface'"
                f" with different '{test_data['property']}' on the 'device' relationship"
            ),
        )
        for test_data in [
            {
                "relationships": [
                    {
                        "name": "device",
                        "peer": "LogicalDevice",
                        "cardinality": "one",
                        "identifier": "device__interface",
                        "optional": False,
                    },
                    {
                        "name": "device",
                        "peer": "LogicalDevice",
                        "cardinality": "many",
                        "identifier": "device__interface",
                        "optional": False,
                    },
                ],
                "property": "cardinality",
            },
            {
                "relationships": [
                    {
                        "name": "device",
                        "peer": "NetworkGenericDevice",
                        "identifier": "device__interface",
                        "optional": False,
                        "cardinality": "one",
                        "kind": "Parent",
                        "order_weight": 1025,
                    },
                    {
                        "name": "device",
                        "peer": "LogicalDevice",
                        "cardinality": "one",
                        "identifier": "device__interface",
                        "optional": False,
                    },
                ],
                "property": "peer",
            },
            {
                "relationships": [
                    {
                        "name": "device",
                        "peer": "LogicalDevice",
                        "cardinality": "one",
                        "identifier": "device__interface",
                        "optional": False,
                        "on_delete": "cascade",
                    },
                    {
                        "name": "device",
                        "peer": "LogicalDevice",
                        "cardinality": "one",
                        "identifier": "device__interface",
                        "optional": False,
                        "on_delete": "no-action",
                    },
                ],
                "property": "on_delete",
            },
        ]
    ],
    InheritedRelationshipsTestData(
        name="inherit-from-3-generics-peer-fail",
        schema={
            "generics": [
                {
                    "name": "GenericInterface",
                    "namespace": "Network",
                    "description": "Generic Network Interface",
                    "label": "Interface",
                    "include_in_menu": False,
                    "display_labels": ["name__value"],
                    "order_by": ["device__name__value", "name__value"],
                    "uniqueness_constraints": [["device", "name__value"]],
                    "human_friendly_id": ["device__name__value", "name__value"],
                    "attributes": [
                        {
                            "name": "name",
                            "kind": "Text",
                            "description": "Name of the interface",
                            "order_weight": 1000,
                        }
                    ],
                    "relationships": [
                        {
                            "name": "device",
                            "peer": "NetworkDevice",
                            "identifier": "device__interface",
                            "optional": False,
                            "cardinality": "one",
                            "kind": "Parent",
                        }
                    ],
                },
                {
                    "name": "IndexedInterface",
                    "namespace": "Logical",
                    "description": "Generic for an interface that is part of a logical device and has an index",
                    "include_in_menu": False,
                    "human_friendly_id": ["device__name__value", "index__value"],
                    "uniqueness_constraints": [["device", "index__value"]],
                    "attributes": [
                        {
                            "name": "index",
                            "kind": "Number",
                            "description": "Index of the interface in the device",
                        }
                    ],
                    "relationships": [
                        {
                            "name": "device",
                            "peer": "NetworkDevice",
                            "cardinality": "one",
                            "identifier": "device__interface",
                            "optional": False,
                            "kind": "Parent",
                        }
                    ],
                },
                {
                    "name": "Device",
                    "namespace": "Logical",
                    "description": "Generic for a logical device that could be part of a logical network",
                    "include_in_menu": False,
                    "attributes": [
                        {
                            "name": "index",
                            "kind": "Number",
                            "description": "Index of the device in the network",
                        },
                    ],
                    "relationships": [
                        {
                            "name": "device",
                            "peer": "NetworkThirdDevice",
                            "cardinality": "one",
                            "identifier": "device__interface",
                            "optional": False,
                        },
                    ],
                },
            ],
            "nodes": [
                {
                    "name": "Device",
                    "namespace": "Network",
                    "label": "Network device",
                    "description": "Physical network port on a device",
                    "attributes": [
                        {
                            "name": "name",
                            "kind": "Text",
                            "description": "Name of the interface",
                            "unique": True,
                            "optional": False,
                            "order_weight": 1000,
                        }
                    ],
                },
                {
                    "name": "ThirdDevice",
                    "namespace": "Network",
                    "label": "Network device",
                    "description": "Physical network port on a device",
                    "attributes": [
                        {
                            "name": "name",
                            "kind": "Text",
                            "description": "Name of the interface",
                            "unique": True,
                            "optional": False,
                            "order_weight": 1000,
                        }
                    ],
                },
                {
                    "name": "Physical",
                    "namespace": "Interface",
                    "label": "Physical Interface",
                    "description": "Physical network port on a device",
                    "inherit_from": [
                        "NetworkGenericInterface",
                        "LogicalIndexedInterface",
                        "LogicalDevice",
                    ],
                },
            ],
        },
        error_message=(
            "InterfacePhysical inherits from 'NetworkGenericInterface' & 'LogicalDevice'"
            " with different 'peer' on the 'device' relationship"
        ),
    ),
]


@pytest.mark.parametrize(
    "test_case",
    [pytest.param(tc, id=tc.name) for tc in INHERITED_RELATIONSHIPS_TEST_CASES],
)
def test_schema_branch_validates_inherited_relationships_fields(test_case: InheritedRelationshipsTestData) -> None:
    schema = SchemaBranch(cache={}, name=test_case.name)
    schema.load_schema(schema=SchemaRoot(**test_case.schema))

    with pytest.raises(ValueError) as exc:
        schema.validate_inherited_relationships_fields()

    assert exc.value.args[0] == test_case.error_message


async def test_schema_branch_processes_relationships_state(
    db: InfrahubDatabase, default_branch: Branch, register_internal_models_schema
) -> None:
    schema = {
        "nodes": [
            {
                "name": "Thing",
                "namespace": "Infra",
                "label": "Thing",
                "attributes": [{"name": "name", "label": "Name", "kind": "Text", "optional": False, "unique": True}],
                "relationships": [
                    {
                        "name": "other_thing",
                        "peer": "InfraOtherThing",
                        "kind": "Attribute",
                        "state": "absent",
                        "cardinality": "one",
                        "optional": True,
                    },
                ],
            },
            {
                "name": "OtherThing",
                "namespace": "Infra",
                "label": "OtherThing",
                "attributes": [
                    {"name": "name", "label": "Name", "kind": "Text", "optional": False, "unique": True},
                ],
            },
        ],
    }
    schema_branch = registry.schema.register_schema(schema=SchemaRoot(**schema), branch=default_branch.name)
    await registry.schema.load_schema_to_db(schema=schema_branch, db=db, branch=default_branch.name)
    returned_schema = await registry.schema.load_schema_from_db(db=db, branch=default_branch.name)

    assert "other_thing" not in returned_schema.get(name="InfraThing").relationship_names


async def test_schema_branch_processes_nodes_state(
    db: InfrahubDatabase, default_branch: Branch, register_internal_models_schema
) -> None:
    schema = {
        "generics": [
            {
                "namespace": "Test",
                "name": "GenericInterface",
                "label": "Generic Interface",
                "include_in_menu": True,
                "state": "absent",
                "attributes": [
                    {"name": "my_generic_name", "kind": "Text", "label": "My Generic String"},
                ],
            },
        ],
        "nodes": [
            {
                "name": "Widget",
                "namespace": "Test",
                "label": "Widget",
                "state": "absent",
                "display_labels": ["name__value"],
                "attributes": [
                    {"name": "name", "kind": "Text", "unique": True},
                    {"name": "description", "kind": "Text"},
                ],
            }
        ],
    }
    schema_branch = registry.schema.register_schema(schema=SchemaRoot(**schema), branch=default_branch.name)
    await registry.schema.load_schema_to_db(schema=schema_branch, db=db, branch=default_branch.name)
    returned_schema = await registry.schema.load_schema_from_db(db=db, branch=default_branch.name)

    with pytest.raises(SchemaNotFoundError) as exc:
        returned_schema.get(name="TestWidget")
    assert exc.value.args[0] == "Unable to find the schema 'TestWidget' in the registry"

    with pytest.raises(SchemaNotFoundError) as exc:
        returned_schema.get(name="TestGenericInterface")
    assert exc.value.args[0] == "Unable to find the schema 'TestGenericInterface' in the registry"


async def test_schema_branch_processes_attributes_state(
    db: InfrahubDatabase, default_branch: Branch, register_internal_models_schema
) -> None:
    schema = {
        "generics": [
            {
                "namespace": "Test",
                "name": "GenericInterface",
                "label": "Generic Interface",
                "include_in_menu": True,
                "attributes": [
                    {"name": "my_generic_name", "kind": "Text", "label": "My Generic String", "state": "absent"},
                ],
            },
        ],
        "nodes": [
            {
                "name": "Widget",
                "namespace": "Test",
                "label": "Widget",
                "display_labels": ["name__value"],
                "attributes": [
                    {"name": "name", "kind": "Text", "unique": True},
                    {"name": "description", "kind": "Text", "state": "absent"},
                ],
            }
        ],
    }
    schema_branch = registry.schema.register_schema(schema=SchemaRoot(**schema), branch=default_branch.name)
    await registry.schema.load_schema_to_db(schema=schema_branch, db=db, branch=default_branch.name)
    returned_schema = await registry.schema.load_schema_from_db(db=db, branch=default_branch.name)

    assert "description" not in returned_schema.get(name="TestWidget").attribute_names
    assert "my_generic_name" not in returned_schema.get(name="TestGenericInterface").attribute_names

    schema = {
        "generics": [
            {
                "namespace": "Test",
                "name": "GenericInterface",
                "label": "Generic Interface",
                "include_in_menu": True,
                "attributes": [
                    {"name": "my_generic_name", "kind": "Text", "label": "My Generic String"},
                ],
            },
        ],
        "nodes": [
            {
                "name": "Widget",
                "namespace": "Test",
                "label": "Widget",
                "display_labels": ["name__value"],
                "attributes": [
                    {"name": "name", "kind": "Text", "unique": True},
                    {"name": "description", "kind": "Text"},
                ],
            }
        ],
    }
    schema_branch = registry.schema.register_schema(schema=SchemaRoot(**schema), branch=default_branch.name)
    await registry.schema.load_schema_to_db(schema=schema_branch, db=db, branch=default_branch.name)
    returned_schema = await registry.schema.load_schema_from_db(db=db, branch=default_branch.name)

    assert "description" in returned_schema.get(name="TestWidget").attribute_names
    assert "my_generic_name" in returned_schema.get(name="TestGenericInterface").attribute_names


async def test_process_deprecations(organization_schema) -> None:
    SCHEMA1 = {
        "name": "Criticality",
        "namespace": "Test",
        "default_filter": "name__value",
        "branch": BranchSupportType.AWARE.value,
        "attributes": [
            {"name": "name", "kind": "Text", "unique": True},
            {"name": "description", "kind": "Text", "deprecation": "I'm not used anymore"},
        ],
        "relationships": [
            {
                "name": "first",
                "peer": "CoreOrganization",
                "cardinality": "one",
                "optional": False,
                "deprecation": "Use the second one instead",
            },
            {"name": "second", "peer": "CoreOrganization", "cardinality": "one", "optional": False},
        ],
    }

    copy_core_models = copy.deepcopy(core_models)
    copy_core_models["nodes"].append(SCHEMA1)
    schema = SchemaRoot(**copy_core_models)

    schema_branch = SchemaBranch(cache={}, name="test")
    schema_branch.load_schema(schema=schema)
    schema_branch.load_schema(schema=organization_schema)

    schema_branch.process_deprecations()

    test_criticality = schema_branch.get_node(name="TestCriticality", duplicate=False)

    assert not test_criticality.get_attribute(name="name").is_deprecated
    assert test_criticality.get_attribute(name="description").is_deprecated
    assert test_criticality.get_relationship(name="first").is_deprecated
    assert not test_criticality.get_relationship(name="second").is_deprecated

    assert not test_criticality.get_attribute(name="name").optional
    assert test_criticality.get_attribute(name="description").optional
    assert test_criticality.get_relationship(name="first").optional
    assert not test_criticality.get_relationship(name="second").optional


async def test_hierarchical_validate_parent_children(
    db: InfrahubDatabase, default_branch: Branch, hierarchical_location_schema_simple_unregistered: SchemaRoot
) -> None:
    site_schema = hierarchical_location_schema_simple_unregistered.get(name="LocationSite")
    site_schema.human_friendly_id = ["parent__name__value", "name__value"]
    site_schema.uniqueness_constraints = [["parent", "name__value"]]

    registry.schema.register_schema(schema=hierarchical_location_schema_simple_unregistered, branch=default_branch.name)

    schema_branch = registry.schema.get_schema_branch(name=default_branch.name)

    with pytest.raises(ValueError, match=r"Unable to find the relationship"):
        region_schema = schema_branch.get(name="LocationRegion", duplicate=False)
        region_schema.get_relationship(name="parent")

    with pytest.raises(ValueError, match=r"Unable to find the relationship"):
        rack_schema = schema_branch.get(name="LocationRack", duplicate=False)
        rack_schema.get_relationship(name="children")

    eu: Node = await Node.init(db=db, schema="LocationRegion", branch=default_branch)
    await eu.new(db=db, name="Europe")
    await eu.save(db=db)

    fr: Node = await Node.init(db=db, schema="LocationSite", branch=default_branch)
    await fr.new(db=db, name="France", parent=eu)
    await fr.save(db=db)

    uk: Node = await Node.init(db=db, schema="LocationSite", branch=default_branch)
    with pytest.raises(ValidationError, match=r"parent is mandatory"):
        await uk.new(db=db, name="United Kingdom")

    await uk.new(db=db, name="United Kingdom", parent=eu)
    await uk.save(db=db)


async def test_schema_branch_add_object_template_schema() -> None:
    SIMPLE_DEVICE = copy.deepcopy(DEVICE)
    SIMPLE_DEVICE.inherit_from = []
    device_schema = SchemaRoot(generics=[core_object_template], nodes=[SIMPLE_DEVICE])

    schema = SchemaBranch(cache={}, name="test")
    schema.load_schema(schema=device_schema)
    schema.process_inheritance()
    schema.manage_object_template_schemas()

    node_template = schema.get(name=f"Template{TestKind.DEVICE}", duplicate=False)
    assert node_template
    core_template_schema = schema.get(name=InfrahubKind.OBJECTTEMPLATE, duplicate=False)
    assert set(core_template_schema.used_by) == {f"Template{TestKind.DEVICE}"}


async def test_schema_branch_remove_object_template_schema() -> None:
    SIMPLE_DEVICE = copy.deepcopy(DEVICE)
    SIMPLE_DEVICE.inherit_from = []
    device_schema = SchemaRoot(generics=[core_object_template], nodes=[SIMPLE_DEVICE])

    schema = SchemaBranch(cache={}, name="test")
    schema.load_schema(schema=device_schema)
    schema.process_inheritance()
    schema.manage_object_template_schemas()

    node_template = schema.get(name=f"Template{TestKind.DEVICE}", duplicate=False)
    assert node_template
    core_template_schema = schema.get(name=InfrahubKind.OBJECTTEMPLATE, duplicate=False)
    assert set(core_template_schema.used_by) == {f"Template{TestKind.DEVICE}"}

    # Disable template
    SIMPLE_DEVICE.generate_template = False

    schema = SchemaBranch(cache={}, name="test")
    schema.load_schema(schema=device_schema)
    schema.process_inheritance()
    schema.manage_object_template_schemas()

    with pytest.raises(SchemaNotFoundError, match=r"Unable to find the schema"):
        schema.get(name=f"Template{TestKind.DEVICE}", duplicate=False)
    core_template_schema = schema.get(name=InfrahubKind.OBJECTTEMPLATE, duplicate=False)
    assert not core_template_schema.used_by


async def test_schema_branch_diff_core_object_template() -> None:
    SIMPLE_DEVICE = copy.deepcopy(DEVICE)
    SIMPLE_DEVICE.inherit_from = []
    device_schema = SchemaRoot(generics=[core_object_template, core_object_component_template], nodes=[SIMPLE_DEVICE])

    schema = SchemaBranch(cache={}, name="test")
    schema.load_schema(schema=device_schema)
    schema.process_inheritance()
    schema.manage_object_template_schemas()

    new_schema = schema.duplicate()
    template_schema = new_schema.get(name=InfrahubKind.OBJECTTEMPLATE, duplicate=True)
    template_schema.description = "New description"
    new_schema.set(name=InfrahubKind.OBJECTTEMPLATE, schema=template_schema)

    diff = new_schema.diff(other=schema)
    assert diff.all == [InfrahubKind.OBJECTTEMPLATE]

    DEVICE_SCHEMA.generics.extend([core_object_template, core_object_component_template])
    new_schema = SchemaBranch(cache={}, name="test")
    new_schema.load_schema(schema=DEVICE_SCHEMA)
    new_schema.process_inheritance()
    new_schema.manage_object_template_schemas()

    diff = schema.diff(other=new_schema)
    # We must not see kinds from the Template namespace
    assert diff.all == [
        TestKind.DEVICE,
        TestKind.INTERFACE,
        TestKind.INTERFACE_HOLDER,
        TestKind.PHYSICAL_INTERFACE,
        TestKind.SFP,
        TestKind.VIRTUAL_INTERFACE,
    ]


@pytest.mark.parametrize("relationship_kind", (RelationshipKind.ATTRIBUTE, RelationshipKind.GENERIC))
async def test_manage_object_templates(relationship_kind: RelationshipKind) -> None:
    schema_branch = SchemaBranch(cache={}, name="test")
    THING_WITH_TEMPLATE = copy.deepcopy(THING)
    THING_WITH_TEMPLATE.generate_template = True
    THING_WITH_TEMPLATE.relationships[0].kind = relationship_kind
    schema_branch.load_schema(
        schema=SchemaRoot(**core_models).merge(schema=SchemaRoot(nodes=[THING_WITH_TEMPLATE, CHILD]))
    )

    identified = schema_branch.identify_required_object_templates(
        node_schema=schema_branch.get(name=TestKind.THING, duplicate=False), identified=set()
    )
    assert {n.kind for n in identified} == {TestKind.THING}

    schema_branch.manage_object_template_schemas()
    schema_branch.manage_object_template_relationships()

    # Verify the generated template
    test_object_template_thing = schema_branch.get_template(f"Template{TestKind.THING}", duplicate=False)
    assert test_object_template_thing.human_friendly_id == ["template_name__value"]
    assert test_object_template_thing.uniqueness_constraints == [["template_name__value"]]
    assert sorted(
        [a.name for a in test_object_template_thing.attributes if a.name != OBJECT_TEMPLATE_NAME_ATTR]
    ) == sorted([a.name for a in THING_WITH_TEMPLATE.attributes if not a.unique and not a.read_only])
    assert sorted(
        [
            r.name
            for r in test_object_template_thing.relationships
            if r.name not in (OBJECT_TEMPLATE_RELATIONSHIP_NAME, "related_nodes")
        ]
    ) == sorted([r.name for r in THING_WITH_TEMPLATE.relationships])


async def test_manage_object_templates_with_component_relationships() -> None:
    schema_branch = SchemaBranch(cache={}, name="test")
    schema_branch.load_schema(schema=SchemaRoot(**core_models).merge(schema=DEVICE_SCHEMA))
    schema_branch.process_inheritance()

    identified = schema_branch.identify_required_object_templates(
        node_schema=schema_branch.get(name=TestKind.DEVICE, duplicate=False), identified=set()
    )
    assert {n.kind for n in identified} == {
        TestKind.DEVICE,
        TestKind.INTERFACE,
        TestKind.INTERFACE_HOLDER,
        TestKind.PHYSICAL_INTERFACE,
        TestKind.SFP,
        TestKind.VIRTUAL_INTERFACE,
    }

    schema_branch.manage_object_template_schemas()
    schema_branch.manage_object_template_relationships()

    # Verify the generated template
    test_object_template_device = schema_branch.get_template(f"Template{TestKind.DEVICE}", duplicate=False)
    for attr in DEVICE.attributes:
        if attr.unique:
            with pytest.raises(ValueError, match=r"Unable to find the attribute"):
                test_object_template_device.get_attribute(name=attr.name)
        else:
            template_attr = test_object_template_device.get_attribute(name=attr.name)
            assert template_attr.optional

    # Check for the relationship from the object back to its template
    test_device = schema_branch.get_node(name=TestKind.DEVICE, duplicate=False)
    assert test_device.generate_template
    assert test_device.get_relationship(name="object_template").peer == test_object_template_device.kind

    # Make sure interfaces relationship is converted to interface templates
    assert test_object_template_device.get_relationship("interfaces").peer == f"Template{TestKind.INTERFACE}"
    # Make sure identifier matches as they are set to be the same
    assert (
        test_object_template_device.get_relationship("interfaces").identifier.removeprefix("template_")
        == schema_branch.get_node(name=TestKind.DEVICE, duplicate=False).get_relationship("interfaces").identifier
    )

    # Verify attributes mapping of components
    test_interface_template = schema_branch.get(name=f"Template{TestKind.PHYSICAL_INTERFACE}", duplicate=False)
    assert test_interface_template.human_friendly_id == ["device__template_name__value", "template_name__value"]
    assert test_interface_template.uniqueness_constraints == [["template_name__value", "device"]]
    test_interface = schema_branch.get(name=TestKind.PHYSICAL_INTERFACE, duplicate=False)
    for attr in test_interface.attributes:
        template_attr = test_interface_template.get_attribute(name=attr.name)
        # Optional value in component template should match original's
        assert attr.optional == template_attr.optional

    # Verify the generic by checking its attributes and relationships
    test_interface_template = schema_branch.get(name=f"Template{TestKind.INTERFACE}", duplicate=False)
    assert test_interface_template.is_generic_schema
    test_interface = schema_branch.get(name=TestKind.INTERFACE, duplicate=False)
    assert test_interface.is_generic_schema
    for attr in test_interface.attributes:
        template_attr = test_interface_template.get_attribute(name=attr.name)
        assert attr.optional == template_attr.optional
    for rel in test_interface.relationships:
        template_rel = test_interface_template.get_relationship(name=rel.name)
        assert template_rel.peer == f"Template{rel.peer}"

    # Verify when a node is marked as absent
    ABSENT_VIRTUAL_INTERFACE = copy.deepcopy(DEVICE_SCHEMA)
    ABSENT_VIRTUAL_INTERFACE.get(name=TestKind.VIRTUAL_INTERFACE).state = HashableModelState.ABSENT

    schema_branch = SchemaBranch(cache={}, name="absent-node")
    schema_branch.load_schema(schema=SchemaRoot(**core_models).merge(schema=ABSENT_VIRTUAL_INTERFACE))
    schema_branch.process_inheritance()

    identified = schema_branch.identify_required_object_templates(
        node_schema=schema_branch.get(name=TestKind.DEVICE, duplicate=False), identified=set()
    )
    assert {n.kind for n in identified} == {
        TestKind.DEVICE,
        TestKind.INTERFACE,
        TestKind.INTERFACE_HOLDER,
        TestKind.PHYSICAL_INTERFACE,
        TestKind.SFP,
    }


async def test_identify_object_templates_with_generics() -> None:
    USELESS_DEVICE_SCHEMA = copy.deepcopy(DEVICE_SCHEMA)
    USELESS_DEVICE_SCHEMA.nodes.append(
        NodeSchema(
            name="UselessDevice",
            namespace="Testing",
            inherit_from=[TestKind.INTERFACE_HOLDER],
            include_in_menu=True,
            label="Useless Device",
            default_filter="name__value",
            generate_template=True,
            attributes=[AttributeSchema(name="name", kind="Text", unique=True)],
        )
    )

    schema_branch = SchemaBranch(cache={}, name="test")
    schema_branch.load_schema(schema=SchemaRoot(**core_models).merge(schema=USELESS_DEVICE_SCHEMA))
    schema_branch.process_inheritance()

    # As we requested template for TestingDevice, which is an implementation of generic TestingInterfaceHolder we must make sure not to propagate
    # templating to TestingUselessDevice
    identified = schema_branch.identify_required_object_templates(
        node_schema=schema_branch.get(name=TestKind.DEVICE, duplicate=False), identified=set()
    )
    assert {n.kind for n in identified} == {
        TestKind.DEVICE,
        TestKind.INTERFACE,
        TestKind.INTERFACE_HOLDER,
        TestKind.PHYSICAL_INTERFACE,
        TestKind.SFP,
        TestKind.VIRTUAL_INTERFACE,
    }
