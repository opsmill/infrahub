import { TableCell } from "@/entities/nodes/object/ui/objects-table/cells/table-cell";
import { useSchema } from "@/entities/schema/hooks/useSchema";

export function KindBodyCell({ schemaKind }: { schemaKind: string }) {
  const { schema } = useSchema(schemaKind);

  return (
    <TableCell>
      <span className="truncate">{schema?.label ?? schemaKind}</span>
    </TableCell>
  );
}
