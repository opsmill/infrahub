import { gql } from "@apollo/client";
import { jsonToGraphQLQuery } from "json-to-graphql-query";

import graphqlClient from "@/shared/api/graphql/graphqlClientApollo";
import { addAttributesToRequest, addRelationshipsToRequest } from "@/shared/api/graphql/utils";
import type { ContextParams } from "@/shared/api/types";

import type { AttributeSchema, RelationshipSchema } from "@/entities/schema/types";

export interface GetObjectFromApiParams extends ContextParams {
  schemaKind: string;
  objectId: string;
  attributes: AttributeSchema[];
  relationships: RelationshipSchema[];
  relationshipFragment?: Record<string, string>;
}

export const getObjectFromApi = async ({
  schemaKind,
  objectId,
  attributes,
  relationships,
  relationshipFragment,
  branchName,
  atDate,
}: GetObjectFromApiParams) => {
  const queryString = jsonToGraphQLQuery({
    query: {
      __name: `GetObject${schemaKind}`,
      [schemaKind]: {
        __args: {
          ids: [objectId],
        },
        edges: {
          node: {
            id: true,
            display_label: true,
            hfid: true,
            ...addAttributesToRequest(attributes, { withMetadata: true }),
            ...addRelationshipsToRequest(relationships, {
              relationshipFragment,
              withMetadata: true,
            }),
          },
        },
      },
    },
  });

  const query = gql(queryString);
  return graphqlClient.query({
    query,
    context: {
      branch: branchName,
      date: atDate,
    },
  });
};
