import { Select, SelectItem, SelectList, SelectTrigger } from "@/shared/components/aria/select";
import { SelectProps } from "react-aria-components";

////////////////////////////////////////////////////////////////////////////////////////////////////

export const FILTER_CONDITION_OPTIONS = [
  { key: "is any of", label: "is any of" },
  { key: "is empty", label: "Is empty" },
  { key: "is not empty", label: "Is not empty" },
] as const;

export type FilterCondition = (typeof FILTER_CONDITION_OPTIONS)[number]["key"];

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
