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
import { Popover, type PopoverProps } from "../popover/popover";

export const selectTriggerVariants = tv({
  base: [
    "flex w-full items-center gap-2 rounded-lg border border-border-strong outline-none",
    "bg-input text-sm placeholder:text-subtle-muted",
    "disabled:cursor-not-allowed disabled:opacity-60",
    focusVisibleStyle,
  ],
  variants: {
    size: {
      sm: "h-8 px-2",
      md: "min-h-10 p-2",
    },
  },
  defaultVariants: {
    size: "md",
  },
});

export interface SelectTriggerProps
  extends Omit<AriaButtonProps, "children">,
    VariantProps<typeof selectTriggerVariants> {}

export function SelectTrigger({ className, size, ...props }: SelectTriggerProps) {
  return (
    <AriaButton
      className={composeAriaClassName(className, selectTriggerVariants({ size }))}
      {...props}
    >
      <AriaSelectValue className="truncate data-placeholder:text-subtle-muted" />
      <ChevronDownIcon className="ml-auto size-4" />
    </AriaButton>
  );
}

export interface SelectListProps<T> extends AriaListBoxProps<T>, Pick<PopoverProps, "width"> {}

export function SelectList<T extends object>({ width = "trigger", ...props }: SelectListProps<T>) {
  return (
    <Popover width={width}>
      <ListBox selectionMode="single" {...props} />
    </Popover>
  );
}

export function SelectItem<T extends object>({ className, ...props }: ListBoxItemProps<T>) {
  return (
    <ListBoxItem
      className={composeAriaClassName(className, ({ isSelected }) =>
        isSelected ? undefined : "pr-8"
      )}
      {...props}
    />
  );
}
