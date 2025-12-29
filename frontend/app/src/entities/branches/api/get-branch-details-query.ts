import { gql } from "@apollo/client";

export const GET_BRANCH_DETAILS = gql`
  query GetBranchDetails($branchName: String!) {
    InfrahubBranch(name__value: $branchName) {
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
      }
    }
  }
`;
