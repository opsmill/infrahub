import { Icon } from "@iconify-icon/react";
import type React from "react";
import { useState } from "react";
import type { TagProps } from "react-aria-components";

import { Popover, PopoverContent, PopoverTrigger } from "@/shared/components/ui/popover";
import useFilters from "@/shared/hooks/useFilters";

import { getNodeLabel } from "@/entities/nodes/object/utils/get-node-label";
import type { AttributeSchema, RelationshipSchema } from "@/entities/schema/types";

import { GlobalFilterForm } from "./global-filter-form";
import { FilterTag } from "./global-filter-tag";

interface FilterTagProps extends TagProps {
  label: React.ReactNode;
  name: string;
  fieldSchema: AttributeSchema | RelationshipSchema;
}

export function GlobalFilter({ label, name, fieldSchema, ...props }: FilterTagProps) {
  const [filters, setFilters] = useFilters();
  const [showFilters, setShowFilters] = useState(false);

  const currentFilter = filters.find((filter) => filter.name.startsWith(name));

  const handleRemoveFilter = (filterName: string) => {
    setFilters(filters.filter((f) => f.name !== `${filterName}__value`));
  };

  const getFilterDisplayValue = () => {
    if (typeof currentFilter?.value === "boolean") {
      return JSON.stringify(currentFilter?.value);
    }

    if (fieldSchema.kind === "Dropdown") {
      return fieldSchema.choices?.find((choice) => {
        return choice.name === currentFilter?.value;
      })?.label;
    }

    if (Array.isArray(currentFilter?.value)) {
      return currentFilter?.value
        .map((value) => {
          return getNodeLabel(value);
        })
        .join(", ");
    }

    return currentFilter?.value;
  };

  return (
    <FilterTag currentFilter={currentFilter} label={label} {...props}>
      <Popover open={showFilters} onOpenChange={setShowFilters}>
        <PopoverTrigger className="flex h-6 items-center pl-1">
          <span>{label}</span>

          <div className="ml-1 w-px self-stretch bg-gray-300" />

          {(currentFilter?.value === undefined || currentFilter?.value === null) && (
            <Icon
              icon="mdi:plus-circle-outline"
              className="mx-1 text-base text-gray-400 transition-all group-hover:text-custom-blue-700"
            />
          )}

          {currentFilter?.value !== undefined && currentFilter?.value !== null && (
            <div
              className="flex h-6 items-center gap-1 rounded-r-full px-1 transition-all hover:bg-gray-300"
              onClick={(event) => {
                event.stopPropagation();
                handleRemoveFilter(name);
              }}
            >
              <div className="inline-flex items-center font-medium text-custom-blue-700">
                {getFilterDisplayValue()}
              </div>

              <Icon
                icon="mdi:close-circle-outline"
                className="text-base text-gray-400 transition-all group-hover:text-custom-blue-700"
              />
            </div>
          )}
        </PopoverTrigger>
        <PopoverContent className="relative rounded-tl-none" align="start">
          <div className="absolute -top-[1.8rem] -left-px rounded-t-md border border-gray-200 border-b-0 bg-white px-2 py-1">
            Filter by
            <span className="ml-1 font-semibold">{label}</span>
          </div>

          <GlobalFilterForm
            name={name}
            fieldSchema={fieldSchema}
            onSuccess={() => {
              setShowFilters(false);
            }}
          />
        </PopoverContent>
      </Popover>
    </FilterTag>
  );
}
