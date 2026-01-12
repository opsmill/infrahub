import { graphql } from "gql.tada";

export const BRANCH_VALIDATE = graphql(`
  mutation BRANCH_VALIDATE($name: String) {
    BranchValidate(wait_until_completion: false, data: { name: $name }) {
      ok
      task {
        id
      }
    }
  }
`);
