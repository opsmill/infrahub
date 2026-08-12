import { graphql, graphqlClient } from "@/shared/api/graphql/client";
import type { StateType } from "@/shared/api/graphql/generated/types";

const GET_BRANCH_ACTION_STATE = graphql(`
  query GET_BRANCH_ACTION_STATE($branch: String!, $workflow: [String], $state: [StateType]) {
    InfrahubTask(branch: $branch, workflow: $workflow, state: $state) {
      count
    }
  }
`);

export interface GetBranchActionStateFromApiParams {
  branchName: string;
  workflow: ReadonlyArray<string>;
  state: ReadonlyArray<StateType>;
}

export function getBranchActionStateFromApi(params: GetBranchActionStateFromApiParams) {
  return graphqlClient.query({
    query: GET_BRANCH_ACTION_STATE,
    variables: {
      branch: params.branchName,
      workflow: [...params.workflow],
      state: [...params.state],
    },
  });
}
