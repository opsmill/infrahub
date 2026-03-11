from infrahub.core.constants import BranchSupportType, InfrahubKind

from ...attribute_schema import AttributeSchema as Attr
from ...generic_schema import GenericSchema
from ...node_schema import NodeSchema

core_key_value = GenericSchema(
    name="KeyValue",
    namespace="Core",
    description="A reusable key-value configuration pair",
    label="Key Value",
    default_filter="name__value",
    order_by=["name__value"],
    display_labels=["name__value"],
    include_in_menu=True,
    icon="mdi:key-variant",
    branch=BranchSupportType.AGNOSTIC,
    uniqueness_constraints=[["name__value"]],
    attributes=[
        Attr(name="name", kind="Text", unique=True, order_weight=1000),
        Attr(
            name="key",
            kind="Text",
            description="The key name (e.g., HTTP header field name)",
            order_weight=2000,
        ),
        Attr(name="description", kind="Text", optional=True, order_weight=3000),
    ],
)

core_key_value_static = NodeSchema(
    name="KeyValueStatic",
    namespace="Core",
    description="A plain-text key-value pair for non-sensitive data",
    label="Static Key Value",
    default_filter="name__value",
    order_by=["name__value"],
    display_labels=["name__value"],
    include_in_menu=False,
    icon="mdi:key-variant",
    branch=BranchSupportType.AGNOSTIC,
    generate_profile=False,
    inherit_from=[InfrahubKind.KEYVALUE],
    attributes=[
        Attr(
            name="value",
            kind="Text",
            description="The value stored as plain text",
            order_weight=2500,
        ),
    ],
)

core_key_value_password = NodeSchema(
    name="KeyValuePassword",
    namespace="Core",
    description="A sensitive key-value pair with masked display",
    label="Password Key Value",
    default_filter="name__value",
    order_by=["name__value"],
    display_labels=["name__value"],
    include_in_menu=False,
    icon="mdi:key-variant",
    branch=BranchSupportType.AGNOSTIC,
    generate_profile=False,
    inherit_from=[InfrahubKind.KEYVALUE],
    attributes=[
        Attr(
            name="value",
            kind="Password",
            description="The sensitive value, masked in UI and API responses",
            order_weight=2500,
        ),
    ],
)

core_key_value_environment_variable = NodeSchema(
    name="KeyValueEnvironmentVariable",
    namespace="Core",
    description="A key-value pair that resolves from an environment variable at use time",
    label="Environment Variable Key Value",
    default_filter="name__value",
    order_by=["name__value"],
    display_labels=["name__value"],
    include_in_menu=False,
    icon="mdi:key-variant",
    branch=BranchSupportType.AGNOSTIC,
    generate_profile=False,
    inherit_from=[InfrahubKind.KEYVALUE],
    attributes=[
        Attr(
            name="value",
            kind="Text",
            description="The environment variable name to resolve at send time",
            regex=r"^[A-Za-z_][A-Za-z0-9_]*$",
            order_weight=2500,
        ),
    ],
)
