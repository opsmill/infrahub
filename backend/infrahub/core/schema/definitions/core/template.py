from ...attribute_schema import AttributeSchema as Attr
from ...generic_schema import GenericSchema

core_object_template = GenericSchema(
    name="ObjectTemplate",
    namespace="Core",
    include_in_menu=False,
    icon="mdi:pencil-ruler",
    description="Template to create pre-shaped objects.",
    label="Object Templates",
    display_labels=["template_name__value"],
    default_filter="template_name__value",
    uniqueness_constraints=[["template_name__value"]],
    attributes=[Attr(name="template_name", kind="Text", optional=False, unique=True, order_weight=1000)],
)

core_object_component_template = GenericSchema(
    name="ObjectComponentTemplate",
    namespace="Core",
    include_in_menu=False,
    icon="mdi:pencil-ruler",
    description="Component template to create pre-shaped objects.",
    label="Object Component Templates",
    display_labels=["template_name__value"],
    default_filter="template_name__value",
    attributes=[Attr(name="template_name", kind="Text", optional=False, order_weight=1000)],
)
