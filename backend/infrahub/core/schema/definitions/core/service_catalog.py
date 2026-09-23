from infrahub.core.constants import BranchSupportType, InfrahubKind
from infrahub.core.constants import RelationshipCardinality as Cardinality
from infrahub.core.constants import RelationshipKind as RelKind
from infrahub.service_portal.constants import ServiceCatalogEntryMode, ServiceRequestStatus

from ...attribute_schema import AttributeSchema as Attr
from ...node_schema import NodeSchema
from ...relationship_schema import (
    RelationshipSchema as Rel,
)

core_service_catalog_entry = NodeSchema(
    name="ServiceCatalogEntry",
    namespace="Core",
    description="A service that requesters can order from the Service Portal",
    include_in_menu=False,
    icon="mdi:storefront-outline",
    label="Service Catalog Entry",
    default_filter="name__value",
    order_by=["name__value"],
    display_label="name__value",
    branch=BranchSupportType.AWARE,
    uniqueness_constraints=[["name__value"]],
    generate_profile=False,
    attributes=[
        Attr(name="name", kind="Text", unique=True, description="Name of the service shown on its catalog card"),
        Attr(
            name="description",
            kind="TextArea",
            optional=True,
            description="Short explanation of the service shown on its catalog card",
        ),
        Attr(
            name="icon",
            kind="Text",
            optional=True,
            description="Icon shown on the catalog card, as an mdi: icon name",
        ),
        Attr(
            name="target_kind",
            kind="Text",
            optional=False,
            description="Kind of the service object created when the service is ordered",
        ),
        Attr(
            name="generators",
            kind="List",
            optional=True,
            description="Names of the generator definitions to run on the service object, in run order",
        ),
        Attr(
            name="mode",
            kind="Text",
            enum=ServiceCatalogEntryMode.available_types(),
            default_value=ServiceCatalogEntryMode.REVIEW.value,
            optional=True,
            description="review opens a proposed change from a request branch, direct writes to the default branch",
        ),
        Attr(
            name="fields",
            kind="List",
            optional=False,
            description="Attribute and relationship names of the target kind shown on the order form, in form order",
        ),
    ],
    relationships=[
        Rel(
            name="tags",
            peer=InfrahubKind.TAG,
            kind=RelKind.ATTRIBUTE,
            optional=True,
            cardinality=Cardinality.MANY,
            identifier="servicecatalogentry__tag",
        ),
        Rel(
            # `object_template` is reserved for the template a node is created from
            name="template",
            peer=InfrahubKind.OBJECTTEMPLATE,
            kind=RelKind.ATTRIBUTE,
            optional=True,
            cardinality=Cardinality.ONE,
            identifier="servicecatalogentry__objecttemplate",
            description="Template applied to the service object, supplying the values not on the order form",
        ),
    ],
)

core_service_request = NodeSchema(
    name="ServiceRequest",
    namespace="Core",
    description="An order placed through the Service Portal and the state of its fulfilment",
    include_in_menu=False,
    icon="mdi:clipboard-text-clock-outline",
    label="Service Request",
    order_by=["node_metadata__created_at"],
    generate_profile=False,
    branch=BranchSupportType.AGNOSTIC,
    attributes=[
        Attr(
            name="status",
            kind="Text",
            enum=ServiceRequestStatus.available_types(),
            default_value=ServiceRequestStatus.SUBMITTED.value,
            optional=True,
            read_only=True,
            description="Current stage of the request, written by the Service Portal workflow",
        ),
        Attr(
            name="message",
            kind="Text",
            optional=True,
            read_only=True,
            description="Human-readable progress or failure summary",
        ),
        Attr(
            name="inputs",
            kind="JSON",
            optional=True,
            description="Submitted form values, in the shape of the target kind's create input",
        ),
        Attr(
            name="branch",
            kind="Text",
            optional=True,
            read_only=True,
            description="Name of the branch the request is built on",
        ),
        Attr(
            name="task_id",
            kind="Text",
            optional=True,
            read_only=True,
            description="Identifier of the latest workflow run for this request",
        ),
    ],
    relationships=[
        Rel(
            name="entry",
            peer=InfrahubKind.SERVICECATALOGENTRY,
            kind=RelKind.ATTRIBUTE,
            optional=False,
            cardinality=Cardinality.ONE,
            identifier="servicerequest__servicecatalogentry",
        ),
        Rel(
            name="requester",
            peer=InfrahubKind.GENERICACCOUNT,
            kind=RelKind.ATTRIBUTE,
            optional=False,
            cardinality=Cardinality.ONE,
            branch=BranchSupportType.AGNOSTIC,
            identifier="servicerequest__requester",
        ),
        Rel(
            name="service",
            peer=InfrahubKind.NODE,
            kind=RelKind.ATTRIBUTE,
            optional=True,
            cardinality=Cardinality.ONE,
            read_only=True,
            identifier="servicerequest__service",
        ),
        Rel(
            name="proposed_change",
            peer=InfrahubKind.PROPOSEDCHANGE,
            kind=RelKind.ATTRIBUTE,
            optional=True,
            cardinality=Cardinality.ONE,
            read_only=True,
            identifier="servicerequest__proposedchange",
        ),
    ],
)
