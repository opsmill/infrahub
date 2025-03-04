import { Label as AriaLabel, LabelProps as AriaLabelProps } from "react-aria-components";
import { classNames } from "@/shared/utils/common";

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
