import { AttributeType } from "@/entities/nodes/getObjectItemDisplayValue";
import { TableCell } from "@/entities/nodes/object/ui/objects-table/cells/table-cell";
import { formatAttributeValue } from "@/entities/nodes/object/ui/objects-table/utils";
import { AttributeKind, AttributeSchema } from "@/entities/schema/types";

export interface TableAttributeCellProps {
  attributeSchema: AttributeSchema;
  attributeData: AttributeType;
}

export function TableAttributeCell({ attributeSchema, attributeData }: TableAttributeCellProps) {
  return (
    <TableCell>
      <span className="truncate">
        {formatAttributeValue({
          kind: attributeSchema.kind as AttributeKind,
          value: attributeData.value,
        })}
      </span>
    </TableCell>
  );
}
