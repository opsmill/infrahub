import type { ContextParams, PaginationParams } from "@/shared/api/types";
import { DEFAULT_PAGE_SIZE } from "@/shared/utils/pagination";

import { IP_NAMESPACE_GENERIC } from "@/entities/ipam/constants";
import { getIpNamespaceListFromApi } from "@/entities/ipam/ip-namespaces/api/get-ip-namespace-list-from-api";
import type { Filter } from "@/entities/nodes/filters/domain/model/filter";
import type { NodeCore } from "@/entities/nodes/object/domain/model/node";

export interface GetIpNamespaceListParams extends ContextParams, PaginationParams {
  filters?: Array<Filter>;
}

export interface IpNamespace extends NodeCore {
  description: { value: string };
  ip_addresses: { count: number };
  ip_prefixes: { count: number };
  default?: { value: boolean };
}

export type GetIpNamespaceList = (params: GetIpNamespaceListParams) => Promise<IpNamespace[]>;

export const getIpNamespaceList: GetIpNamespaceList = async ({
  filters,
  limit = DEFAULT_PAGE_SIZE,
  offset,
  branchName,
  atDate,
}) => {
  const { data, errors } = await getIpNamespaceListFromApi({
    filters,
    limit,
    offset,
    branchName,
    atDate,
  });

  if (errors?.[0]?.message) {
    throw new Error(errors[0].message);
  }

  return data?.[IP_NAMESPACE_GENERIC]?.edges?.map(({ node }: { node: IpNamespace }) => node) ?? [];
};
