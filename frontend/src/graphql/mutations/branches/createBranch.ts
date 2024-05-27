import { gql } from "@apollo/client";

export const BRANCH_CREATE = gql`
  mutation BranchCreate($name: String!, $description: String!, $sync_with_git: Boolean!) {
    BranchCreate(data: { name: $name, description: $description, sync_with_git: $sync_with_git }) {
      object {
        id
        name
        description
        origin_branch
        branched_from
        created_at
        sync_with_git
        is_default
      }
    }
  }
`;
