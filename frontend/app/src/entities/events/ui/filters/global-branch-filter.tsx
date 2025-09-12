import { Icon } from "@iconify-icon/react";
import React, { useEffect, useState } from "react";
import { TagProps } from "react-aria-components";
import { useQueryParam } from "use-query-params";

import { QSP } from "@/config/qsp";

import { Popover, PopoverContent, PopoverTrigger } from "@/shared/components/ui/popover";
import useFilters from "@/shared/hooks/useFilters";

import { AttributeSchema, RelationshipSchema } from "@/entities/schema/types";

import { GlobalFilterForm } from "./global-filter-form";
import { FilterTag } from "./global-filter-tag";

interface FilterTagProps extends TagProps {
  label: React.ReactNode;
  name: string;
  fieldSchema: AttributeSchema | RelationshipSchema;
}

export function GlobalBranchFilter({ label, name, fieldSchema, ...props }: FilterTagProps) {
  const [filters, setFilters] = useFilters();
  const [branch] = useQueryParam(QSP.BRANCH);
  const [showFilters, setShowFilters] = useState(false);

  const currentFilter = filters.find((filter) => filter.name.startsWith(name));

  const handleRemoveFilter = () => {
    setFilters([...filters, { name: "branches__value", value: null }]);
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
          return value.display_label;
        })
        .join(", ");
    }

    return currentFilter?.value;
  };

  useEffect(() => {
    if (!branch || branch === "main") return;

    if (currentFilter?.value === null) return;

    // Set the current branch if it's not main and if it has not been removed from the filters
    setFilters([...filters, { name: "branches__value", value: branch }]);
  }, []);

  return (
    <FilterTag label="branches" currentFilter={currentFilter} {...props}>
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
                handleRemoveFilter();
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
          <div className="-top-[1.8rem] -left-px absolute rounded-t-md border border-gray-200 border-b-0 bg-white px-2 py-1">
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
