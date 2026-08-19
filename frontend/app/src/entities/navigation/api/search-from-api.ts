import { graphql } from "gql.tada";

import graphqlClient from "@/shared/api/graphql/graphqlClientApollo";
import type { ContextParams } from "@/shared/api/types";

const SEARCH = graphql(`
  query Search($search: String!, $limit: Int, $caseSensitive: Boolean) {
    InfrahubSearchAnywhere(q: $search, limit: $limit, partial_match: true, case_sensitive: $caseSensitive) {
      count
      edges {
        node {
          id
          kind
        }
      }
      parent_prefixes {
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
  limit?: number;
  caseSensitive?: boolean;
}

export function searchAnywhereFromApi({
  search,
  branchName,
  atDate,
  limit = 4,
  caseSensitive,
}: SearchAnywhereFromApiParams) {
  return graphqlClient.query({
    query: SEARCH,
    variables: { search, limit, caseSensitive },
    context: {
      branch: branchName,
      date: atDate,
    },
  });
}
