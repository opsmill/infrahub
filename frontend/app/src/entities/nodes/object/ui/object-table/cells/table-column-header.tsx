import { Icon } from "@iconify-icon/react";
import type { PopoverTriggerProps } from "@radix-ui/react-popover";
import { useState } from "react";

import { cellHeaderStyle, cellsStyle } from "@/shared/components/table/style";
import { Popover, PopoverContent, PopoverTrigger } from "@/shared/components/ui/popover";
import useFilters from "@/shared/hooks/useFilters";
import { classNames } from "@/shared/utils/common";

import { AttributeFilterForm } from "@/entities/nodes/object/ui/filters/attribute-filter-form";
import { RelationshipFilterForm } from "@/entities/nodes/object/ui/filters/relationship-filter-form";
import type { AttributeSchema, RelationshipSchema } from "@/entities/schema/types";
import { FieldSchemaIcon } from "@/entities/schema/ui/field-schema-icon";

export interface TableColumnHeaderProps extends PopoverTriggerProps {
  columnSchema: AttributeSchema | RelationshipSchema;
  className?: string;
}

export function TableColumnHeader({ columnSchema, className, ...props }: TableColumnHeaderProps) {
  const [filters] = useFilters();
  const [showFilters, setShowFilters] = useState(false);
  const currentColumnFilters = filters.find((f) => f.name.startsWith(columnSchema.name));

  const closePopover = () => {
    setShowFilters(false);
  };

  return (
    <Popover open={showFilters} onOpenChange={setShowFilters}>
      <PopoverTrigger className={classNames(cellsStyle, cellHeaderStyle, className)} {...props}>
        <FieldSchemaIcon fieldSchema={columnSchema} />

        <span className="mr-2 truncate">{columnSchema.label ?? columnSchema.name}</span>
        <Icon
          icon="mdi:filter-variant"
          className={classNames(
            "ml-auto text-lg",
            currentColumnFilters ? "text-indigo-700" : "invisible"
          )}
        />
      </PopoverTrigger>

      <PopoverContent className="relative rounded-tl-none p-0" align="start">
        <div className="absolute -top-[1.8rem] -left-px rounded-t-md border border-gray-200 border-b-0 bg-white px-2 py-1 font-semibold">
          Filter by {columnSchema.label ?? columnSchema.name}
        </div>
        {"peer" in columnSchema ? (
          <RelationshipFilterForm relationshipSchema={columnSchema} onSuccess={closePopover} />
        ) : (
          <AttributeFilterForm attributeSchema={columnSchema} onSuccess={closePopover} />
        )}
      </PopoverContent>
    </Popover>
  );
}
