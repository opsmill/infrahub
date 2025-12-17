import { gql } from "@apollo/client";

export const GET_BRANCHES_COUNT = gql`
query GetBranchesCount($branchSearch: String) {
    InfrahubBranch(name__value: $branchSearch, partial_match: true) {
      count
    }
  }
`;
