from infrahub.core.constants import ComputedAttributeKind
from infrahub.core.schema import AttributeSchema, GenericSchema, NodeSchema
from infrahub.core.schema.computed_attribute import ComputedAttribute

SNOW_TASK = GenericSchema(
    name="Task",
    namespace="Snow",
    include_in_menu=False,
    label="Task",
    attributes=[
        AttributeSchema(name="title", kind="Text", unique=False, optional=False),
        AttributeSchema(name="number", kind="NumberPool", optional=False, read_only=True, unique=True),
        AttributeSchema(
            name="identifier",
            kind="Text",
            optional=False,
            read_only=True,
            computed_attribute=ComputedAttribute(
                kind=ComputedAttributeKind.JINJA2,
                jinja2_template="T{{ number__value}}",
            ),
        ),
    ],
)


SNOW_INCIDENT = NodeSchema(
    name="Incident",
    namespace="Snow",
    inherit_from=["SnowTask"],
    include_in_menu=True,
    label="Incident",
    attributes=[
        AttributeSchema(
            name="identifier",
            kind="Text",
            optional=False,
            read_only=True,
            computed_attribute=ComputedAttribute(
                kind=ComputedAttributeKind.JINJA2,
                jinja2_template="INC{{ number__value}}",
            ),
        ),
    ],
)


SNOW_REQUEST = NodeSchema(
    name="Request",
    namespace="Snow",
    inherit_from=["SnowTask"],
    include_in_menu=True,
    label="Request",
    attributes=[
        AttributeSchema(
            name="identifier",
            kind="Text",
            optional=False,
            read_only=True,
            computed_attribute=ComputedAttribute(
                kind=ComputedAttributeKind.JINJA2,
                jinja2_template="REQ{{ number__value}}",
            ),
        ),
    ],
)
