import { graphql, type VariablesOf } from "gql.tada";

import graphqlClient from "@/shared/api/graphql/graphqlClientApollo";
import type { BranchContextParams } from "@/shared/api/types";

const generatorRunMutation = graphql(`
  mutation CoreGeneratorDefinitionRun($generatorId: String!, $waitUntilCompletion: Boolean, $targetNodeIds: [String!]) {
    CoreGeneratorDefinitionRun(
      wait_until_completion: $waitUntilCompletion
      data: { id: $generatorId, nodes: $targetNodeIds }
    ) {
      task {
        id
      }
    }
  }
`);

export interface RunGeneratorFromApiParams
  extends BranchContextParams,
    VariablesOf<typeof generatorRunMutation> {}

export const runGeneratorFromApi = async ({
  branchName,
  generatorId,
  targetNodeIds,
  waitUntilCompletion = false,
}: RunGeneratorFromApiParams) => {
  return graphqlClient.mutate({
    mutation: generatorRunMutation,
    variables: {
      generatorId,
      targetNodeIds,
      waitUntilCompletion,
    },
    context: {
      branch: branchName,
    },
  });
};
