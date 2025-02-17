import { getObjectDetailsUrl2 } from "@/entities/nodes/utils";
import { LinkButton } from "@/shared/components/buttons/button-primitive";
import { TableCell } from "@/shared/components/table/table-cell";

export interface TableRowIdentifierProps {
  objectKind: string;
  objectId: string;
  identifier: string | string[];
}

export function TableRowIdentifier({ objectKind, objectId, identifier }: TableRowIdentifierProps) {
  const display = Array.isArray(identifier) ? identifier.join(", ") : identifier;
  return (
    <TableCell className="sticky left-0 bg-white px-1">
      <LinkButton
        variant="ghost"
        size="sm"
        to={getObjectDetailsUrl2(objectKind, objectId)}
        className="truncate px-2.5 rounded-full text-custom-blue-700 hover:underline hover:bg-custom-blue-700/10"
      >
        {display}
      </LinkButton>

      <div className="absolute -right-4 top-0 bottom-0 w-4 bg-gradient-to-r from-gray-500/10 pointer-events-none" />
    </TableCell>
  );
}
