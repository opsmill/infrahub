import { useSchema } from "@/entities/schema/ui/hooks/useSchema";
import { TableCell } from "@/shared/components/table/table-cell";

export function KindBodyCell({ schemaKind }: { schemaKind: string }) {
  const { schema } = useSchema(schemaKind);

  return (
    <TableCell>
      <span className="truncate">{schema?.label ?? schemaKind}</span>
    </TableCell>
  );
}
