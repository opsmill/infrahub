import {
  Separator as AriaSeparator,
  type SeparatorProps as AriaSeparatorProps,
} from "react-aria-components";

import { classNames } from "@/shared/utils/common";

export interface SeparatorProps extends AriaSeparatorProps {}

export function Separator({ orientation = "horizontal", className, ...props }: SeparatorProps) {
  return (
    <AriaSeparator
      {...props}
      className={classNames(
        // Painting the rule as a border rather than a 1px background avoids stacking on top of
        // the border Tailwind's preflight already gives `hr`, which rendered as two lines.
        "shrink-0 border-border-strong",
        orientation === "horizontal" ? "w-full border-t" : "h-full border-t-0 border-l",
        className
      )}
    />
  );
}
