from infrahub.core.constants import (
    BranchSupportType,
    InfrahubKind,
)
from infrahub.core.constants import RelationshipCardinality as Cardinality
from infrahub.core.constants import RelationshipKind as RelKind

from ...attribute_schema import AttributeSchema as Attr
from ...generic_schema import GenericSchema
from ...node_schema import NodeSchema
from ...relationship_schema import (
    RelationshipSchema as Rel,
)

core_transform = GenericSchema(
    name="Transformation",
    namespace="Core",
    description="Generic Transformation Object.",
    include_in_menu=False,
    icon="mdi:cog-transfer",
    label="Transformation",
    default_filter="name__value",
    order_by=["name__value"],
    display_labels=["label__value"],
    branch=BranchSupportType.AWARE,
    documentation="/topics/proposed-change",
    uniqueness_constraints=[["name__value"]],
    attributes=[
        Attr(name="name", kind="Text", description="Unique identifier for the transformation", unique=True),
        Attr(name="label", kind="Text", description="Display label for the transformation", optional=True),
        Attr(
            name="description", kind="Text", description="Description of what this transformation does", optional=True
        ),
        Attr(name="timeout", kind="Number", description="Maximum execution time in seconds", default_value=60),
    ],
    relationships=[
        Rel(
            name="query",
            peer=InfrahubKind.GRAPHQLQUERY,
            identifier="graphql_query__transformation",
            kind=RelKind.ATTRIBUTE,
            cardinality=Cardinality.ONE,
            optional=False,
        ),
        Rel(
            name="repository",
            peer=InfrahubKind.GENERICREPOSITORY,
            kind=RelKind.ATTRIBUTE,
            cardinality=Cardinality.ONE,
            identifier="repository__transformation",
            optional=False,
        ),
        Rel(
            name="tags",
            peer=InfrahubKind.TAG,
            kind=RelKind.ATTRIBUTE,
            optional=True,
            cardinality=Cardinality.MANY,
        ),
    ],
)

core_transform_jinja2 = NodeSchema(
    name="TransformJinja2",
    namespace="Core",
    description="A file rendered from a Jinja2 template",
    include_in_menu=False,
    label="Transform Jinja2",
    default_filter="name__value",
    order_by=["name__value"],
    display_labels=["name__value"],
    inherit_from=[InfrahubKind.TRANSFORM],
    generate_profile=False,
    branch=BranchSupportType.AWARE,
    documentation="/topics/transformation",
    attributes=[
        Attr(name="template_path", kind="Text", description="Path to the Jinja2 template file in the repository"),
    ],
)

core_transform_python = NodeSchema(
    name="TransformPython",
    namespace="Core",
    description="A transform function written in Python",
    include_in_menu=False,
    label="Transform Python",
    default_filter="name__value",
    order_by=["name__value"],
    display_labels=["name__value"],
    inherit_from=[InfrahubKind.TRANSFORM],
    generate_profile=False,
    branch=BranchSupportType.AWARE,
    documentation="/topics/transformation",
    attributes=[
        Attr(name="file_path", kind="Text", description="Path to the Python file in the repository"),
        Attr(name="class_name", kind="Text", description="Name of the Python class implementing the transformation"),
        Attr(
            name="convert_query_response",
            kind="Boolean",
            description="Whether to convert the GraphQL response to SDK objects",
            optional=True,
            default_value=False,
        ),
    ],
)
