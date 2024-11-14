import { gql } from "@apollo/client";

export const BRANCH_DELETE = gql`
mutation BRANCH_DELETE($name: String) {
  BranchDelete (
    wait_until_completion: false
    data: {
      name: $name
    }
  ) {
      ok
  }
}
`;
