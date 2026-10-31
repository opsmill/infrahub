import { jsonToGraphQLQuery, VariableType } from "json-to-graphql-query";

import { graphql, graphqlClient } from "@/shared/api/graphql/client";
import {
  addAttributesToRequest,
  addFiltersToRequest,
  addOrderByToRequest,
  addRelationshipsToRequest,
  dropIncludeAvailableWhenFalse,
} from "@/shared/api/graphql/utils";
import type { ContextParams, PaginationParams } from "@/shared/api/types";

import {
  IP_ADDRESS_AVAILABLE_KIND,
  IP_ADDRESS_GENERIC,
} from "@/entities/ipam/ip-addresses/domain/model/ip-address";
import type { Filter } from "@/entities/nodes/filters/domain/model/filter";
import type { Sort } from "@/entities/nodes/sort/domain/model/sort";
import type { AttributeSchema, RelationshipSchema } from "@/entities/schema/domain/model/schema";

export interface GetIpAddressListGraphQLQueryParams extends PaginationParams {
  filters?: Array<Filter>;
  sort?: Sort[] | null;
  objectKind: string;
  attributes: Array<AttributeSchema>;
  relationships: Array<RelationshipSchema>;
}

export function getIpAddressListWithAvailabilityGraphQLQuery({
  filters,
  sort,
  objectKind,
  attributes,
  relationships,
}: Omit<GetIpAddressListGraphQLQueryParams, "limit" | "offset">) {
  return jsonToGraphQLQuery({
    query: {
      __name: `GetObjects${objectKind}`,
      __variables: {
        limit: "Int",
        offset: "Int",
      },
      [IP_ADDRESS_GENERIC]: {
        __args: {
          limit: new VariableType("limit"),
          offset: new VariableType("offset"),
          include_available: true,
          ...(objectKind !== IP_ADDRESS_GENERIC ? { kinds: [objectKind] } : {}),
          ...(filters ? addFiltersToRequest(filters) : {}),
          ...(sort?.length ? addOrderByToRequest(sort) : {}),
        },
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
  filters,
  sort,
  objectKind,
  attributes,
  relationships,
}: Omit<GetIpAddressListGraphQLQueryParams, "limit" | "offset">) {
  const cleanedFilters = dropIncludeAvailableWhenFalse(filters);

  return jsonToGraphQLQuery({
    query: {
      __name: `GetObjects${objectKind}`,
      __variables: {
        limit: "Int",
        offset: "Int",
      },
      [objectKind]: {
        __args: {
          limit: new VariableType("limit"),
          offset: new VariableType("offset"),
          ...(cleanedFilters?.length ? addFiltersToRequest(cleanedFilters) : {}),
          ...(sort?.length ? addOrderByToRequest(sort) : {}),
        },
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
  limit,
  offset,
  ...params
}: getIpAddressListFromApiParams) {
  const graphqlQuery = getIpAddressListWithAvailabilityGraphQLQuery(params);

  return graphqlClient.query({
    query: graphql(graphqlQuery),
    variables: { limit, offset },
    context: {
      branch: branchName,
      date: atDate,
    },
  });
}

export function getIpAddressListWithoutAvailabilityFromApi({
  branchName,
  atDate,
  limit,
  offset,
  ...params
}: getIpAddressListFromApiParams) {
  const graphqlQuery = getIpAddressListWithoutAvailabilityGraphQLQuery(params);

  return graphqlClient.query({
    query: graphql(graphqlQuery),
    variables: { limit, offset },
    context: {
      branch: branchName,
      date: atDate,
    },
  });
}
