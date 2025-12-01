import { gql } from "@apollo/client";

import type { SearchQuery } from "@/shared/api/graphql/generated/graphql";
import graphqlClient from "@/shared/api/graphql/graphqlClientApollo";
import type { ContextParams } from "@/shared/api/types";

export const SEARCH = gql`
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
`;

export interface SearchAnywhereFromApiParams extends ContextParams {
  search: string;
}

export function searchAnywhereFromApi({ search, branchName, atDate }: SearchAnywhereFromApiParams) {
  return graphqlClient.query<SearchQuery>({
    query: SEARCH,
    variables: { search },
    context: {
      branch: branchName,
      date: atDate,
    },
  });
}
