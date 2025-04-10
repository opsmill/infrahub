from infrahub.core.constants import ComputedAttributeKind
from infrahub.core.schema import AttributeSchema, GenericSchema, NodeSchema
from infrahub.core.schema.computed_attribute import ComputedAttribute
from tests.constants import TestKind

LOCATION = GenericSchema(
    name="Location",
    namespace="Testing",
    hierarchical=True,
    label="Generic Location",
    default_filter="name__value",
    attributes=[
        AttributeSchema(name="name", kind="Text", unique=True, optional=False),
        AttributeSchema(name="shortname", kind="Text", unique=True, optional=False),
        AttributeSchema(name="description", kind="Text", optional=True),
        AttributeSchema(
            name="code",
            kind="Text",
            optional=False,
            read_only=True,
            computed_attribute=ComputedAttribute(
                kind=ComputedAttributeKind.JINJA2,
                jinja2_template="{{ name__value[:2] | lower }}",
            ),
        ),
    ],
)


CONTINENT = NodeSchema(
    name="Continent",
    namespace="Testing",
    label="Continent",
    default_filter="name__value",
    inherit_from=["TestingLocation"],
    parent="",
    children=TestKind.COUNTRY,
    generate_profile=False,
)


COUNTRY = NodeSchema(
    name="Country",
    namespace="Testing",
    label="Country",
    default_filter="name__value",
    inherit_from=["TestingLocation"],
    parent=TestKind.CONTINENT,
    children=TestKind.SITE,
    generate_profile=False,
    attributes=[
        AttributeSchema(
            name="slug",
            kind="Text",
            optional=False,
            read_only=True,
            computed_attribute=ComputedAttribute(
                kind=ComputedAttributeKind.JINJA2,
                jinja2_template="{{ parent__shortname__value }}-{{ shortname__value }}",
            ),
        ),
        AttributeSchema(
            name="code",
            kind="Text",
            optional=False,
            read_only=True,
            computed_attribute=ComputedAttribute(
                kind=ComputedAttributeKind.JINJA2,
                jinja2_template="{{ name__value[:3] | lower }}",
            ),
        ),
    ],
)


SITE = NodeSchema(
    name="Site",
    namespace="Testing",
    label="Site",
    default_filter="name__value",
    inherit_from=["TestingLocation"],
    parent=TestKind.COUNTRY,
    children="",
    generate_profile=False,
    attributes=[
        AttributeSchema(
            name="slug",
            kind="Text",
            optional=False,
            read_only=True,
            computed_attribute=ComputedAttribute(
                kind=ComputedAttributeKind.JINJA2,
                jinja2_template="{{ parent__slug__value }}-{{ shortname__value }}",
            ),
        )
    ],
)
