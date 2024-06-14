import { Button, ButtonProps } from "@/components/buttons/button-primitive";
import { classNames } from "@/utils/common";
import { ComboboxOptionProps, Combobox as ComboboxPrimitive } from "@headlessui/react";
import { Icon } from "@iconify-icon/react";
import { PopoverTriggerProps } from "@radix-ui/react-popover";
import React, { forwardRef, ReactNode, useState } from "react";
import { Popover, PopoverContent, PopoverTrigger } from "./popover";
import { SearchInput } from "./search-input";

export interface ComboboxProps extends Omit<ButtonProps, "onChange"> {
  children?: React.ReactNode;
  placeholder?: string;
  items?: ComboboxListProps["items"];
  onChange?: (value: string) => void;
}

export const Combobox = forwardRef<HTMLButtonElement, ComboboxProps>(
  ({ value, onChange, items = [], ...props }, ref) => {
    const [open, setOpen] = React.useState(false);

    const handleChange = (v: unknown) => {
      if (onChange) onChange(v as string);
      setOpen(false);
    };

    return (
      <ComboboxPrimitive onChange={handleChange}>
        <Popover open={open} onOpenChange={setOpen}>
          <ComboboxTrigger ref={ref} {...props}>
            {value}
          </ComboboxTrigger>

          <ComboboxList items={items} onReset={handleChange} />
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
  items: Array<string | { value: any; label: string }>;
  onReset: (value: unknown) => void;
};

export const ComboboxList = ({ items, onReset }: ComboboxListProps) => {
  const [query, setQuery] = useState("");

  const filteredOptions =
    query === ""
      ? items
      : items
          .map((item) => (typeof item === "string" ? item : item.label))
          .filter((item) => item.toLowerCase().includes(query.toLowerCase()));

  return (
    <PopoverContent
      className="p-2 space-y-1 overflow-hidden flex flex-col"
      style={{
        width: "var(--radix-popover-trigger-width)",
        maxHeight: "min(var(--radix-popover-content-available-height), 264px)",
      }}>
      <div className="flex items-center gap-2">
        <div className="flex-grow">
          <ComboboxPrimitive.Input
            as={SearchInput}
            className="h-8 shrink-0"
            onChange={(event) => setQuery(event.target.value)}
          />
        </div>
        <Button size="sm" variant="ghost" onClick={() => onReset(null)}>
          Clear
        </Button>
      </div>

      {filteredOptions.length > 0 ? (
        <ComboboxPrimitive.Options static className="h-full overflow-auto">
          {filteredOptions.map((item) => {
            return typeof item === "string" ? (
              <ComboboxItem key={item} value={item}>
                {item}
              </ComboboxItem>
            ) : (
              <ComboboxItem key={item.label} value={item.value}>
                {item.label}
              </ComboboxItem>
            );
          })}
        </ComboboxPrimitive.Options>
      ) : (
        <div className="px-2 py-1.5 text-gray-600">Nothing found.</div>
      )}
    </PopoverContent>
  );
};

export const ComboboxItem = <T,>({
  className,
  children,
  ...props
}: ComboboxOptionProps<"li", T>) => {
  return (
    <ComboboxPrimitive.Option
      className={({ active, selected }) =>
        classNames(
          "px-2 py-1.5 rounded",
          selected && "bg-sky-100",
          active && "bg-gray-100",
          className
        )
      }
      {...props}>
      {({ selected }) => (
        <div className="flex justify-between items-center">
          {children as ReactNode}
          {selected && <Icon icon="mdi:check" />}
        </div>
      )}
    </ComboboxPrimitive.Option>
  );
};
