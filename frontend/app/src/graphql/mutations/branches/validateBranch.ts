import { gql } from "@apollo/client";

export const BRANCH_VALIDATE = gql`
mutation BRANCH_VALIDATE($name: String) {
  BranchValidate (
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
