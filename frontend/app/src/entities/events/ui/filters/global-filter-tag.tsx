import { Tag, type TagProps } from "react-aria-components";

import { focusVisibleStyle } from "@/shared/components/aria/style-rac";
import type { Filter } from "@/shared/hooks/useFilters";
import { classNames } from "@/shared/utils/common";

type FilterTagProps = {
  label: string;
  currentFilter?: Filter;
} & TagProps;

export const FilterTag = ({ children, label, currentFilter, ...props }: FilterTagProps) => {
  return (
    <Tag
      className={classNames(
        focusVisibleStyle,
        "group inline-flex items-center gap-1.5 whitespace-nowrap rounded-full border border-gray-300 text-sm",
        currentFilter?.value && "cursor-pointer bg-neutral-100 pl-1 text-gray-600",
        !currentFilter?.value && "cursor-pointer border-dashed px-1 text-gray-400",
        "data-hovered:border-gray-600 data-hovered:bg-gray-100 data-hovered:text-gray-600"
      )}
      aria-label={`${label} contains ${currentFilter?.value}`}
      textValue={`${label} contains ${currentFilter?.value}`}
      {...props}
    >
      {children}
    </Tag>
  );
};
