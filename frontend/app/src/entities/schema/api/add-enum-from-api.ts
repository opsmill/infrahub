import type { VariablesOf } from "gql.tada";

import graphqlClient from "@/shared/api/graphql/graphqlClientApollo";

import { ENUM_ADD_MUTATION } from "@/entities/schema/api/enum";

export interface AddEnumFromApiParams extends VariablesOf<typeof ENUM_ADD_MUTATION> {}

export function addEnumFromApi(variables: AddEnumFromApiParams) {
  return graphqlClient.mutate({
    mutation: ENUM_ADD_MUTATION,
    variables,
  });
}
