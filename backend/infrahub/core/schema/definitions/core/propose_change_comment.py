from infrahub.core.constants import (
    BranchSupportType,
    InfrahubKind,
    RelationshipDeleteBehavior,
)
from infrahub.core.constants import RelationshipCardinality as Cardinality
from infrahub.core.constants import RelationshipKind as RelKind

from ...attribute_schema import AttributeSchema as Attr
from ...generic_schema import GenericSchema
from ...node_schema import NodeSchema
from ...relationship_schema import (
    RelationshipSchema as Rel,
)

core_propose_change_comment = GenericSchema(
    name="Comment",
    namespace="Core",
    description="A comment on a Proposed Change",
    label="Comment",
    display_labels=["text__value"],
    order_by=["created_at__value"],
    include_in_menu=False,
    branch=BranchSupportType.AGNOSTIC,
    attributes=[
        Attr(name="text", kind="TextArea", unique=False, optional=False),
        Attr(name="created_at", kind="DateTime", optional=True),
    ],
    relationships=[
        Rel(
            name="created_by",
            peer=InfrahubKind.GENERICACCOUNT,
            optional=True,
            branch=BranchSupportType.AGNOSTIC,
            cardinality=Cardinality.ONE,
            identifier="comment__account",
        ),
    ],
)

core_thread = GenericSchema(
    name="Thread",
    namespace="Core",
    description="A thread on a Proposed Change",
    label="Thread",
    order_by=["created_at__value"],
    branch=BranchSupportType.AGNOSTIC,
    include_in_menu=False,
    attributes=[
        Attr(name="label", kind="Text", optional=True),
        Attr(name="resolved", kind="Boolean", default_value=False),
        Attr(name="created_at", kind="DateTime", optional=True),
    ],
    relationships=[
        Rel(
            name="change",
            peer=InfrahubKind.PROPOSEDCHANGE,
            identifier="proposedchange__thread",
            kind=RelKind.PARENT,
            optional=False,
            cardinality=Cardinality.ONE,
        ),
        Rel(
            name="comments",
            peer=InfrahubKind.THREADCOMMENT,
            identifier="thread__threadcomment",
            kind=RelKind.COMPONENT,
            optional=True,
            cardinality=Cardinality.MANY,
            on_delete=RelationshipDeleteBehavior.CASCADE,
        ),
        Rel(
            name="created_by",
            peer=InfrahubKind.GENERICACCOUNT,
            identifier="thread__account",
            optional=True,
            branch=BranchSupportType.AGNOSTIC,
            cardinality=Cardinality.ONE,
        ),
    ],
)

core_change_thread = NodeSchema(
    name="ChangeThread",
    namespace="Core",
    description="A thread on proposed change",
    include_in_menu=False,
    label="Change Thread",
    branch=BranchSupportType.AGNOSTIC,
    inherit_from=[InfrahubKind.THREAD],
    generate_profile=False,
)

core_file_thread = NodeSchema(
    name="FileThread",
    namespace="Core",
    description="A thread related to a file on a proposed change",
    include_in_menu=False,
    label="Thread - File",
    branch=BranchSupportType.AGNOSTIC,
    inherit_from=[InfrahubKind.THREAD],
    generate_profile=False,
    attributes=[
        Attr(name="file", kind="Text", optional=True),
        Attr(name="commit", kind="Text", optional=True),
        Attr(name="line_number", kind="Number", optional=True),
    ],
    relationships=[
        Rel(
            name="repository",
            peer=InfrahubKind.REPOSITORY,
            optional=False,
            cardinality=Cardinality.ONE,
            branch=BranchSupportType.AGNOSTIC,
        ),
    ],
)

core_artifact_thread = NodeSchema(
    name="ArtifactThread",
    namespace="Core",
    description="A thread related to an artifact on a proposed change",
    include_in_menu=False,
    label="Thread - Artifact",
    branch=BranchSupportType.AGNOSTIC,
    inherit_from=[InfrahubKind.THREAD],
    generate_profile=False,
    attributes=[
        Attr(name="artifact_id", kind="Text", optional=True),
        Attr(name="storage_id", kind="Text", optional=True),
        Attr(name="line_number", kind="Number", optional=True),
    ],
)

core_object_thread = NodeSchema(
    name="ObjectThread",
    namespace="Core",
    description="A thread related to an object on a proposed change",
    include_in_menu=False,
    label="Thread - Object",
    branch=BranchSupportType.AGNOSTIC,
    inherit_from=[InfrahubKind.THREAD],
    generate_profile=False,
    attributes=[
        Attr(name="object_path", kind="Text", optional=False),
    ],
)

core_change_comment = NodeSchema(
    name="ChangeComment",
    namespace="Core",
    description="A comment on proposed change",
    include_in_menu=False,
    label="Change Comment",
    default_filter="text__value",
    display_labels=["text__value"],
    branch=BranchSupportType.AGNOSTIC,
    inherit_from=[InfrahubKind.COMMENT],
    generate_profile=False,
    relationships=[
        Rel(
            name="change",
            kind=RelKind.PARENT,
            peer=InfrahubKind.PROPOSEDCHANGE,
            cardinality=Cardinality.ONE,
            optional=False,
        ),
    ],
)

core_thread_comment = NodeSchema(
    name="ThreadComment",
    namespace="Core",
    description="A comment on thread within a Proposed Change",
    include_in_menu=False,
    label="Thread Comment",
    default_filter="text__value",
    display_labels=["text__value"],
    branch=BranchSupportType.AGNOSTIC,
    inherit_from=[InfrahubKind.COMMENT],
    generate_profile=False,
    attributes=[],
    relationships=[
        Rel(
            name="thread",
            peer=InfrahubKind.THREAD,
            kind=RelKind.PARENT,
            identifier="thread__threadcomment",
            cardinality=Cardinality.ONE,
            optional=False,
        ),
    ],
)
