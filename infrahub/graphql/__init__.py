from .generator import generate_mutation_mixin, generate_query_mixin
from .schema import InfrahubBaseMutation, InfrahubBaseQuery


def get_gql_query(branch=None):

    QueryMixin = generate_query_mixin(branch=branch)

    class Query(InfrahubBaseQuery, QueryMixin):
        pass

    return Query


def get_gql_mutation(branch=None):

    MutationMixin = generate_mutation_mixin(branch=branch)

    class Mutation(InfrahubBaseMutation, MutationMixin):
        pass

    return Mutation
