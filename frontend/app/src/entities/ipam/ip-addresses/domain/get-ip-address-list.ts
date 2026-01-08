import type { ContextParams, PaginationParams } from "@/shared/api/types";
import type { Filter } from "@/shared/hooks/useFilters";
import { DEFAULT_PAGE_SIZE, type PaginatedResponse } from "@/shared/utils/pagination";

import { IP_ADDRESS_GENERIC } from "@/entities/ipam/constants";
import {
  getIpAddressListWithAvailabilityFromApi,
  getIpAddressListWithoutAvailabilityFromApi,
} from "@/entities/ipam/ip-addresses/api/get-ip-address-list-from-api";
import type { IpAddressAvailableNode } from "@/entities/ipam/ip-addresses/domain/types";
import { getIpAddressAttributesVisibleInListView } from "@/entities/ipam/ip-addresses/utils/get-ip-address-attributes-visible-in-list-view";
import { getIpAddressRelationshipsVisibleInListView } from "@/entities/ipam/ip-addresses/utils/get-ip-address-relationships-visible-in-list-view";
import { hasIncompatibleFiltersForIpAvailability } from "@/entities/ipam/utils";
import type { NodeObject } from "@/entities/nodes/types";
import type { ModelSchema } from "@/entities/schema/types";

export interface GetIpAddressListParams extends ContextParams, PaginationParams {
  schema: ModelSchema;
  filters?: Array<Filter>;
}

export type GetIpAddressList = (
  params: GetIpAddressListParams
) => Promise<PaginatedResponse<NodeObject | IpAddressAvailableNode>>;

export const getIpAddressList: GetIpAddressList = async ({
  schema,
  limit = DEFAULT_PAGE_SIZE,
  offset,
  branchName,
  atDate,
  filters = [],
}) => {
  const attributesVisible = getIpAddressAttributesVisibleInListView(schema.attributes ?? []);
  const relationshipsVisible = getIpAddressRelationshipsVisibleInListView(
    schema.relationships ?? []
  );

  const excludeIpAvailability = hasIncompatibleFiltersForIpAvailability(filters);
  const schemaKind = schema.kind as string;

  const getIpAddressListFromApi = excludeIpAvailability
    ? getIpAddressListWithoutAvailabilityFromApi
    : getIpAddressListWithAvailabilityFromApi;

  const { data, errors } = await getIpAddressListFromApi({
    branchName,
    atDate,
    limit,
    offset,
    filters,
    objectKind: schemaKind,
    attributes: attributesVisible,
    relationships: relationshipsVisible,
  });

  if (errors) {
    throw new Error(errors.map((e) => e.message).join("; "));
  }

  const result = data[excludeIpAvailability ? schemaKind : IP_ADDRESS_GENERIC];

  return {
    items:
      result?.edges?.map((edge: { node: NodeObject | IpAddressAvailableNode }) => edge.node) ?? [],
    count: result?.count ?? 0,
  };
};
