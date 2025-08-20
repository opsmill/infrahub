from infrahub.core.schema import AttributeSchema, NodeSchema

TICKET = NodeSchema(
    name="Ticket",
    namespace="Testing",
    include_in_menu=True,
    label="Ticket",
    human_friendly_id=["title__value", "ticket_id__value"],
    default_filter="title__value",
    attributes=[
        AttributeSchema(name="title", kind="Text", optional=False),
        AttributeSchema(name="description", kind="TextArea", optional=True),
        AttributeSchema(name="ticket_id", kind="Number", optional=True, unique=True),
    ],
)
