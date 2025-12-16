import { gql } from "@apollo/client";

export const GET_BRANCHES_COUNT = gql`
query GetBranchesCount($branchName: String) {
    InfrahubBranch(name__value: $branchName, partial_match: true) {
      count
    }
  }
`;
