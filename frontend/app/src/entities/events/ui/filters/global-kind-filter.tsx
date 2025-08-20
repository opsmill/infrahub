import { AttributeSchema, RelationshipSchema } from "@/entities/schema/types";
import { Popover, PopoverContent, PopoverTrigger } from "@/shared/components/ui/popover";
import useFilters from "@/shared/hooks/useFilters";
import { Icon } from "@iconify-icon/react";
import React, { useState } from "react";
import { TagProps } from "react-aria-components";
import { FilterTag } from "./global-filter-tag";
import { GlobalKindFilterForm } from "./global-kind-filter-form";

interface FilterTagProps extends TagProps {
  label: React.ReactNode;
  name: string;
  fieldSchema: AttributeSchema | RelationshipSchema;
}

export function GlobalKindFilter({ label, name, fieldSchema, ...props }: FilterTagProps) {
  const [filters, setFilters] = useFilters();
  const [showFilters, setShowFilters] = useState(false);

  const currentFilter = filters.find((filter) => filter.name.startsWith(name));

  const handleRemoveFilter = (filterName: string) => {
    setFilters(filters.filter((f) => f.name !== `${filterName}__value`));
  };

  const getFilterDisplayValue = () => {
    return currentFilter?.value
      .map((value) => {
        return value.display_label;
      })
      .join(", ");
  };

  return (
    <FilterTag currentFilter={currentFilter} label={label} {...props}>
      <Popover open={showFilters} onOpenChange={setShowFilters}>
        <PopoverTrigger className="flex items-center h-6 pl-1">
          <span>{label}</span>

          <div className="w-px bg-gray-300 self-stretch ml-1" />

          {(currentFilter?.value === undefined || currentFilter?.value === null) && (
            <Icon
              icon="mdi:plus-circle-outline"
              className="text-base text-gray-400 group-hover:text-custom-blue-700 transition-all mx-1"
            />
          )}

          {currentFilter?.value !== undefined && currentFilter?.value !== null && (
            <div
              className="flex items-center gap-1 h-6 rounded-r-full px-1 hover:bg-gray-300 transition-all"
              onClick={(event) => {
                event.stopPropagation();
                handleRemoveFilter(name);
              }}
            >
              <div className="text-custom-blue-700 font-medium inline-flex items-center">
                {getFilterDisplayValue()}
              </div>

              <Icon
                icon="mdi:close-circle-outline"
                className="text-base text-gray-400 group-hover:text-custom-blue-700 transition-all"
              />
            </div>
          )}
        </PopoverTrigger>

        <PopoverContent className="relative rounded-tl-none" align="start">
          <div className="absolute -top-[1.8rem] bg-white border border-gray-200 px-2 py-1 rounded-t-md border-b-0 -left-px">
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
