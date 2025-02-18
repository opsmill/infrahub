import { AttributeSchema, RelationshipSchema } from "@/entities/schema/types";
import { focusVisibleStyle } from "@/shared/components/style-rac";
import { Popover, PopoverContent, PopoverTrigger } from "@/shared/components/ui/popover";
import useFilters from "@/shared/hooks/useFilters";
import { classNames } from "@/shared/utils/common";
import { Icon } from "@iconify-icon/react";
import React, { useState } from "react";
import { Tag, TagProps } from "react-aria-components";
import { GlobalFilterForm } from "./global-filter-form";

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

  return (
    <Tag
      className={classNames(
        focusVisibleStyle,
        "group text-gray-600 text-sm whitespace-nowrap bg-neutral-100 rounded-full inline-flex items-center gap-1.5 pl-1 border border-gray-300 cursor-pointer",
        "data-[hovered]:bg-gray-100 data-[hovered]:border-custom-blue-700"
      )}
      textValue={`${label} contains ${currentFilter?.value}`}
      {...props}
    >
      <Popover open={showFilters} onOpenChange={setShowFilters}>
        <PopoverTrigger className="flex items-center h-6 pl-1">
          <span>{label}</span>

          <div className="w-px bg-gray-300 self-stretch ml-1" />

          {!currentFilter?.value && (
            <Icon
              icon="mdi:plus-circle-outline"
              className="text-base text-gray-400 group-hover:text-custom-blue-700 transition-all mx-1"
            />
          )}

          {currentFilter?.value && (
            <div
              className="flex items-center gap-1 h-6 rounded-r-full px-1 hover:bg-gray-300 transition-all"
              onClick={(event) => {
                event.stopPropagation();
                handleRemoveFilter(name);
              }}
            >
              <span className="text-custom-blue-700 font-medium inline-flex items-center">
                {currentFilter?.value}
              </span>

              <Icon
                icon="mdi:close-circle-outline"
                className="text-base text-gray-400 group-hover:text-custom-blue-700 transition-all"
              />
            </div>
          )}
        </PopoverTrigger>
        <PopoverContent className="relative rounded-tl-none">
          <div className="absolute -top-[1.8rem] bg-white border px-2 py-1 rounded-t-md border-b-0 -left-px">
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
    </Tag>
  );
}
