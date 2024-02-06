from graphql import GraphQLSchema

from infrahub.core import registry
from infrahub.core.branch import Branch
from infrahub.database import InfrahubDatabase
from infrahub.graphql.manager import GraphQLSchemaManager


def test_graphql_generate_schema(
    benchmark, db: InfrahubDatabase, default_branch: Branch, data_schema, car_person_schema
):
    schema = registry.schema.get_schema_branch(name=default_branch.name)
    gqlm = GraphQLSchemaManager(schema=schema)
    schema = benchmark(gqlm.generate)

    assert isinstance(schema, GraphQLSchema)
