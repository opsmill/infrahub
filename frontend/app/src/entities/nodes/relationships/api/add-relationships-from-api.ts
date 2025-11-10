import { gql } from "@apollo/client";

import graphqlClient from "@/shared/api/graphql/graphqlClientApollo";
import type { BranchContextParams } from "@/shared/api/types";

export const ADD_RELATIONSHIP = gql`
  mutation RelationshipAdd(
    $objectId: String!
    $relationshipName: String!
    $relationshipIds: [RelatedNodeInput]
  ) {
    RelationshipAdd(data: { id: $objectId, name: $relationshipName, nodes: $relationshipIds }) {
      ok
    }
  }
`;

export type AddRelationshipsToApiParams = BranchContextParams & {
  objectId: string;
  relationshipName: string;
  relationshipIds: Array<{ id: string }>;
};

export const addRelationshipsToApi = async ({
  objectId,
  relationshipName,
  relationshipIds,
  branchName,
}: AddRelationshipsToApiParams) => {
  return graphqlClient.mutate({
    mutation: ADD_RELATIONSHIP,
    variables: {
      objectId,
      relationshipName,
      relationshipIds,
    },
    context: {
      branch: branchName,
    },
  });
};
