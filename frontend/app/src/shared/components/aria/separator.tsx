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
        "shrink-0 bg-gray-200 text-gray-200 dark:bg-gray-700 dark:text-gray-700",
        orientation === "horizontal" ? "h-px w-full" : "h-full w-px",
        className
      )}
    />
  );
}
