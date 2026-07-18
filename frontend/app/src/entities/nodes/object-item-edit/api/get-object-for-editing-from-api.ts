import { gql } from "@apollo/client";

import graphqlClient from "@/shared/api/graphql/graphqlClientApollo";
import type { ContextParams } from "@/shared/api/types";

import { generateObjectEditFormQuery } from "@/entities/nodes/object-item-edit/generateObjectEditFormQuery";
import type { NodeSchema, ProfileSchema } from "@/entities/schema/types";

export interface GetObjectForEditingFromApiParams extends ContextParams {
  schema: NodeSchema | ProfileSchema;
  objectId: string;
  extraRelationshipNames?: string[];
}

export async function getObjectForEditingFromApi({
  schema,
  objectId,
  extraRelationshipNames,
  branchName,
  atDate,
}: GetObjectForEditingFromApiParams) {
  const queryString = generateObjectEditFormQuery({ schema, objectId, extraRelationshipNames });

  return graphqlClient.query({
    query: gql(queryString),
    context: {
      branch: branchName,
      date: atDate,
    },
    fetchPolicy: "no-cache",
  });
}
