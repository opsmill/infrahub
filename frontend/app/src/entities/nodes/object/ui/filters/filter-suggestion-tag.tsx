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
        "inline-flex cursor-pointer items-center gap-1.5 whitespace-nowrap rounded-full border border-border-strong pr-1.5 pl-2 text-foreground text-sm",
        "group border-dashed text-subtle-muted",
        "hover:border-subtle hover:bg-highlight hover:text-foreground-muted",
        className
      )}
      textValue={label}
      {...props}
    >
      <span>{label}</span>
      <div className="h-6 border-border-strong border-r border-dashed group-hover:border-subtle" />
      <PlusIcon className="size-4" />
    </Tag>
  );
}
