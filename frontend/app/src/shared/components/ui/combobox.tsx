import { Icon } from "@iconify-icon/react";
import type { PopoverTriggerProps } from "@radix-ui/react-popover";
import type React from "react";
import { useState } from "react";

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
  placeholder?: string;
  /**
   * The item `value` that should be ACTIVE (highlighted + scrolled into view) when the
   * list first mounts — pass the currently-selected option here. Without it cmdk seeds
   * its active item to the FIRST option on open, so a value selected further down the
   * list (e.g. a timezone) is neither highlighted nor scrolled to. Must be the exact
   * same string used as the matching item's `value`: cmdk matches the active item on the
   * trimmed value case-SENSITIVELY (only its fuzzy search filter lowercases), so
   * mixed-case values like "Europe/Paris" or "ISO_DATETIME" line up as-is.
   */
  activeValue?: string | null;
}

export const ComboboxList = ({
  shouldFilter,
  className,
  autoFocus,
  onValueChange,
  placeholder = "Filter...",
  activeValue,
  ref,
  ...props
}: ComboboxListProps) => {
  // Drive cmdk's active item as a controlled value so the selected option starts
  // highlighted/scrolled-in. It's seeded from `activeValue` but kept in local state and
  // updated via `onValueChange` so keyboard/pointer navigation still moves the highlight;
  // a purely-static controlled value would freeze cmdk's internal navigation. Undefined
  // when no `activeValue` is given, preserving the previous uncontrolled behaviour for the
  // many call sites that don't opt in.
  const [activeItemValue, setActiveItemValue] = useState<string | undefined>(
    activeValue ?? undefined
  );
  return (
    <Command
      shouldFilter={shouldFilter}
      className={className}
      value={activeValue == null ? undefined : activeItemValue}
      onValueChange={activeValue == null ? undefined : setActiveItemValue}
    >
      <CommandInput placeholder={placeholder} autoFocus={autoFocus} onValueChange={onValueChange} />
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
