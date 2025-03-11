from infrahub.core.constants import (
    BranchSupportType,
    InfrahubKind,
)

core_transform = {
    "name": "Transformation",
    "namespace": "Core",
    "description": "Generic Transformation Object.",
    "include_in_menu": False,
    "icon": "mdi:cog-transfer",
    "label": "Transformation",
    "default_filter": "name__value",
    "order_by": ["name__value"],
    "display_labels": ["label__value"],
    "branch": BranchSupportType.AWARE.value,
    "documentation": "/topics/proposed-change",
    "uniqueness_constraints": [["name__value"]],
    "attributes": [
        {"name": "name", "kind": "Text", "unique": True},
        {"name": "label", "kind": "Text", "optional": True},
        {"name": "description", "kind": "Text", "optional": True},
        {"name": "timeout", "kind": "Number", "default_value": 10},
    ],
    "relationships": [
        {
            "name": "query",
            "peer": InfrahubKind.GRAPHQLQUERY,
            "identifier": "graphql_query__transformation",
            "kind": "Attribute",
            "cardinality": "one",
            "optional": False,
        },
        {
            "name": "repository",
            "peer": InfrahubKind.GENERICREPOSITORY,
            "kind": "Attribute",
            "cardinality": "one",
            "identifier": "repository__transformation",
            "optional": False,
        },
        {
            "name": "tags",
            "peer": InfrahubKind.TAG,
            "kind": "Attribute",
            "optional": True,
            "cardinality": "many",
        },
    ],
}

core_transform_jinja2 = {
    "name": "TransformJinja2",
    "namespace": "Core",
    "description": "A file rendered from a Jinja2 template",
    "include_in_menu": False,
    "label": "Transform Jinja2",
    "default_filter": "name__value",
    "order_by": ["name__value"],
    "display_labels": ["name__value"],
    "inherit_from": [InfrahubKind.TRANSFORM],
    "generate_profile": False,
    "branch": BranchSupportType.AWARE.value,
    "documentation": "/topics/transformation",
    "attributes": [
        {"name": "template_path", "kind": "Text"},
    ],
}

core_transform_python = {
    "name": "TransformPython",
    "namespace": "Core",
    "description": "A transform function written in Python",
    "include_in_menu": False,
    "label": "Transform Python",
    "default_filter": "name__value",
    "order_by": ["name__value"],
    "display_labels": ["name__value"],
    "inherit_from": [InfrahubKind.TRANSFORM],
    "generate_profile": False,
    "branch": BranchSupportType.AWARE.value,
    "documentation": "/topics/transformation",
    "attributes": [
        {"name": "file_path", "kind": "Text"},
        {"name": "class_name", "kind": "Text"},
    ],
}
