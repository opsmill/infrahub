import { AVAILABLE_IP_FILTER_NAME } from "@/entities/ipam/constants";
import type { Filter } from "@/entities/nodes/filters/domain/model/filter";

const allowedFiltersWithIpAvailability: Array<Filter["name"]> = [
  "parent__ids",
  "ip_prefix__ids",
  AVAILABLE_IP_FILTER_NAME,
];

export function hasIncompatibleFiltersForIpAvailability(filters: Filter[]) {
  return filters.some(({ name }) => !allowedFiltersWithIpAvailability.includes(name));
}
