import { classNames } from "@/shared/utils/common";
import { Label as AriaLabel, LabelProps as AriaLabelProps } from "react-aria-components";

export function Label({ className, ...props }: AriaLabelProps) {
  return (
    <AriaLabel
      className={classNames(
        "text-sm font-medium text-gray-900 cursor-pointer peer-disabled:cursor-not-allowed peer-disabled:opacity-70",
        className
      )}
      {...props}
    />
  );
}
