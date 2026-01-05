import { gql } from "@apollo/client";

import graphqlClient from "@/shared/api/graphql/graphqlClientApollo";
import type { BranchContextParams } from "@/shared/api/types";

const REPOSITORY_GROUP = gql`
query REPOSITORY_GROUP($nodeIds: [ID]){
  CoreRepositoryGroup(repository__ids: $nodeIds){
    edges{
      node{
        id
      }
    }
  }
}
`;

export interface GetRepositoryGroupFromApiParams extends BranchContextParams {
  nodeIds: Array<string>;
}

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
