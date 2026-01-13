import { cellHeaderStyle, cellsStyle } from "@/shared/components/table/style";
import { classNames } from "@/shared/utils/common";

import { TableColumnHeaderIcon } from "@/entities/nodes/object/ui/object-table/cells/table-column-header-icon";
import type { AttributeSchema, RelationshipSchema } from "@/entities/schema/types";

interface BranchTableHeaderProps {
  children: React.ReactNode;
  fieldSchema: AttributeSchema | RelationshipSchema;
  className?: string;
}

export function BranchTableHeader({ children, fieldSchema, className }: BranchTableHeaderProps) {
  return (
    <div className={classNames(cellsStyle, cellHeaderStyle, className)}>
      <TableColumnHeaderIcon fieldSchema={fieldSchema} />
      {children}
    </div>
  );
}
