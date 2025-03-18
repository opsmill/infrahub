from ...attribute_schema import AttributeSchema as Attr
from ...generic_schema import GenericSchema

core_profile_schema_definition = GenericSchema(
    name="Profile",
    namespace="Core",
    include_in_menu=False,
    icon="mdi:shape-plus-outline",
    description="Base Profile in Infrahub.",
    label="Profile",
    display_labels=["profile_name__value"],
    default_filter="profile_name__value",
    uniqueness_constraints=[["profile_name__value"]],
    attributes=[
        Attr(name="profile_name", kind="Text", min_length=3, max_length=32, unique=True, optional=False),
        Attr(name="profile_priority", kind="Number", default_value=1000, optional=True),
    ],
)
