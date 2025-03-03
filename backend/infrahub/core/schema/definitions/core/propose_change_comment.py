from infrahub.core.constants import (
    BranchSupportType,
    InfrahubKind,
    RelationshipDeleteBehavior,
)

core_propose_change_comment = {
    "name": "Comment",
    "namespace": "Core",
    "description": "A comment on a Proposed Change",
    "label": "Comment",
    "display_labels": ["text__value"],
    "order_by": ["created_at__value"],
    "include_in_menu": False,
    "branch": BranchSupportType.AGNOSTIC.value,
    "attributes": [
        {"name": "text", "kind": "TextArea", "unique": False, "optional": False},
        {"name": "created_at", "kind": "DateTime", "optional": True},
    ],
    "relationships": [
        {
            "name": "created_by",
            "peer": InfrahubKind.GENERICACCOUNT,
            "optional": True,
            "branch": BranchSupportType.AGNOSTIC.value,
            "cardinality": "one",
            "identifier": "comment__account",
        },
    ],
}

core_thread = {
    "name": "Thread",
    "namespace": "Core",
    "description": "A thread on a Proposed Change",
    "label": "Thread",
    "order_by": ["created_at__value"],
    "branch": BranchSupportType.AGNOSTIC.value,
    "include_in_menu": False,
    "attributes": [
        {"name": "label", "kind": "Text", "optional": True},
        {"name": "resolved", "kind": "Boolean", "default_value": False},
        {"name": "created_at", "kind": "DateTime", "optional": True},
    ],
    "relationships": [
        {
            "name": "change",
            "peer": InfrahubKind.PROPOSEDCHANGE,
            "identifier": "proposedchange__thread",
            "kind": "Parent",
            "optional": False,
            "cardinality": "one",
        },
        {
            "name": "comments",
            "peer": InfrahubKind.THREADCOMMENT,
            "identifier": "thread__threadcomment",
            "kind": "Component",
            "optional": True,
            "cardinality": "many",
            "on_delete": RelationshipDeleteBehavior.CASCADE,
        },
        {
            "name": "created_by",
            "peer": InfrahubKind.GENERICACCOUNT,
            "identifier": "thread__account",
            "optional": True,
            "branch": BranchSupportType.AGNOSTIC.value,
            "cardinality": "one",
        },
    ],
}

core_change_thread = {
    "name": "ChangeThread",
    "namespace": "Core",
    "description": "A thread on proposed change",
    "include_in_menu": False,
    "label": "Change Thread",
    "branch": BranchSupportType.AGNOSTIC.value,
    "inherit_from": [InfrahubKind.THREAD],
    "generate_profile": False,
    "attributes": [],
    "relationships": [],
}

core_file_thread = {
    "name": "FileThread",
    "namespace": "Core",
    "description": "A thread related to a file on a proposed change",
    "include_in_menu": False,
    "label": "Thread - File",
    "branch": BranchSupportType.AGNOSTIC.value,
    "inherit_from": [InfrahubKind.THREAD],
    "generate_profile": False,
    "attributes": [
        {"name": "file", "kind": "Text", "optional": True},
        {"name": "commit", "kind": "Text", "optional": True},
        {"name": "line_number", "kind": "Number", "optional": True},
    ],
    "relationships": [
        {
            "name": "repository",
            "peer": InfrahubKind.REPOSITORY,
            "optional": False,
            "cardinality": "one",
            "branch": BranchSupportType.AGNOSTIC.value,
        },
    ],
}

core_artifact_thread = {
    "name": "ArtifactThread",
    "namespace": "Core",
    "description": "A thread related to an artifact on a proposed change",
    "include_in_menu": False,
    "label": "Thread - Artifact",
    "branch": BranchSupportType.AGNOSTIC.value,
    "inherit_from": [InfrahubKind.THREAD],
    "generate_profile": False,
    "attributes": [
        {"name": "artifact_id", "kind": "Text", "optional": True},
        {"name": "storage_id", "kind": "Text", "optional": True},
        {"name": "line_number", "kind": "Number", "optional": True},
    ],
    "relationships": [],
}

core_object_thread = {
    "name": "ObjectThread",
    "namespace": "Core",
    "description": "A thread related to an object on a proposed change",
    "include_in_menu": False,
    "label": "Thread - Object",
    "branch": BranchSupportType.AGNOSTIC.value,
    "inherit_from": [InfrahubKind.THREAD],
    "generate_profile": False,
    "attributes": [
        {"name": "object_path", "kind": "Text", "optional": False},
    ],
    "relationships": [],
}

core_change_comment = {
    "name": "ChangeComment",
    "namespace": "Core",
    "description": "A comment on proposed change",
    "include_in_menu": False,
    "label": "Change Comment",
    "default_filter": "text__value",
    "display_labels": ["text__value"],
    "branch": BranchSupportType.AGNOSTIC.value,
    "inherit_from": [InfrahubKind.COMMENT],
    "generate_profile": False,
    "relationships": [
        {
            "name": "change",
            "kind": "Parent",
            "peer": InfrahubKind.PROPOSEDCHANGE,
            "cardinality": "one",
            "optional": False,
        },
    ],
}

core_thread_comment = {
    "name": "ThreadComment",
    "namespace": "Core",
    "description": "A comment on thread within a Proposed Change",
    "include_in_menu": False,
    "label": "Thread Comment",
    "default_filter": "text__value",
    "display_labels": ["text__value"],
    "branch": BranchSupportType.AGNOSTIC.value,
    "inherit_from": [InfrahubKind.COMMENT],
    "generate_profile": False,
    "attributes": [],
    "relationships": [
        {
            "name": "thread",
            "peer": InfrahubKind.THREAD,
            "kind": "Parent",
            "identifier": "thread__threadcomment",
            "cardinality": "one",
            "optional": False,
        },
    ],
}
