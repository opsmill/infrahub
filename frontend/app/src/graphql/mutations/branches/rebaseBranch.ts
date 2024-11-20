import { gql } from "@apollo/client";

export const BRANCH_REBASE = gql`
mutation BRANCH_REBASE($name: String) {
  BranchRebase (
    wait_until_completion: false
    data: {
      name: $name
    }
  ) {
      ok
      task {
        id
      }
  }
}
`;
