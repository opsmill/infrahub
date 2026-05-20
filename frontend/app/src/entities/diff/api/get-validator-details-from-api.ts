import type { VariablesOf } from "gql.tada";

import graphqlClient from "@/shared/api/graphql/graphqlClientApollo";

import { GET_VALIDATOR_DETAILS } from "@/entities/diff/api/getValidatorDetails";

export interface GetValidatorDetailsFromApiParams
  extends VariablesOf<typeof GET_VALIDATOR_DETAILS> {}

export function getValidatorDetailsFromApi(variables: GetValidatorDetailsFromApiParams) {
  return graphqlClient.query({
    query: GET_VALIDATOR_DETAILS,
    variables,
  });
}
