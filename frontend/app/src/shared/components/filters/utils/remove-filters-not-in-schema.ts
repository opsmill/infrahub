import type { Filter } from "@/shared/hooks/useFilters";

import {
  AVAILABLE_IP_FILTER_NAME,
  IP_ADDRESS_GENERIC,
  IP_PREFIX_GENERIC,
} from "@/entities/ipam/constants";
import type { ModelSchema } from "@/entities/schema/types";
import { isOfKind } from "@/entities/schema/utils/is-of-kind";

export const removeFiltersNotInSchema = (filters: Filter[], schema: ModelSchema | null) => {
  if (!schema) {
    return [];
  }

  const isIpamSchema = isOfKind(IP_PREFIX_GENERIC, schema) || isOfKind(IP_ADDRESS_GENERIC, schema);

  return filters.filter((filter) => {
    if (isIpamSchema && filter.name === AVAILABLE_IP_FILTER_NAME) return true;

    const [fieldName] = filter.name.split("__");
    return (
      schema.attributes?.some((attr) => attr.name === fieldName) ||
      schema.relationships?.some((rel) => rel.name === fieldName)
    );
  });
};
