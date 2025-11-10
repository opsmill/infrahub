import { gql } from "@apollo/client";
import { jsonToGraphQLQuery } from "json-to-graphql-query";

import graphqlClient from "@/shared/api/graphql/graphqlClientApollo";
import { addFiltersToRequest } from "@/shared/api/graphql/utils";
import type { ContextParams, PaginationParams } from "@/shared/api/types";
import type { Filter } from "@/shared/hooks/useFilters";

import { OBJECTS_PER_PAGE } from "@/entities/nodes/object/domain/get-objects";
import type { NodeCore } from "@/entities/nodes/types";

import { IP_NAMESPACE_GENERIC } from "../../constants";

export interface GetIpNamespaceListParams extends ContextParams, PaginationParams {
  filters?: Array<Filter>;
}

export interface IpNamespace extends NodeCore {
  description: { value: string };
  ip_addresses: { count: number };
  ip_prefixes: { count: number };
  default?: { value: boolean };
}

export type GetIpNamespaceList = (params: GetIpNamespaceListParams) => Promise<Array<IpNamespace>>;

export const getIpNamespaceList: GetIpNamespaceList = async ({
  filters,
  limit = OBJECTS_PER_PAGE,
  offset,
  branchName,
  atDate,
}) => {
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

  const { data, errors } = await graphqlClient.query({
    query,
    context: {
      branch: branchName,
      date: atDate,
      processErrorMessage: () => {},
    },
  });

  if (errors?.[0]?.message) {
    throw new Error(errors[0].message);
  }

  return data?.[IP_NAMESPACE_GENERIC]?.edges?.map((edge: any) => edge.node) ?? [];
};
