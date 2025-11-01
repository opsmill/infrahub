import type { SelectProps } from "react-aria-components";

import { Select, SelectItem, SelectList, SelectTrigger } from "@/shared/components/aria/select";

////////////////////////////////////////////////////////////////////////////////////////////////////

export const FILTER_CONDITION = {
  CONTAINS: "contains",
  IS_ANY_OF: "is any of",
  IS_EMPTY: "is empty",
  IS_NOT_EMPTY: "is not empty",
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

////////////////////////////////////////////////////////////////////////////////////////////////////

export interface FilterConditionSelectProps extends SelectProps {
  filterType: "attribute" | "relationship";
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
      <SelectTrigger className="w-[132px]" />

      <SelectList
        items={
          filterType === "relationship"
            ? RELATIONSHIP_FILTER_CONDITION_OPTIONS
            : ATTRIBUTE_FILTER_CONDITION_OPTIONS
        }
      >
        {(item) => <SelectItem>{item.label}</SelectItem>}
      </SelectList>
    </Select>
  );
}
