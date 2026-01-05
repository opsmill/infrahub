import { gql } from "@apollo/client";
import { jsonToGraphQLQuery } from "json-to-graphql-query";

import graphqlClient from "@/shared/api/graphql/graphqlClientApollo";
import { addAttributesToRequest, addRelationshipsToRequest } from "@/shared/api/graphql/utils";
import type { ContextParams } from "@/shared/api/types";

import { getAttributesVisibleInDetailedView } from "@/entities/nodes/object/utils/get-attributes-visible-in-detailed-view";
import { getRelationshipsVisibleInDetailedView } from "@/entities/nodes/object/utils/get-relationships-visible-in-detailed-view";
import type { NodeObject } from "@/entities/nodes/types";
import type { AttributeSchema, ModelSchema, RelationshipSchema } from "@/entities/schema/types";

export interface GetObjectParams extends ContextParams {
  objectSchema: ModelSchema;
  objectId: string;
  getAttributesVisible?: (attributes: AttributeSchema[]) => AttributeSchema[];
  getRelationshipsVisible?: (relationships: RelationshipSchema[]) => RelationshipSchema[];
  relationshipFragment?: Record<string, string>;
}

export type GetObject = (params: GetObjectParams) => Promise<NodeObject>;

export const getObject: GetObject = async ({
  branchName,
  atDate,
  objectSchema,
  objectId,
  getAttributesVisible = getAttributesVisibleInDetailedView,
  getRelationshipsVisible = getRelationshipsVisibleInDetailedView,
  relationshipFragment,
}) => {
  const attributesVisible = getAttributesVisible(objectSchema.attributes ?? []);
  const relationshipsVisible = getRelationshipsVisible(objectSchema.relationships ?? []);

  const schemaKind = objectSchema.kind as string;

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
            ...addAttributesToRequest(attributesVisible, { withMetadata: true }),
            ...addRelationshipsToRequest(relationshipsVisible, {
              relationshipFragment,
              withMetadata: true,
            }),
          },
        },
      },
    },
  });

  const query = gql(queryString);
  const { data } = await graphqlClient.query({
    query,
    context: {
      branch: branchName,
      date: atDate,
    },
  });

  const result = data[schemaKind]?.edges?.map((edge: { node: NodeObject }) => edge.node) ?? [];

  if (!result || result.length === 0) {
    throw new Error(`Cannot find ${objectSchema.label} with id ${objectId}`);
  }

  return result[0];
};
