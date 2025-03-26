from infrahub.core.constants import (
    BranchSupportType,
    InfrahubKind,
)
from infrahub.core.constants import RelationshipCardinality as Cardinality
from infrahub.core.constants import RelationshipKind as RelKind

from ...attribute_schema import AttributeSchema as Attr
from ...node_schema import NodeSchema
from ...relationship_schema import (
    RelationshipSchema as Rel,
)

core_graphql_query = NodeSchema(
    name="GraphQLQuery",
    namespace="Core",
    description="A pre-defined GraphQL Query",
    include_in_menu=False,
    icon="mdi:graphql",
    label="GraphQL Query",
    default_filter="name__value",
    order_by=["name__value"],
    display_labels=["name__value"],
    generate_profile=False,
    branch=BranchSupportType.AWARE,
    uniqueness_constraints=[["name__value"]],
    documentation="/topics/graphql",
    attributes=[
        Attr(name="name", kind="Text", unique=True),
        Attr(name="description", kind="Text", optional=True),
        Attr(name="query", kind="TextArea"),
        Attr(name="variables", kind="JSON", description="variables in use in the query", optional=True, read_only=True),
        Attr(
            name="operations",
            kind="List",
            description="Operations in use in the query, valid operations: 'query', 'mutation' or 'subscription'",
            read_only=True,
            optional=True,
        ),
        Attr(
            name="models",
            kind="List",
            description="List of models associated with this query",
            read_only=True,
            optional=True,
        ),
        Attr(
            name="depth",
            kind="Number",
            description="number of nested levels in the query",
            read_only=True,
            optional=True,
        ),
        Attr(
            name="height",
            kind="Number",
            description="total number of fields requested in the query",
            read_only=True,
            optional=True,
        ),
    ],
    relationships=[
        Rel(
            name="repository",
            peer=InfrahubKind.GENERICREPOSITORY,
            kind=RelKind.ATTRIBUTE,
            identifier="graphql_query__repository",
            cardinality=Cardinality.ONE,
            optional=True,
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
