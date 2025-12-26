import { graphql, type VariablesOf } from "gql.tada";

import graphqlClient from "@/shared/api/graphql/graphqlClientApollo";
import type { BranchContextParams } from "@/shared/api/types";

const ADD_RELATIONSHIP = graphql(`
  mutation RelationshipAdd(
    $objectId: String!
    $relationshipName: String!
    $relationshipIds: [RelatedNodeInput]
  ) {
    RelationshipAdd(data: { id: $objectId, name: $relationshipName, nodes: $relationshipIds }) {
      ok
    }
  }
`);

export interface AddRelationshipsToApiParams
  extends BranchContextParams,
    VariablesOf<typeof ADD_RELATIONSHIP> {}

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
