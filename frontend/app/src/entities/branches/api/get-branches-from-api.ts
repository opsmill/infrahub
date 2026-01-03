import { graphql, type VariablesOf } from "gql.tada";

import graphqlClient from "@/shared/api/graphql/graphqlClientApollo";
import type { PaginationParams } from "@/shared/api/types";

const GET_BRANCHES = graphql(`
  query GetBranches($branchSearch: String, $limit: Int, $offset: Int) {
    InfrahubBranch(name__value: $branchSearch, limit: $limit, offset: $offset, partial_match: true) {
      edges {
        node {
          id
          name {
            value
          }
          description {
            value
          }
          origin_branch {
            value
          }
          branched_from {
            value
          }
          status {
            value
          }
          created_at
          sync_with_git {
            value
          }
          is_default {
            value
          }
          has_schema_changes {
            value
          }
        }
        node_metadata {
          created_at
          created_by {
            id
            display_label
            hfid
            __typename
          }
          updated_at
          updated_by {
            id
            display_label
            hfid
            __typename
          }
        }
      }
    }
  }
`);

export const BRANCHES_PER_PAGE = 40;

export interface GetBranchesFromApiParams
  extends PaginationParams,
    VariablesOf<typeof GET_BRANCHES> {}

export const getBranchesFromApi = async ({
  branchSearch,
  limit = BRANCHES_PER_PAGE,
  offset,
}: GetBranchesFromApiParams = {}) => {
  return graphqlClient.query({
    query: GET_BRANCHES,
    variables: {
      branchSearch,
      limit,
      offset,
    },
  });
};
