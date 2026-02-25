import { graphql } from "gql.tada";

import graphqlClient from "@/shared/api/graphql/graphqlClientApollo";
import type { ContextParams } from "@/shared/api/types";

const SEARCH_RESULTS = graphql(`
  query SearchResults($search: String!, $limit: Int, $offset: Int, $caseSensitive: Boolean) {
    InfrahubSearchAnywhere(
      q: $search
      limit: $limit
      offset: $offset
      partial_match: true
      case_sensitive: $caseSensitive
    ) {
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

export interface SearchResultsFromApiParams extends ContextParams {
  search: string;
  limit?: number;
  offset?: number;
  caseSensitive?: boolean;
}

export function searchResultsFromApi({
  search,
  limit,
  offset,
  branchName,
  atDate,
  caseSensitive,
}: SearchResultsFromApiParams) {
  return graphqlClient.query({
    query: SEARCH_RESULTS,
    variables: { search, limit, offset, caseSensitive },
    context: {
      branch: branchName,
      date: atDate,
    },
  });
}
