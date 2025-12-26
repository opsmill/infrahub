import { graphql, type VariablesOf } from "gql.tada";

import graphqlClient from "@/shared/api/graphql/graphqlClientApollo";
import type { ContextParams } from "@/shared/api/types";

const SEARCH = graphql(`
  query Search($search: String!) {
    InfrahubSearchAnywhere(q: $search, limit: 4, partial_match: true) {
      count
      edges {
        node {
          id
          kind
        }
      }
    }
  }
`);

export interface SearchAnywhereFromApiParams extends ContextParams {
  search: string;
}

export function searchAnywhereFromApi({ search, branchName, atDate }: SearchAnywhereFromApiParams) {
  return graphqlClient.query({
    query: SEARCH,
    variables: { search } satisfies VariablesOf<typeof SEARCH>,
    context: {
      branch: branchName,
      date: atDate,
    },
  });
}
