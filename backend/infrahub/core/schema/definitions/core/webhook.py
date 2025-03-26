from infrahub.core.constants import (
    AllowOverrideType,
    BranchSupportType,
    EventType,
    InfrahubKind,
)
from infrahub.core.constants import RelationshipCardinality as Cardinality
from infrahub.core.constants import RelationshipKind as RelKind

from ...attribute_schema import AttributeSchema as Attr
from ...dropdown import DropdownChoice
from ...generic_schema import GenericSchema
from ...node_schema import NodeSchema
from ...relationship_schema import (
    RelationshipSchema as Rel,
)

core_webhook = GenericSchema(
    name="Webhook",
    namespace="Core",
    description="A webhook that connects to an external integration",
    label="Webhook",
    default_filter="name__value",
    order_by=["name__value"],
    display_labels=["name__value"],
    include_in_menu=False,
    icon="mdi:webhook",
    branch=BranchSupportType.AGNOSTIC,
    uniqueness_constraints=[["name__value"]],
    attributes=[
        Attr(name="name", kind="Text", unique=True, order_weight=1000),
        Attr(
            name="event_type",
            kind="Text",
            enum=["all"] + EventType.available_types(),
            default_value="all",
            order_weight=1500,
            description="The event type that triggers the webhook",
        ),
        Attr(
            name="branch_scope",
            kind="Dropdown",
            choices=[
                DropdownChoice(
                    name="all_branches",
                    label="All Branches",
                    description="All branches",
                    color="#fef08a",
                ),
                DropdownChoice(
                    name="default_branch",
                    label="Default Branch",
                    description="Only the default branch",
                    color="#86efac",
                ),
                DropdownChoice(
                    name="other_branches",
                    label="Other Branches",
                    description="All branches except the default branch",
                    color="#e5e7eb",
                ),
            ],
            default_value="default_branch",
            optional=False,
            order_weight=2000,
            allow_override=AllowOverrideType.NONE,
        ),
        Attr(
            name="node_kind",
            kind="Text",
            optional=True,
            description="Only send node mutation events for nodes of this kind",
            order_weight=2250,
        ),
        Attr(
            name="description",
            kind="Text",
            optional=True,
            order_weight=2500,
        ),
        Attr(name="url", kind="URL", order_weight=3000),
        Attr(
            name="validate_certificates",
            kind="Boolean",
            default_value=True,
            optional=True,
            order_weight=5000,
        ),
    ],
)

core_standard_webhook = NodeSchema(
    name="StandardWebhook",
    namespace="Core",
    description="A webhook that connects to an external integration",
    label="Standard Webhook",
    default_filter="name__value",
    order_by=["name__value"],
    display_labels=["name__value"],
    include_in_menu=False,
    icon="mdi:webhook",
    branch=BranchSupportType.AGNOSTIC,
    generate_profile=False,
    inherit_from=[InfrahubKind.WEBHOOK, InfrahubKind.TASKTARGET],
    attributes=[
        Attr(name="shared_key", kind="Password", unique=False, order_weight=4000),
    ],
)

core_custom_webhook = NodeSchema(
    name="CustomWebhook",
    namespace="Core",
    description="A webhook that connects to an external integration",
    label="Custom Webhook",
    default_filter="name__value",
    order_by=["name__value"],
    display_labels=["name__value"],
    include_in_menu=False,
    icon="mdi:cog-outline",
    branch=BranchSupportType.AGNOSTIC,
    generate_profile=False,
    inherit_from=[InfrahubKind.WEBHOOK, InfrahubKind.TASKTARGET],
    relationships=[
        Rel(
            name="transformation",
            peer=InfrahubKind.TRANSFORMPYTHON,
            kind=RelKind.ATTRIBUTE,
            identifier="webhook___transformation",
            cardinality=Cardinality.ONE,
            optional=True,
            order_weight=7000,
        ),
    ],
)
