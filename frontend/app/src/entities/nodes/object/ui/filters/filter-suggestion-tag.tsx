import { focusVisibleStyle } from "@/shared/components/style-rac";
import { classNames } from "@/shared/utils/common";
import { Icon } from "@iconify-icon/react";
import { Tag, TagProps } from "react-aria-components";

interface FilterSuggestionTagProps extends TagProps {
  label: string;
}

export function FilterSuggestionTag({ label, className, ...props }: FilterSuggestionTagProps) {
  return (
    <Tag
      className={classNames(
        focusVisibleStyle,
        "text-gray-400 text-sm whitespace-nowrap rounded-full inline-flex items-center gap-1.5 px-1 cursor-pointer",
        "border border-gray-300 border-dashed",
        "data-hovered:bg-gray-100 data-hovered:text-gray-600 data-hovered:border-gray-600",
        className
      )}
      textValue={label}
      {...props}
    >
      <span className="ml-1.5">{label}</span>
      <div className="border-r border-dashed border-gray-300 h-6" />
      <Icon icon="mdi:plus" className="text-base text-gray-400 group-hover:text-indigo-700" />
    </Tag>
  );
}
