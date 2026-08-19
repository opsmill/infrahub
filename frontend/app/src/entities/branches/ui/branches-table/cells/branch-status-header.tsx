import { useState } from "react";

import { Icon } from "@/shared/components/display/icon";
import {
  cellHeaderInteractiveStyle,
  cellHeaderStyle,
  cellsStyle,
} from "@/shared/components/table/style";
import { Popover, PopoverContent, PopoverTrigger } from "@/shared/components/ui/popover";
import { classNames } from "@/shared/utils/common";

import { BRANCH_FIELD_SCHEMAS } from "@/entities/branches/ui/branches-table/branch-field-schemas";
import { BranchStatusFilterForm } from "@/entities/branches/ui/filters/branch-status-filter-form";
import { useFilters } from "@/entities/nodes/filters/ui/hooks/use-filters";
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
      <PopoverTrigger
        className={classNames(cellsStyle, cellHeaderStyle, cellHeaderInteractiveStyle)}
      >
        <FieldSchemaIcon fieldSchema={fieldSchema} />

        <span className="mr-2 truncate">{fieldSchema.label ?? fieldSchema.name}</span>
        <Icon
          icon="mdi:filter-variant"
          className={classNames(
            "ml-auto text-lg",
            currentColumnFilters ? "text-active" : "invisible"
          )}
        />
      </PopoverTrigger>

      <PopoverContent className="relative rounded-tl-none p-0" align="start">
        <div className="absolute -top-[1.8rem] -left-px rounded-t-md border border-b-0 bg-table-cell-pinned px-2 py-1 font-semibold">
          Filter by {fieldSchema.label ?? fieldSchema.name}
        </div>
        <BranchStatusFilterForm onSuccess={closePopover} />
      </PopoverContent>
    </Popover>
  );
}
