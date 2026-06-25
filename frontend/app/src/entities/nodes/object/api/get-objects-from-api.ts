import { gql } from "@apollo/client";
import { jsonToGraphQLQuery } from "json-to-graphql-query";

import { nodeCoreFragment } from "@/shared/api/graphql/fragments";
import graphqlClient from "@/shared/api/graphql/graphqlClientApollo";
import {
  type AddAttributesToRequestOptions,
  addAttributesToRequest,
  addFiltersToRequest,
  addOrderByToRequest,
  addRelationshipsToRequest,
} from "@/shared/api/graphql/utils";
import type { ContextParams, PaginationParams } from "@/shared/api/types";
import type { Filter } from "@/shared/hooks/useFilters";

import type { Sort } from "@/entities/nodes/object/domain/sort";
import type { AttributeSchema, RelationshipSchema } from "@/entities/schema/types";

interface GetObjectsQueryParams {
  schemaKind: string;
  attributes: AttributeSchema[];
  relationships: RelationshipSchema[];
  limit?: number;
  offset?: number;
  filters?: Array<Filter>;
  sort?: Sort[] | null;
  attributesOptions?: AddAttributesToRequestOptions;
  relationshipsOptions?: AddAttributesToRequestOptions;
}

const getObjectsQuery = ({
  schemaKind,
  attributes,
  relationships,
  limit,
  offset,
  filters,
  sort,
  attributesOptions,
  relationshipsOptions,
}: GetObjectsQueryParams) => {
  return gql(
    jsonToGraphQLQuery({
      query: {
        __name: `GetObjects${schemaKind}`,
        [schemaKind]: {
          __args: {
            limit,
            offset,
            ...(filters?.length ? addFiltersToRequest(filters) : {}),
            ...(sort?.length ? addOrderByToRequest(sort) : {}),
          },
          edges: {
            node: {
              ...nodeCoreFragment,
              ...addAttributesToRequest(attributes, attributesOptions),
              ...addRelationshipsToRequest(relationships, relationshipsOptions),
            },
          },
        },
      },
    })
  );
};

export interface GetObjectsFromApiParams
  extends ContextParams,
    PaginationParams,
    GetObjectsQueryParams {}

export async function getObjectsFromApi({
  schemaKind,
  attributes,
  relationships,
  limit,
  offset,
  branchName,
  atDate,
  filters,
  sort,
  attributesOptions,
  relationshipsOptions,
}: GetObjectsFromApiParams) {
  return graphqlClient.query({
    query: getObjectsQuery({
      schemaKind,
      attributes,
      relationships,
      limit,
      offset,
      filters,
      sort,
      attributesOptions,
      relationshipsOptions,
    }),
    context: {
      branch: branchName,
      date: atDate,
    },
  });
}
