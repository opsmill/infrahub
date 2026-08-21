import { CircleXIcon } from "lucide-react";
import type React from "react";
import { Button, Tag, type TagProps } from "react-aria-components";

import { Separator } from "@/shared/components/aria/separator";
import { focusVisibleStyle } from "@/shared/components/aria/style-rac";
import { classNames } from "@/shared/utils/common";

interface FilterTagProps extends TagProps {
  label: React.ReactNode;
  value: React.ReactNode;
  condition?: string;
  ref?: React.Ref<HTMLDivElement>;
}

export function FilterTag({ label, value, condition, ref, ...props }: FilterTagProps) {
  return (
    <Tag
      ref={ref}
      className={classNames(
        focusVisibleStyle,
        "inline-flex cursor-pointer items-center gap-1.5 whitespace-nowrap rounded-full border border-border-strong bg-background pr-1 pl-2 text-foreground text-sm",
        "data-hovered:border-ring data-hovered:bg-highlight",
        "data-selected:border-ring data-selected:bg-selected data-selected:text-selected-foreground data-selected:shadow-selected"
      )}
      textValue={`${label} ${condition || "contains"} ${value}`}
      {...props}
    >
      <span>{label}</span>
      {condition && (
        <>
          <Separator orientation="vertical" className="h-6" />
          <span>{condition}</span>
        </>
      )}
      {(value || value === 0 || value === false) && (
        <>
          <Separator orientation="vertical" className="h-6" />
          <span className="max-w-xs truncate font-medium text-accent">
            {typeof value === "boolean" ? String(value) : value}
          </span>
        </>
      )}
      <Button
        slot="remove"
        className={classNames(
          focusVisibleStyle,
          "inline-flex cursor-pointer rounded-full border border-transparent"
        )}
      >
        <CircleXIcon className="size-3.5 text-subtle-muted hover:text-accent" />
      </Button>
    </Tag>
  );
}
