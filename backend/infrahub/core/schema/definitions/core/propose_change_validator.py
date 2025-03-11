from infrahub.core.constants import (
    DEFAULT_KIND_MAX_LENGTH,
    DEFAULT_KIND_MIN_LENGTH,
    BranchConflictKeep,
    BranchSupportType,
    InfrahubKind,
    RelationshipDeleteBehavior,
    Severity,
    ValidatorConclusion,
    ValidatorState,
)

core_propose_change_validator = {
    "name": "Validator",
    "namespace": "Core",
    "description": "",
    "include_in_menu": False,
    "label": "Validator",
    "order_by": ["started_at__value"],
    "display_labels": ["label__value"],
    "branch": BranchSupportType.AGNOSTIC.value,
    "attributes": [
        {"name": "label", "kind": "Text", "optional": True},
        {
            "name": "state",
            "kind": "Text",
            "enum": ValidatorState.available_types(),
            "default_value": ValidatorState.QUEUED.value,
        },
        {
            "name": "conclusion",
            "kind": "Text",
            "enum": ValidatorConclusion.available_types(),
            "default_value": ValidatorConclusion.UNKNOWN.value,
        },
        {"name": "completed_at", "kind": "DateTime", "optional": True},
        {"name": "started_at", "kind": "DateTime", "optional": True},
    ],
    "relationships": [
        {
            "name": "proposed_change",
            "peer": InfrahubKind.PROPOSEDCHANGE,
            "kind": "Parent",
            "optional": False,
            "cardinality": "one",
            "identifier": "proposed_change__validator",
        },
        {
            "name": "checks",
            "peer": "CoreCheck",
            "kind": "Component",
            "optional": True,
            "cardinality": "many",
            "identifier": "validator__check",
            "on_delete": RelationshipDeleteBehavior.CASCADE,
        },
    ],
}

core_data_validator = {
    "name": "DataValidator",
    "namespace": "Core",
    "description": "A check to validate the data integrity between two branches",
    "include_in_menu": False,
    "label": "Data Validator",
    "display_labels": ["label__value"],
    "inherit_from": [InfrahubKind.VALIDATOR],
    "generate_profile": False,
    "branch": BranchSupportType.AGNOSTIC.value,
}

core_repository_validator = {
    "name": "RepositoryValidator",
    "namespace": "Core",
    "description": "A Validator related to a specific repository",
    "include_in_menu": False,
    "label": "Repository Validator",
    "display_labels": ["label__value"],
    "inherit_from": [InfrahubKind.VALIDATOR],
    "generate_profile": False,
    "branch": BranchSupportType.AGNOSTIC.value,
    "relationships": [
        {
            "name": "repository",
            "peer": InfrahubKind.GENERICREPOSITORY,
            "kind": "Attribute",
            "optional": False,
            "cardinality": "one",
            "branch": BranchSupportType.AGNOSTIC.value,
        },
    ],
}

core_user_validator = {
    "name": "UserValidator",
    "namespace": "Core",
    "description": "A Validator related to a user defined checks in a repository",
    "include_in_menu": False,
    "label": "User Validator",
    "display_labels": ["label__value"],
    "inherit_from": [InfrahubKind.VALIDATOR],
    "generate_profile": False,
    "branch": BranchSupportType.AGNOSTIC.value,
    "relationships": [
        {
            "name": "check_definition",
            "peer": InfrahubKind.CHECKDEFINITION,
            "kind": "Attribute",
            "optional": False,
            "cardinality": "one",
            "branch": BranchSupportType.AGNOSTIC.value,
        },
        {
            "name": "repository",
            "peer": InfrahubKind.GENERICREPOSITORY,
            "kind": "Attribute",
            "optional": False,
            "cardinality": "one",
            "branch": BranchSupportType.AGNOSTIC.value,
        },
    ],
}

core_schema_validator = {
    "name": "SchemaValidator",
    "namespace": "Core",
    "description": "A validator related to the schema",
    "include_in_menu": False,
    "label": "Schema Validator",
    "display_labels": ["label__value"],
    "generate_profile": False,
    "inherit_from": [InfrahubKind.VALIDATOR],
    "branch": BranchSupportType.AGNOSTIC.value,
}

core_artifact_validator = {
    "name": "ArtifactValidator",
    "namespace": "Core",
    "description": "A validator related to the artifacts",
    "include_in_menu": False,
    "label": "Artifact Validator",
    "display_labels": ["label__value"],
    "inherit_from": [InfrahubKind.VALIDATOR],
    "generate_profile": False,
    "branch": BranchSupportType.AGNOSTIC.value,
    "relationships": [
        {
            "name": "definition",
            "peer": InfrahubKind.ARTIFACTDEFINITION,
            "kind": "Attribute",
            "optional": False,
            "cardinality": "one",
            "branch": BranchSupportType.AGNOSTIC.value,
        },
    ],
}

core_generator_validator = {
    "name": "GeneratorValidator",
    "namespace": "Core",
    "description": "A validator related to generators",
    "include_in_menu": False,
    "label": "Generator Validator",
    "display_labels": ["label__value"],
    "inherit_from": [InfrahubKind.VALIDATOR],
    "generate_profile": False,
    "branch": BranchSupportType.AGNOSTIC.value,
    "relationships": [
        {
            "name": "definition",
            "peer": InfrahubKind.GENERATORDEFINITION,
            "kind": "Attribute",
            "optional": False,
            "cardinality": "one",
            "branch": BranchSupportType.AGNOSTIC.value,
        },
    ],
}

core_check = {
    "name": "Check",
    "namespace": "Core",
    "description": "",
    "display_labels": ["label__value"],
    "include_in_menu": False,
    "label": "Check",
    "branch": BranchSupportType.AGNOSTIC.value,
    "attributes": [
        {"name": "name", "kind": "Text", "optional": True},
        {"name": "label", "kind": "Text", "optional": True},
        {"name": "origin", "kind": "Text", "optional": False},
        {
            "name": "kind",
            "kind": "Text",
            "regex": "^[A-Z][a-zA-Z0-9]+$",
            "optional": False,
            "min_length": DEFAULT_KIND_MIN_LENGTH,
            "max_length": DEFAULT_KIND_MAX_LENGTH,
        },
        {"name": "message", "kind": "TextArea", "optional": True},
        {
            "name": "conclusion",
            "kind": "Text",
            "enum": ValidatorConclusion.available_types(),
            "default_value": ValidatorConclusion.UNKNOWN.value,
            "optional": True,
        },
        {
            "name": "severity",
            "kind": "Text",
            "enum": Severity.available_types(),
            "default_value": Severity.INFO.value,
            "optional": True,
        },
        {"name": "created_at", "kind": "DateTime", "optional": True},
    ],
    "relationships": [
        {
            "name": "validator",
            "peer": InfrahubKind.VALIDATOR,
            "identifier": "validator__check",
            "kind": "Parent",
            "optional": False,
            "cardinality": "one",
        },
    ],
}

core_data_check = {
    "name": "DataCheck",
    "namespace": "Core",
    "description": "A check related to some Data",
    "include_in_menu": False,
    "label": "Data Check",
    "display_labels": ["label__value"],
    "inherit_from": ["CoreCheck"],
    "generate_profile": False,
    "branch": BranchSupportType.AGNOSTIC.value,
    "attributes": [
        {"name": "conflicts", "kind": "JSON"},
        {"name": "keep_branch", "enum": BranchConflictKeep.available_types(), "kind": "Text", "optional": True},
        {"name": "enriched_conflict_id", "kind": "Text", "optional": True},
    ],
}

core_standard_check = {
    "name": "StandardCheck",
    "namespace": "Core",
    "description": "A standard check",
    "include_in_menu": False,
    "label": "Standard Check",
    "display_labels": ["label__value"],
    "inherit_from": ["CoreCheck"],
    "generate_profile": False,
    "branch": BranchSupportType.AGNOSTIC.value,
}

core_schema_check = {
    "name": "SchemaCheck",
    "namespace": "Core",
    "description": "A check related to the schema",
    "include_in_menu": False,
    "label": "Schema Check",
    "display_labels": ["label__value"],
    "inherit_from": ["CoreCheck"],
    "generate_profile": False,
    "branch": BranchSupportType.AGNOSTIC.value,
    "attributes": [
        {"name": "conflicts", "kind": "JSON"},
        {"name": "enriched_conflict_id", "kind": "Text", "optional": True},
    ],
}

core_file_check = {
    "name": "FileCheck",
    "namespace": "Core",
    "description": "A check related to a file in a Git Repository",
    "include_in_menu": False,
    "label": "File Check",
    "display_labels": ["label__value"],
    "inherit_from": ["CoreCheck"],
    "generate_profile": False,
    "branch": BranchSupportType.AGNOSTIC.value,
    "attributes": [
        {"name": "files", "kind": "List", "optional": True},
        {"name": "commit", "kind": "Text", "optional": True},
    ],
}

core_artifact_check = {
    "name": "ArtifactCheck",
    "namespace": "Core",
    "description": "A check related to an artifact",
    "include_in_menu": False,
    "label": "Artifact Check",
    "display_labels": ["label__value"],
    "inherit_from": ["CoreCheck"],
    "generate_profile": False,
    "branch": BranchSupportType.AGNOSTIC.value,
    "attributes": [
        {"name": "changed", "kind": "Boolean", "optional": True},
        {"name": "checksum", "kind": "Text", "optional": True},
        {"name": "artifact_id", "kind": "Text", "optional": True},
        {"name": "storage_id", "kind": "Text", "optional": True},
        {"name": "line_number", "kind": "Number", "optional": True},
    ],
}

core_generator_check = {
    "name": "GeneratorCheck",
    "namespace": "Core",
    "description": "A check related to a Generator instance",
    "include_in_menu": False,
    "label": "Generator Check",
    "display_labels": ["label__value"],
    "inherit_from": ["CoreCheck"],
    "generate_profile": False,
    "branch": BranchSupportType.AGNOSTIC.value,
    "attributes": [
        {
            "name": "instance",
            "kind": "Text",
            "optional": False,
        },
    ],
}
