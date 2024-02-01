import copy

import pytest
from deepdiff import DeepDiff
from infrahub_sdk.utils import compare_lists

from infrahub.core import registry
from infrahub.core.branch import Branch
from infrahub.core.constants import BranchSupportType, FilterSchemaKind, InfrahubKind
from infrahub.core.schema import (
    GenericSchema,
    NodeSchema,
    SchemaRoot,
    core_models,
    internal_schema,
)
from infrahub.core.schema_manager import SchemaBranch, SchemaManager
from infrahub.database import InfrahubDatabase


# -----------------------------------------------------------------
# SchemaBranch
# -----------------------------------------------------------------
@pytest.fixture
def schema_all_in_one():
    FULL_SCHEMA = {
        "nodes": [
            {
                "name": "Criticality",
                "namespace": "Builtin",
                "inherit_from": ["InfraGenericInterface"],
                "default_filter": "name__value",
                "branch": BranchSupportType.AGNOSTIC.value,
                "attributes": [
                    {"name": "name", "kind": "Text", "unique": True},
                    {"name": "level", "kind": "Number", "branch": BranchSupportType.AWARE.value},
                    {"name": "color", "kind": "Text", "default_value": "#444444"},
                    {"name": "description", "kind": "Text", "optional": True},
                ],
                "relationships": [
                    {
                        "name": "tags",
                        "peer": InfrahubKind.TAG,
                        "label": "Tags",
                        "optional": True,
                        "cardinality": "many",
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
                    {
                        "name": "description",
                        "kind": "Text",
                        "label": "Description",
                        "optional": True,
                        "branch": BranchSupportType.AGNOSTIC.value,
                    },
                ],
            },
            {
                "name": "Status",
                "namespace": "Builtin",
                "branch": BranchSupportType.AGNOSTIC.value,
                "attributes": [
                    {"name": "name", "kind": "Text", "label": "Name", "unique": True},
                ],
            },
            {
                "name": "Badge",
                "namespace": "Builtin",
                "branch": BranchSupportType.LOCAL.value,
                "attributes": [
                    {"name": "name", "kind": "Text", "label": "Name", "unique": True},
                ],
            },
            {
                "name": "StandardGroup",
                "namespace": "Core",
                "inherit_from": [InfrahubKind.GENERICGROUP],
                "attributes": [
                    {"name": "name", "kind": "Text", "label": "Name", "unique": True},
                ],
            },
        ],
        "generics": [
            {
                "name": "GenericInterface",
                "namespace": "Infra",
                "attributes": [
                    {"name": "my_generic_name", "kind": "Text"},
                    {"name": "mybool", "kind": "Boolean", "default_value": False},
                    {"name": "local_attr", "kind": "Number", "branch": BranchSupportType.LOCAL.value},
                ],
                "relationships": [
                    {
                        "name": "primary_tag",
                        "peer": InfrahubKind.TAG,
                        "label": "Primary Tag",
                        "identifier": "primary_tag__criticality",
                        "optional": True,
                        "cardinality": "one",
                        "branch": BranchSupportType.AGNOSTIC.value,
                    },
                    {
                        "name": "status",
                        "peer": "BuiltinStatus",
                        "optional": True,
                        "cardinality": "one",
                    },
                    {
                        "name": "badges",
                        "peer": "BuiltinBadge",
                        "optional": True,
                        "cardinality": "many",
                    },
                ],
            },
            {
                "name": "Node",
                "namespace": "Core",
                "description": "Base Node in Infrahub.",
                "label": "Node",
            },
            {
                "name": "Group",
                "namespace": "Core",
                "description": "Generic Group Object.",
                "label": "Group",
                "default_filter": "name__value",
                "order_by": ["name__value"],
                "display_labels": ["label__value"],
                "branch": BranchSupportType.AWARE.value,
                "attributes": [
                    {"name": "name", "kind": "Text", "unique": True},
                    {"name": "label", "kind": "Text", "optional": True},
                    {"name": "description", "kind": "Text", "optional": True},
                ],
                "relationships": [
                    {
                        "name": "members",
                        "peer": "CoreNode",
                        "optional": True,
                        "identifier": "group_member",
                        "cardinality": "many",
                    },
                    {
                        "name": "subscribers",
                        "peer": "CoreNode",
                        "optional": True,
                        "identifier": "group_subscriber",
                        "cardinality": "many",
                    },
                ],
            },
        ],
    }

    return FULL_SCHEMA


def _get_schema_by_kind(full_schema, kind):
    for schema_dict in full_schema["nodes"] + full_schema["generics"]:
        schema_kind = schema_dict["namespace"] + schema_dict["name"]
        if schema_kind == kind:
            return schema_dict


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
    assert std_group.get_relationship(name="member_of_groups", raise_on_error=False) is None
    assert std_group.get_relationship(name="subscriber_of_groups", raise_on_error=False) is None


async def test_schema_branch_generate_weight(schema_all_in_one):
    def extract_weights(schema: SchemaBranch):
        weights = []
        for _, node in schema.get_all().items():
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


async def test_schema_branch_validate_menu_placement():
    """Validate that menu placements points to objects that exists in the schema."""
    FULL_SCHEMA = {
        "version": "1.0",
        "nodes": [
            {
                "name": "Criticality",
                "namespace": "Test",
                "default_filter": "name__value",
                "branch": BranchSupportType.AWARE.value,
                "attributes": [
                    {"name": "name", "kind": "Text", "unique": True},
                ],
            },
            {
                "name": "SubObject",
                "namespace": "Test",
                "menu_placement": "NoSuchObject",
                "default_filter": "name__value",
                "branch": BranchSupportType.AWARE.value,
                "attributes": [
                    {"name": "name", "kind": "Text", "unique": True},
                ],
            },
        ],
    }

    schema = SchemaBranch(cache={})
    schema.load_schema(schema=SchemaRoot(**FULL_SCHEMA))

    with pytest.raises(ValueError) as exc:
        schema.validate_menu_placements()

    assert str(exc.value) == "TestSubObject: NoSuchObject is not a valid menu placement"


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
            "InfraGenericInterface.display_labels: notanattribute is not an attribute of InfraGenericInterface",
        ),
        (["my_generic_name__something"], "InfraGenericInterface.display_labels: attribute property must be one of"),
        (
            ["status__value"],
            "InfraGenericInterface.display_labels: status is not an attribute of InfraGenericInterface",
        ),
        (["badges__name__value"], "InfraGenericInterface.display_labels: this property only supports attributes"),
        (["mybool"], "InfraGenericInterface.display_labels: mybool must be of the format"),
        (["badges"], "InfraGenericInterface.display_labels: badges must be of the format"),
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
            "InfraGenericInterface.order_by: notanattribute is not an attribute of InfraGenericInterface",
        ),
        (["my_generic_name__something"], "InfraGenericInterface.order_by: attribute property must be one of"),
        (["status__value"], "InfraGenericInterface.order_by: status is not an attribute of InfraGenericInterface"),
        (["badges__name__value"], "InfraGenericInterface.order_by: cannot use badges relationship"),
        (["mybool"], "InfraGenericInterface.order_by: mybool must be of the format"),
        (["badges"], "InfraGenericInterface.order_by: badges must be of the format"),
        (["status__name__nothing"], "InfraGenericInterface.order_by: attribute property must be one of"),
    ],
)
async def test_validate_order_by_error(schema_all_in_one, order_by, expected_error):
    schema_dict = _get_schema_by_kind(schema_all_in_one, "InfraGenericInterface")
    schema_dict["order_by"] = order_by

    schema = SchemaBranch(cache={}, name="test")
    schema.load_schema(schema=SchemaRoot(**schema_all_in_one))

    with pytest.raises(ValueError, match=expected_error):
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
            "InfraGenericInterface.default_filter: notanattribute is not an attribute of InfraGenericInterface",
        ),
        ("my_generic_name__something", "InfraGenericInterface.default_filter: attribute property must be one of"),
        ("badges__name__value", "InfraGenericInterface.default_filter: this property only supports attributes"),
        ("mybool", "InfraGenericInterface.default_filter: mybool must be of the format"),
        ("badges", "InfraGenericInterface.default_filter: badges must be of the format"),
        ("status__name__nothing", "InfraGenericInterface.default_filter: this property only supports attributes"),
        ("primary_tag__name__value", "InfraGenericInterface.default_filter: this property only supports attributes"),
        ("status__name__value", "InfraGenericInterface.default_filter: this property only supports attributes"),
    ],
)
async def test_validate_default_filter_error(schema_all_in_one, default_filter, expected_error):
    schema_dict = _get_schema_by_kind(schema_all_in_one, "InfraGenericInterface")
    schema_dict["default_filter"] = default_filter

    schema = SchemaBranch(cache={}, name="test")
    schema.load_schema(schema=SchemaRoot(**schema_all_in_one))

    with pytest.raises(ValueError, match=expected_error):
        schema.validate_default_filters()


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


async def test_schema_branch_process_filters(
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
    schema_branch.process_filters()

    assert len(schema_branch.nodes) == 2
    criticality_dict = schema_branch.get("BuiltinCriticality").model_dump()

    expected_filters = [
        {"name": "ids", "kind": FilterSchemaKind.TEXT, "enum": None, "object_kind": None, "description": None},
        {"name": "name__value", "kind": FilterSchemaKind.TEXT, "enum": None, "object_kind": None, "description": None},
        {"name": "name__values", "kind": FilterSchemaKind.TEXT, "enum": None, "object_kind": None, "description": None},
        {
            "name": "name__is_visible",
            "kind": FilterSchemaKind.BOOLEAN,
            "enum": None,
            "object_kind": None,
            "description": None,
        },
        {
            "name": "name__is_protected",
            "kind": FilterSchemaKind.BOOLEAN,
            "enum": None,
            "object_kind": None,
            "description": None,
        },
        {
            "name": "name__source__id",
            "kind": FilterSchemaKind.TEXT,
            "enum": None,
            "object_kind": None,
            "description": None,
        },
        {
            "name": "name__owner__id",
            "kind": FilterSchemaKind.TEXT,
            "enum": None,
            "object_kind": None,
            "description": None,
        },
        {
            "name": "level__value",
            "kind": FilterSchemaKind.NUMBER,
            "enum": None,
            "object_kind": None,
            "description": None,
        },
        {
            "name": "level__values",
            "kind": FilterSchemaKind.TEXT,
            "enum": None,
            "object_kind": None,
            "description": None,
        },
        {
            "name": "level__is_visible",
            "kind": FilterSchemaKind.BOOLEAN,
            "enum": None,
            "object_kind": None,
            "description": None,
        },
        {
            "name": "level__is_protected",
            "kind": FilterSchemaKind.BOOLEAN,
            "enum": None,
            "object_kind": None,
            "description": None,
        },
        {
            "name": "level__source__id",
            "kind": FilterSchemaKind.TEXT,
            "enum": None,
            "object_kind": None,
            "description": None,
        },
        {
            "name": "level__owner__id",
            "kind": FilterSchemaKind.TEXT,
            "enum": None,
            "object_kind": None,
            "description": None,
        },
        {"name": "color__value", "kind": FilterSchemaKind.TEXT, "enum": None, "object_kind": None, "description": None},
        {
            "name": "color__values",
            "kind": FilterSchemaKind.TEXT,
            "enum": None,
            "object_kind": None,
            "description": None,
        },
        {
            "name": "color__is_visible",
            "kind": FilterSchemaKind.BOOLEAN,
            "enum": None,
            "object_kind": None,
            "description": None,
        },
        {
            "name": "color__is_protected",
            "kind": FilterSchemaKind.BOOLEAN,
            "enum": None,
            "object_kind": None,
            "description": None,
        },
        {
            "name": "color__source__id",
            "kind": FilterSchemaKind.TEXT,
            "enum": None,
            "object_kind": None,
            "description": None,
        },
        {
            "name": "color__owner__id",
            "kind": FilterSchemaKind.TEXT,
            "enum": None,
            "object_kind": None,
            "description": None,
        },
        {
            "name": "description__value",
            "kind": FilterSchemaKind.TEXT,
            "enum": None,
            "object_kind": None,
            "description": None,
        },
        {
            "name": "description__values",
            "kind": FilterSchemaKind.TEXT,
            "enum": None,
            "object_kind": None,
            "description": None,
        },
        {
            "name": "description__is_visible",
            "kind": FilterSchemaKind.BOOLEAN,
            "enum": None,
            "object_kind": None,
            "description": None,
        },
        {
            "name": "description__is_protected",
            "kind": FilterSchemaKind.BOOLEAN,
            "enum": None,
            "object_kind": None,
            "description": None,
        },
        {
            "name": "description__source__id",
            "kind": FilterSchemaKind.TEXT,
            "enum": None,
            "object_kind": None,
            "description": None,
        },
        {
            "name": "description__owner__id",
            "kind": FilterSchemaKind.TEXT,
            "enum": None,
            "object_kind": None,
            "description": None,
        },
        {"name": "any__value", "kind": FilterSchemaKind.TEXT, "enum": None, "object_kind": None, "description": None},
        {
            "name": "any__is_visible",
            "kind": FilterSchemaKind.BOOLEAN,
            "enum": None,
            "object_kind": None,
            "description": None,
        },
        {
            "name": "any__is_protected",
            "kind": FilterSchemaKind.BOOLEAN,
            "enum": None,
            "object_kind": None,
            "description": None,
        },
        {
            "name": "any__source__id",
            "kind": FilterSchemaKind.TEXT,
            "enum": None,
            "object_kind": None,
            "description": None,
        },
        {
            "name": "any__owner__id",
            "kind": FilterSchemaKind.TEXT,
            "enum": None,
            "object_kind": None,
            "description": None,
        },
    ]

    assert not DeepDiff(criticality_dict["filters"], expected_filters, ignore_order=True)


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


async def test_schema_branch_diff(
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

    node = new_schema.get(name="BuiltinCriticality")
    node.attributes[0].unique = False
    new_schema.set(name="BuiltinCriticality", schema=node)

    diff = schema_branch.diff(obj=new_schema)
    assert diff.model_dump() == {"added": [], "changed": ["BuiltinCriticality"], "removed": []}


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


async def test_load_schema_to_db_core_models(
    db: InfrahubDatabase, default_branch: Branch, register_internal_models_schema
):
    schema = SchemaRoot(**core_models)
    new_schema = registry.schema.register_schema(schema=schema, branch=default_branch.name)

    await registry.schema.load_schema_to_db(schema=new_schema, db=db)

    node_schema = registry.schema.get(name="SchemaGeneric")
    results = await SchemaManager.query(schema=node_schema, db=db)
    assert len(results) > 1


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
    schema2 = await registry.schema.load_schema_from_db(db=db, branch=default_branch.name)

    assert len(schema2.nodes) == 6
    assert len(schema2.generics) == 1

    assert schema11.get(name="TestCriticality").get_hash() == schema2.get(name="TestCriticality").get_hash()
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
    assert len(schema2.generics) == 1

    assert schema11.get(name="TestCriticality").get_hash() == schema2.get(name="TestCriticality").get_hash()
    assert schema11.get(name=InfrahubKind.TAG).get_hash() == schema2.get(name=InfrahubKind.TAG).get_hash()
    assert schema11.get(name="TestGenericInterface").get_hash() == schema2.get(name="TestGenericInterface").get_hash()
