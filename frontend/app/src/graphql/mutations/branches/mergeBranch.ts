import { gql } from "@apollo/client";

export const BRANCH_MERGE = gql`
mutation BRANCH_MERGE($name: String) {
  BranchMerge (
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
