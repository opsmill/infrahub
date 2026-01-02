from infrahub.core.schema import AttributeSchema, NodeSchema

COLOR = NodeSchema(
    name="Color",
    namespace="Testing",
    include_in_menu=True,
    label="Color",
    default_filter="name__value",
    display_label="name__value",
    attributes=[
        AttributeSchema(name="name", kind="Text", unique=True),
        AttributeSchema(name="description", kind="Text", optional=False),
    ],
)
