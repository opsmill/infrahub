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
from infrahub.core.constants import RelationshipCardinality as Cardinality
from infrahub.core.constants import RelationshipKind as RelKind

from ...attribute_schema import AttributeSchema as Attr
from ...generic_schema import GenericSchema
from ...node_schema import NodeSchema
from ...relationship_schema import (
    RelationshipSchema as Rel,
)

core_propose_change_validator = GenericSchema(
    name="Validator",
    namespace="Core",
    description="",
    include_in_menu=False,
    label="Validator",
    order_by=["started_at__value"],
    display_labels=["label__value"],
    branch=BranchSupportType.AGNOSTIC,
    attributes=[
        Attr(name="label", kind="Text", optional=True),
        Attr(
            name="state", kind="Text", enum=ValidatorState.available_types(), default_value=ValidatorState.QUEUED.value
        ),
        Attr(
            name="conclusion",
            kind="Text",
            enum=ValidatorConclusion.available_types(),
            default_value=ValidatorConclusion.UNKNOWN.value,
        ),
        Attr(name="completed_at", kind="DateTime", optional=True),
        Attr(name="started_at", kind="DateTime", optional=True),
    ],
    relationships=[
        Rel(
            name="proposed_change",
            peer=InfrahubKind.PROPOSEDCHANGE,
            kind=RelKind.PARENT,
            optional=False,
            cardinality=Cardinality.ONE,
            identifier="proposed_change__validator",
        ),
        Rel(
            name="checks",
            peer=InfrahubKind.CHECK,
            kind=RelKind.COMPONENT,
            optional=True,
            cardinality=Cardinality.MANY,
            identifier="validator__check",
            on_delete=RelationshipDeleteBehavior.CASCADE,
        ),
    ],
)

core_data_validator = NodeSchema(
    name="DataValidator",
    namespace="Core",
    description="A check to validate the data integrity between two branches",
    include_in_menu=False,
    label="Data Validator",
    display_labels=["label__value"],
    inherit_from=[InfrahubKind.VALIDATOR],
    generate_profile=False,
    branch=BranchSupportType.AGNOSTIC,
)

core_repository_validator = NodeSchema(
    name="RepositoryValidator",
    namespace="Core",
    description="A Validator related to a specific repository",
    include_in_menu=False,
    label="Repository Validator",
    display_labels=["label__value"],
    inherit_from=[InfrahubKind.VALIDATOR],
    generate_profile=False,
    branch=BranchSupportType.AGNOSTIC,
    relationships=[
        Rel(
            name="repository",
            peer=InfrahubKind.GENERICREPOSITORY,
            kind=RelKind.ATTRIBUTE,
            optional=False,
            cardinality=Cardinality.ONE,
            branch=BranchSupportType.AGNOSTIC,
        ),
    ],
)

core_user_validator = NodeSchema(
    name="UserValidator",
    namespace="Core",
    description="A Validator related to a user defined checks in a repository",
    include_in_menu=False,
    label="User Validator",
    display_labels=["label__value"],
    inherit_from=[InfrahubKind.VALIDATOR],
    generate_profile=False,
    branch=BranchSupportType.AGNOSTIC,
    relationships=[
        Rel(
            name="check_definition",
            peer=InfrahubKind.CHECKDEFINITION,
            kind=RelKind.ATTRIBUTE,
            optional=False,
            cardinality=Cardinality.ONE,
            branch=BranchSupportType.AGNOSTIC,
        ),
        Rel(
            name="repository",
            peer=InfrahubKind.GENERICREPOSITORY,
            kind=RelKind.ATTRIBUTE,
            optional=False,
            cardinality=Cardinality.ONE,
            branch=BranchSupportType.AGNOSTIC,
        ),
    ],
)

core_schema_validator = NodeSchema(
    name="SchemaValidator",
    namespace="Core",
    description="A validator related to the schema",
    include_in_menu=False,
    label="Schema Validator",
    display_labels=["label__value"],
    generate_profile=False,
    inherit_from=[InfrahubKind.VALIDATOR],
    branch=BranchSupportType.AGNOSTIC,
)

core_artifact_validator = NodeSchema(
    name="ArtifactValidator",
    namespace="Core",
    description="A validator related to the artifacts",
    include_in_menu=False,
    label="Artifact Validator",
    display_labels=["label__value"],
    inherit_from=[InfrahubKind.VALIDATOR],
    generate_profile=False,
    branch=BranchSupportType.AGNOSTIC,
    relationships=[
        Rel(
            name="definition",
            peer=InfrahubKind.ARTIFACTDEFINITION,
            kind=RelKind.ATTRIBUTE,
            optional=False,
            cardinality=Cardinality.ONE,
            branch=BranchSupportType.AGNOSTIC,
        ),
    ],
)

core_generator_validator = NodeSchema(
    name="GeneratorValidator",
    namespace="Core",
    description="A validator related to generators",
    include_in_menu=False,
    label="Generator Validator",
    display_labels=["label__value"],
    inherit_from=[InfrahubKind.VALIDATOR],
    generate_profile=False,
    branch=BranchSupportType.AGNOSTIC,
    relationships=[
        Rel(
            name="definition",
            peer=InfrahubKind.GENERATORDEFINITION,
            kind=RelKind.ATTRIBUTE,
            optional=False,
            cardinality=Cardinality.ONE,
            branch=BranchSupportType.AGNOSTIC,
        ),
    ],
)

core_check = GenericSchema(
    name="Check",
    namespace="Core",
    description="",
    display_labels=["label__value"],
    include_in_menu=False,
    label="Check",
    branch=BranchSupportType.AGNOSTIC,
    attributes=[
        Attr(name="name", kind="Text", optional=True),
        Attr(name="label", kind="Text", optional=True),
        Attr(name="origin", kind="Text", optional=False),
        Attr(
            name="kind",
            kind="Text",
            regex=r"^[A-Z][a-zA-Z0-9]+$",
            optional=False,
            min_length=DEFAULT_KIND_MIN_LENGTH,
            max_length=DEFAULT_KIND_MAX_LENGTH,
        ),
        Attr(name="message", kind="TextArea", optional=True),
        Attr(
            name="conclusion",
            kind="Text",
            enum=ValidatorConclusion.available_types(),
            default_value=ValidatorConclusion.UNKNOWN.value,
            optional=True,
        ),
        Attr(
            name="severity",
            kind="Text",
            enum=Severity.available_types(),
            default_value=Severity.INFO.value,
            optional=True,
        ),
        Attr(name="created_at", kind="DateTime", optional=True),
    ],
    relationships=[
        Rel(
            name="validator",
            peer=InfrahubKind.VALIDATOR,
            identifier="validator__check",
            kind=RelKind.PARENT,
            optional=False,
            cardinality=Cardinality.ONE,
        ),
    ],
)

core_data_check = NodeSchema(
    name="DataCheck",
    namespace="Core",
    description="A check related to some Data",
    include_in_menu=False,
    label="Data Check",
    display_labels=["label__value"],
    inherit_from=[InfrahubKind.CHECK],
    generate_profile=False,
    branch=BranchSupportType.AGNOSTIC,
    attributes=[
        Attr(name="conflicts", kind="JSON"),
        Attr(name="keep_branch", kind="Text", enum=BranchConflictKeep.available_types(), optional=True),
        Attr(name="enriched_conflict_id", kind="Text", optional=True),
    ],
)

core_standard_check = NodeSchema(
    name="StandardCheck",
    namespace="Core",
    description="A standard check",
    include_in_menu=False,
    label="Standard Check",
    display_labels=["label__value"],
    inherit_from=[InfrahubKind.CHECK],
    generate_profile=False,
    branch=BranchSupportType.AGNOSTIC,
)

core_schema_check = NodeSchema(
    name="SchemaCheck",
    namespace="Core",
    description="A check related to the schema",
    include_in_menu=False,
    label="Schema Check",
    display_labels=["label__value"],
    inherit_from=[InfrahubKind.CHECK],
    generate_profile=False,
    branch=BranchSupportType.AGNOSTIC,
    attributes=[
        Attr(name="conflicts", kind="JSON"),
        Attr(name="enriched_conflict_id", kind="Text", optional=True),
    ],
)

core_file_check = NodeSchema(
    name="FileCheck",
    namespace="Core",
    description="A check related to a file in a Git Repository",
    include_in_menu=False,
    label="File Check",
    display_labels=["label__value"],
    inherit_from=[InfrahubKind.CHECK],
    generate_profile=False,
    branch=BranchSupportType.AGNOSTIC,
    attributes=[
        Attr(name="files", kind="List", optional=True),
        Attr(name="commit", kind="Text", optional=True),
    ],
)

core_artifact_check = NodeSchema(
    name="ArtifactCheck",
    namespace="Core",
    description="A check related to an artifact",
    include_in_menu=False,
    label="Artifact Check",
    display_labels=["label__value"],
    inherit_from=[InfrahubKind.CHECK],
    generate_profile=False,
    branch=BranchSupportType.AGNOSTIC,
    attributes=[
        Attr(name="changed", kind="Boolean", optional=True),
        Attr(name="checksum", kind="Text", optional=True),
        Attr(name="artifact_id", kind="Text", optional=True),
        Attr(name="storage_id", kind="Text", optional=True),
        Attr(name="line_number", kind="Number", optional=True),
    ],
)

core_generator_check = NodeSchema(
    name="GeneratorCheck",
    namespace="Core",
    description="A check related to a Generator instance",
    include_in_menu=False,
    label="Generator Check",
    display_labels=["label__value"],
    inherit_from=[InfrahubKind.CHECK],
    generate_profile=False,
    branch=BranchSupportType.AGNOSTIC,
    attributes=[
        Attr(name="instance", kind="Text", optional=False),
    ],
)
