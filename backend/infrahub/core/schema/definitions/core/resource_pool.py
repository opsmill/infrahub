from infrahub.core.constants import (
    BranchSupportType,
    InfrahubKind,
    NumberPoolType,
)
from infrahub.core.constants import RelationshipCardinality as Cardinality
from infrahub.core.constants import RelationshipKind as RelKind

from ...attribute_schema import AttributeSchema as Attr
from ...generic_schema import GenericSchema
from ...node_schema import NodeSchema
from ...relationship_schema import (
    RelationshipSchema as Rel,
)

core_resource_pool = GenericSchema(
    name="ResourcePool",
    namespace="Core",
    label="Resource Pool",
    description="The resource manager contains pools of resources to allow for automatic assignments.",
    include_in_menu=False,
    default_filter="name__value",
    order_by=["name__value"],
    display_labels=["name__value"],
    human_friendly_id=["name__value"],
    icon="mdi:view-grid-outline",
    branch=BranchSupportType.AGNOSTIC,
    uniqueness_constraints=[["name__value"]],
    generate_profile=False,
    attributes=[
        Attr(name="name", kind="Text", order_weight=1000, unique=True),
        Attr(name="description", kind="Text", optional=True, order_weight=2000),
    ],
)

core_weighted_pool_resource = GenericSchema(
    name="WeightedPoolResource",
    namespace="Core",
    label="Weighted Pool Resource",
    description="Resource to be used in a pool, its weight is used to determine its priority on allocation.",
    include_in_menu=False,
    branch=BranchSupportType.AWARE,
    generate_profile=False,
    attributes=[
        Attr(
            name="allocation_weight",
            label="Weight",
            description="Weight determines allocation priority, resources with higher values are selected first.",
            kind="Number",
            optional=True,
            order_weight=10000,
        )
    ],
)

core_ip_prefix_pool = NodeSchema(
    name="IPPrefixPool",
    namespace="Core",
    description="A pool of IP prefix resources",
    label="IP Prefix Pool",
    include_in_menu=False,
    branch=BranchSupportType.AGNOSTIC,
    generate_profile=False,
    inherit_from=[InfrahubKind.RESOURCEPOOL, InfrahubKind.LINEAGESOURCE],
    attributes=[
        Attr(
            name="default_prefix_length",
            kind="Number",
            description="The default prefix length as an integer for prefixes allocated from this pool.",
            optional=True,
            order_weight=5000,
        ),
        Attr(
            name="default_member_type",
            kind="Text",
            enum=["prefix", "address"],
            default_value="prefix",
            optional=True,
            order_weight=3000,
        ),
        Attr(name="default_prefix_type", kind="Text", optional=True, order_weight=4000),
    ],
    relationships=[
        Rel(
            name="resources",
            peer=InfrahubKind.IPPREFIX,
            kind=RelKind.ATTRIBUTE,
            identifier="prefixpool__resource",
            cardinality=Cardinality.MANY,
            branch=BranchSupportType.AGNOSTIC,
            optional=False,
            order_weight=6000,
        ),
        Rel(
            name="ip_namespace",
            peer=InfrahubKind.IPNAMESPACE,
            kind=RelKind.ATTRIBUTE,
            identifier="prefixpool__ipnamespace",
            cardinality=Cardinality.ONE,
            branch=BranchSupportType.AGNOSTIC,
            optional=False,
            order_weight=7000,
        ),
    ],
)

core_ip_address_pool = NodeSchema(
    name="IPAddressPool",
    namespace="Core",
    description="A pool of IP address resources",
    label="IP Address Pool",
    include_in_menu=False,
    branch=BranchSupportType.AGNOSTIC,
    generate_profile=False,
    inherit_from=[InfrahubKind.RESOURCEPOOL, InfrahubKind.LINEAGESOURCE],
    attributes=[
        Attr(
            name="default_address_type",
            kind="Text",
            optional=False,
            description="The object type to create when reserving a resource in the pool",
            order_weight=3000,
        ),
        Attr(
            name="default_prefix_length",
            kind="Number",
            optional=True,
            description="The default prefix length as an integer for addresses allocated from this pool.",
            order_weight=4000,
        ),
    ],
    relationships=[
        Rel(
            name="resources",
            peer=InfrahubKind.IPPREFIX,
            kind=RelKind.ATTRIBUTE,
            identifier="ipaddresspool__resource",
            cardinality=Cardinality.MANY,
            branch=BranchSupportType.AGNOSTIC,
            optional=False,
            order_weight=5000,
        ),
        Rel(
            name="ip_namespace",
            peer=InfrahubKind.IPNAMESPACE,
            kind=RelKind.ATTRIBUTE,
            identifier="ipaddresspool__ipnamespace",
            cardinality=Cardinality.ONE,
            branch=BranchSupportType.AGNOSTIC,
            optional=False,
            order_weight=6000,
        ),
    ],
)

core_number_pool = NodeSchema(
    name="NumberPool",
    namespace="Core",
    description="A pool of number resources",
    label="Number Pool",
    include_in_menu=False,
    branch=BranchSupportType.AGNOSTIC,
    generate_profile=False,
    inherit_from=[InfrahubKind.RESOURCEPOOL, InfrahubKind.LINEAGESOURCE],
    attributes=[
        Attr(
            name="node",
            kind="Text",
            optional=False,
            description="The model of the object that requires integers to be allocated",
            order_weight=3000,
        ),
        Attr(
            name="node_attribute",
            kind="Text",
            description="The attribute of the selected model",
            optional=False,
            order_weight=4000,
        ),
        Attr(
            name="start_range",
            kind="Number",
            optional=False,
            description="The start range for the pool",
            order_weight=5000,
        ),
        Attr(
            name="end_range", kind="Number", optional=False, description="The end range for the pool", order_weight=6000
        ),
        Attr(
            name="pool_type",
            kind="Text",
            description="Defines how this number pool was created",
            default_value=NumberPoolType.USER.value,
            enum=NumberPoolType.available_types(),
            read_only=True,
        ),
    ],
)
