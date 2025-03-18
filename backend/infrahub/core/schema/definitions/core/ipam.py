from infrahub.core.constants import (
    AllowOverrideType,
    BranchSupportType,
    InfrahubKind,
    RelationshipDeleteBehavior,
)
from infrahub.core.constants import RelationshipCardinality as Cardinality

from ...attribute_schema import AttributeSchema as Attr
from ...dropdown import DropdownChoice
from ...generic_schema import GenericSchema
from ...node_schema import NodeSchema
from ...relationship_schema import (
    RelationshipSchema as Rel,
)

builtin_ipam = GenericSchema(
    name="IPNamespace",
    namespace="Builtin",
    label="IP Namespace",
    description="A generic container for IP prefixes and IP addresses",
    include_in_menu=False,
    default_filter="name__value",
    order_by=["name__value"],
    display_labels=["name__value"],
    icon="mdi:format-list-group",
    branch=BranchSupportType.AWARE,
    uniqueness_constraints=[["name__value"]],
    generate_profile=False,
    attributes=[
        Attr(name="name", kind="Text", unique=True, branch=BranchSupportType.AWARE, order_weight=1000),
        Attr(name="description", kind="Text", optional=True, branch=BranchSupportType.AWARE, order_weight=2000),
    ],
    relationships=[
        Rel(
            name="ip_prefixes",
            label="IP Prefixes",
            peer=InfrahubKind.IPPREFIX,
            identifier="ip_namespace__ip_prefix",
            optional=True,
            cardinality=Cardinality.MANY,
            on_delete=RelationshipDeleteBehavior.CASCADE,
            allow_override=AllowOverrideType.NONE,
        ),
        Rel(
            name="ip_addresses",
            label="IP Addresses",
            peer=InfrahubKind.IPADDRESS,
            identifier="ip_namespace__ip_address",
            optional=True,
            cardinality=Cardinality.MANY,
            on_delete=RelationshipDeleteBehavior.CASCADE,
            allow_override=AllowOverrideType.NONE,
        ),
    ],
)

builtin_ip_prefix = GenericSchema(
    name="IPPrefix",
    label="IP Prefix",
    namespace="Builtin",
    description="IPv6 or IPv4 prefix also referred as network",
    include_in_menu=False,
    default_filter="prefix__value",
    order_by=["prefix__version", "prefix__binary_address", "prefix__prefixlen"],
    display_labels=["prefix__value"],
    icon="mdi:ip-network",
    branch=BranchSupportType.AWARE,
    hierarchical=True,
    attributes=[
        Attr(name="prefix", kind="IPNetwork", branch=BranchSupportType.AWARE, order_weight=1000),
        Attr(name="description", kind="Text", optional=True, branch=BranchSupportType.AWARE, order_weight=2000),
        Attr(
            name="member_type",
            kind="Dropdown",
            choices=[
                DropdownChoice(
                    name="prefix",
                    label="Prefix",
                    description="Prefix serves as container for other prefixes",
                ),
                DropdownChoice(
                    name="address",
                    label="Address",
                    description="Prefix serves as subnet for IP addresses",
                ),
            ],
            branch=BranchSupportType.AWARE,
            default_value="address",
            order_weight=3000,
        ),
        Attr(
            name="is_pool",
            kind="Boolean",
            branch=BranchSupportType.AWARE,
            default_value=False,
            order_weight=4000,
            description="All IP addresses within this prefix are considered usable",
        ),
        Attr(name="is_top_level", kind="Boolean", read_only=True, optional=True, allow_override=AllowOverrideType.NONE),
        Attr(name="utilization", kind="Number", read_only=True, optional=True, allow_override=AllowOverrideType.NONE),
        Attr(name="netmask", kind="Text", read_only=True, optional=True, allow_override=AllowOverrideType.NONE),
        Attr(name="hostmask", kind="Text", read_only=True, optional=True, allow_override=AllowOverrideType.NONE),
        Attr(name="network_address", kind="Text", read_only=True, optional=True, allow_override=AllowOverrideType.NONE),
        Attr(
            name="broadcast_address", kind="Text", read_only=True, optional=True, allow_override=AllowOverrideType.NONE
        ),
    ],
    relationships=[
        Rel(
            name="ip_namespace",
            label="IP Namespace",
            peer=InfrahubKind.IPNAMESPACE,
            identifier="ip_namespace__ip_prefix",
            optional=True,
            cardinality=Cardinality.ONE,
            allow_override=AllowOverrideType.NONE,
        ),
        Rel(
            name="ip_addresses",
            label="IP Addresses",
            peer=InfrahubKind.IPADDRESS,
            identifier="ip_prefix__ip_address",
            optional=True,
            cardinality=Cardinality.MANY,
            allow_override=AllowOverrideType.NONE,
            read_only=True,
        ),
        Rel(
            name="resource_pool",
            peer="CoreIPAddressPool",
            identifier="ipaddresspool__resource",
            cardinality=Cardinality.MANY,
            branch=BranchSupportType.AGNOSTIC,
            optional=True,
            read_only=True,
        ),
    ],
)

builtin_ip_address = GenericSchema(
    name="IPAddress",
    label="IP Address",
    namespace="Builtin",
    description="IPv6 or IPv4 address",
    include_in_menu=False,
    default_filter="address__value",
    order_by=["address__version", "address__binary_address"],
    display_labels=["address__value"],
    icon="mdi:ip-outline",
    branch=BranchSupportType.AWARE,
    attributes=[
        Attr(name="address", kind="IPHost", branch=BranchSupportType.AWARE, order_weight=1000),
        Attr(name="description", kind="Text", optional=True, branch=BranchSupportType.AWARE, order_weight=2000),
    ],
    relationships=[
        Rel(
            name="ip_namespace",
            label="IP Namespace",
            peer=InfrahubKind.IPNAMESPACE,
            identifier="ip_namespace__ip_address",
            optional=True,
            cardinality=Cardinality.ONE,
            allow_override=AllowOverrideType.NONE,
        ),
        Rel(
            name="ip_prefix",
            label="IP Prefix",
            peer=InfrahubKind.IPPREFIX,
            identifier="ip_prefix__ip_address",
            optional=True,
            cardinality=Cardinality.ONE,
            allow_override=AllowOverrideType.NONE,
            read_only=True,
        ),
    ],
)

core_ipam_namespace = NodeSchema(
    name="Namespace",
    namespace="Ipam",
    description="A namespace that segments IPAM",
    label="IPAM Namespace",
    default_filter="name__value",
    human_friendly_id=["name__value"],
    order_by=["name__value"],
    display_labels=["name__value"],
    include_in_menu=False,
    icon="mdi:format-list-group",
    branch=BranchSupportType.AWARE,
    inherit_from=[InfrahubKind.IPNAMESPACE],
    attributes=[Attr(name="default", kind="Boolean", optional=True, read_only=True, order_weight=9000)],
)
