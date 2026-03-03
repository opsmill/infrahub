import { gql } from "@apollo/client";
import { VariableType, jsonToGraphQLQuery } from "json-to-graphql-query";

import { nodeCoreFragment } from "@/shared/api/graphql/fragments";
import graphqlClient from "@/shared/api/graphql/graphqlClientApollo";
import { addAttributesToRequest, addRelationshipsToRequest } from "@/shared/api/graphql/utils";
import type { ContextParams } from "@/shared/api/types";

import type { AttributeSchema, RelationshipSchema } from "@/entities/schema/types";

interface GetObjectQueryParams {
  schemaKind: string;
  attributes: AttributeSchema[];
  relationships: RelationshipSchema[];
  relationshipFragment?: Record<string, string>;
}

const getObjectQuery = ({
  schemaKind,
  attributes,
  relationships,
  relationshipFragment,
}: GetObjectQueryParams) => {
  return gql(
    jsonToGraphQLQuery({
      query: {
        __name: `GetObject${schemaKind}`,
        __variables: {
          ids: "[ID!]",
        },
        [schemaKind]: {
          __args: {
            ids: new VariableType("ids"),
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

export interface GetObjectFromApiParams extends ContextParams, GetObjectQueryParams {
  objectId: string;
}

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
      attributes,
      relationships,
      relationshipFragment,
    }),
    variables: {
      ids: [objectId],
    },
    context: {
      branch: branchName,
      date: atDate,
    },
  });
}
