import { gql } from "@apollo/client";

export const GET_BRANCH_ACTION_STATE = gql`
  query GET_BRANCH_ACTION_STATE($branch: String!, $workflow: [String], $state: [StateType]) {
    InfrahubTask(branch: $branch, workflow: $workflow, state: $state) {
      count
    }
  }
`;
