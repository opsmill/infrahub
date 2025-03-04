from infrahub.core.constants import (
    ArtifactStatus,
    BranchSupportType,
    ContentType,
    InfrahubKind,
)

core_artifact_target = {
    "name": "ArtifactTarget",
    "include_in_menu": False,
    "namespace": "Core",
    "description": "Extend a node to be associated with artifacts",
    "label": "Artifact Target",
    "relationships": [
        {
            "name": "artifacts",
            "peer": InfrahubKind.ARTIFACT,
            "optional": True,
            "cardinality": "many",
            "kind": "Generic",
            "identifier": "artifact__node",
        },
    ],
}

core_artifact = {
    "name": "Artifact",
    "namespace": "Core",
    "label": "Artifact",
    "include_in_menu": False,
    "icon": "mdi:file-document-outline",
    "default_filter": "name__value",
    "order_by": ["name__value"],
    "display_labels": ["name__value"],
    "branch": BranchSupportType.LOCAL.value,
    "generate_profile": False,
    "inherit_from": [InfrahubKind.TASKTARGET],
    "documentation": "/topics/artifact",
    "attributes": [
        {"name": "name", "kind": "Text"},
        {
            "name": "status",
            "kind": "Text",
            "enum": ArtifactStatus.available_types(),
        },
        {
            "name": "content_type",
            "kind": "Text",
            "enum": ContentType.available_types(),
        },
        {
            "name": "checksum",
            "kind": "Text",
            "optional": True,
        },
        {
            "name": "storage_id",
            "kind": "Text",
            "optional": True,
            "description": "ID of the file in the object store",
        },
        {"name": "parameters", "kind": "JSON", "optional": True},
    ],
    "relationships": [
        {
            "name": "object",
            "peer": InfrahubKind.ARTIFACTTARGET,
            "kind": "Attribute",
            "identifier": "artifact__node",
            "cardinality": "one",
            "optional": False,
        },
        {
            "name": "definition",
            "peer": InfrahubKind.ARTIFACTDEFINITION,
            "kind": "Attribute",
            "identifier": "artifact__artifact_definition",
            "cardinality": "one",
            "optional": False,
        },
    ],
}

core_artifact_definition = {
    "name": "ArtifactDefinition",
    "namespace": "Core",
    "include_in_menu": False,
    "icon": "mdi:file-document-multiple-outline",
    "label": "Artifact Definition",
    "default_filter": "name__value",
    "order_by": ["name__value"],
    "display_labels": ["name__value"],
    "branch": BranchSupportType.AWARE.value,
    "generate_profile": False,
    "uniqueness_constraints": [["name__value"]],
    "inherit_from": [InfrahubKind.TASKTARGET],
    "documentation": "/topics/artifact",
    "attributes": [
        {"name": "name", "kind": "Text", "unique": True},
        {"name": "artifact_name", "kind": "Text"},
        {"name": "description", "kind": "Text", "optional": True},
        {"name": "parameters", "kind": "JSON"},
        {
            "name": "content_type",
            "kind": "Text",
            "enum": ContentType.available_types(),
        },
    ],
    "relationships": [
        {
            "name": "targets",
            "peer": InfrahubKind.GENERICGROUP,
            "kind": "Attribute",
            "identifier": "artifact_definition___group",
            "cardinality": "one",
            "optional": False,
        },
        {
            "name": "transformation",
            "peer": InfrahubKind.TRANSFORM,
            "kind": "Attribute",
            "identifier": "artifact_definition___transformation",
            "cardinality": "one",
            "optional": False,
        },
    ],
}
