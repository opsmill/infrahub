from infrahub.core.constants import (
    BranchSupportType,
    InfrahubKind,
)
from infrahub.core.constants import RelationshipCardinality as Cardinality
from infrahub.core.constants import RelationshipKind as RelKind

from ...attribute_schema import AttributeSchema as Attr
from ...node_schema import NodeSchema
from ...relationship_schema import RelationshipSchema as Rel

core_proposed_change_approval = NodeSchema(
    name="ProposedChangeApproval",
    namespace="Core",
    description="Approval for a proposed change",
    include_in_menu=False,
    label="Approval",
    icon="mdi:check-circle-outline",
    branch=BranchSupportType.AGNOSTIC,
    attributes=[
        Attr(name="approved_at", kind="Text", optional=False),
    ],
    relationships=[
        Rel(
            name="approver",
            peer=InfrahubKind.GENERICACCOUNT,
            optional=False,
            cardinality=Cardinality.ONE,
            kind=RelKind.ATTRIBUTE,
            branch=BranchSupportType.AGNOSTIC,
            identifier="coreaccount__approval_approver",
        ),
    ],
)


core_proposed_change_reject = NodeSchema(
    name="ProposedChangeReject",
    namespace="Core",
    description="Reject for a proposed change",
    include_in_menu=False,
    label="Reject",
    icon="mdi:close-circle-outline",
    branch=BranchSupportType.AGNOSTIC,
    attributes=[
        Attr(name="rejected_at", kind="Text", optional=False),
    ],
    relationships=[
        Rel(
            name="rejecter",
            peer=InfrahubKind.GENERICACCOUNT,
            optional=False,
            cardinality=Cardinality.ONE,
            kind=RelKind.ATTRIBUTE,
            branch=BranchSupportType.AGNOSTIC,
            identifier="coreaccount__approval_rejecter",
        ),
    ],
)
