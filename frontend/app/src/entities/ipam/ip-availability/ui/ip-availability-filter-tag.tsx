import type { TagProps } from "react-aria-components";
import { useParams } from "react-router";

import {
  AVAILABLE_IP_FILTER_NAME,
  HIDE_AVAILABLE_IP,
  SHOW_AVAILABLE_IP,
} from "@/entities/ipam/ip-availability/domain/model/ip-availability-filter";
import { shouldExcludeIpAvailability } from "@/entities/ipam/ip-availability/domain/rules/should-exclude-ip-availability";
import { useFilters } from "@/entities/nodes/filters/ui/hooks/use-filters";
import { FilterSuggestionTag } from "@/entities/nodes/object/ui/filters/filter-suggestion-tag";
import { FilterTag } from "@/entities/nodes/object/ui/filters/filter-tag";
import { useObjectTableContext } from "@/entities/nodes/object/ui/object-table/object-table-context";
import { useSort } from "@/entities/nodes/sort/ui/hooks/use-sort";

interface IpAvailabilityFilterTagProps extends TagProps {
  label: string;
}

export function IpAvailabilityFilterTag({ label, ...props }: IpAvailabilityFilterTagProps) {
  const [filters] = useFilters();
  const { objectId } = useParams();
  const { selectedSchema } = useObjectTableContext();
  const { customSort } = useSort(selectedSchema);

  if (!objectId) return null; // to hide it on IPAM homepage
  // Hide whenever available IPs aren't actually shown (incompatible filters or a custom sort).
  if (shouldExcludeIpAvailability(filters, customSort)) return null;

  const currentIpAvailabilityFilter = filters.find(
    (filter) => filter.name === AVAILABLE_IP_FILTER_NAME
  );

  if (!currentIpAvailabilityFilter || currentIpAvailabilityFilter.value) {
    return <FilterTag id={HIDE_AVAILABLE_IP} label={label} value="visible" {...props} />;
  }

  return <FilterSuggestionTag id={SHOW_AVAILABLE_IP} label={label} {...props} />;
}
