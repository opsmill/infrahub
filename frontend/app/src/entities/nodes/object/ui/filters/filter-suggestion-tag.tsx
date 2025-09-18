import { Icon } from "@iconify-icon/react";
import { Tag, type TagProps } from "react-aria-components";

import { focusVisibleStyle } from "@/shared/components/style-rac";
import { classNames } from "@/shared/utils/common";

interface FilterSuggestionTagProps extends TagProps {
  label: string;
}

export function FilterSuggestionTag({ label, className, ...props }: FilterSuggestionTagProps) {
  return (
    <Tag
      className={classNames(
        focusVisibleStyle,
        "inline-flex cursor-pointer items-center gap-1.5 whitespace-nowrap rounded-full px-1 text-gray-400 text-sm",
        "border border-gray-300 border-dashed",
        "data-hovered:border-gray-600 data-hovered:bg-gray-100 data-hovered:text-gray-600",
        className
      )}
      textValue={label}
      {...props}
    >
      <span className="ml-1.5">{label}</span>
      <div className="h-6 border-gray-300 border-r border-dashed" />
      <Icon icon="mdi:plus" className="text-base text-gray-400 group-hover:text-indigo-700" />
    </Tag>
  );
}
