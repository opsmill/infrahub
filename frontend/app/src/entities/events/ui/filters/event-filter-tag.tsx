import type React from "react";
import { useState } from "react";
import type { TagProps } from "react-aria-components";

import { Icon } from "@/shared/components/display/icon";
import { Popover, PopoverContent, PopoverTrigger } from "@/shared/components/ui/popover";

import type { Filter } from "@/entities/nodes/filters/domain/model/filter";

import { FilterTag } from "./global-filter-tag";

export interface EventFilterTagProps extends Omit<TagProps, "children"> {
  /** Name shown on the tag's trigger. */
  label: string;
  currentFilter?: Filter;
  /** Formats the filter value on the trigger; called only when the filter has a value. */
  renderValue: () => React.ReactNode;
  onRemove: () => void;
  renderForm: (close: () => void) => React.ReactNode;
  /** Name in the tag's accessible name, when it differs from `label`. */
  tagLabel?: string;
  /** Name in the "Filter by" tab above the form, when it differs from `label`. */
  tabLabel?: string;
}

export function EventFilterTag({
  label,
  currentFilter,
  renderValue,
  onRemove,
  renderForm,
  tagLabel = label,
  tabLabel = label,
  ...props
}: EventFilterTagProps) {
  const [isOpen, setIsOpen] = useState(false);

  const hasValue = currentFilter?.value !== undefined && currentFilter?.value !== null;

  return (
    <FilterTag currentFilter={currentFilter} label={tagLabel} {...props}>
      <Popover open={isOpen} onOpenChange={setIsOpen}>
        <PopoverTrigger className="flex h-6 items-center pl-1">
          <span>{label}</span>

          <div className="ml-1 w-px self-stretch bg-border-strong" />

          {hasValue ? (
            <div
              className="flex h-6 items-center gap-1 rounded-r-full px-1 transition-all hover:bg-highlight"
              onClick={(event) => {
                event.stopPropagation();
                onRemove();
              }}
            >
              <div className="inline-flex items-center font-medium text-accent">
                {renderValue()}
              </div>

              <Icon
                icon="mdi:close-circle-outline"
                className="text-base text-subtle-muted transition-all group-hover:text-accent"
              />
            </div>
          ) : (
            <Icon
              icon="mdi:plus-circle-outline"
              className="mx-1 text-base text-subtle-muted transition-all group-hover:text-accent"
            />
          )}
        </PopoverTrigger>

        <PopoverContent className="relative rounded-tl-none" align="start">
          <div className="absolute -top-filter-tab -left-px rounded-t-md border border-b-0 bg-input px-2 py-1">
            Filter by
            <span className="ml-1 font-semibold">{tabLabel}</span>
          </div>

          {renderForm(() => setIsOpen(false))}
        </PopoverContent>
      </Popover>
    </FilterTag>
  );
}
