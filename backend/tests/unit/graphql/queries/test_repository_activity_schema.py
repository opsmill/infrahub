from __future__ import annotations

import graphene
from graphql import GraphQLEnumType, GraphQLNamedType, GraphQLObjectType, get_named_type

from infrahub.graphql.queries.repository_git_state import InfrahubRepositoryActivity


class ActivityQuery(graphene.ObjectType):
    InfrahubRepositoryActivity = InfrahubRepositoryActivity


def build_query_type() -> GraphQLObjectType:
    query_type = graphene.Schema(query=ActivityQuery).graphql_schema.query_type
    if not isinstance(query_type, GraphQLObjectType):
        raise TypeError("The schema has no query type")
    return query_type


def reachable_types(root: GraphQLNamedType) -> dict[str, GraphQLNamedType]:
    """Return every object and enum type reachable from the root type, by name."""
    found: dict[str, GraphQLNamedType] = {}
    pending = [root]
    while pending:
        current = pending.pop()
        if current.name in found or not isinstance(current, (GraphQLObjectType, GraphQLEnumType)):
            continue
        found[current.name] = current
        if isinstance(current, GraphQLObjectType):
            pending.extend(get_named_type(field.type) for field in current.fields.values())
    return found


def test_the_activity_query_describes_its_argument_and_every_type_field_and_value() -> None:
    query_field = build_query_type().fields["InfrahubRepositoryActivity"]
    types = reachable_types(get_named_type(query_field.type))

    assert sorted(types) == [
        "RepositoryActivity",
        "RepositoryActivityBranchEdge",
        "RepositoryActivityBranchNode",
        "RepositoryActivityBranchOutcome",
        "RepositoryActivityBranches",
        "RepositoryActivityLastRunEdge",
        "RepositoryActivityLastRunNode",
        "RepositoryActivityLastRuns",
        "RepositoryActivityLock",
        "RepositoryActivityOperation",
        "RepositoryActivityPhase",
        "RepositoryActivityRunEdge",
        "RepositoryActivityRunNode",
        "RepositoryActivityRuns",
    ]
    undescribed = [] if query_field.description else ["InfrahubRepositoryActivity"]
    undescribed += [
        f"InfrahubRepositoryActivity({name})" for name, argument in query_field.args.items() if not argument.description
    ]
    for type_name, named_type in types.items():
        if not named_type.description:
            undescribed.append(type_name)
        if isinstance(named_type, GraphQLObjectType):
            undescribed += [f"{type_name}.{name}" for name, field in named_type.fields.items() if not field.description]
        if isinstance(named_type, GraphQLEnumType):
            undescribed += [f"{type_name}.{name}" for name, value in named_type.values.items() if not value.description]

    assert undescribed == []
