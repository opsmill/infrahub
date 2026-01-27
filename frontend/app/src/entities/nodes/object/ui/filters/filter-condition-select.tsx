import type { SelectProps } from "react-aria-components";

import { Select, SelectItem, SelectList, SelectTrigger } from "@/shared/components/aria/select";

////////////////////////////////////////////////////////////////////////////////////////////////////

export const FILTER_CONDITION = {
  CONTAINS: "contains",
  IS_ANY_OF: "is any of",
  IS_EMPTY: "is empty",
  IS_NOT_EMPTY: "is not empty",
  BEFORE: "before",
  AFTER: "after",
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

export const DATE_FILTER_CONDITION_OPTIONS: Array<{ key: FilterCondition; label: string }> = [
  { key: FILTER_CONDITION.BEFORE, label: "before" },
  { key: FILTER_CONDITION.AFTER, label: "after" },
  { key: FILTER_CONDITION.IS_EMPTY, label: "is empty" },
  { key: FILTER_CONDITION.IS_NOT_EMPTY, label: "is not empty" },
];

////////////////////////////////////////////////////////////////////////////////////////////////////

export interface FilterConditionSelectProps extends SelectProps {
  filterType: "attribute" | "relationship" | "date";
}

function getFilterConditionOptions(filterType: FilterConditionSelectProps["filterType"]) {
  switch (filterType) {
    case "relationship":
      return RELATIONSHIP_FILTER_CONDITION_OPTIONS;
    case "date":
      return DATE_FILTER_CONDITION_OPTIONS;
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
      <SelectTrigger className="w-33" />

      <SelectList items={getFilterConditionOptions(filterType)}>
        {(item) => <SelectItem>{item.label}</SelectItem>}
      </SelectList>
    </Select>
  );
}
