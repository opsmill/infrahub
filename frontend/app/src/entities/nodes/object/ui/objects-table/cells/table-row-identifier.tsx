import { TableCell } from "@/entities/nodes/object/ui/objects-table/cells/table-cell";
import { getObjectDetailsUrl2 } from "@/entities/nodes/utils";
import { LinkButton } from "@/shared/components/buttons/button-primitive";

export interface TableRowIdentifierProps {
  objectKind: string;
  objectId: string;
  identifier: string | string[];
}

export function TableRowIdentifier({ objectKind, objectId, identifier }: TableRowIdentifierProps) {
  const display = Array.isArray(identifier) ? identifier.join(", ") : identifier;
  return (
    <TableCell className="sticky left-0">
      <LinkButton
        variant="ghost"
        size="sm"
        to={getObjectDetailsUrl2(objectKind, objectId)}
        className="underline truncate rounded-full text-custom-blue-700 hover:bg-custom-blue-700/10"
      >
        {display}
      </LinkButton>
    </TableCell>
  );
}
