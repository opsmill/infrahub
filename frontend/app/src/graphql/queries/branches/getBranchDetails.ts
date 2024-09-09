import { gql } from "@apollo/client";

export const getBranchDetailsQuery = gql`
  query GET_BRANCH_DETAILS($branchName: String!) {
    Branch(name: $branchName) {
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
`;
