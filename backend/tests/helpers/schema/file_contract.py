from infrahub.core.schema import AttributeSchema, NodeSchema

FILE_CONTRACT = NodeSchema(
    name="FileContract",
    namespace="Testing",
    inherit_from=["CoreFileObject"],
    include_in_menu=True,
    label="File Contract",
    human_friendly_id=["file_name__value"],
    display_label="file_name__value",
    attributes=[
        AttributeSchema(name="description", kind="Text", optional=True),
        AttributeSchema(name="contract_start", kind="DateTime", optional=True),
        AttributeSchema(name="contract_end", kind="DateTime", optional=True),
    ],
)
