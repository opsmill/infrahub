import { gql } from "@apollo/client";
import { jsonToGraphQLQuery } from "json-to-graphql-query";

import { nodeCoreFragment } from "@/shared/api/graphql/fragments";
import graphqlClient from "@/shared/api/graphql/graphqlClientApollo";
import { addAttributesToRequest, addRelationshipsToRequest } from "@/shared/api/graphql/utils";
import type { ContextParams } from "@/shared/api/types";

import type { AttributeSchema, RelationshipSchema } from "@/entities/schema/types";

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
  return gql(
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
