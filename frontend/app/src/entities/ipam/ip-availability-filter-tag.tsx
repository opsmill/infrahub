import { FilterSuggestionTag } from "@/entities/nodes/object/ui/filters/filter-suggestion-tag";
import { FilterTag } from "@/entities/nodes/object/ui/filters/filter-tag";
import useFilters, { Filter } from "@/shared/hooks/useFilters";
import type { TagProps } from "react-aria-components";

////////////////////////////////////////////////////////////////////////////////////////////////////

export const AVAILABLE_IP_FILTER_NAME = "include_available" as const;
export const SHOW_AVAILABLE_IP_FILTER: Filter = { name: AVAILABLE_IP_FILTER_NAME, value: true };
export const HIDE_AVAILABLE_IP = "hide-available-ip";
export const SHOW_AVAILABLE_IP = "show-available-ip";

////////////////////////////////////////////////////////////////////////////////////////////////////

export function IpAvailabilityFilterTag({ ...props }: TagProps) {
  const [filters] = useFilters();

  const currentIpAvailabilityFilter = filters.find(
    (filter) => filter.name === AVAILABLE_IP_FILTER_NAME
  );

  if (!currentIpAvailabilityFilter) {
    return <FilterSuggestionTag id={SHOW_AVAILABLE_IP} label="show available IPs" {...props} />;
  }

  return <FilterTag id={HIDE_AVAILABLE_IP} label="available IPs" value="show" {...props} />;
}
