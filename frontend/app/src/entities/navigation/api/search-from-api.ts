import { graphql, graphqlClient } from "@/shared/api/graphql/client";
import type { ContextParams } from "@/shared/api/types";

const SEARCH = graphql(`
  query Search($search: String!, $limit: Int!, $caseSensitive: Boolean, $partialMatch: Boolean) {
    InfrahubSearchAnywhere(
      q: $search
      limit: $limit
      partial_match: $partialMatch
      case_sensitive: $caseSensitive
    ) {
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
  limit: number;
  caseSensitive?: boolean;
  exactMatch?: boolean;
}

export function searchAnywhereFromApi({
  search,
  limit,
  branchName,
  atDate,
  caseSensitive,
  exactMatch,
}: SearchAnywhereFromApiParams) {
  return graphqlClient.query({
    query: SEARCH,
    variables: { search, limit, caseSensitive, partialMatch: !exactMatch },
    context: {
      branch: branchName,
      date: atDate,
    },
  });
}
