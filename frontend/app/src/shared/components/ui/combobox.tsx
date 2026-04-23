import { Icon } from "@iconify-icon/react";
import type { PopoverTriggerProps } from "@radix-ui/react-popover";
import type React from "react";

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
    React.HTMLAttributes<HTMLButtonElement> {
  ref?: React.Ref<HTMLButtonElement>;
}

export const ComboboxTrigger = ({ children, className, ref, ...props }: ComboboxTriggerProps) => {
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
        <Icon icon="mdi:unfold-more-horizontal" className="ml-auto pl-2 text-gray-600" />
      </button>
    </PopoverTrigger>
  );
};

interface ComboboxContentProps extends React.ComponentProps<typeof PopoverContent> {
  fitTriggerWidth?: boolean;
}

export const ComboboxContent = ({
  className,
  fitTriggerWidth = true,
  style,
  ref,
  ...props
}: ComboboxContentProps) => {
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
};

export interface ComboboxListProps extends React.ComponentProps<typeof CommandList> {
  shouldFilter?: boolean;
  onValueChange?: (search: string) => void;
}

export const ComboboxList = ({
  shouldFilter,
  className,
  autoFocus,
  onValueChange,
  ref,
  ...props
}: ComboboxListProps) => {
  return (
    <Command shouldFilter={shouldFilter} className={className}>
      <CommandInput placeholder="Filter..." autoFocus={autoFocus} onValueChange={onValueChange} />
      <CommandList ref={ref} {...props} />
    </Command>
  );
};

interface ComboboxItemProps extends React.ComponentProps<typeof CommandItem> {
  selectedValue?: string | null;
  value: string;
}

export const ComboboxItem = ({ children, selectedValue, ref, ...props }: ComboboxItemProps) => {
  return (
    <CommandItem ref={ref} {...props}>
      <Icon
        icon="mdi:check"
        className={classNames("text-green-900", selectedValue !== props.value && "w-3.5 opacity-0")}
      />
      {children}
    </CommandItem>
  );
};

export const ComboboxEmpty = CommandEmpty;
