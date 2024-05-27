import pytest

from infrahub.core.constants import BranchSupportType, InfrahubKind


def _get_schema_by_kind(full_schema, kind):
    for schema_dict in full_schema["nodes"] + full_schema["generics"]:
        schema_kind = schema_dict["namespace"] + schema_dict["name"]
        if schema_kind == kind:
            return schema_dict


@pytest.fixture
async def animal_person_schema_dict() -> dict:
    FULL_SCHEMA = {
        "generics": [
            {
                "name": "Animal",
                "namespace": "Test",
                "display_labels": ["name__value"],
                "human_friendly_id": ["owner__name__value", "name__value"],
                "order_by": ["name__value"],
                "icon": "myicon",
                "uniqueness_constraints": [
                    ["owner", "name__value"],
                ],
                "branch": BranchSupportType.AWARE.value,
                "attributes": [
                    {"name": "name", "kind": "Text"},
                ],
                "relationships": [
                    {
                        "name": "owner",
                        "peer": "TestPerson",
                        "optional": False,
                        "identifier": "person__animal",
                        "cardinality": "one",
                        "direction": "outbound",
                    },
                ],
            },
        ],
        "nodes": [
            {
                "name": "Dog",
                "namespace": "Test",
                "inherit_from": ["TestAnimal"],
                "attributes": [
                    {"name": "breed", "kind": "Text", "optional": False},
                    {"name": "color", "kind": "Color", "default_value": "#444444", "optional": True},
                ],
            },
            {
                "name": "Cat",
                "namespace": "Test",
                "inherit_from": ["TestAnimal"],
                "display_labels": ["name__value", "breed__value", "color__value"],
                "human_friendly_id": ["owner__name__value", "name__value", "breed__value"],
                "order_by": ["breed__value", "name__value"],
                "attributes": [
                    {"name": "breed", "kind": "Text", "optional": False},
                    {"name": "color", "kind": "Color", "default_value": "#444444", "optional": True},
                ],
            },
            {
                "name": "Person",
                "namespace": "Test",
                "display_labels": ["name__value"],
                "attributes": [
                    {"name": "name", "kind": "Text", "unique": True},
                    {"name": "other_name", "kind": "Text", "unique": True},
                    {"name": "height", "kind": "Number", "optional": True},
                ],
                "relationships": [
                    {
                        "name": "animals",
                        "peer": "TestAnimal",
                        "identifier": "person__animal",
                        "cardinality": "many",
                        "direction": "inbound",
                    }
                ],
            },
        ],
    }

    return FULL_SCHEMA


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
            {
                "name": "TinySchema",
                "namespace": "Infra",
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
                        "optional": False,
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


@pytest.fixture
def schema_criticality_tag():
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
    return FULL_SCHEMA


@pytest.fixture
def schema_parent_component() -> dict:
    FULL_SCHEMA = {
        "generics": [
            {
                "name": "ComponentGenericOne",
                "namespace": "Test",
                "attributes": [
                    {"name": "smell", "kind": "Text", "label": "Name"},
                ],
                "relationships": [],
            },
        ],
        "nodes": [
            {
                "name": "ParentNodeOne",
                "namespace": "Test",
                "attributes": [
                    {"name": "name", "kind": "Text", "label": "Name", "unique": True},
                    {"name": "level", "kind": "Number", "label": "Level"},
                    {"name": "color", "kind": "Text", "label": "Color", "default_value": "#444444"},
                    {"name": "description", "kind": "Text", "label": "Description", "optional": True},
                ],
                "relationships": [
                    {
                        "name": "component_ones",
                        "peer": "TestComponentNodeOne",
                        "optional": True,
                        "cardinality": "many",
                        "kind": "Component",
                    },
                ],
            },
            {
                "name": "ParentNodeTwo",
                "namespace": "Test",
                "attributes": [
                    {"name": "height", "kind": "Number", "label": "Height"},
                    {"name": "width", "kind": "Number", "label": "Width"},
                ],
                "relationships": [],
            },
            {
                "name": "ComponentNodeOne",
                "namespace": "Test",
                "inherit_from": ["TestComponentGenericOne"],
                "attributes": [
                    {"name": "name", "kind": "Text", "label": "Name", "unique": True},
                    {"name": "description", "kind": "Text", "label": "Description", "optional": True},
                ],
                "relationships": [
                    {
                        "name": "parent_one",
                        "peer": "TestParentNodeOne",
                        "kind": "Parent",
                        "optional": False,
                        "cardinality": "one",
                    },
                ],
            },
        ],
    }
    return FULL_SCHEMA
