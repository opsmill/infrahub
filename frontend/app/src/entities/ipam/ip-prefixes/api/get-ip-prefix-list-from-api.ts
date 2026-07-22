import { gql } from "@apollo/client";
import { jsonToGraphQLQuery } from "json-to-graphql-query";

import graphqlClient from "@/shared/api/graphql/graphqlClientApollo";
import {
  addAttributesToRequest,
  addFiltersToRequest,
  addOrderByToRequest,
  addRelationshipsToRequest,
  dropIncludeAvailableWhenFalse,
} from "@/shared/api/graphql/utils";
import type { ContextParams, PaginationParams } from "@/shared/api/types";

import { AVAILABLE_IP_FILTER_NAME } from "@/entities/ipam/ip-availability/domain/model/ip-availability-filter";
import {
  IP_PREFIX_AVAILABLE_KIND,
  IP_PREFIX_GENERIC,
} from "@/entities/ipam/ip-prefixes/domain/model/ip-prefix";
import type { Filter } from "@/entities/nodes/filters/domain/model/filter";
import type { Sort } from "@/entities/nodes/sort/domain/model/sort";
import type { AttributeSchema, RelationshipSchema } from "@/entities/schema/domain/model/schema";

export interface GetIpPrefixListFromApiParams extends ContextParams, PaginationParams {
  filters: Array<Filter>;
  sort?: Sort[] | null;
  objectKind: string;
  attributes: Array<AttributeSchema>;
  relationships: Array<RelationshipSchema>;
  excludeIpAvailability: boolean;
}

export async function getIpPrefixListFromApi({
  limit,
  offset,
  branchName,
  atDate,
  filters,
  sort,
  objectKind,
  attributes,
  relationships,
  excludeIpAvailability,
}: GetIpPrefixListFromApiParams) {
  const queryString = (
    excludeIpAvailability
      ? buildGetIpPrefixListWithoutAvailabilityQuery
      : buildGetIpPrefixListWithAvailabilityQuery
  )({
    limit,
    offset,
    filters,
    sort,
    objectKind,
    attributes,
    relationships,
  });

  const query = gql(queryString);
  return graphqlClient.query({
    query,
    context: {
      branch: branchName,
      date: atDate,
    },
  });
}

export interface BuildGetIpPrefixListQueryParams extends PaginationParams {
  filters?: Array<Filter>;
  sort?: Sort[] | null;
  objectKind: string;
  attributes: Array<AttributeSchema>;
  relationships: Array<RelationshipSchema>;
}

// Common fields reused across IP Prefix queries
export const IP_PREFIX_KIND_DETAILS_FRAGMENT = {
  ancestors: {
    count: true,
  },
  children: {
    count: true,
  },
  ip_addresses: {
    count: true,
  },
};

export function buildGetIpPrefixListWithoutAvailabilityQuery({
  limit,
  offset,
  filters,
  sort,
  objectKind,
  attributes,
  relationships,
}: BuildGetIpPrefixListQueryParams) {
  const cleanedFilters = dropIncludeAvailableWhenFalse(filters);

  return jsonToGraphQLQuery({
    query: {
      __name: `GetObjects${objectKind}`,
      [objectKind]: {
        __args: {
          limit,
          offset,
          ...(cleanedFilters?.length ? addFiltersToRequest(cleanedFilters) : {}),
          ...(sort?.length ? addOrderByToRequest(sort) : {}),
        },
        edges: {
          node: {
            id: true,
            display_label: true,
            hfid: true,
            ...IP_PREFIX_KIND_DETAILS_FRAGMENT,
            ...addAttributesToRequest(attributes),
            ...addRelationshipsToRequest(relationships),
          },
        },
      },
    },
  });
}

export function buildGetIpPrefixListWithAvailabilityQuery({
  limit,
  offset,
  filters,
  sort,
  objectKind,
  attributes,
  relationships,
}: BuildGetIpPrefixListQueryParams) {
  return jsonToGraphQLQuery({
    query: {
      __name: `GetObjects${objectKind}`,
      [IP_PREFIX_GENERIC]: {
        __args: {
          limit,
          offset,
          [AVAILABLE_IP_FILTER_NAME]: true,
          ...(objectKind !== IP_PREFIX_GENERIC ? { kinds: [objectKind] } : {}),
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
                ...IP_PREFIX_KIND_DETAILS_FRAGMENT,
                ...addAttributesToRequest(attributes),
                ...addRelationshipsToRequest(relationships),
              },
              {
                __typeName: IP_PREFIX_AVAILABLE_KIND,
                parent: {
                  node: {
                    id: true,
                    display_label: true,
                    hfid: true,
                    ancestors: {
                      count: true, // Ancestors are not available on this kind. Instead, we do parent ancestors + 1
                    },
                  },
                },
              },
            ],
          },
        },
      },
    },
  });
}
