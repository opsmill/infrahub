from infrahub.core.constants import (
    BranchSupportType,
    InfrahubKind,
)

from ...attribute_schema import AttributeSchema as Attr
from ...generic_schema import GenericSchema
from ...node_schema import NodeSchema

core_key_value = GenericSchema(
    name="KeyValue",
    namespace="Core",
    description="A reusable key-value pair for associating named values with other objects",
    label="Key Value",
    default_filter="name__value",
    order_by=["name__value"],
    display_labels=["name__value"],
    uniqueness_constraints=[["name__value"]],
    include_in_menu=True,
    icon="mdi:key-variant",
    branch=BranchSupportType.AGNOSTIC,
    generate_profile=False,
    attributes=[
        Attr(name="name", kind="Text", unique=True, order_weight=1000),
        Attr(name="key", kind="Text", order_weight=2000),
        Attr(name="description", kind="Text", optional=True, order_weight=3000),
    ],
)

core_static_key_value = NodeSchema(
    name="StaticKeyValue",
    namespace="Core",
    description="A key-value pair with a plain-text value",
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
        Attr(name="value", kind="Text", order_weight=4000),
    ],
)

core_password_key_value = NodeSchema(
    name="PasswordKeyValue",
    namespace="Core",
    description="A key-value pair with a password-protected value",
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
        Attr(name="value", kind="Password", order_weight=4000),
    ],
)

core_environment_variable_key_value = NodeSchema(
    name="EnvironmentVariableKeyValue",
    namespace="Core",
    description="A key-value pair whose value is resolved from an environment variable at send time",
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
            description="Environment variable name to resolve at send time",
            order_weight=4000,
        ),
    ],
)
