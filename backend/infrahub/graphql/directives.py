from graphql.type.definition import GraphQLArgument, GraphQLList
from graphql.type.directives import DirectiveLocation, GraphQLDirective, specified_directives
from graphql.type.scalars import GraphQLBoolean, GraphQLString

GraphQLExpand = GraphQLDirective(
    name="expand",
    locations=[
        DirectiveLocation.FIELD,
        DirectiveLocation.FRAGMENT_SPREAD,
        DirectiveLocation.INLINE_FRAGMENT,
    ],
    args={
        "add_properties": GraphQLArgument(
            GraphQLBoolean, description="Indicated if applicable properties should be added to the query"
        ),
        "exclude": GraphQLArgument(GraphQLList(GraphQLString), description="Exclude specific fields"),
    },
    description="Expands a field to include Node defaults",
)


DIRECTIVES = list(specified_directives) + [GraphQLExpand]
