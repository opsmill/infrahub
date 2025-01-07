import { gql } from "@apollo/client";

export const GET_BRANCH_MERGE_STATE = gql`
  query GET_BRANCH_MERGE_STATE($branch: String!, $workflow: [String]) {
    InfrahubTask(branch: $branch, workflow: $workflow) {
      count
    }
  }
`;
