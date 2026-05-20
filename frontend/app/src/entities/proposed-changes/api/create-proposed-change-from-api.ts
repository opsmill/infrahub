import type { VariablesOf } from "gql.tada";

import graphqlClient from "@/shared/api/graphql/graphqlClientApollo";

import { CREATE_PROPOSED_CHANGE } from "@/entities/proposed-changes/api/createProposedChange";

export interface CreateProposedChangeFromApiParams
  extends VariablesOf<typeof CREATE_PROPOSED_CHANGE> {}

export function createProposedChangeFromApi(variables: CreateProposedChangeFromApiParams) {
  return graphqlClient.mutate({
    mutation: CREATE_PROPOSED_CHANGE,
    variables,
  });
}
