import { gql } from "@apollo/client";
import { jsonToGraphQLQuery } from "json-to-graphql-query";

import graphqlClient from "@/shared/api/graphql/graphqlClientApollo";
import { addFiltersToRequest } from "@/shared/api/graphql/utils";
import type { ContextParams, PaginationParams } from "@/shared/api/types";
import type { Filter } from "@/shared/hooks/useFilters";
import { DEFAULT_PAGE_SIZE } from "@/shared/utils/pagination";

import { IP_NAMESPACE_GENERIC } from "@/entities/ipam/constants";

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
  const query = gql(
    jsonToGraphQLQuery({
      query: {
        __name: `GetObjects${IP_NAMESPACE_GENERIC}`,
        [IP_NAMESPACE_GENERIC]: {
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
    context: {
      branch: branchName,
      date: atDate,
      processErrorMessage: () => {},
    },
  });
}
