import type { VariablesOf } from "gql.tada";

import graphqlClient from "@/shared/api/graphql/graphqlClientApollo";

import { ENUM_REMOVE_MUTATION } from "@/entities/schema/api/enum";

export interface RemoveEnumFromApiParams extends VariablesOf<typeof ENUM_REMOVE_MUTATION> {}

export function removeEnumFromApi(variables: RemoveEnumFromApiParams) {
  return graphqlClient.mutate({
    mutation: ENUM_REMOVE_MUTATION,
    variables,
  });
}
