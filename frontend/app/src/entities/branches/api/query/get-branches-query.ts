import { gql } from "@apollo/client";

export const GET_BRANCHES = gql`
  query GetBranches($branchName: String) {
    Branch(name: $branchName) {
      id
      name
      description
      origin_branch
      branched_from
      status
      created_at
      sync_with_git
      is_default
      has_schema_changes
    }
  }
`;
