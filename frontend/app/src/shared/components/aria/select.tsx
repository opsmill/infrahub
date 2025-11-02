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
import { focusVisibleStyle } from "@/shared/components/style-rac";
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
  className,
  children,
  ...props
}: AriaListBoxItemProps<T>) => {
  return (
    <AriaListBoxItem
      textValue={props.textValue || (typeof children === "string" ? children : undefined)}
      className={composeRenderProps(className, (className) =>
        classNames(
          "relative flex w-full cursor-default select-none items-center rounded-lg px-2 py-1.5 text-sm outline-hidden",
          "data-disabled:pointer-events-none data-disabled:opacity-50",
          "data-focused:bg-gray-100",
          "data-selection-mode:pl-8",
          className
        )
      )}
      {...props}
    >
      {composeRenderProps(children, (children, renderProps) => (
        <>
          {renderProps.isSelected && (
            <span className="absolute left-2 flex size-4 items-center justify-center">
              <CheckIcon className="size-3.5" />
            </span>
          )}
          {children}
        </>
      ))}
    </AriaListBoxItem>
  );
};
