import { AttributeFilterForm } from "@/entities/nodes/object/ui/filters/attribute-filter-form";
import { RelationshipFilterForm } from "@/entities/nodes/object/ui/filters/relationship-filter-form";
import { TableColumnHeaderIcon } from "@/entities/nodes/object/ui/object-table/cells/table-column-header-icon";
import { AttributeSchema, ModelSchema, RelationshipSchema } from "@/entities/schema/types";
import { cellHeaderStyle, cellsStyle } from "@/shared/components/table/style";
import { Popover, PopoverContent, PopoverTrigger } from "@/shared/components/ui/popover";
import useFilters from "@/shared/hooks/useFilters";
import { classNames } from "@/shared/utils/common";
import { Icon } from "@iconify-icon/react";
import { PopoverTriggerProps } from "@radix-ui/react-popover";
import { useState } from "react";

export interface TableColumnHeaderProps extends PopoverTriggerProps {
  schema: ModelSchema;
  columnSchema: AttributeSchema | RelationshipSchema;
}

export function ProposedChangeTableFilter({
  schema,
  columnSchema,
  ...props
}: TableColumnHeaderProps) {
  const [filters] = useFilters();
  const [showFilters, setShowFilters] = useState(false);
  const currentColumnFilters = filters.find((f) => f.name.startsWith(columnSchema.name));

  const closePopover = () => {
    setShowFilters(false);
  };

  return (
    <Popover open={showFilters} onOpenChange={setShowFilters}>
      <PopoverTrigger
        className={classNames(cellsStyle, cellHeaderStyle, "border-0 transition-all rounded-sm")}
        {...props}
      >
        <TableColumnHeaderIcon fieldSchema={columnSchema} />

        <span className="truncate mr-1">{columnSchema.label ?? columnSchema.name}</span>
        <Icon
          icon="mdi:filter-variant"
          className={classNames(
            "text-lg ml-auto",
            currentColumnFilters ? "text-indigo-700" : "invisible"
          )}
        />
      </PopoverTrigger>

      <PopoverContent className="p-0 relative rounded-tl-none" align="start">
        <div className="absolute font-semibold -top-[1.8rem] bg-white border border-gray-200 px-2 py-1 rounded-t-md border-b-0 -left-px">
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
