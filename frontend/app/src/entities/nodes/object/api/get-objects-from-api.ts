import { jsonToGraphQLQuery } from "json-to-graphql-query";

import { graphql, graphqlClient } from "@/shared/api/graphql/client";
import { nodeCoreFragment } from "@/shared/api/graphql/fragments";
import {
  type AddAttributesToRequestOptions,
  addAttributesToRequest,
  addFiltersToRequest,
  addOrderByToRequest,
  addRelationshipsToRequest,
} from "@/shared/api/graphql/utils";
import type { ContextParams, PaginationParams } from "@/shared/api/types";

import type { Filter } from "@/entities/nodes/filters/domain/model/filter";
import type { Sort } from "@/entities/nodes/sort/domain/model/sort";
import type { AttributeSchema, RelationshipSchema } from "@/entities/schema/domain/model/schema";

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
  return graphql(
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
