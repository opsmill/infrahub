from graphql.type.definition import GraphQLArgument, GraphQLList
from graphql.type.directives import DirectiveLocation, GraphQLDirective, specified_directives
from graphql.type.scalars import GraphQLString

GraphQLExpand = GraphQLDirective(
    name="expand",
    locations=[
        DirectiveLocation.FIELD,
        DirectiveLocation.FRAGMENT_SPREAD,
        DirectiveLocation.INLINE_FRAGMENT,
    ],
    args={
        "exclude": GraphQLArgument(GraphQLList(GraphQLString), description="Exclude specific fields"),
    },
    description="Expands a field to include Node defaults",
)


DIRECTIVES = list(specified_directives) + [GraphQLExpand]
