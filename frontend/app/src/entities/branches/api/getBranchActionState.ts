import { graphql } from "gql.tada";

export const GET_BRANCH_ACTION_STATE = graphql(`
  query GET_BRANCH_ACTION_STATE($branch: String!, $workflow: [String], $state: [StateType]) {
    InfrahubTask(branch: $branch, workflow: $workflow, state: $state) {
      count
    }
  }
`);
