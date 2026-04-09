import { PlusIcon } from "lucide-react";
import { Tag, type TagProps } from "react-aria-components";

import { focusVisibleStyle } from "@/shared/components/aria/style-rac";
import { classNames } from "@/shared/utils/common";

interface FilterSuggestionTagProps extends TagProps {
  label: string;
}

export function FilterSuggestionTag({ label, className, ...props }: FilterSuggestionTagProps) {
  return (
    <Tag
      className={classNames(
        focusVisibleStyle,
        "inline-flex cursor-pointer items-center gap-1.5 whitespace-nowrap rounded-full border border-stone-300 pr-1.5 pl-2 text-sm text-stone-800",
        "group border-dashed text-stone-400",
        "hover:border-stone-600 hover:bg-stone-100 hover:text-stone-600",
        className
      )}
      textValue={label}
      {...props}
    >
      <span>{label}</span>
      <div className="h-6 border-stone-300 border-r border-dashed group-hover:border-stone-600" />
      <PlusIcon className="size-4" />
    </Tag>
  );
}
