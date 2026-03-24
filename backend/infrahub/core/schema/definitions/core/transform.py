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
        Attr(name="name", kind="Text", unique=True),
        Attr(name="label", kind="Text", optional=True),
        Attr(name="description", kind="Text", optional=True),
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

core_transform_ai = NodeSchema(
    name="TransformAI",
    namespace="Core",
    description="An AI-powered transformation that generates reports using Claude API",
    include_in_menu=False,
    label="Transform AI",
    default_filter="name__value",
    order_by=["name__value"],
    display_labels=["name__value"],
    inherit_from=[InfrahubKind.TRANSFORM],
    generate_profile=False,
    branch=BranchSupportType.AWARE,
    documentation="/topics/transformation",
    attributes=[
        Attr(
            name="prompt_template_path",
            kind="Text",
            description="Path to the markdown prompt template file in the repository",
        ),
        Attr(
            name="model",
            kind="Text",
            description="Claude model to use for generation",
            optional=True,
            default_value="claude-sonnet-4-5-20250929",
        ),
        Attr(
            name="temperature",
            kind="Number",
            description="Temperature for Claude API (0-100 scale, maps to 0.0-1.0)",
            optional=True,
            default_value=100,
        ),
        Attr(
            name="max_tokens",
            kind="Number",
            description="Maximum tokens for Claude API response",
            optional=True,
            default_value=4096,
        ),
        Attr(
            name="output_format",
            kind="Text",
            description="Output format: markdown, csv, or svg",
            optional=True,
            default_value="markdown",
        ),
        Attr(
            name="result_kind",
            kind="Text",
            description="Schema kind for the result FileObject (must inherit from CoreFileObject)",
            optional=True,
        ),
    ],
)
