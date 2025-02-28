from infrahub.core.constants import (
    BranchSupportType,
    InfrahubKind,
)

core_group = {
    "name": "Group",
    "namespace": "Core",
    "description": "Generic Group Object.",
    "label": "Group",
    "default_filter": "name__value",
    "order_by": ["name__value"],
    "display_labels": ["label__value"],
    "include_in_menu": False,
    "icon": "mdi:group",
    "hierarchical": True,
    "branch": BranchSupportType.AWARE.value,
    "uniqueness_constraints": [["name__value"]],
    "attributes": [
        {"name": "name", "kind": "Text", "unique": True},
        {"name": "label", "kind": "Text", "optional": True},
        {"name": "description", "kind": "Text", "optional": True},
        {
            "name": "group_type",
            "kind": "Text",
            "enum": ["default", "internal"],
            "default_value": "default",
            "optional": False,
        },
    ],
    "relationships": [
        {
            "name": "members",
            "peer": InfrahubKind.NODE,
            "optional": True,
            "identifier": "group_member",
            "cardinality": "many",
            "branch": BranchSupportType.AWARE,
        },
        {
            "name": "subscribers",
            "peer": InfrahubKind.NODE,
            "optional": True,
            "identifier": "group_subscriber",
            "cardinality": "many",
        },
    ],
}

core_standard_group = {
    "name": "StandardGroup",
    "namespace": "Core",
    "description": "Group of nodes of any kind.",
    "include_in_menu": False,
    "icon": "mdi:account-group",
    "label": "Standard Group",
    "default_filter": "name__value",
    "order_by": ["name__value"],
    "display_labels": ["name__value"],
    "branch": BranchSupportType.AWARE.value,
    "inherit_from": [InfrahubKind.GENERICGROUP],
    "generate_profile": False,
}

core_generator_group = {
    "name": "GeneratorGroup",
    "namespace": "Core",
    "description": "Group of nodes that are created by a generator.",
    "include_in_menu": False,
    "icon": "mdi:state-machine",
    "label": "Generator Group",
    "default_filter": "name__value",
    "order_by": ["name__value"],
    "display_labels": ["name__value"],
    "branch": BranchSupportType.LOCAL.value,
    "inherit_from": [InfrahubKind.GENERICGROUP],
    "generate_profile": False,
}

core_graphql_query_group = {
    "name": "GraphQLQueryGroup",
    "namespace": "Core",
    "description": "Group of nodes associated with a given GraphQLQuery.",
    "include_in_menu": False,
    "icon": "mdi:account-group",
    "label": "GraphQL Query Group",
    "default_filter": "name__value",
    "order_by": ["name__value"],
    "display_labels": ["name__value"],
    "branch": BranchSupportType.LOCAL.value,
    "inherit_from": [InfrahubKind.GENERICGROUP],
    "generate_profile": False,
    "attributes": [
        {"name": "parameters", "kind": "JSON", "optional": True},
    ],
    "relationships": [
        {
            "name": "query",
            "peer": InfrahubKind.GRAPHQLQUERY,
            "optional": False,
            "cardinality": "one",
            "kind": "Attribute",
        },
    ],
}
