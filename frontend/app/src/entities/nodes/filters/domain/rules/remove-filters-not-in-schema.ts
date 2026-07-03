import { IP_ADDRESS_GENERIC } from "@/entities/ipam/ip-addresses/domain/model/ip-address";
import { AVAILABLE_IP_FILTER_NAME } from "@/entities/ipam/ip-availability/domain/model/ip-availability-filter";
import { IP_PREFIX_GENERIC } from "@/entities/ipam/ip-prefixes/domain/model/ip-prefix";
import type { Filter } from "@/entities/nodes/filters/domain/model/filter";
import type { ModelSchema } from "@/entities/schema/domain/model/schema";
import { isOfKind } from "@/entities/schema/domain/rules/is-of-kind";

export const removeFiltersNotInSchema = (filters: Filter[], schema: ModelSchema | null) => {
  if (!schema) {
    return [];
  }

  const isIpamSchema = isOfKind(IP_PREFIX_GENERIC, schema) || isOfKind(IP_ADDRESS_GENERIC, schema);

  return filters.filter((filter) => {
    if (isIpamSchema && filter.name === AVAILABLE_IP_FILTER_NAME) return true;

    if (filter.name.startsWith("node_metadata__")) return true;

    const [fieldName] = filter.name.split("__");
    return (
      schema.attributes?.some((attr) => attr.name === fieldName) ||
      schema.relationships?.some((rel) => rel.name === fieldName)
    );
  });
};
