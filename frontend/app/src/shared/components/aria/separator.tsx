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
        "shrink-0 bg-stone-300 text-stone-300",
        orientation === "horizontal" ? "h-px w-full" : "h-full w-px",
        className
      )}
    />
  );
}
