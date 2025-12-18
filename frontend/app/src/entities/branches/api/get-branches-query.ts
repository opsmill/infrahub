import { gql } from "@apollo/client";

export const GET_BRANCHES = gql`
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
          branched_from {
            value
          }
          status {
            value
          }
          sync_with_git {
            value
          }
          is_default {
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
`;
