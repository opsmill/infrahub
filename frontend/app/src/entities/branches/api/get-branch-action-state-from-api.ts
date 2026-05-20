import { graphql } from "gql.tada";

import graphqlClient from "@/shared/api/graphql/graphqlClientApollo";

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
  state: ReadonlyArray<string>;
}

export function getBranchActionStateFromApi(params: GetBranchActionStateFromApiParams) {
  return graphqlClient.query({
    query: GET_BRANCH_ACTION_STATE,
    variables: {
      branch: params.branchName,
      workflow: [...params.workflow],
      state: [...params.state],
    },
    fetchPolicy: "no-cache",
  });
}
