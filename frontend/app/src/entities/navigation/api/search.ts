import { graphql } from "gql.tada";

import graphqlClient from "@/shared/api/graphql/graphqlClientApollo";
import type { ContextParams } from "@/shared/api/types";

const SEARCH = graphql(`
  query Search($search: String!, $caseSensitive: Boolean) {
    InfrahubSearchAnywhere(q: $search, limit: 10, partial_match: true, case_sensitive: $caseSensitive) {
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
  caseSensitive?: boolean;
}

export function searchAnywhereFromApi({
  search,
  branchName,
  atDate,
  caseSensitive,
}: SearchAnywhereFromApiParams) {
  return graphqlClient.query({
    query: SEARCH,
    variables: { search, caseSensitive },
    context: {
      branch: branchName,
      date: atDate,
    },
  });
}
