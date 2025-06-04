import { getRelationshipsVisibleInDetailedView } from "@/entities/nodes/object/utils/get-relationships-visible-in-detailed-view";
import { NodeObject } from "@/entities/nodes/types";
import { AttributeSchema, ModelSchema, RelationshipSchema } from "@/entities/schema/types";
import graphqlClient from "@/shared/api/graphql/graphqlClientApollo";
import { addAttributesToRequest, addRelationshipsToRequest } from "@/shared/api/graphql/utils";
import { ContextParams } from "@/shared/api/types";
import { gql } from "@apollo/client";
import { jsonToGraphQLQuery } from "json-to-graphql-query";

export type GetObjectParams = ContextParams & {
  objectSchema: ModelSchema;
  objectId: string;
  getAttributesVisible?: (attributes: AttributeSchema[]) => AttributeSchema[];
  getRelationshipsVisible?: (relationships: RelationshipSchema[]) => RelationshipSchema[];
};

export type GetObject = (params: GetObjectParams) => Promise<NodeObject>;

export const getObject: GetObject = async ({
  branchName,
  atDate,
  objectSchema,
  objectId,
  getAttributesVisible = (attributes) => attributes, // all attributes are visible by default on detailed view
  getRelationshipsVisible = getRelationshipsVisibleInDetailedView,
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
            ...addRelationshipsToRequest(relationshipsVisible, { withMetadata: true }),
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
