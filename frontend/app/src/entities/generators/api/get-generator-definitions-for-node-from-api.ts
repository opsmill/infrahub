import { graphql, graphqlClient, type VariablesOf } from "@/shared/api/graphql/client";
import type { ContextParams } from "@/shared/api/types";

const GET_GENERATOR_DEFINITIONS_FOR_NODE = graphql(`
  query GetGeneratorDefinitionsForNode($nodeId: ID!) {
    CoreGeneratorDefinition {
      edges {
        node {
          id
          display_label
          targets {
            node {
              id
              display_label
              members(ids: [$nodeId]) {
                count
              }
            }
          }
        }
      }
    }
  }
`);

export interface GetGeneratorDefinitionsForNodeFromApiParams
  extends ContextParams,
    VariablesOf<typeof GET_GENERATOR_DEFINITIONS_FOR_NODE> {}

export const getGeneratorDefinitionsForNodeFromApi = async ({
  nodeId,
  branchName,
  atDate,
}: GetGeneratorDefinitionsForNodeFromApiParams) => {
  return graphqlClient.query({
    query: GET_GENERATOR_DEFINITIONS_FOR_NODE,
    variables: { nodeId },
    context: {
      branch: branchName,
      date: atDate,
      // A failed read only means no generator can be offered, which is not worth an error toast.
      processErrorMessage: () => {},
    },
  });
};
