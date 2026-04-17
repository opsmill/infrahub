import { ChevronDownIcon } from "lucide-react";
import {
  Button as AriaButton,
  type ButtonProps as AriaButtonProps,
  ListBox as AriaListBox,
  type ListBoxProps as AriaListBoxProps,
  Select as AriaSelect,
  SelectValue as AriaSelectValue,
  composeRenderProps,
} from "react-aria-components";

import { ListBoxItem, type ListBoxItemProps } from "@/shared/components/aria/list-box";
import { Popover, type PopoverProps } from "@/shared/components/aria/popover";
import { focusVisibleStyle } from "@/shared/components/aria/style-rac";
import { inputStyle } from "@/shared/components/ui/style";
import { classNames } from "@/shared/utils/common";

export const Select = AriaSelect;

export const SelectTrigger = ({ className, children, ...props }: AriaButtonProps) => (
  <AriaButton
    className={composeRenderProps(className, (className) =>
      classNames(inputStyle, focusVisibleStyle, "gap-2", className)
    )}
    {...props}
  >
    <AriaSelectValue className="truncate data-placeholder:text-gray-400" />
    <ChevronDownIcon className="ml-auto size-4" />
  </AriaButton>
);

export const SelectPopover = ({ className, ...props }: PopoverProps) => (
  <Popover
    className={composeRenderProps(className, (className) =>
      classNames("min-w-(--trigger-width)", className)
    )}
    {...props}
  />
);

export const SelectList = <T extends object>({ ...props }: AriaListBoxProps<T>) => (
  <SelectPopover>
    <AriaListBox selectionMode="single" className="p-1" {...props} />
  </SelectPopover>
);

export const SelectItem = <T extends object>({ className, ...props }: ListBoxItemProps<T>) => {
  return (
    <ListBoxItem
      className={composeRenderProps(className, (className, { isSelected }) =>
        classNames(!isSelected && "pr-8", className)
      )}
      {...props}
    />
  );
};
