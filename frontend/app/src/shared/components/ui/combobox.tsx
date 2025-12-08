import { Icon } from "@iconify-icon/react";
import type { PopoverTriggerProps } from "@radix-ui/react-popover";
import React from "react";

import {
  Command,
  CommandEmpty,
  CommandInput,
  CommandItem,
  CommandList,
} from "@/shared/components/ui/command";
import { Popover, PopoverContent, PopoverTrigger } from "@/shared/components/ui/popover";
import { inputStyle } from "@/shared/components/ui/style";
import { classNames } from "@/shared/utils/common";

export const Combobox = Popover;

export interface ComboboxTriggerProps
  extends PopoverTriggerProps,
    React.HTMLAttributes<HTMLButtonElement> {}

export const ComboboxTrigger = React.forwardRef<HTMLButtonElement, ComboboxTriggerProps>(
  ({ children, className, ...props }, ref) => {
    return (
      <PopoverTrigger asChild ref={ref} {...props}>
        <button
          type="button"
          role="combobox"
          className={classNames(
            inputStyle,
            "focus:border-custom-blue-600 focus:outline-hidden focus:ring-2 focus:ring-custom-blue-600/25",
            className
          )}
        >
          {children}
          <Icon
            icon="mdi:unfold-more-horizontal"
            className="ml-auto pl-2 text-gray-600 dark:text-slate-400"
          />
        </button>
      </PopoverTrigger>
    );
  }
);

export const ComboboxContent = React.forwardRef<
  React.ElementRef<typeof PopoverContent>,
  React.ComponentPropsWithoutRef<typeof PopoverContent> & { fitTriggerWidth?: boolean }
>(({ className, fitTriggerWidth = true, style, ...props }, ref) => {
  return (
    <PopoverContent
      ref={ref}
      className={classNames("p-0", className)}
      align="start"
      portal={false}
      style={{
        ...(fitTriggerWidth
          ? { width: "var(--radix-popover-trigger-width)" }
          : { minWidth: "var(--radix-popover-trigger-width)" }),
        ...style,
      }}
      {...props}
    />
  );
});

export interface ComboboxListProps extends React.ComponentPropsWithoutRef<typeof CommandList> {
  shouldFilter?: boolean;
  onValueChange?: (search: string) => void;
}

export const ComboboxList = React.forwardRef<
  React.ElementRef<typeof CommandList>,
  ComboboxListProps
>(({ shouldFilter, className, autoFocus, onValueChange, ...props }, ref) => {
  return (
    <Command shouldFilter={shouldFilter} className={className}>
      <CommandInput placeholder="Filter..." autoFocus={autoFocus} onValueChange={onValueChange} />
      <CommandList ref={ref} {...props} />
    </Command>
  );
});

export const ComboboxItem = React.forwardRef<
  React.ElementRef<typeof CommandItem>,
  React.ComponentPropsWithoutRef<typeof CommandItem> & {
    selectedValue?: string | null;
    value: string;
  }
>(({ children, selectedValue, ...props }, ref) => {
  return (
    <CommandItem ref={ref} {...props}>
      <Icon
        icon="mdi:check"
        className={classNames(
          "text-green-900 dark:text-green-400",
          selectedValue !== props.value && "w-3.5 opacity-0"
        )}
      />
      {children}
    </CommandItem>
  );
});

export const ComboboxEmpty = CommandEmpty;
