import graphqlClient from "@/shared/api/graphql/graphqlClientApollo";
import { BranchContextParams } from "@/shared/api/types";
import { gql } from "@apollo/client";

const REPOSITORY_OBJECTS_COUNT = gql`
query REPOSITORY_OBJECTS_COUNT($nodeIds: [ID]){
  CoreRepositoryGroup(repository__ids: $nodeIds){
    count
  }
}
`;

export interface GetTaskCountFromApiParams extends BranchContextParams {
  nodeIds: Array<string>;
}

export function getRepositoryObjectsCountFromApi({
  nodeIds,
  branchName,
}: GetTaskCountFromApiParams) {
  return graphqlClient.query({
    query: REPOSITORY_OBJECTS_COUNT,
    variables: {
      nodeIds,
    },
    context: {
      branch: branchName,
    },
  });
}
