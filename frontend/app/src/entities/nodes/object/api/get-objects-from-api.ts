import { gql } from "@apollo/client";
import { VariableType, jsonToGraphQLQuery } from "json-to-graphql-query";

import { nodeCoreFragment } from "@/shared/api/graphql/fragments";
import graphqlClient from "@/shared/api/graphql/graphqlClientApollo";
import {
  type AddAttributesToRequestOptions,
  addAttributesToRequest,
  addFiltersToRequest,
  addRelationshipsToRequest,
} from "@/shared/api/graphql/utils";
import type { ContextParams, PaginationParams } from "@/shared/api/types";
import type { Filter } from "@/shared/hooks/useFilters";

import type { AttributeSchema, RelationshipSchema } from "@/entities/schema/types";

interface GetObjectsQueryParams {
  schemaKind: string;
  attributes: AttributeSchema[];
  relationships: RelationshipSchema[];
  filters?: Array<Filter>;
  attributesOptions?: AddAttributesToRequestOptions;
  relationshipsOptions?: AddAttributesToRequestOptions;
}

const getObjectsQuery = ({
  schemaKind,
  attributes,
  relationships,
  filters,
  attributesOptions,
  relationshipsOptions,
}: GetObjectsQueryParams) => {
  return gql(
    jsonToGraphQLQuery({
      query: {
        __name: `GetObjects${schemaKind}`,
        __variables: {
          limit: "Int",
          offset: "Int",
        },
        [schemaKind]: {
          __args: {
            limit: new VariableType("limit"),
            offset: new VariableType("offset"),
            ...(filters ? addFiltersToRequest(filters) : {}),
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
  attributesOptions,
  relationshipsOptions,
}: GetObjectsFromApiParams) {
  return graphqlClient.query({
    query: getObjectsQuery({
      schemaKind,
      attributes,
      relationships,
      filters,
      attributesOptions,
      relationshipsOptions,
    }),
    variables: {
      limit,
      offset,
    },
    context: {
      branch: branchName,
      date: atDate,
    },
  });
}
