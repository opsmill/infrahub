import { buttonVariants, LinkButton, type LinkButtonProps } from "@infrahub/ui";
import type React from "react";

import { classNames } from "@/shared/utils/common";

const pillStyle =
  "rounded-full border-border pr-2.5 dark:border-white/10 dark:bg-white/5 dark:shadow-none";

export interface LinkPillProps extends Omit<LinkButtonProps, "className"> {
  className?: string;
}

export function LinkPill({ className, ...props }: LinkPillProps) {
  return (
    <LinkButton
      variant="input"
      size="sm"
      className={classNames(
        pillStyle,
        "hover:border-ring hover:underline dark:hover:border-ring",
        className
      )}
      {...props}
    />
  );
}

export interface PillProps extends React.HTMLAttributes<HTMLSpanElement> {
  size?: LinkPillProps["size"];
}

/** A `LinkPill` that does not link, for a place where the link has to stay out of the Tab order. */
export function Pill({ size = "sm", className, ...props }: PillProps) {
  return (
    <span
      className={buttonVariants({
        variant: "input",
        size,
        className: classNames(pillStyle, "cursor-default", className),
      })}
      {...props}
    />
  );
}
