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
    "group/checkbox-card relative flex cursor-pointer items-center gap-3 rounded-lg border border-border-strong bg-input px-3 py-2 text-foreground-muted text-sm transition-all",
    "data-disabled:cursor-not-allowed data-disabled:opacity-60",
    "data-pressed:scale-97 data-pressed:shadow-none data-pressed:duration-75",
  ],
  variants: {
    isSelected: {
      true: [
        "inset-shadow-[0_1px_0_rgba(255,255,255,0.9)] bg-gradient-to-b from-stone-100 to-white text-foreground shadow-xs",
        "dark:inset-shadow-[0_1px_0_rgba(255,255,255,0.08)] dark:from-white/10 dark:to-white/5 dark:shadow-none",
      ],
    },
  },
});

const checkboxCardIndicatorVariants = tv({
  base: "flex size-4 shrink-0 items-center justify-center rounded-full border border-border-strong bg-input text-white transition-all",
  variants: {
    isSelected: {
      true: "inset-shadow-[0_1px_0_rgba(255,255,255,0.4)] border-cyan-800 bg-linear-to-b from-cyan-800 to-cyan-600",
    },
  },
});

export interface CheckboxCardProps extends AriaCheckboxFieldProps {}

export function CheckboxCard({ className, children, ...props }: CheckboxCardProps) {
  return (
    <AriaCheckboxField {...props}>
      <AriaCheckboxButton
        className={composeAriaClassName(className, ({ isSelected }) =>
          checkboxCardVariants({ isSelected })
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
