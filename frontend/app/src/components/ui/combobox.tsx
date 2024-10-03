import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { classNames } from "@/utils/common";
import { Icon } from "@iconify-icon/react";
import React from "react";
import {
  Command,
  CommandEmpty,
  CommandInput,
  CommandItem,
  CommandList,
} from "@/components/ui/command";
import { PopoverTriggerProps } from "@radix-ui/react-popover";

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
            "h-10 flex items-center w-full rounded-md border border-gray-300 bg-white p-2 text-sm placeholder:text-gray-400 focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-inset focus-visible:ring-custom-blue-600 focus-visible:border-custom-blue-600 disabled:cursor-not-allowed disabled:bg-gray-100",
            className
          )}>
          {children}
          <Icon icon="mdi:unfold-more-horizontal" className="ml-auto text-gray-600 pl-2" />
        </button>
      </PopoverTrigger>
    );
  }
);

export const ComboboxContent = React.forwardRef<
  React.ElementRef<typeof PopoverContent>,
  React.ComponentPropsWithoutRef<typeof PopoverContent>
>(({ ...props }, ref) => {
  return <PopoverContent ref={ref} className={classNames("p-0")} portal={false} {...props} />;
});

export const ComboboxList = React.forwardRef<
  React.ElementRef<typeof CommandList>,
  React.ComponentPropsWithoutRef<typeof CommandList>
>(({ ...props }, ref) => {
  return (
    <Command
      style={{
        width: "var(--radix-popover-trigger-width)",
        maxHeight: "min(var(--radix-popover-content-available-height), 300px)",
      }}>
      <CommandInput placeholder="Filter..." />
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
        className={classNames("text-green-900", selectedValue !== props.value && "opacity-0")}
      />
      {children}
    </CommandItem>
  );
});

export const ComboboxEmpty = CommandEmpty;
