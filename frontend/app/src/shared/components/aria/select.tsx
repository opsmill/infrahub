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

import { ListBoxItem } from "@/shared/components/aria/list-box";
import { focusVisibleStyle } from "@/shared/components/style-rac";
import { inputStyle } from "@/shared/components/ui/style";
import { classNames } from "@/shared/utils/common";

import { Popover, type PopoverProps } from "./popover";

export const Select = AriaSelect;

export const SelectItem = ListBoxItem;

export const SelectTrigger = ({ className, children, ...props }: AriaButtonProps) => (
  <AriaButton
    className={composeRenderProps(className, (className) =>
      classNames(inputStyle, focusVisibleStyle, "gap-2", className)
    )}
    {...props}
  >
    <AriaSelectValue className="grow truncate data-placeholder:text-gray-400" />
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

export const SelectList = <T extends object>({ className, ...props }: AriaListBoxProps<T>) => (
  <SelectPopover>
    <AriaListBox
      className={composeRenderProps(className, (className) =>
        classNames(
          "max-h-[inherit] overflow-auto p-1 outline-hidden [clip-path:inset(0_0_0_0_round_calc(var(--radius)-2px))]",
          className
        )
      )}
      {...props}
    />
  </SelectPopover>
);
