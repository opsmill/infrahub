import { gql } from "@apollo/client";

import graphqlClient from "@/shared/api/graphql/graphqlClientApollo";
import type { ContextParams, PaginationParams } from "@/shared/api/types";
import type { Filter } from "@/shared/hooks/useFilters";

import { IP_PREFIX_GENERIC } from "@/entities/ipam/constants";
import {
  buildGetIpPrefixListWithAvailabilityQuery,
  buildGetIpPrefixListWithoutAvailabilityQuery,
} from "@/entities/ipam/ip-prefixes/api/get-ip-prefix-list-from-api";
import type { IpPrefixNode } from "@/entities/ipam/ip-prefixes/types";
import { getPrefixAttributesVisibleInListView } from "@/entities/ipam/ip-prefixes/utils/get-prefix-attributes-visible-in-list-view";
import { hasIncompatibleFiltersForIpAvailability } from "@/entities/ipam/utils";
import { OBJECTS_PER_PAGE } from "@/entities/nodes/object/domain/get-objects";
import { getRelationshipsVisibleInListView } from "@/entities/nodes/object/utils/get-relationships-visible-in-list-view";
import type { ModelSchema } from "@/entities/schema/types";

export interface GetIpPrefixListParams extends ContextParams, PaginationParams {
  schema: ModelSchema;
  filters?: Array<Filter>;
}

export type GetIpPrefixList = (params: GetIpPrefixListParams) => Promise<Array<IpPrefixNode>>;

export const getIpPrefixList: GetIpPrefixList = async ({
  schema,
  limit = OBJECTS_PER_PAGE,
  offset,
  branchName,
  atDate,
  filters = [],
}) => {
  const attributesVisible = getPrefixAttributesVisibleInListView(schema.attributes ?? []);
  const relationshipsVisible = getRelationshipsVisibleInListView(schema.relationships ?? []);

  const excludeIpAvailability = hasIncompatibleFiltersForIpAvailability(filters);
  const schemaKind = schema.kind as string;

  const queryString = (
    excludeIpAvailability
      ? buildGetIpPrefixListWithoutAvailabilityQuery
      : buildGetIpPrefixListWithAvailabilityQuery
  )({
    limit,
    offset,
    filters,
    objectKind: schemaKind,
    attributes: attributesVisible,
    relationships: relationshipsVisible,
  });

  const query = gql(queryString);
  const { data } = await graphqlClient.query({
    query,
    context: {
      branch: branchName,
      date: atDate,
    },
  });

  return (
    data[excludeIpAvailability ? schemaKind : IP_PREFIX_GENERIC]?.edges?.map(
      (edge: any) => edge.node
    ) ?? []
  );
};
