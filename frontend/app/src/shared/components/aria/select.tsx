import { CheckIcon, ChevronDownIcon } from "lucide-react";
import {
  Button as AriaButton,
  type ButtonProps as AriaButtonProps,
  ListBox as AriaListBox,
  ListBoxItem as AriaListBoxItem,
  type ListBoxItemProps as AriaListBoxItemProps,
  type ListBoxProps as AriaListBoxProps,
  Select as AriaSelect,
  SelectValue as AriaSelectValue,
  composeRenderProps,
} from "react-aria-components";

import { Popover, type PopoverProps } from "@/shared/components/aria/popover";
import { disabledStyle, focusVisibleStyle } from "@/shared/components/aria/style-rac";
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

export const SelectItem = <T extends object>({
  children,
  className,
  textValue,
  ...props
}: AriaListBoxItemProps<T>) => {
  return (
    <AriaListBoxItem
      textValue={textValue ?? (typeof children === "string" ? children : undefined)}
      className={composeRenderProps(className, (className) =>
        classNames(
          disabledStyle,
          "relative flex w-full select-none items-center rounded-lg px-2 py-1.5 text-sm outline-hidden",
          "data-focused:bg-stone-100",
          "data-selection-mode:pl-8",
          className
        )
      )}
      {...props}
    >
      {composeRenderProps(children, (children, { isSelected }) => (
        <>
          {isSelected && <CheckIcon className="absolute left-2 size-4" />}
          {children}
        </>
      ))}
    </AriaListBoxItem>
  );
};
