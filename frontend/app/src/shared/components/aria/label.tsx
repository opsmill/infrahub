import { cva } from "class-variance-authority";
import { Label as AriaLabel, type LabelProps as AriaLabelProps } from "react-aria-components";

import { classNames } from "@/shared/utils/common";

export const labelVariants = cva([
  "cursor-pointer font-medium text-gray-900 text-sm leading-none",
  "data-[disabled]:cursor-not-allowed data-[disabled]:opacity-70",
]);

export function Label({ className, ...props }: AriaLabelProps) {
  return <AriaLabel className={classNames(labelVariants(), className)} {...props} />;
}
