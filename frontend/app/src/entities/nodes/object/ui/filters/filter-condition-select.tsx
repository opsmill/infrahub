import type { SelectProps } from "react-aria-components";

import { ListBox, ListBoxItem } from "@/shared/components/aria/list-box";
import { Popover } from "@/shared/components/aria/popover";
import { Select, SelectTrigger } from "@/shared/components/aria/select";

import type { FilterDefinition } from "@/entities/nodes/object/domain/filter-definition";

////////////////////////////////////////////////////////////////////////////////////////////////////

export const FILTER_CONDITION = {
  CONTAINS: "contains",
  IS_ANY_OF: "is any of",
  IS_EMPTY: "is empty",
  IS_NOT_EMPTY: "is not empty",
  BEFORE: "before",
  AFTER: "after",
  BETWEEN: "between",
} as const;

export type FilterCondition = (typeof FILTER_CONDITION)[keyof typeof FILTER_CONDITION];

export const RELATIONSHIP_FILTER_CONDITION_OPTIONS: Array<{ key: FilterCondition; label: string }> =
  [
    { key: FILTER_CONDITION.IS_ANY_OF, label: "is any of" },
    { key: FILTER_CONDITION.IS_EMPTY, label: "is empty" },
    { key: FILTER_CONDITION.IS_NOT_EMPTY, label: "is not empty" },
  ];

export const ATTRIBUTE_FILTER_CONDITION_OPTIONS: Array<{ key: FilterCondition; label: string }> = [
  { key: FILTER_CONDITION.CONTAINS, label: "contains" },
  { key: FILTER_CONDITION.IS_EMPTY, label: "is empty" },
  { key: FILTER_CONDITION.IS_NOT_EMPTY, label: "is not empty" },
];

export const DATETIME_FILTER_CONDITION_OPTIONS: Array<{ key: FilterCondition; label: string }> = [
  { key: FILTER_CONDITION.IS_EMPTY, label: "is empty" },
  { key: FILTER_CONDITION.IS_NOT_EMPTY, label: "is not empty" },
];

export const METADATA_DATE_FILTER_CONDITION_OPTIONS: Array<{
  key: FilterCondition;
  label: string;
}> = [
  { key: FILTER_CONDITION.BEFORE, label: "before" },
  { key: FILTER_CONDITION.AFTER, label: "after" },
  { key: FILTER_CONDITION.BETWEEN, label: "between" },
];

export const METADATA_USER_FILTER_CONDITION_OPTIONS: Array<{
  key: FilterCondition;
  label: string;
}> = [{ key: FILTER_CONDITION.IS_ANY_OF, label: "is any of" }];

////////////////////////////////////////////////////////////////////////////////////////////////////

export interface FilterConditionSelectProps extends SelectProps {
  filterType: FilterDefinition["type"] | "datetime";
}

function getFilterConditionOptions(filterType: FilterConditionSelectProps["filterType"]) {
  switch (filterType) {
    case "relationship":
      return RELATIONSHIP_FILTER_CONDITION_OPTIONS;
    case "datetime":
      return DATETIME_FILTER_CONDITION_OPTIONS;
    case "metadata-date":
      return METADATA_DATE_FILTER_CONDITION_OPTIONS;
    case "metadata-user":
      return METADATA_USER_FILTER_CONDITION_OPTIONS;
    default:
      return ATTRIBUTE_FILTER_CONDITION_OPTIONS;
  }
}

export function FilterConditionSelect({ filterType, ...props }: FilterConditionSelectProps) {
  return (
    <Select
      defaultValue="is any of"
      placeholder="Filter by"
      aria-label="select a condition"
      isRequired
      {...props}
    >
      <SelectTrigger className="h-auto min-h-auto border-transparent bg-transparent px-1 py-0" />

      <Popover>
        <ListBox items={getFilterConditionOptions(filterType)} className="p-1">
          {(item) => <ListBoxItem>{item.label}</ListBoxItem>}
        </ListBox>
      </Popover>
    </Select>
  );
}
