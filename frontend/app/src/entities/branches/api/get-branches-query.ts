import { gql } from "@apollo/client";

export const GET_BRANCHES = gql`
query GetBranches($branchName: String, $limit: Int, $offset: Int) {
    InfrahubBranch(name__value: $branchName, limit: $limit, offset: $offset) {
      edges {
        node{
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
      }
    }
  }
`;

export const GET_BRANCHES_COUNT = gql`
query GetBranchesCount($branchName: String) {
    InfrahubBranch(name__value: $branchName) {
      count
    }
  }
`;
