import { useEffect } from "react";
import type { TagProps } from "react-aria-components";

import useFilters, { type Filter } from "@/shared/hooks/useFilters";

import { FilterSuggestionTag } from "@/entities/nodes/object/ui/filters/filter-suggestion-tag";
import { FilterTag } from "@/entities/nodes/object/ui/filters/filter-tag";

////////////////////////////////////////////////////////////////////////////////////////////////////

export const HIDE_INTERNAL_GROUPS_FILTER: Filter = { name: "group_type__value", value: "default" };
export const HIDE_INTERNAL_GROUPS_ID = "hide-internal-groups";
export const SHOW_INTERNAL_GROUPS_ID = "show-internal-groups";

////////////////////////////////////////////////////////////////////////////////////////////////////

export const InternalGroupsFilterTag = ({ ...props }: TagProps) => {
  const [filters, setFilters] = useFilters();

  useEffect(() => {
    if (filters.length === 0) {
      setFilters([HIDE_INTERNAL_GROUPS_FILTER]);
    }
  }, []);

  const groupTypeFilter = filters.find(
    (filter) => filter.name === HIDE_INTERNAL_GROUPS_FILTER.name
  );

  if (!groupTypeFilter || groupTypeFilter.value !== HIDE_INTERNAL_GROUPS_FILTER.value) {
    return (
      <FilterSuggestionTag id={HIDE_INTERNAL_GROUPS_ID} label="Hide internal groups" {...props} />
    );
  }

  return (
    <FilterTag id={SHOW_INTERNAL_GROUPS_ID} label="internal groups" value="hidden" {...props} />
  );
};
