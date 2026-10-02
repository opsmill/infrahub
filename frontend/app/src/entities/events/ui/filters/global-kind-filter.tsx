import type React from "react";
import { useState } from "react";
import type { TagProps } from "react-aria-components";

import { Icon } from "@/shared/components/display/icon";
import { Popover, PopoverContent, PopoverTrigger } from "@/shared/components/ui/popover";

import { useFilters } from "@/entities/nodes/filters/ui/hooks/use-filters";
import type { NodeCore } from "@/entities/nodes/object/domain/model/node";
import { getNodeLabel } from "@/entities/nodes/object/domain/rules/get-node-label";

import { FilterTag } from "./global-filter-tag";
import { GlobalKindFilterForm } from "./global-kind-filter-form";

interface FilterTagProps extends TagProps {
  label: React.ReactNode;
  name: string;
}

export function GlobalKindFilter({ label, name, ...props }: FilterTagProps) {
  const [filters, setFilters] = useFilters();
  const [showFilters, setShowFilters] = useState(false);

  const currentFilter = filters.find((filter) => filter.name.startsWith(name));

  const handleRemoveFilter = (filterName: string) => {
    setFilters(filters.filter((f) => f.name !== `${filterName}__value`));
  };

  const getFilterDisplayValue = () => {
    return currentFilter?.value
      .map((value: NodeCore) => {
        return getNodeLabel(value);
      })
      .join(", ");
  };

  return (
    <FilterTag currentFilter={currentFilter} label={label} {...props}>
      <Popover open={showFilters} onOpenChange={setShowFilters}>
        <PopoverTrigger className="flex h-6 items-center pl-1">
          <span>{label}</span>

          <div className="ml-1 w-px self-stretch bg-border-strong" />

          {(currentFilter?.value === undefined || currentFilter?.value === null) && (
            <Icon
              icon="mdi:plus-circle-outline"
              className="mx-1 text-base text-subtle-muted transition-all group-hover:text-accent"
            />
          )}

          {currentFilter?.value !== undefined && currentFilter?.value !== null && (
            <div
              className="flex h-6 items-center gap-1 rounded-r-full px-1 transition-all hover:bg-highlight"
              onClick={(event) => {
                event.stopPropagation();
                handleRemoveFilter(name);
              }}
            >
              <div className="inline-flex items-center font-medium text-accent">
                {getFilterDisplayValue()}
              </div>

              <Icon
                icon="mdi:close-circle-outline"
                className="text-base text-subtle-muted transition-all group-hover:text-accent"
              />
            </div>
          )}
        </PopoverTrigger>

        <PopoverContent className="relative rounded-tl-none" align="start">
          <div className="absolute -top-filter-tab -left-px rounded-t-md border border-b-0 bg-input px-2 py-1">
            Filter by
            <span className="ml-1 font-semibold">{label}</span>
          </div>

          <GlobalKindFilterForm
            name={name}
            onSuccess={() => {
              setShowFilters(false);
            }}
          />
        </PopoverContent>
      </Popover>
    </FilterTag>
  );
}
