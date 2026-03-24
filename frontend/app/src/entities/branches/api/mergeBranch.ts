import { graphql } from "gql.tada";

export const BRANCH_MERGE = graphql(`
  mutation BRANCH_MERGE($name: String) {
    BranchMerge(wait_until_completion: false, data: { name: $name }) {
      ok
      task {
        id
      }
    }
  }
`);
