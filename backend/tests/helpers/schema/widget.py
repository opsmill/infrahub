from infrahub.core.schema import AttributeSchema, NodeSchema

WIDGET = NodeSchema(
    name="Widget",
    namespace="Testing",
    label="Widget",
    default_filter="name__value",
    order_by=["name__value"],
    attributes=[
        AttributeSchema(name="name", kind="Text", optional=False),
        AttributeSchema(name="description", kind="Text", optional=True),
        AttributeSchema(name="height", kind="Number", optional=True),
        AttributeSchema(name="weight", kind="Number", optional=True),
    ],
    inherit_from=["LineageOwner", "LineageSource"],
)
