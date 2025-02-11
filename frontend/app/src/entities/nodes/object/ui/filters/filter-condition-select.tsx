import { Select, SelectItem, SelectList, SelectTrigger } from "@/shared/components/aria/select";
import { SelectProps } from "react-aria-components";

////////////////////////////////////////////////////////////////////////////////////////////////////

export const FILTER_CONDITION = {
  IS_ANY_OF: "is any of",
  IS_EMPTY: "is empty",
  IS_NOT_EMPTY: "is not empty",
} as const;

export type FilterCondition = (typeof FILTER_CONDITION)[keyof typeof FILTER_CONDITION];

export const FILTER_CONDITION_OPTIONS: Array<{ key: FilterCondition; label: string }> = [
  { key: FILTER_CONDITION.IS_ANY_OF, label: "is any of" },
  { key: FILTER_CONDITION.IS_EMPTY, label: "is empty" },
  { key: FILTER_CONDITION.IS_NOT_EMPTY, label: "is not empty" },
];

////////////////////////////////////////////////////////////////////////////////////////////////////

export interface FilterConditionSelectProps extends SelectProps {}

export function FilterConditionSelect(props: FilterConditionSelectProps) {
  return (
    <Select
      defaultSelectedKey="is any of"
      placeholder="Filter by"
      aria-label="select a condition"
      isRequired
      {...props}
    >
      <SelectTrigger className="w-[132px]" />

      <SelectList items={FILTER_CONDITION_OPTIONS}>
        {(item) => <SelectItem>{item.label}</SelectItem>}
      </SelectList>
    </Select>
  );
}
