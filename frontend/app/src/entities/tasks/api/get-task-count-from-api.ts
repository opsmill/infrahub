import { graphql, type VariablesOf } from "gql.tada";

import graphqlClient from "@/shared/api/graphql/graphqlClientApollo";
import type { BranchContextParams } from "@/shared/api/types";

const TASK_COUNT = graphql(`
  query TASK_COUNT($nodeIds: [String]) {
    InfrahubTask(related_node__ids: $nodeIds) {
      count
      __typename
    }
  }
`);

export interface GetTaskCountFromApiParams
  extends BranchContextParams,
    VariablesOf<typeof TASK_COUNT> {}

export function getTaskCountFromApi({ nodeIds, branchName }: GetTaskCountFromApiParams) {
  return graphqlClient.query({
    query: TASK_COUNT,
    variables: {
      nodeIds,
    },
    context: {
      branch: branchName,
    },
  });
}
