import { classNames } from "@/shared/utils/common";
import { cva } from "class-variance-authority";
import { Label as AriaLabel, LabelProps as AriaLabelProps } from "react-aria-components";

export const labelVariants = cva([
  "text-sm font-medium leading-none text-gray-900 cursor-pointer",
  "data-[disabled]:cursor-not-allowed data-[disabled]:opacity-70",
]);

export function Label({ className, ...props }: AriaLabelProps) {
  return <AriaLabel className={classNames(labelVariants(), className)} {...props} />;
}
