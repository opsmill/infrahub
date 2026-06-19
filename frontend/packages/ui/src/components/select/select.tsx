import { ChevronDownIcon } from "lucide-react";
import {
  Button as AriaButton,
  type ButtonProps as AriaButtonProps,
  type ListBoxProps as AriaListBoxProps,
  SelectValue as AriaSelectValue,
} from "react-aria-components";
import { tv } from "tailwind-variants";
export { Select } from "react-aria-components";

import { focusVisibleStyle } from "../../styles/focus-visible";
import { composeAriaClassName } from "../../utils/compose-aria-class-name";
import { ListBox, ListBoxItem, type ListBoxItemProps } from "../list-box/list-box";
import { Popover } from "../popover/popover";

const triggerStyles = tv({
  base: [
    "flex min-h-10 w-full items-center gap-2 rounded-lg border border-neutral-300 outline-none",
    "bg-white p-2 text-sm placeholder:text-neutral-400",
    "disabled:cursor-not-allowed disabled:bg-neutral-100",
    focusVisibleStyle,
  ],
});

export function SelectTrigger({ className, ...props }: Omit<AriaButtonProps, "children">) {
  return (
    <AriaButton className={composeAriaClassName(className, triggerStyles())} {...props}>
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
  className,
  ...props
}: SelectListProps<T>) {
  return (
    <Popover matchTriggerWidth={matchTriggerWidth}>
      <ListBox
        selectionMode="single"
        className={composeAriaClassName(className, "p-1")}
        {...props}
      />
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
