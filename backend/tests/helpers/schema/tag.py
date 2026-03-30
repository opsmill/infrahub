from infrahub.core.schema import AttributeSchema, NodeSchema

TAG = NodeSchema(
    name="Tag",
    namespace="Testing",
    include_in_menu=True,
    label="Tag",
    default_filter="name__value",
    display_labels=["name__value"],
    attributes=[
        AttributeSchema(name="name", kind="Text", unique=True),
        AttributeSchema(name="description", kind="Text", optional=True),
    ],
)
