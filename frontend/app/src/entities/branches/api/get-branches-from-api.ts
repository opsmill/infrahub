import { graphql, type VariablesOf } from "gql.tada";

import graphqlClient from "@/shared/api/graphql/graphqlClientApollo";

export const BRANCHES_PER_PAGE = 40;

const GET_BRANCHES = graphql(`
  query GetBranches($limit: Int, $offset: Int, $nameValue: String, $partialMatch: Boolean, $statusValue: BranchStatus, $createdById: ID) {
    InfrahubBranch(limit: $limit, offset: $offset, name__value: $nameValue, partial_match: $partialMatch, status__value: $statusValue, node_metadata__created_by__id: $createdById) {
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

export type GetBranchesFromApiParams = VariablesOf<typeof GET_BRANCHES>;

export const getBranchesFromApi = async ({
  limit = BRANCHES_PER_PAGE,
  offset,
  nameValue,
  partialMatch,
  statusValue,
  createdById,
}: GetBranchesFromApiParams = {}) => {
  return graphqlClient.query({
    query: GET_BRANCHES,
    variables: { limit, offset, nameValue, partialMatch, statusValue, createdById },
  });
};
