import copy
import json
import re
import uuid

import pytest
from infrahub_sdk.utils import compare_lists

from infrahub.core import registry
from infrahub.core.branch import Branch
from infrahub.core.constants import (
    AllowOverrideType,
    BranchSupportType,
    InfrahubKind,
    RelationshipDeleteBehavior,
    RelationshipKind,
    SchemaPathType,
)
from infrahub.core.schema import (
    GenericSchema,
    NodeSchema,
    SchemaRoot,
    core_models,
    internal_schema,
)
from infrahub.core.schema.manager import SchemaManager
from infrahub.core.schema.schema_branch import SchemaBranch
from infrahub.database import InfrahubDatabase
from infrahub.exceptions import SchemaNotFoundError, ValidationError

from .conftest import _get_schema_by_kind


async def test_schema_branch_set():
    SCHEMA = {
        "name": "Criticality",
        "namespace": "Builtin",
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


async def test_schema_branch_get(default_branch: Branch):
    SCHEMA = {
        "name": "Criticality",
        "namespace": "Builtin",
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


async def test_schema_branch_load_schema_initial(schema_all_in_one):
    schema = SchemaBranch(cache={}, name="test")
    schema.load_schema(schema=SchemaRoot(**schema_all_in_one))

    assert isinstance(schema.get(name="BuiltinCriticality"), NodeSchema)
    assert isinstance(schema.get(name="InfraGenericInterface"), GenericSchema)


async def test_schema_branch_process_inheritance(schema_all_in_one):
    schema = SchemaBranch(cache={}, name="test")
    schema.load_schema(schema=SchemaRoot(**schema_all_in_one))

    schema.process_inheritance()

    generic = schema.get(name="InfraGenericInterface")
    assert generic.used_by == ["BuiltinCriticality"]

    criticality = schema.get(name="BuiltinCriticality")
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
        "BuiltinCriticality",
        "BuiltinTag",
        "BuiltinStatus",
        "BuiltinBadge",
        "CoreStandardGroup",
        "InfraTinySchema",
    }


async def test_schema_process_inheritance_different_generic_attribute_types(schema_diff_attr_inheritance_types):
    """Test that we raise an exception if a node is inheriting from two generics with different attribute types for a specific attribute."""
    schema = SchemaBranch(cache={}, name="test")
    schema.load_schema(schema=SchemaRoot(**schema_diff_attr_inheritance_types))

    with pytest.raises(ValueError) as exc:
        schema.process_inheritance()

    assert exc.value.args[0] == 'TestWidget.choice inherited from TestStatus must be the same kind ["Number", "Text"]'


async def test_schema_process_inheritance_different_generic_attribute_types_on_node(schema_diff_attr_inheritance_types):
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


async def test_schema_branch_process_inheritance_node_level(animal_person_schema_dict):
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


async def test_schema_branch_process_inheritance_update_inherited_elements(animal_person_schema_dict):
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
):
    schema = SchemaBranch(cache={}, name="test")
    for node_schema in animal_person_schema_dict["generics"]:
        if node_schema["name"] == "Animal" and node_schema["namespace"] == "Test":
            node_schema["uniqueness_constraints"] = None
            node_schema["human_friendly_id"] = None
    for node_schema in animal_person_schema_dict["nodes"]:
        if node_schema["name"] == "Dog" and node_schema["namespace"] == "Test":
            node_schema["uniqueness_constraints"] = uniqueness_constraints
            node_schema["human_friendly_id"] = human_friendly_id
            for attr_schema in node_schema["attributes"]:
                attr_schema["unique"] = attr_schema["name"] in unique_attributes
    schema.load_schema(schema=SchemaRoot(**animal_person_schema_dict))

    schema.process_inheritance()
    schema.validate_human_friendly_id()
    schema.process_human_friendly_id()

    dog_node = schema.get("TestDog")
    expected_uniqueness_constraints = uniqueness_constraints or [human_friendly_id]
    assert dog_node.uniqueness_constraints == expected_uniqueness_constraints


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
):
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


async def test_schema_branch_process_human_friendly_id(animal_person_schema_dict):
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


async def test_schema_branch_infer_human_friendly_id_from_uniqueness_constraints(animal_person_schema_dict):
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
    assert person.uniqueness_constraints == [["name__value"]]


async def test_schema_branch_process_branch_support(schema_all_in_one):
    schema = SchemaBranch(cache={}, name="test")
    schema.load_schema(schema=SchemaRoot(**schema_all_in_one))

    schema.process_inheritance()
    schema.process_branch_support()

    criticality = schema.get(name="BuiltinCriticality")
    assert criticality.get_attribute(name="name").branch == BranchSupportType.AGNOSTIC
    assert criticality.get_attribute(name="level").branch == BranchSupportType.AWARE
    assert criticality.get_attribute(name="local_attr").branch == BranchSupportType.LOCAL
    assert criticality.get_relationship(name="tags").branch == BranchSupportType.AWARE
    assert criticality.get_relationship(name="status").branch == BranchSupportType.AGNOSTIC
    assert criticality.get_relationship(name="badges").branch == BranchSupportType.LOCAL

    criticality = schema.get(name=InfrahubKind.TAG)
    assert criticality.get_attribute(name="name").branch == BranchSupportType.AWARE
    assert criticality.get_attribute(name="description").branch == BranchSupportType.AGNOSTIC


async def test_schema_branch_process_default_values(schema_all_in_one):
    schema = SchemaBranch(cache={}, name="test")
    schema.load_schema(schema=SchemaRoot(**schema_all_in_one))

    schema.process_default_values()

    generic = schema.get(name="InfraGenericInterface")
    assert generic.get_attribute(name="mybool").optional is True
    assert generic.get_attribute(name="my_generic_name").optional is False

    criticality = schema.get(name="BuiltinCriticality")
    assert criticality.get_attribute(name="color").optional is True


async def test_schema_branch_add_groups(schema_all_in_one):
    schema = SchemaBranch(cache={}, name="test")
    schema.load_schema(schema=SchemaRoot(**schema_all_in_one))

    schema.process_inheritance()
    schema.add_groups()

    criticality = schema.get(name="BuiltinCriticality")
    assert criticality.get_relationship(name="member_of_groups")
    assert criticality.get_relationship(name="subscriber_of_groups")

    std_group = schema.get(name=InfrahubKind.STANDARDGROUP)
    assert std_group.get_relationship_or_none(name="member_of_groups") is None
    assert std_group.get_relationship_or_none(name="subscriber_of_groups") is None


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
                            {"name": "status", "peer": "BuiltinStatus", "optional": True, "cardinality": "one"}
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
    ],
)
async def test_schema_protected_generics(schema_dict, expected_error):
    schema = SchemaBranch(cache={}, name="test")
    schema.load_schema(schema=SchemaRoot(**schema_dict))

    with pytest.raises(ValueError) as exc:
        schema.process_inheritance()

    assert str(exc.value) == expected_error


async def test_schema_branch_generate_weight(schema_all_in_one):
    def extract_weights(schema: SchemaBranch):
        weights = []
        for node in schema.get_all().values():
            if not isinstance(node, (NodeSchema, GenericSchema)):
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
    assert len(in_second) == 1 and in_second[0].startswith(new_attr2_partial_id)


async def test_schema_branch_add_profile_schema(schema_all_in_one):
    core_profile_schema = _get_schema_by_kind(core_models, kind="CoreProfile")
    schema_all_in_one["generics"].append(core_profile_schema)

    schema = SchemaBranch(cache={}, name="test")
    schema.load_schema(schema=SchemaRoot(**schema_all_in_one))
    schema.process_inheritance()
    schema.manage_profile_schemas()

    node_profile = schema.get(name="ProfileBuiltinCriticality", duplicate=False)
    assert node_profile.get_attribute("profile_name").branch == BranchSupportType.AGNOSTIC.value
    assert node_profile.get_attribute("profile_priority").branch == BranchSupportType.AGNOSTIC.value
    assert set(node_profile.attribute_names) == {"profile_name", "profile_priority", "description", "mybool"}
    generic_profile = schema.get(name="ProfileInfraGenericInterface", duplicate=False)
    assert set(generic_profile.attribute_names) == {"profile_name", "profile_priority", "mybool"}
    core_profile_schema = schema.get("CoreProfile")
    core_node_schema = schema.get("CoreNode")
    assert set(core_profile_schema.used_by) == {
        "ProfileBuiltinCriticality",
        "ProfileBuiltinTag",
        "ProfileBuiltinStatus",
        "ProfileBuiltinBadge",
        "ProfileInfraTinySchema",
        "ProfileInfraGenericInterface",
    }

    assert set(core_node_schema.used_by) == {
        "BuiltinBadge",
        "BuiltinCriticality",
        "BuiltinStatus",
        "BuiltinTag",
        "CoreStandardGroup",
        "InfraTinySchema",
        "ProfileBuiltinCriticality",
        "ProfileBuiltinTag",
        "ProfileBuiltinStatus",
        "ProfileBuiltinBadge",
        "ProfileInfraTinySchema",
        "ProfileInfraGenericInterface",
    }


async def test_schema_branch_add_profile_schema_respects_flag(schema_all_in_one):
    core_profile_schema = _get_schema_by_kind(core_models, kind="CoreProfile")
    schema_all_in_one["generics"].append(core_profile_schema)
    builtin_tag_schema = _get_schema_by_kind(schema_all_in_one, kind="BuiltinTag")
    builtin_tag_schema["generate_profile"] = False
    generic_interface_schema = schema_all_in_one["generics"][0]
    generic_interface_schema["generate_profile"] = False

    schema = SchemaBranch(cache={}, name="test")
    schema.load_schema(schema=SchemaRoot(**schema_all_in_one))
    schema.manage_profile_schemas()

    with pytest.raises(SchemaNotFoundError):
        schema.get(name="ProfileBuiltinTag")
    builtin_tag_schema = schema.get_node(name="BuiltinTag", duplicate=False)
    with pytest.raises(ValueError):
        builtin_tag_schema.get_relationship("profiles")
    core_profile_schema = schema.get("CoreProfile")
    assert set(core_profile_schema.used_by) == {
        "ProfileBuiltinCriticality",
        "ProfileBuiltinStatus",
        "ProfileBuiltinBadge",
        "ProfileInfraTinySchema",
    }


async def test_schema_branch_generate_identifiers(schema_all_in_one):
    schema = SchemaBranch(cache={}, name="test")
    schema.load_schema(schema=SchemaRoot(**schema_all_in_one))

    schema.generate_identifiers()

    generic = schema.get(name="InfraGenericInterface")
    assert generic.relationships[1].identifier == "builtinstatus__infragenericinterface"


async def test_schema_branch_validate_names():
    SCHEMA1 = {
        "name": "Criticality",
        "namespace": "Test",
        "default_filter": "name__value",
        "branch": BranchSupportType.AWARE.value,
        "attributes": [
            {"name": "name", "kind": "Text", "unique": True},
            {"name": "name", "kind": "Text", "unique": True},
        ],
    }

    schema = SchemaBranch(cache={}, name="test")
    schema.load_schema(schema=SchemaRoot(nodes=[SCHEMA1]))

    with pytest.raises(ValueError) as exc:
        schema.validate_names()

    assert str(exc.value) == "TestCriticality: Names of attributes and relationships must be unique : ['name']"

    SCHEMA2 = {
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

    schema = SchemaBranch(cache={}, name="test")
    schema.load_schema(schema=SchemaRoot(nodes=[SCHEMA2]))

    with pytest.raises(ValueError) as exc:
        schema.validate_names()

    assert str(exc.value) == "TestCriticality: Names of attributes and relationships must be unique : ['dupname']"


async def test_schema_branch_validate_identifiers():
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


async def test_schema_branch_validate_identifiers_direction():
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


async def test_schema_branch_validate_identifiers_matching_direction():
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


async def test_schema_branch_validate_kinds_peer():
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

    assert str(exc.value) == "TestCriticality: Relationship 'first' is referencing an invalid peer 'TestNotPresent'"


async def test_schema_branch_validate_kinds_inherit():
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


async def test_schema_branch_validate_kinds_core(register_core_models_schema: SchemaBranch):
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
async def test_validate_uniqueness_constraints_success(schema_all_in_one, uniqueness_constraints):
    schema_dict = _get_schema_by_kind(schema_all_in_one, "InfraGenericInterface")
    schema_dict["uniqueness_constraints"] = uniqueness_constraints

    schema = SchemaBranch(cache={}, name="test")
    schema.load_schema(schema=SchemaRoot(**schema_all_in_one))

    schema.validate_uniqueness_constraints()


@pytest.mark.parametrize(
    ["uniqueness_constraints", "unique_attributes", "expected_constraints", "expected_unique_attributes"],
    [
        (None, [], None, []),
        (None, ["name"], [["name__value"]], ["name"]),
        ([["name__value"]], ["name"], [["name__value"]], ["name"]),
        ([["name__value"]], [], [["name__value"]], ["name"]),
        ([["name__value"]], ["breed"], [["name__value"], ["breed__value"]], ["name", "breed"]),
        ([["name__value", "owner"]], ["breed"], [["name__value", "owner"], ["breed__value"]], ["breed"]),
        ([["owner"]], ["name"], [["owner"], ["name__value"]], ["name"]),
        (None, ["name", "color"], [["color__value"], ["name__value"]], ["name", "color"]),
        ([["color__value"], ["name__value"]], [], [["color__value"], ["name__value"]], ["name", "color"]),
    ],
)
async def test_synchronize_uniqueness_constraints_and_attributes(
    uniqueness_constraints: list[list[str]] | None,
    unique_attributes: list[str],
    expected_constraints: list[list[str]] | None,
    expected_unique_attributes: list[str],
    animal_person_schema_dict,
):
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
):
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
            "InfraGenericInterface.uniqueness_constraints: value is not a valid attribute of BuiltinStatus",
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
async def test_validate_uniqueness_constraints_error(schema_all_in_one, uniqueness_constraints, expected_error):
    schema_dict = _get_schema_by_kind(schema_all_in_one, "InfraGenericInterface")
    schema_dict["uniqueness_constraints"] = uniqueness_constraints

    schema = SchemaBranch(cache={}, name="test")
    schema.load_schema(schema=SchemaRoot(**schema_all_in_one))

    with pytest.raises(ValueError, match=re.escape(expected_error)):
        schema.validate_uniqueness_constraints()


@pytest.mark.parametrize(
    "display_labels",
    [
        ["my_generic_name__value", "mybool__value"],
        ["my_generic_name__value"],
    ],
)
async def test_validate_display_labels_success(schema_all_in_one, display_labels):
    schema_dict = _get_schema_by_kind(schema_all_in_one, "InfraGenericInterface")
    schema_dict["display_labels"] = display_labels

    schema = SchemaBranch(cache={}, name="test")
    schema.load_schema(schema=SchemaRoot(**schema_all_in_one))

    schema.validate_display_labels()


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
            "InfraGenericInterface.display_labels: value is not a valid attribute of BuiltinStatus",
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
async def test_validate_display_labels_error(schema_all_in_one, display_labels, expected_error):
    schema_dict = _get_schema_by_kind(schema_all_in_one, "InfraGenericInterface")
    schema_dict["display_labels"] = display_labels

    schema = SchemaBranch(cache={}, name="test")
    schema.load_schema(schema=SchemaRoot(**schema_all_in_one))

    with pytest.raises(ValueError, match=expected_error):
        schema.validate_display_labels()


@pytest.mark.parametrize(
    "order_by",
    [
        ["my_generic_name__value", "mybool__value"],
        ["my_generic_name__value"],
        ["primary_tag__name__value"],
        ["status__name__value", "mybool__value"],
    ],
)
async def test_validate_order_by_success(schema_all_in_one, order_by):
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
        (["status__value"], "InfraGenericInterface.order_by: value is not a valid attribute of BuiltinStatus"),
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
async def test_validate_order_by_error(schema_all_in_one, order_by, expected_error):
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
async def test_validate_default_filter_success(schema_all_in_one, default_filter):
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
async def test_validate_default_filter_error(schema_all_in_one, default_filter, expected_error):
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
async def test_validate_default_value_success(schema_all_in_one, default_value_attr):
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
async def test_validate_default_value_error(schema_all_in_one, default_value_attr, expected_error):
    schema_dict = _get_schema_by_kind(schema_all_in_one, "InfraTinySchema")
    schema_dict["attributes"].append(default_value_attr)

    schema = SchemaBranch(cache={}, name="test")
    schema.load_schema(schema=SchemaRoot(**schema_all_in_one))

    with pytest.raises(ValidationError, match=expected_error):
        schema.validate_default_values()


async def test_schema_branch_load_schema_extension(
    db: InfrahubDatabase, default_branch, organization_schema, builtin_schema, helper
):
    schema = SchemaRoot(**core_models)

    schema_branch = SchemaBranch(cache={}, name="test")
    schema_branch.load_schema(schema=schema)
    schema_branch.load_schema(schema=builtin_schema)
    schema_branch.load_schema(schema=organization_schema)
    schema_branch.process()

    org = schema_branch.get(name="CoreOrganization")
    initial_nbr_relationships = len(org.relationships)

    schema_branch.load_schema(schema=SchemaRoot(**helper.schema_file("infra_w_extensions_01.json")))

    org = schema_branch.get(name="CoreOrganization")
    assert len(org.relationships) == initial_nbr_relationships + 1
    assert schema_branch.get(name="InfraDevice")

    # Load it a second time to check if it's idempotent
    schema_branch.load_schema(schema=SchemaRoot(**helper.schema_file("infra_w_extensions_01.json")))
    org = schema_branch.get(name="CoreOrganization")
    assert len(org.relationships) == initial_nbr_relationships + 1
    assert schema_branch.get(name="InfraDevice")


async def test_schema_branch_validate_count_against_cardinality_valid(organization_schema):
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
async def test_schema_branch_validate_count_against_cardinality_invalid(relationship, organization_schema):
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


async def test_schema_branch_from_dict_schema_object():
    schema = SchemaRoot(**core_models)

    schema_branch = SchemaBranch(cache={}, name="test")
    schema_branch.load_schema(schema=schema)

    exported = schema_branch.to_dict_schema_object()

    exported_json = json.dumps(exported, default=lambda x: x.dict())

    exported_dict = json.loads(exported_json)
    schema_branch_after = SchemaBranch.from_dict_schema_object(data=exported_dict)

    assert (
        schema_branch_after.get_node(name=InfrahubKind.TAG).get_hash()
        == schema_branch.get_node(name=InfrahubKind.TAG).get_hash()
    )


async def test_process_relationships_on_delete_defaults_set(schema_all_in_one):
    schema_dict = _get_schema_by_kind(schema_all_in_one, "BuiltinCriticality")
    schema_dict["relationships"][0]["kind"] = "Component"
    schema = SchemaBranch(cache={}, name="test")
    schema.load_schema(schema=SchemaRoot(**schema_all_in_one))

    schema.process_relationships()

    processed_criticality = schema.get(name="BuiltinCriticality", duplicate=False)
    processed_relationship = processed_criticality.get_relationship(name="tags")
    assert processed_relationship.on_delete == RelationshipDeleteBehavior.CASCADE
    for node_schema in schema.get_all(duplicate=False).values():
        for relationship in node_schema.relationships:
            if relationship.kind != RelationshipKind.COMPONENT:
                assert relationship.on_delete == RelationshipDeleteBehavior.NO_ACTION


async def test_process_relationships_component_can_be_overridden(schema_all_in_one):
    schema_dict = _get_schema_by_kind(schema_all_in_one, "BuiltinCriticality")
    schema_dict["relationships"][0]["kind"] = "Component"
    schema_dict["relationships"][0]["on_delete"] = "no-action"
    schema = SchemaBranch(cache={}, name="test")
    schema.load_schema(schema=SchemaRoot(**schema_all_in_one))

    schema.process_relationships()

    processed_criticality = schema.get(name="BuiltinCriticality", duplicate=False)
    processed_relationship = processed_criticality.get_relationship(name="tags")
    assert processed_relationship.on_delete == RelationshipDeleteBehavior.NO_ACTION


async def test_schema_branch_copy(
    db: InfrahubDatabase, reset_registry, default_branch: Branch, register_internal_models_schema
):
    FULL_SCHEMA = {
        "nodes": [
            {
                "name": "Criticality",
                "namespace": "Builtin",
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
                        "peer": InfrahubKind.TAG,
                        "label": "Tags",
                        "optional": True,
                        "cardinality": "many",
                    },
                    {
                        "name": "primary_tag",
                        "peer": InfrahubKind.TAG,
                        "label": "Primary Tag",
                        "identifier": "primary_tag__criticality",
                        "optional": True,
                        "cardinality": "one",
                    },
                ],
            },
            {
                "name": "Tag",
                "namespace": "Builtin",
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
):
    FULL_SCHEMA = {
        "nodes": [
            {
                "name": "Criticality",
                "namespace": "Builtin",
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
                        "peer": InfrahubKind.TAG,
                        "label": "Tags",
                        "optional": True,
                        "cardinality": "many",
                    },
                    {
                        "name": "primary_tag",
                        "peer": InfrahubKind.TAG,
                        "label": "Primary Tag",
                        "identifier": "primary_tag__criticality",
                        "optional": True,
                        "cardinality": "one",
                    },
                ],
            },
            {
                "name": "Tag",
                "namespace": "Builtin",
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

    node = new_schema.get(name="BuiltinCriticality")
    node.attributes[0].unique = False
    new_schema.set(name="BuiltinCriticality", schema=node)

    diff = schema_branch.diff(other=new_schema)
    assert diff.model_dump() == {
        "added": {},
        "changed": {
            "BuiltinCriticality": {
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
):
    FULL_SCHEMA = {
        "nodes": [
            {
                "id": str(uuid.uuid4()),
                "name": "Criticality",
                "namespace": "Builtin",
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
                        "peer": InfrahubKind.TAG,
                        "label": "Tags",
                        "optional": True,
                        "cardinality": "many",
                    },
                    {
                        "id": str(uuid.uuid4()),
                        "name": "primary_tag",
                        "peer": InfrahubKind.TAG,
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
                "namespace": "Builtin",
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

    criticality = new_schema.get(name="BuiltinCriticality")
    criticality.attributes[0].name = f"new-{criticality.attributes[0].name}"
    criticality.relationships[0].name = f"new-{criticality.relationships[0].name}"
    new_schema.set(name="BuiltinCriticality", schema=criticality)

    tag = new_schema.get(name="BuiltinTag")
    tag.name = "NewTag"
    new_schema.delete(name="BuiltinTag")
    new_schema.set(name="BuiltinNewTag", schema=tag)

    diff = schema_branch.diff(other=new_schema)
    assert diff.model_dump() == {
        "added": {},
        "changed": {
            "BuiltinCriticality": {
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
            "BuiltinNewTag": {"added": {}, "changed": {"name": None}, "removed": {}},
        },
        "removed": {},
    }


async def test_schema_branch_diff_add_node_relationship(
    db: InfrahubDatabase, reset_registry, default_branch: Branch, register_internal_models_schema
):
    SCHEMA1 = {
        "nodes": [
            {
                "name": "Criticality",
                "namespace": "Builtin",
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
                "namespace": "Builtin",
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
                    "kind": "BuiltinCriticality",
                    "relationships": [
                        {
                            "name": "tags",
                            "peer": InfrahubKind.TAG,
                            "label": "Tags",
                            "optional": True,
                            "cardinality": "many",
                        },
                        {
                            "name": "primary_tag",
                            "peer": InfrahubKind.TAG,
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
        "added": {"BuiltinTag": {"added": {}, "changed": {}, "removed": {}}},
        "changed": {
            "BuiltinCriticality": {
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
):
    FULL_SCHEMA = {
        "nodes": [
            {
                "name": "Criticality",
                "namespace": "Builtin",
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
                        "peer": InfrahubKind.TAG,
                        "label": "Tags",
                        "optional": True,
                        "cardinality": "many",
                    },
                    {
                        "name": "primary_tag",
                        "peer": InfrahubKind.TAG,
                        "label": "Primary Tag",
                        "identifier": "primary_tag__criticality",
                        "optional": True,
                        "cardinality": "one",
                    },
                ],
            },
            {
                "name": "Tag",
                "namespace": "Builtin",
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

    node = new_schema.get(name="BuiltinCriticality")
    node.attributes[0].unique = False
    new_schema.set(name="BuiltinCriticality", schema=node)

    result = schema_branch.validate_update(other=new_schema)
    assert result.model_dump(exclude=["diff"]) == {
        "constraints": [
            {
                "constraint_name": "attribute.unique.update",
                "path": {
                    "field_name": "name",
                    "path_type": SchemaPathType.ATTRIBUTE,
                    "property_name": "unique",
                    "schema_id": None,
                    "schema_kind": "BuiltinCriticality",
                },
            },
        ],
        "enforce_update_support": True,
        "errors": [],
        "migrations": [],
    }


async def test_schema_branch_validate_add_node_relationships(
    db: InfrahubDatabase, reset_registry, default_branch: Branch, register_internal_models_schema
):
    SCHEMA1 = {
        "nodes": [
            {
                "name": "Criticality",
                "namespace": "Builtin",
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
                "namespace": "Builtin",
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
                    "kind": "BuiltinCriticality",
                    "relationships": [
                        {
                            "name": "tags",
                            "peer": InfrahubKind.TAG,
                            "label": "Tags",
                            "optional": True,
                            "cardinality": "many",
                        },
                        {
                            "name": "primary_tag",
                            "peer": InfrahubKind.TAG,
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

    result = schema_branch.validate_update(other=new_schema)
    assert result.model_dump(exclude=["diff"]) == {
        "constraints": [],
        "enforce_update_support": True,
        "errors": [],
        "migrations": [],
    }


# -----------------------------------------------------------------
# SchemaManager
# -----------------------------------------------------------------
async def test_schema_manager_set():
    SCHEMA = {
        "name": "Criticality",
        "namespace": "Builtin",
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


async def test_schema_manager_get(default_branch: Branch):
    SCHEMA = {
        "name": "Criticality",
        "namespace": "Builtin",
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


# -----------------------------------------------------------------


async def test_load_node_to_db_node_schema(db: InfrahubDatabase, default_branch: Branch):
    registry.schema = SchemaManager()
    registry.schema.register_schema(schema=SchemaRoot(**internal_schema), branch=default_branch.name)

    SCHEMA = {
        "name": "Criticality",
        "namespace": "Builtin",
        "default_filter": "name__value",
        "attributes": [
            {"name": "name", "kind": "Text", "unique": True},
            {"name": "level", "kind": "Number"},
            {"name": "color", "kind": "Text", "default_value": "#444444"},
            {"name": "description", "kind": "Text", "optional": True},
        ],
        "relationships": [
            {"name": "others", "peer": "BuiltinCriticality", "optional": True, "cardinality": "many"},
        ],
    }
    node = NodeSchema(**SCHEMA)

    await registry.schema.load_node_to_db(node=node, db=db, branch=default_branch)

    node2 = registry.schema.get(name=node.kind, branch=default_branch)
    assert node2.id
    assert node2.relationships[0].id
    assert node2.attributes[0].id

    results = await SchemaManager.query(schema="SchemaNode", branch=default_branch, db=db)
    assert len(results) == 1


async def test_load_node_to_db_generic_schema(db: InfrahubDatabase, default_branch):
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
    await registry.schema.load_node_to_db(node=node, db=db, branch=default_branch)

    results = await SchemaManager.query(
        schema="SchemaGeneric", filters={"kind__value": "InfraGenericInterface"}, branch=default_branch, db=db
    )
    assert len(results) == 1


async def test_update_node_in_db_node_schema(db: InfrahubDatabase, default_branch: Branch):
    SCHEMA = {
        "name": "Criticality",
        "namespace": "Builtin",
        "default_filter": "name__value",
        "attributes": [
            {"name": "name", "kind": "Text", "unique": True},
            {"name": "level", "kind": "Number"},
            {"name": "color", "kind": "Text", "default_value": "#444444"},
            {"name": "description", "kind": "Text", "optional": True},
        ],
        "relationships": [
            {"name": "others", "peer": "BuiltinCriticality", "optional": True, "cardinality": "many"},
        ],
    }

    registry.schema = SchemaManager()
    registry.schema.register_schema(schema=SchemaRoot(**internal_schema), branch=default_branch.name)
    await registry.schema.load_node_to_db(node=NodeSchema(**SCHEMA), db=db, branch=default_branch)

    node = registry.schema.get(name="BuiltinCriticality", branch=default_branch)

    new_node = node.duplicate()

    new_node.default_filter = "kind__value"
    new_node.attributes[0].unique = False

    await registry.schema.update_node_in_db(node=new_node, db=db, branch=default_branch)

    results = await SchemaManager.get_many(ids=[node.id, new_node.attributes[0].id], db=db)

    assert results[new_node.id].default_filter.value == "kind__value"
    assert results[new_node.attributes[0].id].unique.value is False


async def test_load_schema_to_db_internal_models(db: InfrahubDatabase, default_branch: Branch):
    schema = SchemaRoot(**internal_schema)
    new_schema = registry.schema.register_schema(schema=schema, branch=default_branch.name)

    await registry.schema.load_schema_to_db(schema=new_schema, db=db, branch=default_branch.name)

    node_schema = registry.schema.get(name="SchemaNode", branch=default_branch)
    results = await SchemaManager.query(schema=node_schema, db=db)
    assert len(results) > 1
    assert all(r for r in results if r.namespace.value != "Profile")


async def test_load_schema_to_db_core_models(
    db: InfrahubDatabase, default_branch: Branch, register_internal_models_schema
):
    schema = SchemaRoot(**core_models)
    new_schema = registry.schema.register_schema(schema=schema, branch=default_branch.name)

    await registry.schema.load_schema_to_db(schema=new_schema, db=db)

    node_schema = registry.schema.get(name="SchemaGeneric")
    results = await SchemaManager.query(schema=node_schema, db=db)
    assert len(results) > 1
    assert all(r for r in results if r.namespace.value != "Profile")


async def test_clean_diff_after_reload_from_db(
    db: InfrahubDatabase, default_branch: Branch, register_internal_models_schema
):
    schema = SchemaRoot(**core_models)
    new_schema = registry.schema.register_schema(schema=schema, branch=default_branch.name)

    await registry.schema.load_schema_to_db(schema=new_schema, db=db)

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
):
    schema = SchemaRoot(**helper.schema_file("infra_simple_01.json"))
    new_schema = registry.schema.register_schema(schema=schema, branch=default_branch.name)
    await registry.schema.load_schema_to_db(schema=new_schema, db=db, branch=default_branch)

    node_schema = registry.schema.get(name="SchemaNode")
    results = await SchemaManager.query(
        schema=node_schema, filters={"name__value": "Device"}, db=db, branch=default_branch
    )
    assert len(results) == 1


async def test_load_schema_to_db_w_generics_01(
    db: InfrahubDatabase,
    default_branch: Branch,
    register_core_models_schema: SchemaBranch,
    register_builtin_models_schema: SchemaBranch,
    helper,
):
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
):
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
                    {"name": "description", "kind": "Text", "label": "Description", "optional": True},
                ],
                "relationships": [
                    {
                        "name": "tags",
                        "peer": InfrahubKind.TAG,
                        "label": "Tags",
                        "optional": True,
                        "cardinality": "many",
                    },
                    {
                        "name": "primary_tag",
                        "peer": InfrahubKind.TAG,
                        "label": "Primary Tag",
                        "identifier": "primary_tag__criticality",
                        "optional": True,
                        "cardinality": "one",
                    },
                ],
            },
            {
                "namespace": "Builtin",
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
        "ProfileBuiltinTag",
        "ProfileTestCriticality",
        "ProfileTestGenericInterface",
    }

    crit_schema = schema2.get(name="TestCriticality", duplicate=False)
    profiles_rel_schema = crit_schema.get_relationship("profiles")
    assert profiles_rel_schema.peer == InfrahubKind.PROFILE
    assert start_crit_hash == crit_schema.get_hash()
    assert schema11.get(name="TestCriticality").get_hash() == crit_schema.get_hash()
    assert schema11.get(name=InfrahubKind.TAG).get_hash() == schema2.get(name="BuiltinTag").get_hash()
    assert schema11.get(name="TestGenericInterface").get_hash() == schema2.get(name="TestGenericInterface").get_hash()


async def test_load_schema(
    db: InfrahubDatabase, reset_registry, default_branch: Branch, register_internal_models_schema
):
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
                        "peer": InfrahubKind.TAG,
                        "label": "Tags",
                        "optional": True,
                        "cardinality": "many",
                    },
                    {
                        "name": "primary_tag",
                        "peer": InfrahubKind.TAG,
                        "label": "Primary Tag",
                        "identifier": "primary_tag__criticality",
                        "optional": True,
                        "cardinality": "one",
                    },
                ],
            },
            {
                "namespace": "Builtin",
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
    schema11 = registry.schema.get_schema_branch(name=default_branch.name)
    schema2 = await registry.schema.load_schema(db=db, branch=default_branch.name)

    assert len(schema2.nodes) == 6
    assert set(schema2.generics.keys()) == {"CoreProfile", "TestGenericInterface"}
    assert set(schema2.profiles.keys()) == {
        "ProfileBuiltinTag",
        "ProfileTestCriticality",
        "ProfileTestGenericInterface",
    }

    assert schema11.get(name="TestCriticality").get_hash() == schema2.get(name="TestCriticality").get_hash()
    assert schema11.get(name=InfrahubKind.TAG).get_hash() == schema2.get(name=InfrahubKind.TAG).get_hash()
    assert schema11.get(name="TestGenericInterface").get_hash() == schema2.get(name="TestGenericInterface").get_hash()


def test_schema_branch_load_schema_append_to_list(schema_all_in_one):
    schema_branch = SchemaBranch(cache={}, name="test")
    schema_branch.load_schema(schema=SchemaRoot(**schema_all_in_one))
    core_group_schema = _get_schema_by_kind(schema_all_in_one, "CoreGroup")
    core_group_schema["display_labels"] = ["label__value", "name__value"]

    schema_branch.load_schema(schema=SchemaRoot(**schema_all_in_one))

    updated_core_group_schema = schema_branch.get(name="CoreGroup", duplicate=False)
    assert updated_core_group_schema.display_labels == ["label__value", "name__value"]


def test_schema_branch_load_schema_remove_from_list(schema_all_in_one):
    schema_branch = SchemaBranch(cache={}, name="test")
    schema_branch.load_schema(schema=SchemaRoot(**schema_all_in_one))
    core_group_schema = _get_schema_by_kind(schema_all_in_one, "CoreGroup")
    core_group_schema["display_labels"] = ["name__value"]

    schema_branch.load_schema(schema=SchemaRoot(**schema_all_in_one))

    updated_core_group_schema = schema_branch.get(name="CoreGroup", duplicate=False)
    assert updated_core_group_schema.display_labels == ["name__value"]


def test_schema_branch_load_schema_empty_list(schema_all_in_one):
    schema_branch = SchemaBranch(cache={}, name="test")
    schema_branch.load_schema(schema=SchemaRoot(**schema_all_in_one))
    core_group_schema = _get_schema_by_kind(schema_all_in_one, "CoreGroup")
    core_group_schema["display_labels"] = []

    schema_branch.load_schema(schema=SchemaRoot(**schema_all_in_one))

    updated_core_group_schema = schema_branch.get(name="CoreGroup", duplicate=False)
    assert updated_core_group_schema.display_labels == []


def test_schema_branch_load_schema_set_nested_list(schema_all_in_one):
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


def test_schema_branch_load_schema_append_to_nested_list(schema_all_in_one):
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


def test_schema_branch_load_schema_remove_from_nested_list(schema_all_in_one):
    schema_branch = SchemaBranch(cache={}, name="test")
    generic_interface_schema = _get_schema_by_kind(schema_all_in_one, "InfraGenericInterface")
    generic_interface_schema["uniqueness_constraints"] = [["primary_tag", "status"], ["my_generic_name", "mybool"]]
    schema_branch.load_schema(schema=SchemaRoot(**schema_all_in_one))
    generic_interface_schema["uniqueness_constraints"] = [["primary_tag", "status"]]

    schema_branch.load_schema(schema=SchemaRoot(**schema_all_in_one))

    updated_core_group_schema = schema_branch.get(name="InfraGenericInterface", duplicate=False)
    assert updated_core_group_schema.uniqueness_constraints == [["primary_tag", "status"]]


def test_schema_branch_load_schema_update_nested_list(schema_all_in_one):
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


def test_schema_branch_conflicting_required_relationships(schema_all_in_one):
    tag_schema = _get_schema_by_kind(full_schema=schema_all_in_one, kind="BuiltinTag")
    tag_schema["relationships"] = [
        {
            "name": "crits",
            "peer": "BuiltinCriticality",
            "label": "Crits",
            "optional": False,
            "cardinality": "many",
        },
    ]
    crit_schema = _get_schema_by_kind(full_schema=schema_all_in_one, kind="BuiltinCriticality")
    crit_schema["relationships"] = [
        {
            "name": "tags",
            "peer": InfrahubKind.TAG,
            "label": "Tags",
            "optional": False,
            "cardinality": "many",
        },
    ]

    schema = SchemaBranch(cache={}, name="test")
    schema.load_schema(schema=SchemaRoot(**schema_all_in_one))

    with pytest.raises(ValueError) as exc:
        schema.validate_required_relationships()

    assert "BuiltinTag" in exc.value.args[0]
    assert "BuiltinCriticality" in exc.value.args[0]
    assert "cannot both have required relationships" in exc.value.args[0]
