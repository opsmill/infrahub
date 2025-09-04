import { Tag, TagProps } from "react-aria-components";

import { focusVisibleStyle } from "@/shared/components/style-rac";
import { Filter } from "@/shared/hooks/useFilters";
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
        "group text-sm whitespace-nowrap rounded-full inline-flex items-center gap-1.5 border border-gray-300",
        currentFilter?.value && "text-gray-600  bg-neutral-100 pl-1 cursor-pointer",
        !currentFilter?.value && "text-gray-400 px-1 cursor-pointer border-dashed",
        "data-hovered:bg-gray-100 data-hovered:text-gray-600 data-hovered:border-gray-600"
      )}
      aria-label={`${label} contains ${currentFilter?.value}`}
      textValue={`${label} contains ${currentFilter?.value}`}
      {...props}
    >
      {children}
    </Tag>
  );
};
