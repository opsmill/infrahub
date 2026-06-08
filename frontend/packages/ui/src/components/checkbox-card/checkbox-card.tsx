import { CheckIcon } from "lucide-react";
import {
  CheckboxButton as AriaCheckboxButton,
  CheckboxField as AriaCheckboxField,
  type CheckboxFieldProps as AriaCheckboxFieldProps,
  composeRenderProps,
} from "react-aria-components";
import { tv } from "tailwind-variants";

import { focusVisibleStyle } from "../../styles/focus-visible";
import { composeAriaClassName } from "../../utils/compose-aria-class-name";

const checkboxCardVariants = tv({
  base: [
    focusVisibleStyle,
    "group/checkbox-card relative flex cursor-pointer items-center gap-3 rounded-lg border border-neutral-300 bg-white px-3 py-2 text-neutral-600 text-sm transition-all",
    "data-disabled:cursor-not-allowed data-disabled:opacity-60",
  ],
  variants: {
    isSelected: {
      true: [
        "inset-shadow-[0_1px_0_rgba(255,255,255,0.9)] bg-gradient-to-b from-stone-100 to-white text-neutral-800 shadow-xs",
      ],
    },
  },
});

const checkboxCardIndicatorVariants = tv({
  base: "flex size-4 shrink-0 items-center justify-center rounded-full border border-neutral-300 bg-white text-white transition-colors",
  variants: {
    isSelected: {
      true: "border-cyan-700 bg-cyan-700",
    },
  },
});

export interface CheckboxCardProps extends AriaCheckboxFieldProps {}

export function CheckboxCard({ className, children, ...props }: CheckboxCardProps) {
  return (
    <AriaCheckboxField {...props}>
      <AriaCheckboxButton
        className={composeAriaClassName(className, ({ isSelected }) =>
          checkboxCardVariants({ isSelected }),
        )}
      >
        {composeRenderProps(children, (resolvedChildren, { isSelected }) => (
          <>
            <span className={checkboxCardIndicatorVariants({ isSelected })} aria-hidden="true">
              {isSelected && <CheckIcon className="size-2.5" />}
            </span>
            <span>{resolvedChildren}</span>
          </>
        ))}
      </AriaCheckboxButton>
    </AriaCheckboxField>
  );
}
