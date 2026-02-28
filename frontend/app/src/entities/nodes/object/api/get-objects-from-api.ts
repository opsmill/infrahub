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

import type { AttributeSchema, RelationshipSchema } from "@/entities/schema/types";

export interface GetObjectsFromApiParams extends ContextParams, PaginationParams {
  schemaKind: string;
  attributes: AttributeSchema[];
  relationships: RelationshipSchema[];
  filters?: Array<Filter>;
  attributesOptions?: AddAttributesToRequestOptions;
  relationshipsOptions?: AddAttributesToRequestOptions;
}

export const getObjectsFromApi = async ({
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
}: GetObjectsFromApiParams) => {
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
            ...addAttributesToRequest(attributes, attributesOptions),
            ...addRelationshipsToRequest(relationships, relationshipsOptions),
          },
        },
      },
    },
  });

  const query = gql(queryString);
  return graphqlClient.query({
    query,
    context: {
      branch: branchName,
      date: atDate,
    },
  });
};
