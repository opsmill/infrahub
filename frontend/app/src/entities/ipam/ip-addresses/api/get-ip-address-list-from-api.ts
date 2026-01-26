import { gql } from "@apollo/client";
import { jsonToGraphQLQuery } from "json-to-graphql-query";

import graphqlClient from "@/shared/api/graphql/graphqlClientApollo";
import {
  addAttributesToRequest,
  addFiltersToRequest,
  addRelationshipsToRequest,
  dropIncludeAvailableWhenFalse,
} from "@/shared/api/graphql/utils";
import type { ContextParams, PaginationParams } from "@/shared/api/types";
import type { Filter } from "@/shared/hooks/useFilters";

import { IP_ADDRESS_AVAILABLE_KIND, IP_ADDRESS_GENERIC } from "@/entities/ipam/constants";
import type { AttributeSchema, RelationshipSchema } from "@/entities/schema/types";

export interface GetIpAddressListGraphQLQueryParams extends PaginationParams {
  filters?: Array<Filter>;
  objectKind: string;
  attributes: Array<AttributeSchema>;
  relationships: Array<RelationshipSchema>;
}

export function getIpAddressListWithAvailabilityGraphQLQuery({
  limit,
  offset,
  filters,
  objectKind,
  attributes,
  relationships,
}: GetIpAddressListGraphQLQueryParams) {
  return jsonToGraphQLQuery({
    query: {
      __name: `GetObjects${objectKind}`,
      [IP_ADDRESS_GENERIC]: {
        __args: {
          limit,
          offset,
          include_available: true,
          ...(objectKind !== IP_ADDRESS_GENERIC ? { kinds: [objectKind] } : {}),
          ...(filters ? addFiltersToRequest(filters) : {}),
        },
        count: true,
        edges: {
          node: {
            id: true,
            display_label: true,
            hfid: true,
            __on: [
              {
                __typeName: objectKind,
                ...addAttributesToRequest(attributes),
                ...addRelationshipsToRequest(relationships),
                ip_namespace: {
                  node: {
                    id: true,
                    display_label: true,
                    hfid: true,
                  },
                },
              },
              {
                __typeName: IP_ADDRESS_AVAILABLE_KIND,
                address: { value: true },
                last_address: { value: true },
              },
            ],
          },
        },
      },
    },
  });
}

export function getIpAddressListWithoutAvailabilityGraphQLQuery({
  limit,
  offset,
  filters,
  objectKind,
  attributes,
  relationships,
}: GetIpAddressListGraphQLQueryParams) {
  const cleanedFilters = dropIncludeAvailableWhenFalse(filters);

  return jsonToGraphQLQuery({
    query: {
      __name: `GetObjects${objectKind}`,
      [objectKind]: {
        __args: {
          limit,
          offset,
          ...(cleanedFilters?.length ? addFiltersToRequest(cleanedFilters) : {}),
        },
        count: true,
        edges: {
          node: {
            id: true,
            display_label: true,
            hfid: true,
            ...addAttributesToRequest(attributes),
            ...addRelationshipsToRequest(relationships),
          },
        },
      },
    },
  });
}

export interface getIpAddressListFromApiParams
  extends ContextParams,
    GetIpAddressListGraphQLQueryParams {}

export function getIpAddressListWithAvailabilityFromApi({
  branchName,
  atDate,
  ...params
}: getIpAddressListFromApiParams) {
  const graphqlQuery = getIpAddressListWithAvailabilityGraphQLQuery(params);

  return graphqlClient.query({
    query: gql(graphqlQuery),
    context: {
      branch: branchName,
      date: atDate,
    },
  });
}

export function getIpAddressListWithoutAvailabilityFromApi({
  branchName,
  atDate,
  ...params
}: getIpAddressListFromApiParams) {
  const graphqlQuery = getIpAddressListWithoutAvailabilityGraphQLQuery(params);

  return graphqlClient.query({
    query: gql(graphqlQuery),
    context: {
      branch: branchName,
      date: atDate,
    },
  });
}
