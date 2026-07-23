import { jsonToGraphQLQuery, VariableType } from "json-to-graphql-query";

import { graphql, graphqlClient } from "@/shared/api/graphql/client";
import { addFiltersToRequest } from "@/shared/api/graphql/utils";
import type { ContextParams, PaginationParams } from "@/shared/api/types";
import { DEFAULT_PAGE_SIZE } from "@/shared/utils/pagination";

import { IP_NAMESPACE_GENERIC } from "@/entities/ipam/ip-namespaces/domain/model/ip-namespace";
import type { Filter } from "@/entities/nodes/filters/domain/model/filter";

export interface GetIpNamespaceListFromApiParams extends ContextParams, PaginationParams {
  filters?: Array<Filter>;
}

export async function getIpNamespaceListFromApi({
  filters,
  limit = DEFAULT_PAGE_SIZE,
  offset,
  branchName,
  atDate,
}: GetIpNamespaceListFromApiParams) {
  const query = graphql(
    jsonToGraphQLQuery({
      query: {
        __name: `GetObjects${IP_NAMESPACE_GENERIC}`,
        __variables: {
          limit: "Int",
          offset: "Int",
        },
        [IP_NAMESPACE_GENERIC]: {
          __args: {
            limit: new VariableType("limit"),
            offset: new VariableType("offset"),
            ...(filters ? addFiltersToRequest(filters) : {}),
          },
          edges: {
            node: {
              id: true,
              display_label: true,
              hfid: true,
              description: {
                value: true,
              },
              ip_prefixes: {
                count: true,
              },
              ip_addresses: {
                count: true,
              },
              __on: {
                __typeName: "IpamNamespace",
                default: {
                  value: true,
                },
              },
            },
          },
        },
      },
    })
  );

  return graphqlClient.query({
    query,
    variables: { limit, offset },
    context: {
      branch: branchName,
      date: atDate,
      processErrorMessage: () => {},
    },
  });
}
