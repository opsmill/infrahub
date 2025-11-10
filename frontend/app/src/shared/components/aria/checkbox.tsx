import { CheckIcon, MinusIcon } from "lucide-react";
import {
  Checkbox as AriaCheckbox,
  type CheckboxProps as AriaCheckboxProps,
  composeRenderProps,
} from "react-aria-components";

import { labelVariants } from "@/shared/components/aria/label";
import { classNames } from "@/shared/utils/common";

export interface CheckboxProps extends AriaCheckboxProps {}

export const Checkbox = ({ className, children, ...props }: CheckboxProps) => (
  <AriaCheckbox
    className={composeRenderProps(className, (className) =>
      classNames(
        "group/checkbox flex cursor-pointer select-none items-center gap-1.5",
        "data-[disabled]:cursor-not-allowed data-[disabled]:opacity-70",
        labelVariants,
        className
      )
    )}
    {...props}
  >
    {composeRenderProps(children, (children, { isIndeterminate, isSelected }) => (
      <>
        <div
          className={classNames(
            "flex size-4 shrink-0 cursor-pointer items-center justify-center rounded border border-gray-300 text-white",
            "transition-colors group-data-[focus-visible]/checkbox:border-custom-blue-600 group-data-[focus-visible]/checkbox:outline-none group-data-[focus-visible]/checkbox:ring-2 group-data-[focus-visible]/checkbox:ring-custom-blue-600/25",
            "group-data-[disabled]/checkbox:cursor-not-allowed group-data-[disabled]/checkbox:opacity-50",
            (isSelected || isIndeterminate) && "border-custom-blue-600 bg-custom-blue-600"
          )}
        >
          {isIndeterminate ? (
            <MinusIcon className="size-3" />
          ) : isSelected ? (
            <CheckIcon className="size-3" />
          ) : null}
        </div>
        {children}
      </>
    ))}
  </AriaCheckbox>
);
