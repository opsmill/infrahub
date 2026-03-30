import { cellHeaderStyle, cellsStyle } from "@/shared/components/table/style";
import { classNames } from "@/shared/utils/common";

import type { AttributeSchema, RelationshipSchema } from "@/entities/schema/types";
import { FieldSchemaIcon } from "@/entities/schema/ui/field-schema-icon";

export interface TableColumnHeaderSimpleProps {
  columnSchema: AttributeSchema | RelationshipSchema;
  className?: string;
}

export function TableColumnHeaderSimple({ columnSchema, className }: TableColumnHeaderSimpleProps) {
  return (
    <div className={classNames(cellsStyle, cellHeaderStyle, "hover:bg-white", className)}>
      <FieldSchemaIcon fieldSchema={columnSchema} />
      <span className="mr-2 truncate">{columnSchema.label ?? columnSchema.name}</span>
    </div>
  );
}
