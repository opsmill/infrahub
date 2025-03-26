from infrahub.core.constants import (
    NAMESPACE_REGEX,
)

from ...attribute_schema import AttributeSchema as Attr
from ...generic_schema import GenericSchema
from ...node_schema import NodeSchema

generic_menu_item = GenericSchema(
    name="Menu",
    namespace="Core",
    include_in_menu=False,
    description="Element of the Menu",
    label="Menu",
    hierarchical=True,
    human_friendly_id=["namespace__value", "name__value"],
    display_labels=["label__value"],
    generate_profile=False,
    attributes=[
        Attr(name="namespace", kind="Text", regex=NAMESPACE_REGEX, order_weight=1000),
        Attr(name="name", kind="Text", order_weight=1000),
        Attr(name="label", kind="Text", optional=True, order_weight=2000),
        Attr(name="kind", kind="Text", optional=True, order_weight=2500),
        Attr(name="path", kind="Text", optional=True, order_weight=2500),
        Attr(name="description", kind="Text", optional=True, order_weight=3000),
        Attr(name="icon", kind="Text", optional=True, order_weight=4000),
        Attr(name="protected", kind="Boolean", default_value=False, read_only=True, order_weight=5000),
        Attr(name="order_weight", kind="Number", default_value=2000, order_weight=6000),
        Attr(name="required_permissions", kind="List", optional=True, order_weight=7000),
        Attr(
            name="section",
            kind="Text",
            enum=["object", "internal"],
            default_value="object",
            order_weight=8000,
        ),
    ],
)

menu_item = NodeSchema(
    name="MenuItem",
    namespace="Core",
    include_in_menu=False,
    description="Menu Item",
    label="Menu Item",
    inherit_from=["CoreMenu"],
    generate_profile=False,
)
