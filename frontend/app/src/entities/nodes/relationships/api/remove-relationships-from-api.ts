import graphqlClient from "@/shared/api/graphql/graphqlClientApollo";
import { BranchContextParams } from "@/shared/api/types";
import { gql } from "@apollo/client";

export const REMOVE_RELATIONSHIP = gql`
  mutation RelationshipRemove(
    $objectId: String!
    $relationshipName: String!
    $relationshipIds: [RelatedNodeInput]
  ) {
    RelationshipRemove(data: { id: $objectId, name: $relationshipName, nodes: $relationshipIds }) {
      ok
    }
  }
`;

export type RemoveRelationshipFromApiParams = BranchContextParams & {
  objectId: string;
  relationshipName: string;
  relationshipIds: Array<{ id: string }>;
};

export const removeRelationshipsFromApi = ({
  objectId,
  relationshipName,
  relationshipIds,
  branchName,
}: RemoveRelationshipFromApiParams) => {
  return graphqlClient.mutate({
    mutation: REMOVE_RELATIONSHIP,
    variables: {
      objectId,
      relationshipName,
      relationshipIds,
    },
    context: { branch: branchName },
  });
};
