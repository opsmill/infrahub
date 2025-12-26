import { graphql, type VariablesOf } from "gql.tada";

import graphqlClient from "@/shared/api/graphql/graphqlClientApollo";

const TASKS_BRANCH_STATUS_COUNT = graphql(`
  query TASKS_BRANCH_STATUS_COUNT($branch: String!) {
    InfrahubTaskBranchStatus(branch: $branch) {
      count
    }
  }
`);

export const getBranchTaskStatusFromApi = (branch: string) => {
  return graphqlClient.query({
    query: TASKS_BRANCH_STATUS_COUNT,
    variables: { branch } satisfies VariablesOf<typeof TASKS_BRANCH_STATUS_COUNT>,
  });
};
