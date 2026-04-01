import { Icon } from "@iconify-icon/react";

import { cellHeaderStyle, cellsStyle } from "@/shared/components/table/style";
import useFilters from "@/shared/hooks/useFilters";
import { classNames } from "@/shared/utils/common";

import type { AttributeSchema, RelationshipSchema } from "@/entities/schema/types";
import { FieldSchemaIcon } from "@/entities/schema/ui/field-schema-icon";

export interface TableColumnHeaderProps {
  columnSchema: AttributeSchema | RelationshipSchema;
  className?: string;
}

export function TableColumnHeader({ columnSchema, className }: TableColumnHeaderProps) {
  const [filters] = useFilters();
  const currentColumnFilters = filters.find((f) => f.name.startsWith(columnSchema.name));

  return (
    <div className={classNames(cellsStyle, cellHeaderStyle, className)}>
      <FieldSchemaIcon fieldSchema={columnSchema} />

      <span className="mr-2 truncate">{columnSchema.label ?? columnSchema.name}</span>
      <Icon
        icon="mdi:filter-variant"
        className={classNames(
          "ml-auto text-lg",
          currentColumnFilters ? "text-indigo-700" : "invisible"
        )}
      />
    </div>
  );
}
