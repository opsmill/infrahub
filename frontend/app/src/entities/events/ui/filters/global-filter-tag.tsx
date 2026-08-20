import { Tag, type TagProps } from "react-aria-components";

import { focusVisibleStyle } from "@/shared/components/aria/style-rac";
import { classNames } from "@/shared/utils/common";

import type { Filter } from "@/entities/nodes/filters/domain/model/filter";

type FilterTagProps = {
  label: string;
  currentFilter?: Filter;
} & TagProps;

export const FilterTag = ({ children, label, currentFilter, ...props }: FilterTagProps) => {
  return (
    <Tag
      className={classNames(
        focusVisibleStyle,
        "group inline-flex items-center gap-1.5 whitespace-nowrap rounded-full border border-border-strong text-sm",
        currentFilter?.value && "cursor-pointer bg-neutral-100 pl-1 text-subtle",
        !currentFilter?.value && "cursor-pointer border-dashed px-1 text-subtle-muted",
        "data-hovered:border-gray-600 data-hovered:bg-gray-100 data-hovered:text-subtle"
      )}
      aria-label={`${label} contains ${currentFilter?.value}`}
      textValue={`${label} contains ${currentFilter?.value}`}
      {...props}
    >
      {children}
    </Tag>
  );
};
