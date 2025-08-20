import { gql } from "@apollo/client";

export const BRANCH_DELETE = gql`
mutation BRANCH_DELETE($name: String) {
  BranchDelete (
    data: {
      name: $name
    }
  ) {
      ok
  }
}
`;
