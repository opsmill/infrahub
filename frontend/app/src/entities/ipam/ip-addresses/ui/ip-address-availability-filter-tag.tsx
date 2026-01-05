import type { TagProps } from "react-aria-components";
import { useParams } from "react-router";

import useFilters from "@/shared/hooks/useFilters";

import {
  AVAILABLE_IP_FILTER_NAME,
  HIDE_AVAILABLE_IP,
  SHOW_AVAILABLE_IP,
} from "@/entities/ipam/constants";
import { hasIncompatibleFiltersForIpAvailability } from "@/entities/ipam/utils";
import { FilterSuggestionTag } from "@/entities/nodes/object/ui/filters/filter-suggestion-tag";
import { FilterTag } from "@/entities/nodes/object/ui/filters/filter-tag";

export function IpAddressAvailabilityFilterTag({ ...props }: TagProps) {
  const [filters] = useFilters();
  const { objectId } = useParams();

  if (!objectId) return null; // to hide it on IPAM homepage
  if (hasIncompatibleFiltersForIpAvailability(filters)) return null;

  const currentIpAvailabilityFilter = filters.find(
    (filter) => filter.name === AVAILABLE_IP_FILTER_NAME
  );

  if (!currentIpAvailabilityFilter || currentIpAvailabilityFilter.value) {
    return (
      <FilterTag id={HIDE_AVAILABLE_IP} label="Available IP addresses" value="visible" {...props} />
    );
  }

  return <FilterSuggestionTag id={SHOW_AVAILABLE_IP} label="Available IP addresses" {...props} />;
}
