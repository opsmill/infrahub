import { gql } from "@apollo/client";

export const BRANCH_CREATE = gql`
  mutation BranchCreate(
    $name: String!
    $description: String!
    $is_data_only: Boolean!
    $is_isolated: Boolean!
  ) {
    BranchCreate(
      data: {
        name: $name
        description: $description
        is_data_only: $is_data_only
        is_isolated: $is_isolated
      }
    ) {
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
