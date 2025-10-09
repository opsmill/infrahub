from graphql.type.definition import GraphQLList, GraphQLNonNull, GraphQLObjectType

from infrahub.core.branch import Branch
from infrahub.database import InfrahubDatabase
from infrahub.graphql.initialization import prepare_graphql_params


async def test_schema_is_nonnull(db: InfrahubDatabase, default_branch: Branch, car_person_schema: None) -> None:
    default_branch.update_schema_hash()
    gql_params = await prepare_graphql_params(db=db, branch=default_branch)

    assert gql_params.schema.query_type

    for name, field in gql_params.schema.query_type.fields.items():
        # ------------------------------------------------------------
        # If edges is defined
        #   validate that edges itself is NonNull and that elements of the list are NonNull as well
        # ------------------------------------------------------------
        if (
            isinstance(field.type, GraphQLNonNull)
            and isinstance(field.type.of_type, GraphQLObjectType)
            and "edges" in field.type.of_type.fields
        ):
            edge_type = field.type.of_type.fields["edges"].type

            assert isinstance(edge_type, GraphQLNonNull), f"Field 'edges' of {name} is not NonNull"

            if isinstance(edge_type.of_type, GraphQLList):
                assert isinstance(edge_type.of_type.of_type, GraphQLNonNull), (
                    f"Element of 'edges' of {name} is not NonNull"
                )

        elif isinstance(field.type, GraphQLObjectType) and "edges" in field.type.fields:
            edge_type = field.type.fields["edges"].type
            assert isinstance(edge_type, GraphQLNonNull), f"Field 'edges' of {name} is not NonNull"
            raise AssertionError(f"Query {name} includes edges and is not NonNull")
