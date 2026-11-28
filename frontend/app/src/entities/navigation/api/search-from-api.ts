import { graphql, graphqlClient } from "@/shared/api/graphql/client";
import type { ContextParams } from "@/shared/api/types";

const SEARCH = graphql(`
  query Search($search: String!, $limit: Int!, $offset: Int, $caseSensitive: Boolean) {
    InfrahubSearchAnywhere(
      q: $search
      limit: $limit
      offset: $offset
      partial_match: true
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
  offset?: number;
  caseSensitive?: boolean;
}

export function searchAnywhereFromApi({
  search,
  limit,
  offset,
  branchName,
  atDate,
  caseSensitive,
}: SearchAnywhereFromApiParams) {
  return graphqlClient.query({
    query: SEARCH,
    variables: { search, limit, offset, caseSensitive },
    context: {
      branch: branchName,
      date: atDate,
    },
  });
}
