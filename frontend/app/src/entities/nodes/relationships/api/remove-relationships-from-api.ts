import { graphql, graphqlClient, type VariablesOf } from "@/shared/api/graphql/client";
import type { BranchContextParams } from "@/shared/api/types";

const REMOVE_RELATIONSHIP = graphql(`
  mutation RelationshipRemove(
    $objectId: String!
    $relationshipName: String!
    $relationshipIds: [RelatedNodeInput]
  ) {
    RelationshipRemove(data: { id: $objectId, name: $relationshipName, nodes: $relationshipIds }) {
      ok
    }
  }
`);

export interface RemoveRelationshipFromApiParams
  extends BranchContextParams,
    VariablesOf<typeof REMOVE_RELATIONSHIP> {}

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
