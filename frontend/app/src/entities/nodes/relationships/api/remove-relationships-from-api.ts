import { graphql, type VariablesOf } from "gql.tada";

import graphqlClient from "@/shared/api/graphql/graphqlClientApollo";
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

type MutationVariables = VariablesOf<typeof REMOVE_RELATIONSHIP>;

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
    } satisfies MutationVariables,
    context: { branch: branchName },
  });
};
