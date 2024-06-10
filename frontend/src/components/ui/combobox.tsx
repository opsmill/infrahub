import { ButtonProps } from "@/components/buttons/button-primitive";
import { classNames } from "@/utils/common";
import { ComboboxOptionProps, Combobox as ComboboxPrimitive } from "@headlessui/react";
import { Icon } from "@iconify-icon/react";
import { PopoverTriggerProps } from "@radix-ui/react-popover";
import React, { forwardRef, useState } from "react";
import { Popover, PopoverContent, PopoverTrigger } from "./popover";
import { SearchInput } from "./search-input";

interface ComboboxProps extends Omit<ButtonProps, "onChange"> {
  children?: React.ReactNode;
  placeholder?: string;
  items?: Array<string>;
  onChange?: (value: string) => void;
}

export const Combobox = forwardRef<HTMLButtonElement, ComboboxProps>(
  ({ value, onChange, items = [], ...props }, ref) => {
    const [open, setOpen] = React.useState(false);

    return (
      <ComboboxPrimitive
        onChange={(value: string) => {
          if (onChange) onChange(value);
          setOpen(false);
        }}>
        <Popover open={open} onOpenChange={setOpen}>
          <ComboboxTrigger ref={ref} {...props}>
            {value}
          </ComboboxTrigger>

          <ComboboxList items={items} />
        </Popover>
      </ComboboxPrimitive>
    );
  }
);

interface ComboboxTriggerProps extends PopoverTriggerProps {
  value?: string;
  placeholder?: string;
}

export const ComboboxTrigger = forwardRef<HTMLButtonElement, ComboboxTriggerProps>(
  ({ className, children, placeholder, ...props }, ref) => {
    return (
      <PopoverTrigger
        ref={ref}
        role="combobox"
        className={classNames(
          "h-10 px-2 flex justify-between items-center w-full rounded-md border border-gray-300 bg-custom-white text-sm focus:outline-none focus:ring-1 focus:ring-inset focus:ring-custom-blue-600 focus:border-custom-blue-600 disabled:cursor-not-allowed disabled:bg-gray-100",
          className
        )}
        {...props}>
        {children || <span className="text-gray-400 font-normal">{placeholder}</span>}
        <Icon icon="mdi:unfold-more-horizontal" className="text-gray-600" />
      </PopoverTrigger>
    );
  }
);

type ComboboxListProps = {
  items: Array<string>;
};

export const ComboboxList = ({ items }: ComboboxListProps) => {
  const [query, setQuery] = useState("");

  const filteredOptions =
    query === "" ? items : items.filter((item) => item.toLowerCase().includes(query.toLowerCase()));

  return (
    <PopoverContent
      className="p-2 space-y-1 overflow-hidden flex flex-col w-"
      style={{
        width: "var(--radix-popover-trigger-width)",
        maxHeight: "min(var(--radix-popover-content-available-height), 264px)",
      }}>
      <ComboboxPrimitive.Input
        as={SearchInput}
        className="h-8 shrink-0"
        onChange={(event) => setQuery(event.target.value)}
      />

      {filteredOptions.length > 0 ? (
        <ComboboxPrimitive.Options static className="h-full overflow-auto">
          {filteredOptions.map((item) => (
            <ComboboxItem key={item} value={item}>
              {item}
            </ComboboxItem>
          ))}
        </ComboboxPrimitive.Options>
      ) : (
        <div className="px-2 py-1.5 text-gray-600">Nothing found.</div>
      )}
    </PopoverContent>
  );
};

export const ComboboxItem = <T,>({ className, ...props }: ComboboxOptionProps<"li", T>) => {
  return (
    <ComboboxPrimitive.Option
      className={({ active, selected }) =>
        classNames(
          "px-2 py-1.5 rounded",
          active && "bg-gray-100",
          selected && "bg-sky-100",
          className
        )
      }
      {...props}
    />
  );
};
