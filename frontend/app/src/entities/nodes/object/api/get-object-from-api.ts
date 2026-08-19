import { jsonToGraphQLQuery } from "json-to-graphql-query";

import { graphql, graphqlClient } from "@/shared/api/graphql/client";
import { nodeCoreFragment } from "@/shared/api/graphql/fragments";
import { addAttributesToRequest, addRelationshipsToRequest } from "@/shared/api/graphql/utils";
import type { ContextParams } from "@/shared/api/types";

import type { AttributeSchema, RelationshipSchema } from "@/entities/schema/domain/model/schema";

interface GetObjectQueryParams {
  schemaKind: string;
  objectId: string;
  attributes: AttributeSchema[];
  relationships: RelationshipSchema[];
  relationshipFragment?: Record<string, string>;
}

const getObjectQuery = ({
  schemaKind,
  objectId,
  attributes,
  relationships,
  relationshipFragment,
}: GetObjectQueryParams) => {
  return graphql(
    jsonToGraphQLQuery({
      query: {
        __name: `GetObject${schemaKind}`,
        [schemaKind]: {
          __args: {
            ids: [objectId],
          },
          edges: {
            node: {
              ...nodeCoreFragment,
              ...addAttributesToRequest(attributes, { withMetadata: true }),
              ...addRelationshipsToRequest(relationships, {
                relationshipFragment,
                withMetadata: true,
              }),
            },
          },
        },
      },
    })
  );
};

export interface GetObjectFromApiParams extends ContextParams, GetObjectQueryParams {}

export async function getObjectFromApi({
  schemaKind,
  objectId,
  attributes,
  relationships,
  relationshipFragment,
  branchName,
  atDate,
}: GetObjectFromApiParams) {
  return graphqlClient.query({
    query: getObjectQuery({
      schemaKind,
      objectId,
      attributes,
      relationships,
      relationshipFragment,
    }),
    context: {
      branch: branchName,
      date: atDate,
    },
  });
}
