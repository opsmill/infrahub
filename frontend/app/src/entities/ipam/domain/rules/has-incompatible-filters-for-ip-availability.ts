import type { Filter } from "@/shared/hooks/useFilters";

import { AVAILABLE_IP_FILTER_NAME } from "@/entities/ipam/constants";

const allowedFiltersWithIpAvailability: Array<Filter["name"]> = [
  "parent__ids",
  "ip_prefix__ids",
  AVAILABLE_IP_FILTER_NAME,
];

export function hasIncompatibleFiltersForIpAvailability(filters: Filter[]) {
  return filters.some(({ name }) => !allowedFiltersWithIpAvailability.includes(name));
}
