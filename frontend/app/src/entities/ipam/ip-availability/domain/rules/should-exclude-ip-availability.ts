import { hasIncompatibleFiltersForIpAvailability } from "@/entities/ipam/ip-availability/domain/rules/has-incompatible-filters-for-ip-availability";
import type { Filter } from "@/entities/nodes/filters/domain/model/filter";
import type { Sort } from "@/entities/nodes/sort/domain/model/sort";

/**
 * Synthetic "available" IPs are interleaved into the list only when it is ordered by address (the
 * backend computes the gaps in address order and discards any other requested order). So a custom
 * sort suppresses available IPs, just like an incompatible filter does — the list falls back to the
 * plain query, which honors the sort.
 */
export function shouldExcludeIpAvailability(filters: Filter[], sort?: Sort[] | null): boolean {
  return hasIncompatibleFiltersForIpAvailability(filters) || Boolean(sort?.length);
}
