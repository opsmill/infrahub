import { labelVariants } from "@/shared/components/aria/label";
import { classNames } from "@/shared/utils/common";
import { CheckIcon, MinusIcon } from "lucide-react";
import {
  Checkbox as AriaCheckbox,
  type CheckboxProps as AriaCheckboxProps,
  composeRenderProps,
} from "react-aria-components";

export const Checkbox = ({ className, children, ...props }: AriaCheckboxProps) => (
  <AriaCheckbox
    className={composeRenderProps(className, (className) =>
      classNames(
        "group/checkbox flex items-center gap-1.5",
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
            "flex size-4 shrink-0 items-center justify-center rounded border border-gray-300 cursor-pointer",
            "transition-colors group-data-[focus-visible]/checkbox:outline-none group-data-[focus-visible]/checkbox:ring-2 group-data-[focus-visible]/checkbox:ring-custom-blue-600/25 group-data-[focus-visible]/checkbox:border-custom-blue-600",
            "group-data-[disabled]/checkbox:cursor-not-allowed group-data-[disabled]/checkbox:opacity-50",
            isSelected && "text-white bg-custom-blue-600 border-custom-blue-600"
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
