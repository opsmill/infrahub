import { Button, ButtonProps } from "@/components/buttons/button-primitive";
import { classNames } from "@/utils/common";
import { Combobox as ComboboxPrimitive } from "@headlessui/react";
import { Icon } from "@iconify-icon/react";
import { PopoverTriggerProps } from "@radix-ui/react-popover";
import React, { forwardRef, useState } from "react";
import { Popover, PopoverContent, PopoverTrigger } from "./popover";
import { SearchInput } from "./search-input";
import { Badge } from "./badge";

export interface MultiComboboxProps extends Omit<ButtonProps, "onChange"> {
  children?: React.ReactNode;
  placeholder?: string;
  value: string[];
  items?: ComboboxListProps["items"];
  onChange?: (value: string[]) => void;
}

export const MultiCombobox = forwardRef<HTMLButtonElement, MultiComboboxProps>(
  ({ value = [], onChange, items = [], ...props }, ref) => {
    const [open, setOpen] = React.useState(false);

    const handleChange = (newValues: any[]) => {
      if (onChange) onChange(newValues);
    };

    const selectedValues = value.map((profile) => profile.id);
    const selectedItems = items.filter((item) => selectedValues.includes(item.value)) ?? [];

    return (
      <ComboboxPrimitive onChange={handleChange} multiple value={selectedValues}>
        <Popover open={open} onOpenChange={setOpen}>
          <ComboboxTrigger ref={ref} {...props}>
            <div className="flex flex-wrap gap-2">
              {selectedItems.map((item, index) => (
                <Badge key={index}>{item.label}</Badge>
              ))}
            </div>
          </ComboboxTrigger>

          <ComboboxList items={items} onReset={handleChange} />
        </Popover>
      </ComboboxPrimitive>
    );
  }
);

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

    const item = items.find((item) => item.value === value);

    return (
      <ComboboxPrimitive onChange={handleChange}>
        <Popover open={open} onOpenChange={setOpen}>
          <ComboboxTrigger ref={ref} {...props}>
            <div className="flex justify-between">
              {item?.label || value}
              {item?.badge && <Badge className="mr-2">{item.badge}</Badge>}
            </div>
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
          "min-h-10 p-2 flex justify-between items-center w-full rounded-md border border-gray-300 bg-custom-white text-sm focus:outline-none focus:ring-1 focus:ring-inset focus:ring-custom-blue-600 focus:border-custom-blue-600 disabled:cursor-not-allowed disabled:bg-gray-100",
          className
        )}
        {...props}>
        <div className="flex-grow">
          {children || <span className="text-gray-400 font-normal">{placeholder}</span>}
        </div>
        <Icon icon="mdi:unfold-more-horizontal" className="text-gray-600" />
      </PopoverTrigger>
    );
  }
);

type ComboboxListProps = {
  items: Array<tComboboxItem>;
  onReset: (value: unknown) => void;
};

export const ComboboxList = ({ items, onReset }: ComboboxListProps) => {
  const [query, setQuery] = useState("");

  const filteredOptions =
    query === ""
      ? items
      : items.filter((item) => {
          const matchLabel = item.label.toLowerCase().includes(query.toLowerCase());
          const matchValue = item.value?.toLowerCase?.()?.includes(query.toLowerCase());

          if (item.badge) {
            return (
              matchLabel || matchValue || item.badge.toLowerCase().includes(query.toLowerCase())
            );
          }

          return matchLabel || matchValue;
        });

  return (
    <PopoverContent
      className="p-2 space-y-2 overflow-hidden flex flex-col"
      style={{
        width: "var(--radix-popover-trigger-width)",
        maxHeight: "min(var(--radix-popover-content-available-height), 264px)",
      }}>
      <div className="flex items-center gap-2">
        <div className="flex-grow">
          <ComboboxPrimitive.Input
            as={SearchInput}
            value={query}
            className="h-8 shrink-0"
            onChange={(event) => setQuery(event.target.value)}
          />
        </div>
        <Button size="sm" variant="ghost" onClick={() => onReset("")}>
          Clear
        </Button>
      </div>

      {filteredOptions.length > 0 ? (
        <ComboboxPrimitive.Options static className="h-full overflow-auto">
          {filteredOptions.map((item) => {
            return typeof item === "string" ? (
              <ComboboxItem key={item} item={item} />
            ) : (
              <ComboboxItem key={item.label} item={item} />
            );
          })}
        </ComboboxPrimitive.Options>
      ) : (
        <div className="px-2 py-1.5 text-gray-600">Nothing found.</div>
      )}
    </PopoverContent>
  );
};

export type tComboboxItem = { value: any; label: string; badge?: string };

type ComboboxItemProps = {
  className?: string;
  item: tComboboxItem;
};

export const ComboboxItem = ({ className, item }: ComboboxItemProps) => {
  return (
    <ComboboxPrimitive.Option
      className={({ active, selected }) =>
        classNames(
          "px-2 py-1.5 rounded mb-2 last:mb-0 cursor-pointer",
          selected && "bg-sky-100",
          active && "bg-gray-100",
          className
        )
      }
      value={item.value?.id || item.value}>
      {({ selected }) => (
        <div className="flex justify-between items-center">
          {item.label}
          <div className="flex">
            {item.badge && <Badge className="mr-2">{item.badge}</Badge>}

            <div className="w-6">{selected && <Icon icon="mdi:check" />}</div>
          </div>
        </div>
      )}
    </ComboboxPrimitive.Option>
  );
};
