import { graphql, type VariablesOf } from "gql.tada";

import graphqlClient from "@/shared/api/graphql/graphqlClientApollo";
import type { ContextParams } from "@/shared/api/types";

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

export type RunGeneratorFromApiParams = Pick<ContextParams, "branchName"> & {
  generatorId: string;
  targetNodeIds?: string[];
  waitUntilCompletion?: boolean;
};

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
    } satisfies VariablesOf<typeof generatorRunMutation>,
    context: {
      branch: branchName,
    },
  });
};
