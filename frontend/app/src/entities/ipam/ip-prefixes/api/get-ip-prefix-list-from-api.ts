import { jsonToGraphQLQuery } from "json-to-graphql-query";

import {
  addAttributesToRequest,
  addFiltersToRequest,
  addRelationshipsToRequest,
  dropIncludeAvailableWhenFalse,
} from "@/shared/api/graphql/utils";
import type { PaginationParams } from "@/shared/api/types";
import type { Filter } from "@/shared/hooks/useFilters";

import {
  AVAILABLE_IP_FILTER_NAME,
  IP_PREFIX_AVAILABLE_KIND,
  IP_PREFIX_GENERIC,
} from "@/entities/ipam/constants";
import type { AttributeSchema, RelationshipSchema } from "@/entities/schema/types";

export interface BuildGetIpPrefixListQueryParams extends PaginationParams {
  filters?: Array<Filter>;
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
