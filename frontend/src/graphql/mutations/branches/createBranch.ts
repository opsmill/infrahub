import { gql } from "@apollo/client";

export const BRANCH_CREATE = gql`
  mutation BranchCreate($name: String!, $description: String!, $isDataOnly: Boolean!) {
    BranchCreate(data: { name: $name, description: $description, is_data_only: $isDataOnly }) {
      object {
        id
        name
        description
        origin_branch
        branched_from
        created_at
        is_data_only
        is_default
      }
    }
  }
`;
