import { ChevronDownIcon } from "lucide-react";
import {
  Button as AriaButton,
  type ButtonProps as AriaButtonProps,
  type ListBoxProps as AriaListBoxProps,
  SelectValue as AriaSelectValue,
} from "react-aria-components";
import { tv, type VariantProps } from "tailwind-variants";
export { Select } from "react-aria-components";

import { focusVisibleStyle } from "../../styles/focus-visible";
import { composeAriaClassName } from "../../utils/compose-aria-class-name";
import { ListBox, ListBoxItem, type ListBoxItemProps } from "../list-box/list-box";
import { Popover } from "../popover/popover";

const triggerStyles = tv({
  base: [
    "min-h-10 flex items-center gap-1 w-full rounded-xl shadow-[0_2px_4px_rgba(0,0,0,0.04)] bg-white p-2 pr-1.5 text-sm border border-neutral-200",
    "data-disabled:cursor-not-allowed data-disabled:bg-neutral-100 data-disabled:shadow-none",
    focusVisibleStyle,
  ],
  // Heights mirror the Button size scale so a trigger can line up with adjacent buttons.
  // The default (no size) keeps the existing min-h-10 input look.
  variants: {
    size: {
      xxs: "h-6 min-h-0 py-0",
      xs: "h-7 min-h-0 py-0",
      sm: "h-8 min-h-0 py-0",
      md: "h-9 min-h-0 py-0",
    },
  },
});

export interface SelectTriggerProps
  extends Omit<AriaButtonProps, "children">, VariantProps<typeof triggerStyles> {}

export function SelectTrigger({ className, size, ...props }: SelectTriggerProps) {
  return (
    <AriaButton className={composeAriaClassName(className, triggerStyles({ size }))} {...props}>
      <AriaSelectValue className="truncate data-placeholder:text-neutral-400" />
      <ChevronDownIcon className="ml-auto size-4" />
    </AriaButton>
  );
}

export interface SelectListProps<T> extends AriaListBoxProps<T> {
  matchTriggerWidth?: boolean;
}

export function SelectList<T extends object>({
  matchTriggerWidth = true,
  ...props
}: SelectListProps<T>) {
  return (
    <Popover matchTriggerWidth={matchTriggerWidth}>
      <ListBox selectionMode="single" {...props} />
    </Popover>
  );
}

export function SelectItem<T extends object>({ className, ...props }: ListBoxItemProps<T>) {
  return (
    <ListBoxItem
      className={composeAriaClassName(className, ({ isSelected }) =>
        isSelected ? undefined : "pr-8",
      )}
      {...props}
    />
  );
}
