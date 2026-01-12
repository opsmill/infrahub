import { cellHeaderStyle, cellsStyle } from "@/shared/components/table/style";
import { classNames } from "@/shared/utils/common";

import { TableColumnHeaderIcon } from "@/entities/nodes/object/ui/object-table/cells/table-column-header-icon";
import type { AttributeSchema, RelationshipSchema } from "@/entities/schema/types";

export interface TableColumnHeaderSimpleProps {
  columnSchema: AttributeSchema | RelationshipSchema;
  className?: string;
}

export function TableColumnHeaderSimple({ columnSchema, className }: TableColumnHeaderSimpleProps) {
  return (
    <div className={classNames(cellsStyle, cellHeaderStyle, className)}>
      <TableColumnHeaderIcon fieldSchema={columnSchema} />
      <span className="mr-2 truncate">{columnSchema.label ?? columnSchema.name}</span>
    </div>
  );
}
