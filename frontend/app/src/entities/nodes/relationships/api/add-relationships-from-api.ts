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

type MutationVariables = VariablesOf<typeof ADD_RELATIONSHIP>;

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
    } satisfies MutationVariables,
    context: {
      branch: branchName,
    },
  });
};
