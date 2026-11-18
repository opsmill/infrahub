import { CheckIcon, MinusIcon } from "lucide-react";
import {
  CheckboxButton as AriaCheckboxButton,
  CheckboxField as AriaCheckboxField,
  type CheckboxFieldProps as AriaCheckboxFieldProps,
  composeRenderProps,
} from "react-aria-components";
import { tv } from "tailwind-variants";

import { composeAriaClassName } from "../../utils/compose-aria-class-name";

const checkboxVariants = tv({
  base: [
    "group/checkbox flex cursor-pointer select-none items-center gap-1.5 text-sm",
    "data-disabled:cursor-not-allowed data-disabled:opacity-70",
  ],
});

const checkboxIndicatorVariants = tv({
  base: [
    "flex size-4.5 shrink-0 items-center justify-center rounded-md border border-border-strong bg-input text-white transition-all duration-200",
    "group-data-pressed/checkbox:scale-90",
    "group-data-focus-visible/checkbox:border-ring group-data-focus-visible/checkbox:outline-hidden group-data-focus-visible/checkbox:ring-2 group-data-focus-visible/checkbox:ring-ring-halo",
  ],
  variants: {
    isActive: {
      true: "inset-shadow-[0_1px_0_rgba(255,255,255,0.4)] border-cyan-800 bg-linear-to-b from-cyan-800 to-cyan-600",
    },
  },
});

function CheckboxIcon({
  isIndeterminate,
  isSelected,
}: {
  isIndeterminate: boolean;
  isSelected: boolean;
}) {
  if (isIndeterminate) {
    return <MinusIcon className="size-3" />;
  }
  if (isSelected) {
    return <CheckIcon className="size-3" />;
  }
  return null;
}

export interface CheckboxProps extends AriaCheckboxFieldProps {}

export function Checkbox({ className, children, ...props }: CheckboxProps) {
  return (
    <AriaCheckboxField {...props}>
      <AriaCheckboxButton className={composeAriaClassName(className, checkboxVariants())}>
        {composeRenderProps(children, (resolvedChildren, { isIndeterminate, isSelected }) => (
          <>
            <div className={checkboxIndicatorVariants({ isActive: isSelected || isIndeterminate })}>
              <CheckboxIcon isIndeterminate={isIndeterminate} isSelected={isSelected} />
            </div>
            {resolvedChildren}
          </>
        ))}
      </AriaCheckboxButton>
    </AriaCheckboxField>
  );
}
