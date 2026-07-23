import { cellHeaderStyle, cellsStyle } from "@/shared/components/table/style";
import { classNames } from "@/shared/utils/common";

import type { AttributeSchema, RelationshipSchema } from "@/entities/schema/domain/model/schema";
import { getRelationshipDisplayLabel } from "@/entities/schema/domain/rules/get-relationship-display-label";
import { FieldSchemaIcon } from "@/entities/schema/ui/field-schema-icon";
import { useSchema } from "@/entities/schema/ui/hooks/useSchema";

export interface TableColumnHeaderSimpleProps {
  columnSchema: AttributeSchema | RelationshipSchema;
  className?: string;
}

export function TableColumnHeaderSimple({ columnSchema, className }: TableColumnHeaderSimpleProps) {
  const { schema: peerSchema } = useSchema("peer" in columnSchema ? columnSchema.peer : undefined);
  const label =
    "peer" in columnSchema
      ? getRelationshipDisplayLabel(columnSchema, peerSchema)
      : (columnSchema.label ?? columnSchema.name);

  return (
    <div className={classNames(cellsStyle, cellHeaderStyle, "hover:bg-white", className)}>
      <FieldSchemaIcon fieldSchema={columnSchema} />
      <span className="mr-2 truncate">{label}</span>
    </div>
  );
}
