import { Icon } from "@iconify-icon/react";
import { useState } from "react";

import { cellHeaderStyle, cellsStyle } from "@/shared/components/table/style";
import { Popover, PopoverContent, PopoverTrigger } from "@/shared/components/ui/popover";
import useFilters from "@/shared/hooks/useFilters";
import { classNames } from "@/shared/utils/common";

import { BRANCH_FIELD_SCHEMAS } from "@/entities/branches/ui/branches-table/branch-field-schemas";
import { BranchStatusFilterForm } from "@/entities/branches/ui/filters/branch-status-filter-form";
import { FieldSchemaIcon } from "@/entities/schema/ui/field-schema-icon";

export function BranchStatusHeader() {
  const [filters] = useFilters();
  const [showFilters, setShowFilters] = useState(false);
  const fieldSchema = BRANCH_FIELD_SCHEMAS.status;
  const currentColumnFilters = filters.find((f) => f.name.startsWith(fieldSchema.name));

  const closePopover = () => {
    setShowFilters(false);
  };

  return (
    <Popover open={showFilters} onOpenChange={setShowFilters}>
      <PopoverTrigger className={classNames(cellsStyle, cellHeaderStyle)}>
        <FieldSchemaIcon fieldSchema={fieldSchema} />

        <span className="mr-2 truncate">{fieldSchema.label ?? fieldSchema.name}</span>
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
          Filter by {fieldSchema.label ?? fieldSchema.name}
        </div>
        <BranchStatusFilterForm onSuccess={closePopover} />
      </PopoverContent>
    </Popover>
  );
}
