import { gql } from "@apollo/client";

const GET_BRANCHES = gql`
  query GetBranches {
    Branch {
      id
      name
      description
      origin_branch
      branched_from
      created_at
      sync_with_git
      is_default
      has_schema_changes
    }
  }
`;

export default GET_BRANCHES;
