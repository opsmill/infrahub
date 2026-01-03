from infrahub.core.constants import BranchSupportType

from ...attribute_schema import AttributeSchema as Attr
from ...node_schema import NodeSchema

builtin_tag = NodeSchema(
    name="Tag",
    namespace="Builtin",
    description="Standard Tag object to attach to other objects to provide some context.",
    include_in_menu=True,
    icon="mdi:tag-multiple",
    label="Tag",
    default_filter="name__value",
    order_by=["name__value"],
    display_labels=["name__value"],
    branch=BranchSupportType.AWARE,
    uniqueness_constraints=[["name__value"]],
    attributes=[
        Attr(name="name", kind="Text", description="Unique name of the tag", unique=True),
        Attr(name="description", kind="Text", description="Description of what the tag represents", optional=True),
    ],
)
