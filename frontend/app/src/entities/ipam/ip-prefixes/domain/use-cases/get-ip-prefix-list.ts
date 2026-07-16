import type { ContextParams, PaginationParams } from "@/shared/api/types";
import { DEFAULT_PAGE_SIZE } from "@/shared/utils/pagination";

import { hasIncompatibleFiltersForIpAvailability } from "@/entities/ipam/ip-availability/domain/rules/has-incompatible-filters-for-ip-availability";
import { getIpPrefixListFromApi } from "@/entities/ipam/ip-prefixes/api/get-ip-prefix-list-from-api";
import type { IpPrefixNode } from "@/entities/ipam/ip-prefixes/domain/model/ip-prefix";
import { IP_PREFIX_GENERIC } from "@/entities/ipam/ip-prefixes/domain/model/ip-prefix";
import { getPrefixAttributesVisibleInListView } from "@/entities/ipam/ip-prefixes/domain/rules/get-prefix-attributes-visible-in-list-view";
import type { Filter } from "@/entities/nodes/filters/domain/model/filter";
import { getRelationshipsVisibleInListView } from "@/entities/nodes/object/domain/rules/get-relationships-visible-in-list-view";
import type { Sort } from "@/entities/nodes/sort/domain/model/sort";
import type { ModelSchema } from "@/entities/schema/domain/model/schema";

export interface GetIpPrefixListParams extends ContextParams, PaginationParams {
  schema: ModelSchema;
  filters?: Array<Filter>;
  sort?: Sort[] | null;
}

export type GetIpPrefixList = (params: GetIpPrefixListParams) => Promise<IpPrefixNode[]>;

export const getIpPrefixList: GetIpPrefixList = async ({
  schema,
  limit = DEFAULT_PAGE_SIZE,
  offset,
  branchName,
  atDate,
  filters = [],
  sort,
}) => {
  const attributesVisible = getPrefixAttributesVisibleInListView(schema.attributes ?? []);
  const relationshipsVisible = getRelationshipsVisibleInListView(schema.relationships ?? []);

  const excludeIpAvailability = hasIncompatibleFiltersForIpAvailability(filters);
  const schemaKind = schema.kind as string;

  const { data } = await getIpPrefixListFromApi({
    limit,
    offset,
    branchName,
    atDate,
    filters,
    sort,
    objectKind: schemaKind,
    attributes: attributesVisible,
    relationships: relationshipsVisible,
    excludeIpAvailability,
  });

  return (
    data[excludeIpAvailability ? schemaKind : IP_PREFIX_GENERIC]?.edges?.map(
      ({ node }: { node: IpPrefixNode }) => node
    ) ?? []
  );
};
