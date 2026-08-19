import { graphql, graphqlClient, type VariablesOf } from "@/shared/api/graphql/client";
import type { BranchContextParams } from "@/shared/api/types";

const REPOSITORY_GROUP = graphql(`
  query REPOSITORY_GROUP($nodeIds: [ID]) {
    CoreRepositoryGroup(repository__ids: $nodeIds) {
      edges {
        node {
          id
        }
      }
    }
  }
`);

export interface GetRepositoryGroupFromApiParams
  extends BranchContextParams,
    VariablesOf<typeof REPOSITORY_GROUP> {}

export function getRepositoryGroupFromApi({
  nodeIds,
  branchName,
}: GetRepositoryGroupFromApiParams) {
  return graphqlClient.query({
    query: REPOSITORY_GROUP,
    variables: {
      nodeIds,
    },
    context: {
      branch: branchName,
    },
  });
}
