import { TableCell } from "@/entities/nodes/object/ui/objects-table/cells/table-cell";
import { getObjectDetailsUrl2 } from "@/entities/nodes/utils";
import { classNames } from "@/shared/utils/common";
import { Link } from "react-router-dom";

export interface TableRowIdentifierProps {
  objectKind: string;
  objectId: string;
  identifier: string | string[];
}
export function TableRowIdentifier({ objectKind, objectId, identifier }: TableRowIdentifierProps) {
  const display = Array.isArray(identifier) ? identifier.join(", ") : identifier;
  return (
    <TableCell className="sticky left-0">
      <Link
        to={getObjectDetailsUrl2(objectKind, objectId)}
        className={classNames(
          "underline text-indigo-700 decoration-indigo-50 truncate",
          "transition-colors hover:bg-indigo-50 px-2 py-1 rounded-full"
        )}
      >
        {display}
      </Link>
    </TableCell>
  );
}
