import { IP_PREFIX_AVAILABLE_KIND, IP_PREFIX_GENERIC } from "@/entities/ipam/constants";
import { AttributeSchema, RelationshipSchema } from "@/entities/schema/types";
import {
  addAttributesToRequest,
  addFiltersToRequest,
  addRelationshipsToRequest,
} from "@/shared/api/graphql/utils";
import { PaginationParams } from "@/shared/api/types";
import { Filter } from "@/shared/hooks/useFilters";
import { jsonToGraphQLQuery } from "json-to-graphql-query";

export interface BuildGetIpPrefixListQueryParams extends PaginationParams {
  filters?: Array<Filter>;
  objectKind: string;
  attributes: Array<AttributeSchema>;
  relationships: Array<RelationshipSchema>;
}

export function buildGetIpPrefixListQuery({
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
          include_available: true,
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
                ...addAttributesToRequest(attributes),
                ...addRelationshipsToRequest(relationships),
                ip_namespace: {
                  node: {
                    id: true,
                    display_label: true,
                    hfid: true,
                  },
                },
                ancestors: {
                  count: true,
                },
                children: {
                  count: true,
                },
                ip_addresses: {
                  count: true,
                },
              },
              {
                __typeName: IP_PREFIX_AVAILABLE_KIND, // Ancestors are not available on this kind. Instead, we do parent ancestors + 1
                parent: {
                  node: {
                    ancestors: {
                      count: true,
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
