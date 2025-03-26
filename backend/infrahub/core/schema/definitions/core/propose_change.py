from infrahub.core.constants import (
    BranchSupportType,
    InfrahubKind,
    RelationshipDeleteBehavior,
)
from infrahub.core.constants import RelationshipCardinality as Cardinality
from infrahub.core.constants import RelationshipKind as RelKind
from infrahub.proposed_change.constants import ProposedChangeState

from ...attribute_schema import AttributeSchema as Attr
from ...node_schema import NodeSchema
from ...relationship_schema import (
    RelationshipSchema as Rel,
)

core_proposed_change = NodeSchema(
    name="ProposedChange",
    namespace="Core",
    description="Metadata related to a proposed change",
    include_in_menu=False,
    icon="mdi:file-replace-outline",
    label="Proposed Change",
    default_filter="name__value",
    display_labels=["name__value"],
    generate_profile=False,
    branch=BranchSupportType.AGNOSTIC,
    inherit_from=[InfrahubKind.TASKTARGET],
    documentation="/topics/proposed-change",
    attributes=[
        Attr(name="name", kind="Text", optional=False),
        Attr(name="description", kind="TextArea", optional=True),
        Attr(name="source_branch", kind="Text", optional=False),
        Attr(name="destination_branch", kind="Text", optional=False),
        Attr(
            name="state",
            kind="Text",
            enum=ProposedChangeState.available_types(),
            default_value=ProposedChangeState.OPEN.value,
            optional=True,
        ),
    ],
    relationships=[
        Rel(
            name="approved_by",
            peer=InfrahubKind.GENERICACCOUNT,
            optional=True,
            cardinality=Cardinality.MANY,
            kind=RelKind.ATTRIBUTE,
            branch=BranchSupportType.AGNOSTIC,
            identifier="coreaccount__proposedchange_approved_by",
        ),
        Rel(
            name="reviewers",
            peer=InfrahubKind.GENERICACCOUNT,
            optional=True,
            cardinality=Cardinality.MANY,
            kind=RelKind.ATTRIBUTE,
            branch=BranchSupportType.AGNOSTIC,
            identifier="coreaccount__proposedchange_reviewed_by",
        ),
        Rel(
            name="created_by",
            peer=InfrahubKind.GENERICACCOUNT,
            optional=True,
            cardinality=Cardinality.ONE,
            kind=RelKind.ATTRIBUTE,
            branch=BranchSupportType.AGNOSTIC,
            identifier="coreaccount__proposedchange_created_by",
        ),
        Rel(
            name="comments",
            peer=InfrahubKind.CHANGECOMMENT,
            kind=RelKind.COMPONENT,
            optional=True,
            cardinality=Cardinality.MANY,
            on_delete=RelationshipDeleteBehavior.CASCADE,
        ),
        Rel(
            name="threads",
            peer=InfrahubKind.THREAD,
            identifier="proposedchange__thread",
            kind=RelKind.COMPONENT,
            optional=True,
            cardinality=Cardinality.MANY,
            on_delete=RelationshipDeleteBehavior.CASCADE,
        ),
        Rel(
            name="validations",
            peer=InfrahubKind.VALIDATOR,
            kind=RelKind.COMPONENT,
            identifier="proposed_change__validator",
            optional=True,
            cardinality=Cardinality.MANY,
            on_delete=RelationshipDeleteBehavior.CASCADE,
        ),
    ],
)
