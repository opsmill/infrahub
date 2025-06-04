import { getAttributesVisibleInListView } from "@/entities/nodes/object/utils/get-attributes-visible-in-list-view";
import { getRelationshipsVisibleInListView } from "@/entities/nodes/object/utils/get-relationships-visible-in-list-view";
import { NodeObject } from "@/entities/nodes/types";
import { AttributeSchema, ModelSchema, RelationshipSchema } from "@/entities/schema/types";
import graphqlClient from "@/shared/api/graphql/graphqlClientApollo";
import {
  addAttributesToRequest,
  addFiltersToRequest,
  addRelationshipsToRequest,
} from "@/shared/api/graphql/utils";
import { ContextParams, PaginationParams } from "@/shared/api/types";
import { Filter } from "@/shared/hooks/useFilters";
import { gql } from "@apollo/client";
import { jsonToGraphQLQuery } from "json-to-graphql-query";

////////////////////////////////////////////////////////////////////////////////////////////////////

export const OBJECTS_PER_PAGE = 40;

////////////////////////////////////////////////////////////////////////////////////////////////////

export type GetObjectsParams = ContextParams &
  PaginationParams & {
    schema: ModelSchema;
    filters?: Array<Filter>;
    getAttributesVisible?: (attributes: AttributeSchema[]) => AttributeSchema[];
    getRelationshipsVisible?: (relationships: RelationshipSchema[]) => RelationshipSchema[];
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
}) => {
  const attributesVisible = getAttributesVisible(schema.attributes ?? []);
  const relationshipsVisible = getRelationshipsVisible(schema.relationships ?? []);

  const schemaKind = schema.kind as string;
  const kindFilter = filters?.find((filter) => filter.name === "kind__value");
  const schemaKindToQuery: string = kindFilter?.value ?? schemaKind;

  const queryString = jsonToGraphQLQuery({
    query: {
      __name: `GetObjects${schemaKind}`,
      [schemaKindToQuery]: {
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
            ...addAttributesToRequest(attributesVisible),
            ...addRelationshipsToRequest(relationshipsVisible),
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

  return data[schemaKindToQuery]?.edges?.map((edge: any) => edge.node) ?? [];
};
