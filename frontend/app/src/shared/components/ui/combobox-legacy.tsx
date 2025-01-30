import { Button } from "@/shared/components/buttons/button-primitive";
import { classNames } from "@/shared/utils/common";
import { Combobox as ComboboxPrimitive } from "@headlessui/react";
import { Icon } from "@iconify-icon/react";
import { useState } from "react";
import { Badge } from "./badge";
import { PopoverContent } from "./popover";
import { SearchInput } from "./search-input";

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
      onCloseAutoFocus={() => setQuery("")}
      className="p-2 space-y-2 overflow-hidden flex flex-col"
      style={{
        width: "var(--radix-popover-trigger-width)",
        maxHeight: "min(var(--radix-popover-content-available-height), 264px)",
      }}
    >
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
          {filteredOptions.map((item, index) => {
            return typeof item === "string" ? (
              <ComboboxItem key={item + index} item={item} />
            ) : (
              <ComboboxItem key={item.label + index} item={item} />
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
      value={item.value?.id || item.value}
    >
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
