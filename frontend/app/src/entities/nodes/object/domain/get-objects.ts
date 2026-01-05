import { gql } from "@apollo/client";
import { jsonToGraphQLQuery } from "json-to-graphql-query";

import graphqlClient from "@/shared/api/graphql/graphqlClientApollo";
import {
  type AddAttributesToRequestOptions,
  addAttributesToRequest,
  addFiltersToRequest,
  addRelationshipsToRequest,
} from "@/shared/api/graphql/utils";
import type { ContextParams, PaginationParams } from "@/shared/api/types";
import type { Filter } from "@/shared/hooks/useFilters";

import { getAttributesVisibleInListView } from "@/entities/nodes/object/utils/get-attributes-visible-in-list-view";
import { getRelationshipsVisibleInListView } from "@/entities/nodes/object/utils/get-relationships-visible-in-list-view";
import type { NodeObject } from "@/entities/nodes/types";
import type { AttributeSchema, ModelSchema, RelationshipSchema } from "@/entities/schema/types";

////////////////////////////////////////////////////////////////////////////////////////////////////

export const OBJECTS_PER_PAGE = 40;

////////////////////////////////////////////////////////////////////////////////////////////////////

export type GetObjectsParams = ContextParams &
  PaginationParams & {
    schema: ModelSchema;
    filters?: Array<Filter>;
    getAttributesVisible?: (attributes: AttributeSchema[]) => AttributeSchema[];
    getRelationshipsVisible?: (relationships: RelationshipSchema[]) => RelationshipSchema[];
    attributesOptions?: AddAttributesToRequestOptions;
    relationshipsOptions?: AddAttributesToRequestOptions;
  };

export type GetObjects = (args: GetObjectsParams) => Promise<Array<NodeObject>>;

export const getObjects: GetObjects = async ({
  schema,
  limit = OBJECTS_PER_PAGE,
  offset,
  branchName,
  atDate,
  filters,
  getAttributesVisible = getAttributesVisibleInListView,
  getRelationshipsVisible = getRelationshipsVisibleInListView,
  attributesOptions,
  relationshipsOptions,
}) => {
  const attributesVisible = getAttributesVisible(schema.attributes ?? []);
  const relationshipsVisible = getRelationshipsVisible(schema.relationships ?? []);

  const schemaKind = schema.kind as string;

  const queryString = jsonToGraphQLQuery({
    query: {
      __name: `GetObjects${schemaKind}`,
      [schemaKind]: {
        __args: {
          limit,
          offset,
          ...(filters ? addFiltersToRequest(filters) : {}),
        },
        edges: {
          node: {
            id: true,
            display_label: true,
            hfid: true,
            ...addAttributesToRequest(attributesVisible, attributesOptions),
            ...addRelationshipsToRequest(relationshipsVisible, relationshipsOptions),
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

  return data[schemaKind]?.edges?.map((edge: any) => edge.node) ?? [];
};
