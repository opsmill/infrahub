import { classNames } from "@/shared/utils/common";
import {
  Separator as AriaSeparator,
  SeparatorProps as AriaSeparatorProps,
} from "react-aria-components";

export interface SeparatorProps extends AriaSeparatorProps {}

export function Separator({ orientation = "horizontal", className, ...props }: SeparatorProps) {
  return (
    <AriaSeparator
      {...props}
      className={classNames(
        "bg-gray-200 text-gray-200 shrink-0",
        orientation === "horizontal" ? "h-px w-full" : "h-full w-px",
        className
      )}
    />
  );
}
