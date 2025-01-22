import { getAttributesVisibleInListView } from "@/entities/nodes/object/utils/get-attributes-visible-in-list";
import { getRelationshipsVisibleInListView } from "@/entities/nodes/object/utils/get-relationships-visible-in-list";
import { IModelSchema } from "@/entities/schema/stores/schema.atom";
import graphqlClient from "@/shared/api/graphql/graphqlClientApollo";
import { addAttributesToRequest, addRelationshipsToRequest } from "@/shared/api/graphql/utils";
import { gql } from "@apollo/client";
import { jsonToGraphQLQuery } from "json-to-graphql-query";

////////////////////////////////////////////////////////////////////////////////////////////////////

export const OBJECTS_PER_PAGE = 20;

////////////////////////////////////////////////////////////////////////////////////////////////////

export type GetObjects = ({ schema, offset }: { schema: IModelSchema; offset?: number }) => Promise<any>;

export const getObjects: GetObjects = async ({ schema, offset }) => {
  const attributesVisible = getAttributesVisibleInListView(schema.attributes ?? []);
  const relationshipsVisible = getRelationshipsVisibleInListView(schema.relationships ?? []);
  const schemaKind = schema.kind as string;
  const queryString = jsonToGraphQLQuery({
    query: {
      __name: `GetObjects${schemaKind}`,
      [schemaKind]: {
        __args: {
          limit: OBJECTS_PER_PAGE,
          offset,
        },
        edges: {
          node: {
            id: true,
            display_label: true,
            ...addAttributesToRequest(attributesVisible),
            ...addRelationshipsToRequest(relationshipsVisible),
          },
        },
      },
    },
  });

  const query = gql(queryString);
  const { data } = await graphqlClient.query({ query });

  return data[schemaKind]?.edges?.map((edge: any) => edge.node) ?? [];
};
