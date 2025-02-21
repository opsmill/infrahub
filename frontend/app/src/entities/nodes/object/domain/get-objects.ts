import { getAttributesVisibleInListView } from "@/entities/nodes/object/utils/get-attributes-visible-in-list";
import { getRelationshipsVisibleInListView } from "@/entities/nodes/object/utils/get-relationships-visible-in-list";
import { NodeObject } from "@/entities/nodes/types";
import { ModelSchema } from "@/entities/schema/types";
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

export type GetObjects = (
  args: ContextParams &
    PaginationParams & {
      schema: ModelSchema;
      filters?: Array<Filter>;
    }
) => Promise<Array<NodeObject>>;

export const getObjects: GetObjects = async ({
  schema,
  limit = OBJECTS_PER_PAGE,
  offset,
  branchName,
  atDate,
  filters,
}) => {
  const attributesVisible = getAttributesVisibleInListView(schema.attributes ?? []);
  const relationshipsVisible = getRelationshipsVisibleInListView(schema.relationships ?? []);

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
